"""长期记忆管理器

存储用户习惯、企业知识和操作历史。
数据以 JSON 格式持久化到本地文件。
"""

import json
import os
from datetime import datetime, timezone, timedelta

CHINA_TZ = timezone(timedelta(hours=8))
MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.getenv("CA05_MEMORY_FILE", os.path.join(MEMORY_DIR, "default_memory.json"))


class MemoryManager:
    """长期记忆管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.memory = self._load()
        print(f"[MemoryManager] loaded from {MEMORY_FILE}")

    def _load(self) -> dict:
        """从文件加载记忆"""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[MemoryManager] load error: {e}")
        return {
            "user_habits": {},
            "org_knowledge": {},
            "operation_history": []
        }

    def save(self):
        """保存记忆到文件"""
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def read(self, category: str = "", key: str = "") -> str:
        """读取记忆

        Args:
            category: 分类 (user_habits, org_knowledge, operation_history)，空则返回全部
            key: 键名，空则返回该分类全部

        Returns:
            格式化的记忆文本
        """
        if not category:
            return json.dumps(self.memory, ensure_ascii=False, indent=2)
        if category not in self.memory:
            return f"分类 '{category}' 不存在"
        if not key:
            return json.dumps(self.memory[category], ensure_ascii=False, indent=2)
        value = self.memory[category].get(key, "")
        return f"{key}: {value}" if value else f"未找到 '{key}'"

    def write(self, category: str, key: str, value: str) -> str:
        """写入记忆

        Args:
            category: 分类
            key: 键名
            value: 值

        Returns:
            操作结果描述
        """
        if category not in self.memory:
            self.memory[category] = {}
        self.memory[category][key] = value
        self.save()
        return f"已保存到 {category}/{key}"

    def add_history(self, action: str, detail: str = ""):
        """添加操作历史记录"""
        self.memory["operation_history"].append({
            "timestamp": datetime.now(CHINA_TZ).isoformat(),
            "action": action,
            "detail": detail
        })
        # 只保留最近 50 条
        if len(self.memory["operation_history"]) > 50:
            self.memory["operation_history"] = self.memory["operation_history"][-50:]
        self.save()

    def list_categories(self) -> list:
        """列出所有记忆分类"""
        return list(self.memory.keys())
