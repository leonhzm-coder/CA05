"""阿里云技能发现工具

基于 alibabacloud-find-skills 技能，封装 aliyun agentexplorer 插件的调用。
用于发现、查看和安装阿里云 CLI 技能。
"""

import subprocess
import json
import shutil
import os


def _get_aliyun_path() -> str:
    return shutil.which("aliyun") or "/usr/local/bin/aliyun"


def _user_agent() -> str:
    return "--user-agent AlibabaCloud-Agent-Skills/alibabacloud-find-skills"


def _endpoint() -> str:
    return "--endpoint agentexplorer.aliyuncs.com"


def search_skills(keyword: str, search_mode: str = "semantic") -> str:
    """搜索阿里云操作技能

    使用 aliyun agentexplorer search-skills 命令搜索相关技能。

    Args:
        keyword: 搜索关键词，如 "ecs 运维"、"vpc 网络"、"oss 存储"
        search_mode: 搜索模式，可选 "semantic"(语义搜索) 或 "exact"(精确匹配)

    Returns:
        搜索结果列表
    """
    try:
        aliyun_path = _get_aliyun_path()
        cmd = [
            aliyun_path, "agentexplorer", "search-skills",
            "--keyword", keyword,
            "--search-mode", search_mode,
            _endpoint(),
            _user_agent()
        ]

        print(f"[SkillDiscovery] 搜索: {keyword}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if not output:
                return "未找到相关技能"
            # 尝试格式化 JSON
            try:
                parsed = json.loads(output)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return output
        else:
            return f"[错误] {result.stderr.strip()[:500]}"

    except subprocess.TimeoutExpired:
        return "[超时] 技能搜索超时"
    except FileNotFoundError:
        return "[错误] aliyun CLI 未安装"
    except Exception as e:
        return f"[错误] {str(e)}"


def get_skill_content(skill_name: str) -> str:
    """获取指定技能的详细内容

    Args:
        skill_name: 技能名称（从 search_skills 结果中获得）

    Returns:
        技能的详细说明和用法
    """
    try:
        aliyun_path = _get_aliyun_path()
        cmd = [
            aliyun_path, "agentexplorer", "get-skill-content",
            "--skill-name", skill_name,
            _endpoint(),
            _user_agent()
        ]

        print(f"[SkillDiscovery] 获取技能内容: {skill_name}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            try:
                parsed = json.loads(output)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return output if output else "技能内容为空"
        else:
            return f"[错误] {result.stderr.strip()[:500]}"

    except subprocess.TimeoutExpired:
        return "[超时] 获取技能内容超时"
    except FileNotFoundError:
        return "[错误] aliyun CLI 未安装"
    except Exception as e:
        return f"[错误] {str(e)}"


def install_skill(skill_name: str) -> str:
    """安装阿里云技能

    使用 npx skills add 命令安装指定技能。

    Args:
        skill_name: 技能名称

    Returns:
        安装结果
    """
    try:
        # 检查 npx 是否可用
        npx_path = shutil.which("npx")
        if not npx_path:
            return "[错误] npx 未安装，请确保容器中安装了 Node.js"

        cmd = [
            npx_path, "skills", "add",
            "aliyun/alibabacloud-aiops-skills",
            "--skill", skill_name,
            "--full-depth",
            "--agent", "qwen-code",
            "-g", "-y"
        ]

        print(f"[SkillDiscovery] 安装技能: {skill_name}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            return f"技能 '{skill_name}' 安装成功"
        else:
            return f"[安装失败] {result.stderr.strip()[:500]}"

    except subprocess.TimeoutExpired:
        return "[超时] 技能安装超时（120秒）"
    except Exception as e:
        return f"[错误] {str(e)}"


def list_categories() -> str:
    """列出阿里云技能分类"""
    try:
        aliyun_path = _get_aliyun_path()
        cmd = [
            aliyun_path, "agentexplorer", "list-categories",
            _endpoint(),
            _user_agent()
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            try:
                parsed = json.loads(output)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return output if output else "无分类数据"
        else:
            return f"[错误] {result.stderr.strip()[:500]}"

    except subprocess.TimeoutExpired:
        return "[超时] 获取分类超时"
    except Exception as e:
        return f"[错误] {str(e)}"
