# -*- coding: utf-8 -*-
"""影灵 CINE · 向量语义检索层
启动时加载 movie_vectors.npz + bge-small-zh 模型；提供 retrieve()。
关键词推荐匹配不到时（语义需求）走这里。"""
from __future__ import annotations
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import logging
import threading
from pathlib import Path

try:
    import numpy as np            # 本地向量检索用；serverless 未装 numpy 时整体降级
except ImportError:               # pragma: no cover - 部署环境
    np = None

log = logging.getLogger("cine.embed")

BASE = Path(__file__).resolve().parent.parent
VECTORS_PATH = BASE / "data" / "enriched" / "movie_vectors.npz"

MIN_SCORE = 0.25               # 最低相似度阈值，低于则丢弃

_model = None                  # SentenceTransformer 实例
_ids: list[str] = []           # movie_id 列表
_vectors = None                # np.ndarray (N, 512)，已归一化
_loaded = False
_lock = threading.Lock()       # 懒加载线程锁


def _ensure_loaded():
    global _model, _ids, _vectors, _loaded
    if _loaded:
        return
    with _lock:                               # 加锁，防并发重复加载
        if _loaded:                           # double-check
            return
        try:
            if not VECTORS_PATH.exists():
                log.warning("movie_vectors.npz 不存在，向量检索不可用。请先运行 cine.build_vectors")
            else:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
                data = np.load(VECTORS_PATH)
                _ids = [str(x) for x in data["ids"]]     # 显式转 str，避免 numpy str_ 类型漂移
                _vectors = data["vectors"]
                log.info("向量检索就绪：%d 部电影，维度 %d", len(_ids), _vectors.shape[1])
        except Exception as e:
            log.warning("向量检索加载失败（降级为关键词模式）：%s", str(e)[:120])
        _loaded = True


def available() -> bool:
    """向量检索是否可用（模型 + npz 都在）。"""
    if np is None:
        return False
    _ensure_loaded()
    return _model is not None and _vectors is not None


def retrieve(query: str, top_k: int = 6, min_score: float = MIN_SCORE) -> list[tuple[str, float]]:
    """语义检索：返回 [(movie_id, score), ...]，按分数降序，过滤低于 min_score 的结果。
    不可用或全部低于阈值时返回空列表。"""
    _ensure_loaded()
    if not available():
        return []
    try:
        qv = _model.encode([query], normalize_embeddings=True)
        scores = _vectors @ qv[0]
        top_idx = np.argsort(-scores)[:top_k]
        out = [(_ids[i], float(scores[i])) for i in top_idx if scores[i] >= min_score]
        return out
    except Exception as e:
        log.warning("向量检索失败：%s", str(e)[:120])
        return []
