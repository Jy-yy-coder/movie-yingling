# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · LLM 封装
读 data/task/llm_config.json；聊天用模型链（默认 deepseek-v4-flash，可行则依次尝试），
全部失败返回 None（调用方降级离线模式）。sensenova-6.7-flash-lite 为推理型、
输出预算全耗在思考上（content 常为 None），不列入聊天候选。
"""
from __future__ import annotations
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("cine.llm")
_lock = threading.Lock()
_last_call = [0.0]

CONFIG = Path(__file__).resolve().parent.parent / "data" / "task" / "llm_config.json"
CHAT_MODELS = ["deepseek-v4-flash", "glm-5.2"]
MIN_INTERVAL = 1.0


_QUOTA_RE = re.compile(r"insufficient_quota|insufficient|quota|balance|credit|欠费|余额|配额|充值|billing", re.I)
_AUTH_RE = re.compile(r"401|invalid.*api.?key|authentication|Unauthorized", re.I)


def _read_local_key() -> str | None:
    """本地密钥文件 data/task/llm_key.local.txt（单行）——不入库/不随提交物，供开发机使用。"""
    try:
        p = CONFIG.parent / "llm_key.local.txt"
        if p.exists():
            k = p.read_text(encoding="utf-8").strip()
            return k or None
    except Exception:
        pass
    return None


def _read_backup_keys() -> list[str]:
    """本地备用 key 列表 data/task/llm_keys_backup.txt（每行一个）——额度耗尽自动轮换。"""
    try:
        p = CONFIG.parent / "llm_keys_backup.txt"
        if p.exists():
            return [k.strip() for k in p.read_text(encoding="utf-8").splitlines() if k.strip()]
    except Exception:
        pass
    return []


def _cfg():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        # key 链：环境变量 -> 本地主 key -> 本地备用 key 列表 -> 配置内联（仅演示）
        keys: list[str] = []
        for k in ([os.environ.get("CINE_LLM_API_KEY")] + [_read_local_key()]
                  + _read_backup_keys() + [cfg.get("api_key")]):
            if k and k not in keys:
                keys.append(k)
        cfg["_keys"] = keys
        cfg["api_key"] = keys[0] if keys else None
        return cfg
    except Exception:
        return None


def _models(cfg):
    m = cfg.get("models", {}).get("chat")
    cands = []
    for x in ([m] if m else []) + CHAT_MODELS:
        if x and x not in cands and x != "sensenova-6.7-flash-lite":
            cands.append(x)
    return cands or ["deepseek-v4-flash"]


def _throttle():
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def chat_reply(system: str, user: str, max_tokens=700, timeout=90, history=None, temperature=0):
    """返回 (回复文本, 所用模型)；全部失败返回 (None, None)。
    history: [{"role":"user","content":"..."},{"role":"assistant","content":"..."}] 列表（最近 10 条，由调用方截好）。
    temperature: 推荐场景用 0.7，问答/搜索用 0（默认 0，防幻觉）。
    额度不足/鉴权失败自动轮换备用 key（llm_keys_backup.txt）。"""
    cfg = _cfg()
    keys = (cfg or {}).get("_keys") or []
    if not keys:
        return None, None
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    # 组装 messages：system + history + 当前 user
    messages = [{"role": "system", "content": system}]
    if history:
        messages += history[-10:]   # 防御性再截一次，正常情况下 main.py 已截好
    messages.append({"role": "user", "content": user})

    for ki, key in enumerate(keys):
        cli = OpenAI(api_key=key, base_url=cfg["base_url"], timeout=timeout)
        for model in _models(cfg):
            try:
                _throttle()
                r = cli.chat.completions.create(
                    model=model, temperature=temperature,
                    messages=messages,
                    max_tokens=max_tokens)
                txt = (getattr(r.choices[0].message, "content", None) or "").strip()
                if txt:
                    return txt, model
            except Exception as e:
                msg = str(e)
                if _QUOTA_RE.search(msg) or _AUTH_RE.search(msg):
                    if ki + 1 < len(keys):
                        log.warning("chat key#%d 额度/鉴权失败，轮换到备用 key", ki + 1)
                        break      # 换 key 后用下一个 key 重试
                    log.error("chat 全部 key 额度/鉴权失败")
                    return None, None
                log.warning("chat 模型 %s 失败: %s", model, msg[:120])
                if "429" in msg:
                    time.sleep(6)
    return None, None
