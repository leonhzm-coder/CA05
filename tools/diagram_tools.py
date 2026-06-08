"""架构图工具

支持：
- 根据描述生成 Mermaid 架构图
- 从用户提供的 Mermaid 代码中提取架构信息
"""

import json
import re


def generate_diagram(description: str, components: str = "") -> str:
    """根据描述生成 Mermaid 架构图。

    Args:
        description: 架构描述，如 "三台 ECS 通过 SLB 负载均衡，前端连接 OSS 存储静态文件"
        components: 可选的组件列表（JSON格式），如 '[{"name":"ECS-1","type":"ecs"},{"name":"SLB-1","type":"slb"}]'

    Returns:
        Mermaid 格式的架构图代码
    """
    # 生成标准化的 Mermaid 架构图
    # 使用 graph TB 布局（自上而下）

    parsed_components = []
    if components:
        try:
            parsed_components = json.loads(components)
        except json.JSONDecodeError:
            pass

    # 如果没有提供组件列表，根据描述生成通用架构图
    if not parsed_components:
        return _generate_from_description(description)

    return _generate_from_components(parsed_components, description)


def _generate_from_description(description: str) -> str:
    """从文本描述生成 Mermaid 图

    这是一个基础实现，返回一个通用模板，LLM 在 ReAct 循环中会进一步优化。
    """
    mermaid_code = """```mermaid
graph TB
    subgraph "用户层"
        User[用户 / 客户端]
    end
    
    subgraph "接入层"
        SLB[SLB 负载均衡]
        CDN[CDN 加速]
    end
    
    subgraph "应用层"
        ECS1[ECS 应用服务器 1]
        ECS2[ECS 应用服务器 2]
    end
    
    subgraph "数据层"
        RDS[RDS 数据库]
        OSS[OSS 对象存储]
        Redis[Redis 缓存]
    end
    
    User --> CDN
    User --> SLB
    SLB --> ECS1
    SLB --> ECS2
    ECS1 --> RDS
    ECS2 --> RDS
    ECS1 --> Redis
    ECS2 --> Redis
    ECS1 --> OSS
    ECS2 --> OSS
    CDN --> OSS
end
```"""
    return mermaid_code


def _generate_from_components(components: list, description: str) -> str:
    """从组件列表生成 Mermaid 图"""
    lines = ["graph TB"]
    layers = {}

    # 按类型分组
    for comp in components:
        comp_type = comp.get("type", "unknown")
        name = comp.get("name", "unknown")
        layer = _get_layer_for_type(comp_type)
        if layer not in layers:
            layers[layer] = []
        layers[layer].append((name, comp_type))

    # 生成子图
    node_id = 0
    node_map = {}
    for layer, items in layers.items():
        lines.append(f"    subgraph \"{layer}\"")
        for name, comp_type in items:
            nid = f"N{node_id}"
            node_map[name] = nid
            shape = _get_shape_for_type(comp_type)
            lines.append(f"        {nid}{shape}")
            node_id += 1
        lines.append("    end")

    # 添加连接关系（如果有描述，解析关键词匹配）
    connections = _extract_connections(description, list(node_map.keys()))
    for src, dst in connections:
        if src in node_map and dst in node_map:
            lines.append(f"    {node_map[src]} --> {node_map[dst]}")

    return "```mermaid\n" + "\n".join(lines) + "\n```"


def _get_layer_for_type(comp_type: str) -> str:
    """根据组件类型返回所属层"""
    layer_map = {
        "ecs": "应用层",
        "slb": "接入层",
        "oss": "数据层",
        "rds": "数据层",
        "redis": "数据层",
        "vpc": "网络层",
        "nat": "网络层",
        "eip": "网络层",
        "cdn": "接入层",
        "dns": "接入层",
        "waf": "安全层",
        "ddos": "安全层",
        "cas": "安全层",
        "fc": "应用层",
        "apigateway": "接入层",
        "rocketmq": "中间件层",
        "mq": "中间件层",
    }
    return layer_map.get(comp_type, "其他")


def _get_shape_for_type(comp_type: str) -> str:
    """根据组件类型返回 Mermaid 形状"""
    shape_map = {
        "ecs": "[\"ECS 云服务器\"]",
        "slb": "{\"SLB 负载均衡\"}",
        "oss": "(\"OSS 对象存储\")",
        "rds": "[\"RDS 数据库\"]",
        "redis": "[\"Redis 缓存\"]",
        "vpc": "(\"VPC 网络\")",
        "cdn": "{\"CDN 加速\"}",
        "waf": "[\"WAF Web防火墙\"]",
    }
    return shape_map.get(comp_type, f"[\"{comp_type}\"]")


def _extract_connections(description: str, known_names: list) -> list:
    """从描述中提取连接关系（简单实现）"""
    # 一个简单的规则：如果描述中包含 "A 连接 B" 或 "A 通过 B" 等模式
    connections = [
        ("SLB", "ECS"),
        ("CDN", "OSS"),
        ("ECS", "RDS"),
        ("ECS", "Redis"),
    ]
    # 只保留两个名称都在已知列表中的连接
    return [(s, d) for s, d in connections if s in known_names and d in known_names]


def parse_user_diagram(diagram_content: str) -> str:
    """解析用户提供的架构图（Mermaid 格式）并提取架构信息

    Args:
        diagram_content: Mermaid 格式的架构图代码

    Returns:
        解析出的架构信息，包括所有组件和连接关系
    """
    # 提取所有节点
    node_pattern = r'(\w+)\[([^\]]+)\]'
    nodes = re.findall(node_pattern, diagram_content)

    # 提取所有连接
    conn_pattern = r'(\w+)\s*--[>\|]?\s*(\w+)'
    connections = re.findall(conn_pattern, diagram_content)

    result = {
        "components": [{"id": n, "label": l} for n, l in nodes],
        "connections": [{"from": s, "to": d} for s, d in connections],
        "summary": f"发现 {len(nodes)} 个组件，{len(connections)} 条连接"
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
