"""CA05 跨云运维助手 - FastAPI 服务入口

提供 OpenAI 兼容的聊天接口和自定义管理接口。
支持惰性初始化（lazy init），首次请求时初始化 LLM 和 Agent。
"""

import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from ca05_agent import CA05Agent
from memory.memory_manager import MemoryManager

from tools.aliyun_cli import execute_aliyun, configure_aliyun, check_aliyun_installed
from tools.skill_discovery import search_skills, get_skill_content, install_skill, list_categories
from tools.memory_tools import read_memory, save_memory, list_memory_categories
from tools.diagram_tools import generate_diagram, parse_user_diagram
from tools.web_search import web_search, web_fetch

# ========== 时区配置 ==========
os.environ['TZ'] = 'Asia/Shanghai'
CHINA_TZ = timezone(timedelta(hours=8))


def get_china_time():
    return datetime.now(CHINA_TZ)


# ========== 声明 LangChain Tools ==========

@tool
def execute_aliyun_cli(command: str) -> str:
    """执行阿里云 CLI 命令。输入为子命令，不需要 'aliyun' 前缀。
    
    示例:
    - "ecs DescribeInstances --region cn-hangzhou"
    - "vpc DescribeVpcs --region cn-hangzhou"
    - "slb DescribeLoadBalancers"
    - "oss ls"
    
    Args:
        command: 阿里云 CLI 子命令
    
    Returns:
        命令执行结果（JSON 格式文本）
    """
    return execute_aliyun(command)


@tool
def web_search_tool(keyword: str, page: int = 1) -> str:
    """使用 Bing 搜索互联网信息。用于搜索技术文档、方案、教程等。
    
    Args:
        keyword: 搜索关键词
        page: 页码，从1开始
    
    Returns:
        搜索结果列表（标题+链接）
    """
    return asyncio.run(web_search(keyword, page))


@tool
def web_fetch_tool(url: str) -> str:
    """获取指定网页的纯文本内容。用于阅读技术文档、新闻等。
    
    Args:
        url: 网页 URL 地址
    
    Returns:
        网页纯文本内容
    """
    return asyncio.run(web_fetch(url))


# ========== 注册所有工具 ==========

ALL_TOOLS = [
    # 阿里云 CLI
    execute_aliyun_cli,
    
    # 技能发现
    tool(search_skills),
    tool(get_skill_content),
    tool(install_skill),
    tool(list_categories),
    
    # 长期记忆
    read_memory,
    save_memory,
    list_memory_categories,
    
    # 架构图
    tool(generate_diagram),
    tool(parse_user_diagram),
    
    # 网页搜索
    web_search_tool,
    web_fetch_tool,
]

# ========== 全局变量 ==========

ca05_agent: Optional[CA05Agent] = None
memory_mgr: MemoryManager = None


# ========== FastAPI App ==========

app = FastAPI(
    title="CA05 - Cross-Cloud Operations Assistant",
    description="跨云运维助手 API",
    version="1.0.0",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 启动事件 ==========

@app.on_event("startup")
async def startup_event():
    global memory_mgr, ca05_agent

    print(f"[startup] CA05 跨云运维助手 启动中...")
    print(f"[startup] Aliyun CLI 已安装: {check_aliyun_installed()}")

    # 初始化记忆管理器
    memory_mgr = MemoryManager()
    print(f"[startup] 记忆管理器已初始化")

    # 配置阿里云 CLI（从环境变量）
    if configure_aliyun():
        print(f"[startup] 阿里云 CLI 已配置")
    else:
        print(f"[startup] 阿里云 CLI 未配置（可在请求时配置）")

    # 初始化 LLM（惰性初始化）
    llm = await _init_llm()
    if llm is not None:
        ca05_agent = CA05Agent(llm, ALL_TOOLS, memory_mgr)
        print(f"[startup] CA05 Agent 初始化成功")
    else:
        ca05_agent = None
        print(f"[startup] LLM 未就绪（首次请求时重试）")

    # 输出工具列表
    print(f"[startup] 已注册 {len(ALL_TOOLS)} 个工具:")
    for t in ALL_TOOLS:
        print(f"  - {t.name}")


async def _init_llm() -> Optional[ChatOpenAI]:
    """尝试初始化 LLM

    优先级:
    1. AgentRun 模型服务 (MODEL_SERVICE_NAME + MODEL)
    2. 直接 API Key (LLM_API_KEY / OPENAI_API_KEY + LLM_MODEL_NAME / MODEL)
    """
    model_service_name = os.getenv("MODEL_SERVICE_NAME")

    # 方式 1: AgentRun 模型服务
    if model_service_name:
        try:
            from agentrun.integration.langchain import model as agentrun_model
            model_service = agentrun_model(model_service_name)
            llm = ChatOpenAI(
                api_key=model_service.openai_api_key,
                model=os.getenv("MODEL", "qwen3-max"),
                base_url=model_service.openai_api_base,
                temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
                streaming=True
            )
            print(f"[init] 使用 AgentRun 模型服务: {model_service_name}, model={os.getenv('MODEL', 'qwen3-max')}")
            return llm
        except Exception as e:
            print(f"[init] AgentRun 模型服务不可用: {e}")
            print(f"[init] 降级到直接 API Key 方式")

    # 方式 2: 直接 API Key
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_name = os.getenv("LLM_MODEL_NAME") or os.getenv("MODEL", "qwen3-max")

    if api_key:
        try:
            llm = ChatOpenAI(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
                streaming=True
            )
            print(f"[init] 使用直接 API Key: model={model_name}")
            return llm
        except Exception as e:
            print(f"[init] LLM 初始化失败: {e}")
            return None

    print(f"[init] 未配置 LLM（设置 MODEL_SERVICE_NAME 或 LLM_API_KEY）")
    return None


async def _ensure_agent():
    """确保 Agent 已初始化"""
    global ca05_agent, memory_mgr
    if ca05_agent is not None:
        return
    print("[lazy-init] 首次请求，初始化 LLM...")
    llm = await _init_llm()
    if llm is None:
        raise HTTPException(
            status_code=500,
            detail="LLM not initialized. Set LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME environment variables."
        )
    ca05_agent = CA05Agent(llm, ALL_TOOLS, memory_mgr)
    print("[lazy-init] CA05 Agent 初始化完成")


# ========== API 模型 ==========

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, Any]]
    stream: bool = False
    thread_id: str = ""


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]


# ========== API 端点 ==========

@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": get_china_time().isoformat(),
        "agent_ready": ca05_agent is not None,
        "aliyun_cli": check_aliyun_installed(),
        "aliyun_configured": bool(os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"))
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """聊天接口 - 统一处理所有消息"""
    await _ensure_agent()
    result = await ca05_agent.process_message(
        request.thread_id,
        request.message
    )
    return {
        "thread_id": request.thread_id,
        "status": result.get("status"),
        "messages": result.get("messages", [])
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI 兼容的聊天补全接口"""
    await _ensure_agent()

    # 提取 thread_id
    thread_id = request.thread_id or "default"

    # 提取最后一条用户消息
    user_messages = [m for m in request.messages if m.get("role") == "user"]
    if not user_messages:
        return ChatCompletionResponse(
            id="chat-0",
            created=int(datetime.now().timestamp()),
            model=os.getenv("LLM_MODEL_NAME", "ca05"),
            choices=[{"index": 0, "message": {"role": "assistant", "content": "请提供用户消息。"}, "finish_reason": "stop"}]
        )

    last_message = user_messages[-1]
    content = last_message.get("content", "")

    result = await ca05_agent.process_message(thread_id, content)
    messages = result.get("messages", [])
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    reply = assistant_messages[-1].get("content", "") if assistant_messages else ""

    if request.stream:
        # 流式响应
        async def stream_generator():
            yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': ''}, 'index': 0}]})}\n\n"
            for char in reply:
                yield f"data: {json.dumps({'choices': [{'delta': {'content': char}, 'index': 0}]})}\n\n"
            yield "data: [DONE]\n\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )

    return ChatCompletionResponse(
        id=f"chat-{hash(thread_id) % 100000}",
        created=int(datetime.now().timestamp()),
        model=os.getenv("LLM_MODEL_NAME", "ca05"),
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": reply},
            "finish_reason": "stop"
        }]
    )


@app.post("/")
@app.post("/invocations")
async def root_invocations(request: ChatCompletionRequest):
    """AgentRun 端点转发到根路径时的处理"""
    return await chat_completions(request)


# ========== 记忆管理 API ==========

class MemoryWriteRequest(BaseModel):
    category: str
    key: str
    value: str


@app.get("/memory")
async def get_memory(category: str = "", key: str = ""):
    """读取长期记忆"""
    global memory_mgr
    if not memory_mgr:
        memory_mgr = MemoryManager()
    content = memory_mgr.read(category, key)
    return {"memory": content}


@app.post("/memory")
async def write_memory(request: MemoryWriteRequest):
    """写入长期记忆"""
    global memory_mgr
    if not memory_mgr:
        memory_mgr = MemoryManager()
    result = memory_mgr.write(request.category, request.key, request.value)
    return {"result": result}


@app.get("/memory/categories")
async def list_memory():
    """列出所有记忆分类"""
    global memory_mgr
    if not memory_mgr:
        memory_mgr = MemoryManager()
    return {"categories": memory_mgr.list_categories()}


# ========== 线程管理 API ==========

@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """获取线程消息历史"""
    await _ensure_agent()
    messages = ca05_agent.get_messages(thread_id)
    return {"thread_id": thread_id, "messages": messages}


@app.get("/threads/{thread_id}/status")
async def get_thread_status(thread_id: str):
    """获取线程状态"""
    await _ensure_agent()
    status = ca05_agent.get_status(thread_id)
    return status


# ========== 阿里云配置 API ==========

@app.post("/aliyun/configure")
async def configure_aliyun_endpoint():
    """配置阿里云 CLI（从环境变量）"""
    success = configure_aliyun()
    return {
        "success": success,
        "message": "阿里云 CLI 已配置" if success else "配置失败，请检查环境变量"
    }


@app.get("/aliyun/status")
async def aliyun_status():
    """阿里云 CLI 状态"""
    return {
        "installed": check_aliyun_installed(),
        "configured": bool(os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        "region": os.environ.get("ALIBABA_CLOUD_REGION_ID", "未设置")
    }


# ========== 主入口 ==========

if __name__ == "__main__":
    port = int(os.getenv("PORT", 9000))
    print(f"🚀 CA05 跨云运维助手 启动在端口 {port}")
    print(f"📚 API 文档: http://127.0.0.1:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)
