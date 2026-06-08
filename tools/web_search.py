"""Web 搜索工具

使用 httpx 进行 Bing 搜索和网页内容提取。
不依赖浏览器沙箱，适合轻量级场景。
"""

import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from utils import filter_html_to_text, extract_bing_search_results

# 默认超时
HTTP_TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 黑名单域名（会拦截自动化工具的网站）
BLOCKED_DOMAINS = ["zhihu.com", "xueqiu.com"]


def _check_blocked(url: str) -> bool:
    """检查 URL 是否在黑名单中"""
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            return True
    return False


async def web_search(keyword: str, page: int = 1) -> str:
    """使用 Bing 搜索指定关键词

    Args:
        keyword: 搜索关键词
        page: 页码（从1开始），默认第1页

    Returns:
        搜索结果文本
    """
    try:
        first = (page - 1) * 10 + 1
        encoded = quote_plus(keyword)
        url = f"https://www.bing.com/search?q={encoded}&first={first}"

        print(f"[WebSearch] 搜索: {keyword} (第{page}页)")

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            html = response.text

        results = extract_bing_search_results(html)
        if not results:
            return f"搜索 '{keyword}'（第{page}页）完成，但未找到结果"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r['title']}\n   链接: {r['link']}")

        return f"搜索 '{keyword}'（第{page}页），找到 {len(results)} 个结果:\n\n" + "\n\n".join(formatted)

    except httpx.TimeoutException:
        return "[超时] 搜索请求超时"
    except httpx.HTTPStatusError as e:
        return f"[HTTP错误] {e.response.status_code}"
    except Exception as e:
        return f"[错误] {str(e)}"


async def web_fetch(url: str, wait_seconds: float = 1.5) -> str:
    """获取指定网页的纯文本内容

    Args:
        url: 网页 URL
        wait_seconds: 此参数仅为兼容（httpx 不需要等待），保留以保持接口一致

    Returns:
        网页的纯文本内容
    """
    if _check_blocked(url):
        return f"获取失败: {url}\n该网站对自动化工具进行了拦截"

    try:
        print(f"[WebFetch] 获取: {url}")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            html = response.text

        text = filter_html_to_text(html)
        if not text.strip():
            return f"成功访问 {url}，但页面内容为空（可能需要 JavaScript 渲染)"

        if len(text) > 50000:
            return f"成功访问 {url}\n\n{text[:50000]}\n\n...(总长度: {len(text)} 字符，已截断)"
        return f"成功访问 {url}\n\n{text}"

    except httpx.TimeoutException:
        return f"[超时] 访问 {url} 超时"
    except httpx.HTTPStatusError as e:
        return f"[HTTP错误] 访问 {url} 返回 {e.response.status_code}"
    except Exception as e:
        return f"[错误] 访问 {url} 失败: {str(e)}"
