# -*- coding: utf-8 -*-
"""Vercel Python Serverless 入口：把 FastAPI 挂为 ASGI 处理器。
路由见 vercel.json：/api/* → 本函数；其余路径走前端静态资源。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cine.main import app  # noqa: E402
