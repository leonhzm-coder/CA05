"""CA05 跨云运维助手 - LangGraph 状态机核心

采用 ReAct Agent 模式，通过 LangGraph 的 create_react_agent 构建。
所有工具统一注册，由 LLM 自主选择和编排。
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import TypedDict, List, Any, Optional, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from memory.memory_manager import MemoryManager
from system_prompts.main_prompt import MAIN_SYSTEM_PROMPT

CHINA_TZ = timezone(timedelta(hours=8))


class ThreadContext(TypedDict):
    """每个会话线程的上下文"""
    messages: List[dict]
    created_at: str
    last_interaction: str


class CA05Agent:
    """CA05 跨云运维助手

    基于 LangGraph ReAct Agent，集成所有运维工具。
    支持多线程会话和长期记忆。
    """

    def __init__(self, llm, tools: list, memory_mgr: Optional[MemoryManager] = None):
        """
        Args:
            llm: ChatOpenAI 实例
            tools: 工具列表
            memory_mgr: MemoryManager 实例（可选，默认创建新实例）
        """
        self.llm = llm
        self.tools = tools
        self.memory_mgr = memory_mgr or MemoryManager()
        self.thread_contexts: dict[str, ThreadContext] = {}

        # 创建 ReAct Agent
        self.react_agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=self._build_system_prompt,
            state_schema=self._get_state_schema(),
        )

        # 使用 MemorySaver 实现对话历史持久化
        self.checkpointer = MemorySaver()

        print(f"[CA05Agent] 初始化完成，已注册 {len(tools)} 个工具:")
        for t in tools:
            print(f"  - {t.name}: {t.description[:50]}...")

    def _get_state_schema(self):
        """定义状态 schema"""
        class AgentState(TypedDict):
            messages: List[BaseMessage]
            memory_context: Optional[str]

        return AgentState

    def _build_system_prompt(self, state: dict) -> List[BaseMessage]:
        """构建系统提示词，注入记忆上下文"""
        # 读取当前记忆
        memory_text = self.memory_mgr.read()
        memory_lines = json.loads(memory_text) if isinstance(memory_text, str) else {}

        # 构建记忆摘要
        memory_summary = self._build_memory_summary(memory_lines)

        # 构建完整的系统消息
        full_prompt = MAIN_SYSTEM_PROMPT + f"""

## 当前记忆上下文
{memory_summary}

## 操作须知
- 当前时间: {datetime.now(CHINA_TZ).isoformat()}
- 阿里云 CLI 已{'配置' if self._is_aliyun_configured() else '未配置，请先 set AK/SK 环境变量'}
"""
        return [SystemMessage(content=full_prompt)]

    def _build_memory_summary(self, memory_data: dict) -> str:
        """从记忆数据构建可读的摘要"""
        parts = []

        # 用户习惯
        habits = memory_data.get("user_habits", {})
        if habits:
            habit_lines = [f"    {k}: {v}" for k, v in habits.items()]
            parts.append("【用户习惯】\n" + "\n".join(habit_lines))
        else:
            parts.append("【用户习惯】暂无记录")

        # 企业知识
        org_knowledge = memory_data.get("org_knowledge", {})
        if org_knowledge:
            knowledge_lines = [f"    {k}: {v}" for k, v in org_knowledge.items()]
            parts.append("【企业知识】\n" + "\n".join(knowledge_lines))
        else:
            parts.append("【企业知识】暂无记录")

        # 操作历史（最近5条）
        history = memory_data.get("operation_history", [])
        if history:
            recent = history[-5:]
            history_lines = []
            for h in recent:
                ts = h.get("timestamp", "")[-19:] if h.get("timestamp") else ""
                action = h.get("action", "")
                history_lines.append(f"    [{ts}] {action}")
            parts.append("【最近操作】\n" + "\n".join(history_lines))

        return "\n\n".join(parts)

    def _is_aliyun_configured(self) -> bool:
        """检查阿里云 CLI 是否已配置"""
        ak_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") or os.environ.get("ALIBABA_CLOUD_AK_ID")
        return bool(ak_id)

    async def process_message(self, thread_id: str, message: str) -> dict:
        """处理用户消息

        Args:
            thread_id: 会话线程 ID
            message: 用户消息

        Returns:
            {
                "messages": 完整消息列表,
                "status": "completed" | "error",
                "error": 错误信息（如有）
            }
        """
        try:
            # 记录操作历史
            self.memory_mgr.add_history("用户消息", message[:100])

            # 构建输入消息
            input_messages = [HumanMessage(content=message)]

            # 运行 ReAct Agent
            result = await self.react_agent.ainvoke(
                {"messages": input_messages},
                config=RunnableConfig(
                    configurable={"thread_id": thread_id},
                    recursion_limit=100,  # 防止无限循环
                )
            )

            # 提取响应
            response_messages = result.get("messages", [])

            # 自动学习：从对话中提取用户习惯
            await self._auto_learn_from_conversation(message, response_messages)

            # 记录到线程上下文
            if thread_id not in self.thread_contexts:
                self.thread_contexts[thread_id] = {
                    "messages": [],
                    "created_at": datetime.now(CHINA_TZ).isoformat(),
                    "last_interaction": datetime.now(CHINA_TZ).isoformat()
                }
            self.thread_contexts[thread_id]["last_interaction"] = datetime.now(CHINA_TZ).isoformat()

            return {
                "messages": self._format_messages(response_messages),
                "status": "completed"
            }

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[CA05Agent] 错误: {e}\n{error_detail}")
            return {
                "messages": [{"role": "assistant", "content": f"处理出错: {str(e)}"}],
                "status": "error",
                "error": str(e)
            }

    async def _auto_learn_from_conversation(self, user_message: str, response_messages: list):
        """从对话中自动学习用户习惯

        检测用户消息中是否包含可记忆的信息：
        - 区域偏好（如"我在杭州"、"用杭州区域"）
        - 命名规范（如"按项目-环境命名"）
        - 常用配置（如"我常用5.7的MySQL"）
        """
        # 区域偏好检测
        region_keywords = {
            "杭州": "cn-hangzhou",
            "上海": "cn-shanghai",
            "北京": "cn-beijing",
            "深圳": "cn-shenzhen",
            "香港": "cn-hongkong",
            "新加坡": "ap-southeast-1",
        }
        for keyword, region in region_keywords.items():
            if keyword in user_message and "region" not in str(self.memory_mgr.read("user_habits", "default_region")):
                self.memory_mgr.write("user_habits", "default_region", region)
                print(f"[CA05Agent] 自动学习: 默认区域 -> {region}")
                break

    def _format_messages(self, messages: list) -> list:
        """将 LangChain 消息格式化为可序列化的字典列表"""
        formatted = []
        for msg in messages:
            if hasattr(msg, "type") and hasattr(msg, "content"):
                role = "assistant" if msg.type == "ai" else msg.type
                formatted.append({
                    "role": role,
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                    "timestamp": datetime.now(CHINA_TZ).isoformat()
                })
            elif isinstance(msg, dict):
                formatted.append(msg)
        return formatted

    def get_messages(self, thread_id: str) -> list:
        """获取指定线程的消息历史"""
        from langgraph.checkpoint.base import BaseCheckpointSaver
        try:
            # 尝试从 checkpointer 获取
            config = RunnableConfig(configurable={"thread_id": thread_id})
            state = self.checkpointer.get(config)
            if state and "messages" in state:
                return self._format_messages(state["messages"])
        except Exception:
            pass
        return self.thread_contexts.get(thread_id, {}).get("messages", [])

    def get_status(self, thread_id: str) -> dict:
        """获取线程状态"""
        context = self.thread_contexts.get(thread_id, {})
        return {
            "thread_id": thread_id,
            "created_at": context.get("created_at", ""),
            "last_interaction": context.get("last_interaction", ""),
            "message_count": len(self.get_messages(thread_id)),
            "memory_size": len(json.dumps(self.memory_mgr.memory, ensure_ascii=False))
        }
