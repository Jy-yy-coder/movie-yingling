# -*- coding: utf-8 -*-
"""
movies_info_clean.csv 第二轮: 质量与完整度筛选 (2026-08-04 对话确认)
基于用户手动筛过的 clean 文件(255,121行)继续:
  顺带修复: 片长非标格式解析('90'/'90min'/'1 hour'/'90 Dakika'/'N小时'/'N秒'/'暂无分钟')
            类型英文/繁中/混写token统一中文, 删'外语'假token, 映射后去重
  筛选规则: 剔 <5分钟超短片 | 片长含'集'的剧集 | 含 Adult/成人/情色 的成人内容
            含 真人秀/脱口秀/游戏秀/新闻 的非电影节目 | 无评分&无人数&简介空&海报空的全空行
执行前自动备份原文件为 movies_info_clean.bak.csv (已存在则不覆盖)
注意: 本脚本刻意不使用 \\b 词边界 (脚本经由 JSON 写入会被误转义), 统一用 (?![a-zA-Z0-9]) 替代
"""
import os
import re
import shutil
import pandas as pd

TARGET = r"D:/111111111/movies_info_clean.csv"
BAK = r"D:/111111111/movies_info_clean.bak.csv"

if not os.path.exists(BAK):
    shutil.copy2(TARGET, BAK)
    print("已备份原文件 ->", BAK)
else:
    print("备份已存在, 跳过:", BAK)

df = pd.read_csv(TARGET, dtype=str, keep_default_na=False, low_memory=False)
n0 = len(df)
print("输入行数:", n0)

# ================= 顺带修复 A: 片长解析 =================
def parse_runtime(s):
    if s == "":
        return ""
    m = re.match(r"^(\d+)\s*分钟\s*(.*)$", s)
    if m:
        rest = m.group(2).strip()
        return f"{m.group(1)}分钟 {rest}".rstrip()
    m = re.fullmatch(r"(\d+)", s)
    if m:
        return f"{m.group(1)}分钟"
    m = re.fullmatch(r"(\d+)\s*min\w*", s, re.I)
    if m:
        return f"{m.group(1)}分钟"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*h(?:our)?s?\s*(?:(\d+)\s*min\w*)?", s, re.I)
    if m:
        total = round(float(m.group(1)) * 60 + float(m.group(2) or 0))
        return f"{total}分钟"
    if s in {"暂无分钟", "暂无"}:
        return ""
    s2 = s.replace("（", "").replace("）", "").replace("(", "").replace(")", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*小时\s*(?:(\d+(?:\.\d+)?)\s*分[钟鐘]?)?", s2)
    if m:
        total = round(float(m.group(1)) * 60 + float(m.group(2) or 0))
        return f"{total}分钟"
    m = re.search(r"(\d+)\s*分[钟鐘]?", s2)
    if m:
        return f"{m.group(1)}分钟"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hrs?|hours?|Dakika)(?![a-zA-Z])", s2, re.I)
    if m:
        return f"{round(float(m.group(1)) * 60)}分钟"
    m = re.search(r"(\d+)\s*[-–—]?\s*(?:min\w*|mn\w*|мин)", s2, re.I)
    if m:
        return f"{m.group(1)}分钟"
    m = re.search(r"(\d+)\s*fenz\w*", s2, re.I)
    if m:
        return f"{m.group(1)}分钟"
    m = re.search(r"(\d+)\s*m(?![a-zA-Z0-9])", s2)
    if m:
        return f"{m.group(1)}分钟"
    m = re.fullmatch(r"(\d{1,3}):(\d{2})", s2)
    if m:
        return f"{int(m.group(1)) + int(m.group(2)) / 60:g}分钟"
    m = re.search(r"(\d+)\s*['′’]", s2)
    if m:
        return f"{m.group(1)}分钟"
    m = re.search(r"(\d+)\s*秒", s2)
    if m:
        return f"{float(m.group(1)) / 60:.1f}分钟"
    return None

l0 = df["片长"].copy()
parsed = l0.map(parse_runtime)
unfixable = parsed.isna()
df["片长"] = parsed.where(~unfixable, l0)
print(f"片长解析修复: {(l0 != df['片长']).sum()} 行 | 保留原样的怪格式 {unfixable.sum()} 行")
if unfixable.sum():
    vc = df.loc[unfixable, "片长"].value_counts()
    print(f"  怪格式共 {len(vc)} 种, 前 25 种:", vc.head(25).to_dict())

# ================= 顺带修复 B: 类型 token 统一中文 =================
GENRE_MAP = {k.lower(): v for k, v in {
"Drama":"剧情","Comedy":"喜剧","Action":"动作","Adventure":"冒险","Thriller":"惊悚","Crime":"犯罪",
"Romance":"爱情","Sci-Fi":"科幻","Horror":"恐怖","Mystery":"悬疑","Fantasy":"奇幻","Biography":"传记",
"Reality-TV":"真人秀","Family":"家庭","Animation":"动画","Talk-Show":"脱口秀","History":"历史",
"Game-Show":"游戏秀","Sport":"运动","Musical":"歌舞","Western":"西部","Short":"短片","Kids":"儿童",
"Music":"音乐","War":"战争","Documentary":"纪录片","Adult":"成人","News":"新闻",
"惊栗":"惊悚","悬念":"悬疑","记录":"纪录片",
"紀錄片":"纪录片","劇情":"剧情","動畫":"动画","懸疑":"悬疑","驚悚":"惊悚","傳記":"传记","愛情":"爱情",
"喜劇":"喜剧","音樂":"音乐","歷史":"历史","動作":"动作","冒險":"冒险","兒童":"儿童","戰爭":"战争",
}.items()}
DROP_TOKENS = {"外语"}

def clean_genres(cell):
    if cell == "":
        return ""
    out = []
    for tok in cell.split(" / "):
        tok = tok.strip()
        if tok in DROP_TOKENS:
            continue
        parts = [p.strip() for p in re.split(r"\s+", tok) if p.strip()]
        mapped = []
        ok = True
        for p in parts:
            cn = GENRE_MAP.get(p.lower())
            if cn is None:
                if re.findall(r"[一-鿿]", p):
                    cn = p
                else:
                    ok = False
                    break
            mapped.append(cn)
        if not ok:
            mapped = [tok]
        for cn in mapped:
            if cn and cn not in out:
                out.append(cn)
    return " / ".join(out)

g0 = df["类型"].copy()
df["类型"] = g0.map(clean_genres)
print(f"类型 token 归并: {(g0 != df['类型']).sum()} 行 | 归并后含拉丁字符行: {df['类型'].str.contains(r'[A-Za-z]').sum()}")
print("  类型空行数:", (df["类型"] == "").sum())

# ================= 筛选剔除 =================
r = pd.to_numeric(df["豆瓣评分"], errors="coerce")
has_r = (r > 0) & (r <= 10)
p = pd.to_numeric(df["评价人数"], errors="coerce").fillna(0)
mn = pd.to_numeric(df["片长"].str.extract(r"(\d+)分钟", expand=False), errors="coerce")
gtoks = df["类型"].str.split(" / ").explode()

mask_series = df["片长"].str.contains("集")
mask_short = mn < 5
adult_ids = gtoks[gtoks.isin(["成人", "情色"])].index.unique()
mask_adult = df.index.isin(adult_ids)
tv_ids = gtoks[gtoks.isin(["真人秀", "脱口秀", "游戏秀", "新闻"])].index.unique()
mask_tv = df.index.isin(tv_ids)
mask_empty = (~has_r) & (p <= 0) & (df["剧情简介"].str.len() <= 10) & (df["海报URL"] == "")

masks = {
    "片长含'集'的剧集": mask_series,
    "<5分钟超短片": mask_short,
    "成人内容(成人/情色)": mask_adult,
    "非电影节目(真人秀/脱口秀/游戏秀/新闻)": mask_tv,
    "全空行(无评分人数简介海报)": mask_empty,
}
union = pd.Series(False, index=df.index)
for name, m in masks.items():
    print(f"{name}: {int(m.sum())} 行")
    union |= m
only_union = int(union.sum())
df = df[~union].reset_index(drop=True)
print(f"剔除合计(去重后): {only_union} 行 | 剩余 {len(df)} 行 (原 {n0})")

df.to_csv(TARGET, index=False, encoding="utf-8-sig")
print("已写回:", TARGET)
