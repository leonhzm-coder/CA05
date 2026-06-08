# CA05 跨云运维助手 - Dockerfile
# 基于 Python 3.11-slim，预装 Aliyun CLI 和 Node.js

FROM python:3.11-slim

# 安装 Node.js (for npx skills) 和 curl
RUN apt-get update && \
    apt-get install -y curl gnupg2 && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 Aliyun CLI (Go 二进制)
RUN curl -sL https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz -o aliyun.tgz && \
    tar -xzf aliyun.tgz && \
    mv aliyun /usr/local/bin/ && \
    rm aliyun.tgz && \
    chmod +x /usr/local/bin/aliyun && \
    aliyun --version

# 安装 Python 依赖
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 创建 memory 目录
RUN mkdir -p /app/memory

# 配置环境变量默认值
ENV PORT=9000
ENV CA05_MEMORY_FILE=/app/memory/ca05_memory.json

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')" || exit 1

# 启动服务
CMD ["python3", "main.py"]
