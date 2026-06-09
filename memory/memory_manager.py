"""长期记忆管理器 - 使用 AgentRun OTS 持久化存储

存储用户习惯、企业知识和操作历史。
数据通过 AgentRun SessionStore 持久化到 OTS（TableStore），支持跨会话共享。
如果 MEMORY_COLLECTION_NAME 未设置，则降级为本地缓存（非持久化）。
"""

import json
import os
from datetime import datetime, timezone, timedelta

CHINA_TZ = timezone(timedelta(hours=8))


class MemoryManager:
    """长期记忆管理器

    使用 AgentRun SessionStore 实现 OTS 持久化，支持跨会话记忆共享。
    单例模式 — 首次初始化后全局共享同一 store 连接。

    如果未提供 store 且 MEMORY_COLLECTION_NAME 未设置，则使用内存缓存（不持久化）。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, store=None):
        if self._initialized:
            return
        self._initialized = True
        self._session_id = "ca05_memory"
        self._store = store
        self._cache = {
            "user_habits": {},
            "org_knowledge": {},
            "operation_history": []
        }

        # If no store provided, try to create from env var
        if self._store is None:
            collection_name = os.getenv("MEMORY_COLLECTION_NAME")
            if collection_name:
                try:
                    from agentrun.conversation_service import SessionStore
                    self._store = SessionStore.from_memory_collection(collection_name)
                    print(f"[MemoryManager] connected to AgentRun memory collection: {collection_name}")
                except Exception as e:
                    print(f"[MemoryManager] failed to init AgentRun store: {e}")
                    print(f"[MemoryManager] falling back to local cache")
                    self._store = None

        # Load persisted data from OTS if available
        if self._store is not None:
            self._load_from_store()
        else:
            print("[MemoryManager] using local cache (no AgentRun store)")

    def _load_from_store(self):
        """从 OTS 加载记忆数据"""
        try:
            data = self._store.get(self._session_id)
            if data:
                loaded = json.loads(data) if isinstance(data, str) else data
                if isinstance(loaded, dict):
                    self._cache = loaded
                    print(f"[MemoryManager] loaded from OTS store")
                    return
            print(f"[MemoryManager] no existing data in OTS store, using defaults")
        except Exception as e:
            print(f"[MemoryManager] load from store error: {e}")

    def _save_to_store(self):
        """保存记忆数据到 OTS"""
        if self._store is not None:
            try:
                self._store.put(self._session_id, json.dumps(self._cache, ensure_ascii=False))
            except Exception as e:
                print(f"[MemoryManager] save to store error: {e}")

    def save(self):
        """保存记忆"""
        self._save_to_store()

    def read(self, category: str = "", key: str = "") -> str:
        """读取记忆

        Args:
            category: 分类 (user_habits, org_knowledge, operation_history)，空则返回全部
            key: 键名，空则返回该分类全部

        Returns:
            格式化的记忆文本
        """
        if not category:
            return json.dumps(self._cache, ensure_ascii=False, indent=2)
        if category not in self._cache:
            return f"分类 '{category}' 不存在"
        if not key:
            return json.dumps(self._cache[category], ensure_ascii=False, indent=2)
        value = self._cache[category].get(key, "")
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
        if category not in self._cache:
            self._cache[category] = {}
        self._cache[category][key] = value
        self._save_to_store()
        return f"已保存到 {category}/{key}"

    def add_history(self, action: str, detail: str = ""):
        """添加操作历史记录"""
        self._cache["operation_history"].append({
            "timestamp": datetime.now(CHINA_TZ).isoformat(),
            "action": action,
            "detail": detail
        })
        # 只保留最近 50 条
        if len(self._cache["operation_history"]) > 50:
            self._cache["operation_history"] = self._cache["operation_history"][-50:]
        self._save_to_store()

    def list_categories(self) -> list:
        """列出所有记忆分类"""
        return list(self._cache.keys())
