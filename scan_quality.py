# -*- coding: utf-8 -*-
"""全维度数据质量扫描（只读，不改数据）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import re
import pandas as pd
from crawler_movie import MOVIES_CSV

df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
print("当前总数:", len(df))
df["rc"] = pd.to_numeric(df["rating_count"], errors="coerce").fillna(0)
df["r"] = pd.to_numeric(df["rating"], errors="coerce")
df["y"] = pd.to_numeric(df["year"], errors="coerce")


def mins(s):
    m = re.findall(r"(\d+)", str(s))
    return int(m[0]) if m else 0


df["mm"] = df["runtime"].apply(mins)

print("\n===== 1. 评分人数分布（冷门度）=====")
for lo, hi in [(0, 1000), (1000, 5000), (5000, 10000), (10000, 50000), (50000, 1e9)]:
    n = ((df.rc >= lo) & (df.rc < hi)).sum()
    print(f"  {int(lo):>7}-{int(hi):<9}: {n} 部")
print("  评分人数最少的15部:")
for r in df.nsmallest(15, "rc").itertuples():
    print(f"    {r.movie_id:>10} | {int(r.rc):>7}人 | 评分{r.rating} | {r.year} | {r.title[:32]}")

print("\n===== 2. 时长异常 =====")
print("  时长>240分钟(疑似合集/剧集打包):")
for r in df[df.mm > 240].itertuples():
    print(f"    {r.movie_id:>10} | {r.runtime} | {r.title[:40]}")
zero = df[df.mm == 0]
print(f"  时长解析为0: {len(zero)} 部")
for r in zero.itertuples():
    print(f"    {r.movie_id:>10} | runtime='{r.runtime}' | {r.title[:32]}")

print("\n===== 3. 疑似剧集/综艺/纪录片（类型或简介关键词）=====")
pat_g = "真人秀|脱口秀|音乐剧|歌舞伎|戏曲"
g = df[df["genres"].str.contains(pat_g, na=False)]
for r in g.itertuples():
    print(f"    [类型] {r.movie_id:>10} | {r.genres} | {r.title[:34]}")
pat_s = "该剧|本剧|电视剧|连续剧|迷你剧|第一季|第二季|系列剧|电视系列|综艺|真人秀节目"
s = df[df["summary"].str.contains(pat_s, na=False)]
for r in s.itertuples():
    print(f"    [简介] {r.movie_id:>10} | {r.title[:30]:<32} | ...{[k for k in pat_s.split('|') if k in r.summary]}")

print("\n===== 4. 标题含 剧场版/特别篇/SP/番外/前篇后篇 =====")
pat_t = "剧场版|劇場版|特别篇|特別篇|前篇|后篇|後篇|番外|总集篇|SP|OVA|完全版|导演剪辑"
t = df[df["title"].str.contains(pat_t, na=False)]
for r in t.itertuples():
    print(f"    {r.movie_id:>10} | {r.runtime:>12} | {r.title[:46]}")

print("\n===== 5. 年份异常（>当前年 或 缺失）=====")
bad_y = df[(df.y.isna()) | (df.y > 2026) | (df.y < 1900)]
for r in bad_y.itertuples():
    print(f"    {r.movie_id:>10} | year='{r.year}' | {r.title[:34]}")

print("\n===== 6. 关键字段疑似异常 =====")
print("  导演为空:", (df["director"] == "").sum())
for r in df[df["director"] == ""].itertuples():
    print(f"    {r.movie_id} | {r.title[:34]}")
print("  编剧为空:", (df["writer"] == "").sum())
for r in df[df["writer"] == ""].itertuples():
    print(f"    {r.movie_id} | {r.title[:34]}")
print("  主演为空:", (df["actors"] == "").sum())
for r in df[df["actors"] == ""].itertuples():
    print(f"    {r.movie_id} | {r.title[:34]}")
print("  简介过短(<30字):", (df["summary"].str.len() < 30).sum())
for r in df[df["summary"].str.len() < 30].itertuples():
    print(f"    {r.movie_id} | {r.title[:30]} | summary='{r.summary[:40]}'")

print("\n===== 7. 标题重复（同名不同ID，疑似重拍/重复）=====")
df["base"] = df["title"].str.split().str[0]
dup = df[df.duplicated("base", keep=False)].sort_values("base")
for base, grp in dup.groupby("base"):
    if len(grp) > 1:
        ids = " / ".join(f"{r.movie_id}({r.year})" for r in grp.itertuples())
        print(f"    {base}: {ids}")
