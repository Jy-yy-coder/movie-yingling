# -*- coding: utf-8 -*-
"""离线一次性脚本：把 590 部电影拼成档案文本 → bge-small-zh 向量化 → 存 npz。
产出：data/enriched/movie_vectors.npz（含 ids + vectors 两个数组）。

档案配方（不依赖 D3 字段，全部使用 movies_core / sentiment 已有数据）：
  - summary（剧情简介）
  - sentiment.ai_summary（590/590 口碑总结，自然语言）
  - region / director / runtime_min（基础信息）
  - DNA 五维（剧情/演技/情感/视听/节奏）
  - quotes 高赞好评
  - emotions（观众情绪词），无 emotions 时降级用 freq 高频词
"""
from __future__ import annotations
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import json
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ENRICHED = BASE / "data" / "enriched"


def build_profile(m: dict, sentiment_map: dict) -> str:
    """拼档案文本——自然语言句式，全部来自现有数据文件。"""
    parts = []

    # —— 第一句：基本信息 + 地区 + 导演 ——
    head = (f"《{m['title']}》（{m['year']}），{m.get('region', '')}电影，"
            f"{'/'.join(m['genres'])}，豆瓣{m['rating']}分，"
            f"片长{m.get('runtime_min', 0)}分钟，语言：{m.get('first_lang', '未知')}。")
    directors = m.get("director") or []
    if directors:
        head += f"导演：{'、'.join(directors[:2])}。"
    parts.append(head)

    # —— 简介：summary ——
    summary = (m.get("summary") or "").strip()
    if summary:
        parts.append("剧情：" + summary[:200])

    # —— 观众情绪（sentiment.json 的 emotions；无 emotions 时降级用 freq 高频词）——
    s = sentiment_map.get(m["movie_id"], {})
    emos = [e["w"] for e in (s.get("emotions") or [])[:6]]
    if emos:
        parts.append("观众普遍感受到：" + "、".join(emos) + "。")
    else:
        # 降级：21 部电影没有 emotions，用 freq 前 6 个高频词代替
        freqs = [f["w"] for f in (s.get("freq") or [])[:6]]
        if freqs:
            parts.append("观众常提到：" + "、".join(freqs) + "。")

    # —— AI 口碑总结（590/590 全覆盖，自然语言）——
    ai_sum = (s.get("ai_summary") or "").strip()
    if ai_sum:
        parts.append("口碑：" + ai_sum[:150])

    # —— DNA 顶维（自然语言句式）——
    d = m.get("dna") or {}
    dims = ["剧情", "演技", "情感", "视听", "节奏"]
    scored = sorted(((name, d.get(k, 0) or 0) for k, name in
                     zip(dims, dims)), key=lambda x: -x[1])
    if scored[0][1] > 0:
        parts.append(f"这部片以{scored[0][0]}和{scored[1][0]}见长，"
                     f"观众打分{scored[0][0]}{scored[0][1]}、{scored[1][0]}{scored[1][1]}。")

    # —— 高赞好评金句 ——
    up = (m.get("quotes") or {}).get("up1")
    if up:
        parts.append(f"高赞观众评论：「{up['text'][:80]}」")

    # —— A3 富化字段（2026-08-19 起全部真实有依据）：一句话简介 / 观影提示 / 冷知识 ——
    brief = (m.get("brief") or "").strip()
    if brief:
        parts.append("一句话简介：" + brief)
    warn = m.get("warn") or {}
    if warn.get("text"):
        parts.append("观影提示：" + str(warn["text"])[:60])
    egg = m.get("egg") or {}
    if egg.get("text"):
        parts.append("冷知识：" + str(egg["text"])[:80])

    return "\n".join(parts)


def main():
    movies = json.loads((ENRICHED / "movies_core.json").read_text(encoding="utf-8"))
    sentiment_map = json.loads((ENRICHED / "sentiment.json").read_text(encoding="utf-8"))

    print(f"加载 {len(movies)} 部电影，开始拼档案…")
    profiles, ids = [], []
    for m in movies:
        p = build_profile(m, sentiment_map)
        if len(p) < 50:          # 过滤残缺数据
            continue
        profiles.append(p)
        ids.append(m["movie_id"])

    print(f"有效档案 {len(profiles)} 部，开始向量化…")
    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    vectors = model.encode(profiles, normalize_embeddings=True, show_progress_bar=True)
    vectors = np.array(vectors, dtype=np.float32)

    out = ENRICHED / "movie_vectors.npz"
    np.savez(out, ids=np.array(ids), vectors=vectors)
    print(f"✅ 已保存：{out}（{vectors.shape}）")

    # 打印 3 条样本，人工检查档案质量
    for i in [0, len(profiles) // 2, -1]:
        print(f"\n--- 样本 {ids[i]} ---")
        print(profiles[i][:400])

    # —— 检索准确度测试 ——
    test_queries = [
        "想哭一场但别太压抑",
        "轻松下饭的喜剧",
        "探讨孤独和存在意义",
    ]
    print("\n" + "=" * 60)
    print("检索准确度测试")
    print("=" * 60)
    for q in test_queries:
        qv = model.encode([q], normalize_embeddings=True)
        scores = (vectors @ qv[0])
        top6 = np.argsort(-scores)[:6]
        print(f"\n「{q}」→")
        for idx in top6:
            mid = ids[idx]
            m = next(x for x in movies if x["movie_id"] == mid)
            print(f"  {scores[idx]:.3f}  《{m['title']}》({m['year']}) 豆瓣{m['rating']}")

    # —— 一致性检查：向量库 ids 与 movies_core.json 全量对齐 ——
    print("\n" + "=" * 60)
    print("一致性检查")
    print("=" * 60)
    core_ids = {m["movie_id"] for m in movies}
    vec_ids = set(ids)
    missing = core_ids - vec_ids
    if missing:
        print(f"⚠️ 有 {len(missing)} 部电影未入向量库（档案过短被过滤）：{list(missing)[:5]}…")
    else:
        print(f"✅ 全部 {len(ids)} 部电影均已入向量库，与 movies_core.json 完全对齐")


if __name__ == "__main__":
    main()
