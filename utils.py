"""通用工具函数模块"""

import re


def filter_html_to_text(html: str) -> str:
    """简单的HTML过滤函数，提取纯文本内容

    过滤掉：
    - <script>...</script> 标签及其内容
    - <style>...</style> 标签及其内容
    - 所有HTML标签（<>中的内容）
    - HTML注释（<!-- ... -->）
    - 多余的空白字符

    Args:
        html: 原始HTML内容

    Returns:
        过滤后的纯文本内容
    """
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    html = re.sub(r'<[^>]+>', '', html)
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&amp;', '&')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")
    html = re.sub(r'\s+', ' ', html)
    return html.strip()


def extract_bing_search_results(html: str) -> list[dict]:
    """从Bing搜索结果页面中提取搜索结果

    Args:
        html: Bing搜索结果页面的HTML内容

    Returns:
        搜索结果列表，每个结果包含 'title' 和 'link' 字段
    """
    results = []
    ol_pattern = r'<ol[^>]*id="b_results"[^>]*>(.*?)</ol>'
    ol_match = re.search(ol_pattern, html, re.DOTALL | re.IGNORECASE)
    if not ol_match:
        return results
    ol_content = ol_match.group(1)
    li_pattern = r'<li[^>]*>(.*?)</li>'
    li_matches = re.findall(li_pattern, ol_content, re.DOTALL | re.IGNORECASE)
    for li_content in li_matches:
        a_pattern = r'<a[^>]*target="_blank"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        a_matches = re.findall(a_pattern, li_content, re.DOTALL | re.IGNORECASE)
        for link, text in a_matches:
            clean_text = re.sub(r'<[^>]+>', '', text)
            clean_text = ' '.join(clean_text.split())
            if clean_text.strip():
                results.append({
                    'title': clean_text.strip(),
                    'link': link
                })
    return results
