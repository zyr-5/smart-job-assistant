# 智能求职助手 —— 生产镜像
# 单容器同时提供 FastAPI 接口与前端静态资源（见 backend/serve.py），
# 因此无需 Nginx，也不存在跨域配置问题。

# ---------- 阶段 1：构建前端 ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

# 先只复制依赖清单，利用 Docker 层缓存：源码改动不会导致重新装依赖
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

# 先装依赖，再复制源码，最大化利用层缓存
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# 数据目录（缓存/历史/上传）。未挂载卷时数据随容器生命周期存在，
# 挂载持久卷后即可长期保留。
RUN mkdir -p /data
VOLUME ["/data"]

# 以非 root 用户运行，降低容器逃逸风险
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

WORKDIR /app/backend
CMD ["python", "serve.py", "--host", "0.0.0.0", "--port", "8000"]
