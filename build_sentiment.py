# -*- coding: utf-8 -*-
"""影灵 CINE · 观众情绪数据构建（规则离线版）
读 data/movie_comments.csv（88,169 条真实短评，590/590 全覆盖）→ 输出 data/enriched/sentiment.json。

抽样口径（重要）：为保证跨片可比，评论按好/中/差各约 50 条分层抽样（每片约 150 条）。
因此"总体占比"类指标（如好/中/差比例）无统计意义，已不输出。
展示口径统一使用与抽样无关或层内相对的信号：
- good5 / bad1：各层内部的星级强度（真实区分信号）
- temp：情绪温度 = good5×0.6 + (1-bad1)×0.4 的百分位复合分（暖冷渐变用）
- emotions / freq：基于评论文本的词频（与抽样比例无关）
- avg_star：样本内平均星（分层抽样使数值向中间压缩，仅作参考）
- trend：按年好评率（每年至少 4 条）
AI 总结为真实数据模板拼装，不改事实。

用法：PYTHONIOENCODING=utf-8 python build_sentiment.py
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jieba
import pandas as pd

BASE = Path(__file__).resolve().parent
CSV = BASE / "data" / "movie_comments.csv"
OUT = BASE / "data" / "enriched" / "sentiment.json"
CORE = BASE / "data" / "enriched" / "movies_core.json"

if sys.stdout.encoding.lower().startswith("gbk"):
    sys.stdout.reconfigure(errors="replace")

# ---------- 词典 ----------
EMOTION_LEX = [
    "治愈", "感动", "温暖", "温馨", "浪漫", "甜蜜", "温柔", "深情", "真挚", "真诚",
    "孤独", "寂寞", "压抑", "沉重", "残酷", "悲伤", "难过", "心碎", "绝望", "揪心",
    "震撼", "惊艳", "热血", "燃", "励志", "奋斗", "成长", "蜕变", "救赎", "释怀",
    "宁静", "纯粹", "美好", "坚强", "勇敢", "幽默", "搞笑", "轻松", "哭", "泪",
]

_STOP = set("""的 了 是 我 你 他 她 它 也 都 就 在 有 不 没 很 太 被 让 给 对 从 到 和 与 或 而 但 却
电影 一部 一个 一种 一次 一点 这个 那个 这些 那些 这种 那种 什么 怎么 这样 那样 自己 他们 我们 你们
因为 所以 但是 而且 于是 如果 虽然 虽然 不过 可是 觉得 真的 非常 特别 还是 就是 一直 然后 可以
需要 应该 可能 已经 现在 当时 以前 之后 其实 当然 确实 完全 总是 有点 有些 很多 看到 知道 喜欢
以为 感觉 那么 这么 不是 没有 只是 还会 至少 哪怕 甚至 为了 关于 对于 越来越 一部 基本 完全
有时 时候 地方 一下 上来 起来 下去 过来 出来 进去 回来 这么着 怎么看 想起来 后来 最后 终于 慢慢""".split())

EMOTION_LEX = [w for w in EMOTION_LEX if w not in _STOP]
_CJK = re.compile(r"^[\u4e00-\u9fff]{2,6}$")


def _tokens(text: str) -> list[str]:
    return [t for t in jieba.lcut(text or "") if _CJK.match(t) and t not in _STOP]


def main() -> None:
    df = pd.read_csv(CSV, dtype=str).fillna("")
    core = json.loads(CORE.read_text(encoding="utf-8"))
    dna_by_id = {m["movie_id"]: m.get("dna") or {} for m in core}
    quote_by_id = {m["movie_id"]: m.get("quotes") or {} for m in core}
    year_s = pd.to_datetime(df["time"], errors="coerce").dt.year

    out: dict[str, dict] = {}
    for mid, g in df.groupby("movie_id"):
        stars = pd.to_numeric(g["star"], errors="coerce").dropna()
        n = len(g)

        # 情感关键词：全样本情感词典命中（好/中/差评论都算，负面情绪词同样代表观众共鸣）
        emo = Counter()
        for t in g["content"].tolist():
            seen = set(_tokens(t))
            for w in EMOTION_LEX:
                if w in seen:
                    emo[w] += 1
        emotions = [{"w": w, "n": c} for w, c in emo.most_common(8) if c >= 2]

        # 高频词：全样本 jieba 词频
        all_toks = Counter()
        for t in g["content"].tolist():
            all_toks.update(_tokens(t))
        freq = [{"w": w, "n": c} for w, c in all_toks.most_common(30) if c >= 3][:12]

        # 评价趋势：按评论年份聚合好评率（每年至少 4 条）
        yr = year_s.loc[g.index]
        trend = []
        for y, idx in g.groupby(yr).groups.items():
            if y is None or pd.isna(y):
                continue
            sub = g.loc[idx]
            n_y = len(sub)
            if n_y < 4:
                continue
            pos_y = (sub["category"] == "好评").sum()
            trend.append({"y": int(y), "pos": round(pos_y / n_y, 3), "n": int(n_y)})
        trend = sorted(trend, key=lambda d: d["y"])[-6:]

        # 情绪强度：桶内星级强度（真实区分信号，抽样按桶分层使类别占比趋同）
        good = g[g["category"] == "好评"]
        bad = g[g["category"] == "差评"]
        g5 = float((good["star"] == "5").mean()) if len(good) >= 5 else 0.5
        b1 = float((bad["star"] == "1").mean()) if len(bad) >= 5 else 0.5

        # AI 总结：真实数据拼装，不改事实
        avg_star = round(float(stars.mean()), 2) if len(stars) else None
        d = dna_by_id.get(mid, {})
        dims = ["剧情", "演技", "情感", "视听", "节奏"]
        top_dim = max(dims, key=lambda k: d.get(k, 0) or 0)
        top_val = round(d.get(top_dim, 0), 1)
        e1 = emotions[0]["w"] if emotions else ""
        e2 = emotions[1]["w"] if len(emotions) > 1 else ""
        q = quote_by_id.get(mid, {}).get("up1")
        quote_txt = (q["text"][:42] + "…") if q else ""
        parts = [f"在 {n} 条真实短评里，好评中有 {round(g5 * 100)}% 给出 5 星"]
        if avg_star:
            parts.append(f"平均 {avg_star} 星")
        parts.append(f"口碑最稳的是「{top_dim}」（{top_val} 分）")
        if e1:
            parts.append(f"观众反复提到「{e1}」{emotions[0]['n']} 次" + (f"、「{e2}」{emotions[1]['n']} 次" if e2 else ""))
        if quote_txt:
            parts.append(f"好评高赞这么说：「{quote_txt}」")
        ai_summary = "。".join(parts) + "。"

        out[mid] = {
            "avg_star": avg_star, "n": n,
            "good5": round(g5, 3), "bad1": round(b1, 3),
            "emotions": emotions, "freq": freq, "trend": trend, "ai_summary": ai_summary,
        }

    # 情绪温度：0-100 复合分 + 语料百分位（暖冷渐变用），保证 590 颗星颜色有区分
    def _score(v: dict) -> float:
        return v["good5"] * 0.6 + (1 - v["bad1"]) * 0.4

    scores = sorted(_score(v) for v in out.values())
    for v in out.values():
        s = _score(v)
        rank = sum(1 for x in scores if x <= s) / len(scores)
        v["temp"] = round(rank * 100)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written {OUT}  {len(out)} 部")
    # QC
    with_emo = sum(1 for v in out.values() if v["emotions"])
    with_freq = sum(1 for v in out.values() if v["freq"])
    with_trend = sum(1 for v in out.values() if v["trend"])
    print(f"有情感词 {with_emo} / 有高频词 {with_freq} / 有趋势 {with_trend}")
    sample = out.get("1291546")
    print("sample 霸王别姬:", json.dumps(sample, ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
