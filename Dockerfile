FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    INSIGHTDESK_DATA_DIR=/app/data

WORKDIR /app

# 先安装依赖，利用镜像层缓存
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# 复制应用代码与前端资源
COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts
COPY run.py ./
COPY README.md ./

RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8770

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8770/api/health', timeout=3).status == 200 else 1)"

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8770", "--no-browser"]
