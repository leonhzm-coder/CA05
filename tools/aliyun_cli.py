"""阿里云 CLI 工具封装

封装 aliyun CLI 的调用，支持：
- 配置 AK/SK
- 执行任意 aliyun 命令
- 获取命令执行结果
"""

import subprocess
import os
import json
import shutil


def _get_aliyun_path() -> str:
    """获取 aliyun CLI 路径"""
    return shutil.which("aliyun") or "/usr/local/bin/aliyun"


def configure_aliyun() -> bool:
    """从环境变量配置 aliyun CLI

    环境变量:
        ALIBABA_CLOUD_ACCESS_KEY_ID
        ALIBABA_CLOUD_SECRET_ACCESS_KEY
        ALIBABA_CLOUD_REGION_ID (默认: cn-hangzhou)

    Returns:
        是否配置成功
    """
    ak_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") or os.environ.get("ALIBABA_CLOUD_AK_ID")
    ak_secret = os.environ.get("ALIBABA_CLOUD_SECRET_ACCESS_KEY") or os.environ.get("ALIBABA_CLOUD_AK_SECRET")
    region = os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")

    if not ak_id or not ak_secret:
        print("[AliyunCLI] 未设置 AK/SK 环境变量")
        return False

    try:
        aliyun_path = _get_aliyun_path()
        # 先检查是否已配置
        result = subprocess.run(
            [aliyun_path, "configure", "list"],
            capture_output=True, text=True, timeout=10
        )
        if ak_id in result.stdout:
            print("[AliyunCLI] 已配置，跳过")
            return True

        # 交互式配置（通过输入管道）
        config_input = f"{ak_id}\n{ak_secret}\n{region}\n\n".encode()
        result = subprocess.run(
            [aliyun_path, "configure", "set"],
            input=config_input,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("[AliyunCLI] 配置成功")
            return True
        else:
            # 尝试非交互式（新版本 aliyun CLI 支持）
            result = subprocess.run(
                [aliyun_path, "configure", "set",
                 "--profile", "default",
                 "--access-key-id", ak_id,
                 "--access-key-secret", ak_secret,
                 "--region", region],
                capture_output=True, text=True, timeout=10
            )
            success = result.returncode == 0
            print(f"[AliyunCLI] 配置{'成功' if success else '失败'}: {result.stderr[:200]}")
            return success
    except Exception as e:
        print(f"[AliyunCLI] 配置异常: {e}")
        return False


def execute_aliyun(command: str, timeout: int = 60) -> str:
    """执行 aliyun CLI 命令

    Args:
        command: 子命令，如 "ecs DescribeInstances --region cn-hangzhou"
                不需要 "aliyun" 前缀
        timeout: 超时秒数

    Returns:
        命令输出（stdout）或错误信息
    """
    try:
        aliyun_path = _get_aliyun_path()
        # 先确保已配置
        configure_aliyun()

        # 分割命令
        import shlex
        parts = shlex.split(command)
        cmd = [aliyun_path] + parts

        print(f"[AliyunCLI] 执行: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout
        )

        if result.returncode == 0:
            output = result.stdout
            # 尝试美化 JSON 输出
            if output.strip().startswith("{"):
                try:
                    parsed = json.loads(output)
                    output = json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    pass
            elif output.strip().startswith("["):
                try:
                    parsed = json.loads(output)
                    output = json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    pass

            # 限制输出长度
            if len(output) > 10000:
                output = output[:10000] + f"\n\n... (输出已截断，共 {len(output)} 字符)"
            return output
        else:
            error_msg = result.stderr.strip()[:1000] if result.stderr else f"退出码: {result.returncode}"
            return f"[错误] {error_msg}"

    except subprocess.TimeoutExpired:
        return f"[超时] 命令执行超过 {timeout} 秒"
    except FileNotFoundError:
        return "[错误] aliyun CLI 未安装，请在容器中安装 Aliyun CLI"
    except Exception as e:
        return f"[错误] {str(e)}"


def check_aliyun_installed() -> bool:
    """检查 aliyun CLI 是否已安装"""
    return shutil.which("aliyun") is not None
