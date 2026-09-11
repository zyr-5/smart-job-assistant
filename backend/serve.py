# -*- coding: utf-8 -*-
"""
生产环境启动入口：FastAPI 同时提供 /api 接口与前端静态资源。

与开发环境的两进程模式（Vite 5173 代理到 uvicorn 8000）不同，生产环境由
本进程单端口同时提供页面与接口，因此前端不需要跨域，也不用额外配置代理。

用法：
    python serve.py                      # 默认 0.0.0.0:8000
    python serve.py --port 8080
    python serve.py --data-dir /data     # 容器/平台持久化目录

环境变量：
    PORT / DATA_DIR 也可用，命令行参数优先。
"""
import argparse
import os
import sys
from pathlib import Path

# 必须在导入 app.* 之前解析参数：app.config 在导入时就会读取 DATA_DIR 并建目录
_parser = argparse.ArgumentParser(description="智能求职助手生产入口")
_parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
_parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
_parser.add_argument("--reload", action="store_true", help="开发用热重载")
_parser.add_argument(
    "--data-dir",
    default=os.environ.get("DATA_DIR", ""),
    help="数据目录（缓存/历史/上传），平台无持久盘时保持默认即可",
)
_args = _parser.parse_args()

if _args.data_dir:
    os.environ["DATA_DIR"] = str(Path(_args.data_dir).expanduser().resolve())

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR))

from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

_FRONTEND_DIST = _BACKEND_DIR.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # html=True 让 / 与未知路径回落到 index.html，配合前端 history 路由
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    print(f"[serve] 前端静态资源已挂载: {_FRONTEND_DIST}")
else:
    print(
        f"[serve] 警告：未找到前端构建产物 {_FRONTEND_DIST}\n"
        f"        请先执行: cd frontend && npm install && npm run build\n"
        f"        当前仅提供 /api 接口。"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=_args.host,
        port=_args.port,
        reload=_args.reload,
        log_level="info",
    )
