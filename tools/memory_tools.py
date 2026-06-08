"""记忆工具 - LangChain 工具封装

将 MemoryManager 封装为 LangChain 可调用的工具。
"""

from langchain.tools import tool
from memory.memory_manager import MemoryManager


@tool
def read_memory(category: str = "", key: str = "") -> str:
    """读取长期记忆。用于获取用户习惯、企业知识和操作历史。
    
    Args:
        category: 记忆分类。可选值: "user_habits"(用户习惯), "org_knowledge"(企业知识), 
                 "operation_history"(操作历史)。留空则返回全部记忆。
        key: 具体键名。留空则返回该分类全部内容。
    
    Returns:
        记忆内容的文本展示
    """
    mgr = MemoryManager()
    return mgr.read(category, key)


@tool
def save_memory(category: str, key: str, value: str) -> str:
    """保存信息到长期记忆。用于记住用户的操作习惯、企业内部知识等。
    
    Args:
        category: 记忆分类。可选值: "user_habits"(用户习惯), "org_knowledge"(企业知识),
                 "operation_history"(操作历史)
        key: 键名，如 "default_region", "naming_convention", "internal_vpc_cidr"
        value: 要保存的值
    
    Returns:
        操作结果描述
    """
    mgr = MemoryManager()
    result = mgr.write(category, key, value)
    return result


@tool
def list_memory_categories() -> str:
    """列出长期记忆中的所有分类。
    
    Returns:
        所有记忆分类列表
    """
    mgr = MemoryManager()
    categories = mgr.list_categories()
    return f"记忆分类: {', '.join(categories)}"
