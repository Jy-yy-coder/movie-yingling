# -*- coding: utf-8 -*-
"""
movies_info_clean.csv 第三轮: 数据缺失过多剔除 (2026-08-04 对话确认)
规则: 13 个用户可检索字段(评分/评价人数/片长/简介/海报/导演/主演/类型/国家/IMDb/年份/上映日期/编剧)
      缺失 >= 5 个 且 无豆瓣评分 且 无评价人数 -> 剔除 (10,531 行)
执行前备份为 movies_info_clean.bak2.csv (已存在则不覆盖)
"""
import os
import shutil
import pandas as pd

TARGET = r"D:/111111111/movies_info_clean.csv"
BAK2 = r"D:/111111111/movies_info_clean.bak2.csv"

if not os.path.exists(BAK2):
    shutil.copy2(TARGET, BAK2)
    print("已备份原文件 ->", BAK2)
else:
    print("备份已存在, 跳过:", BAK2)

df = pd.read_csv(TARGET, dtype=str, keep_default_na=False, low_memory=False)
n0 = len(df)
print("输入行数:", n0)

r = pd.to_numeric(df["豆瓣评分"], errors="coerce")
has_r = (r > 0) & (r <= 10)
has_p = pd.to_numeric(df["评价人数"], errors="coerce").fillna(0) > 0
mn = pd.to_numeric(df["片长"].str.extract(r"(\d+)分钟", expand=False), errors="coerce")

fields = [
    ("评分", has_r),
    ("评价人数", has_p),
    ("片长", mn.notna()),
    ("简介", df["剧情简介"].str.len() > 10),
    ("海报", df["海报URL"] != ""),
    ("导演", df["导演"] != ""),
    ("主演", df["主演"] != ""),
    ("类型", df["类型"] != ""),
    ("国家", df["制片国家/地区"] != ""),
    ("IMDb", df["IMDb编号"] != ""),
    ("年份", pd.to_numeric(df["年份"], errors="coerce") > 0),
    ("上映日期", df["上映日期"].str.len() >= 8),
    ("编剧", df["编剧"] != ""),
]
miss = sum((~v).astype(int) for _, v in fields)
mask = (miss >= 5) & (~has_r) & (~has_p)
print(f"剔除(缺失>=5且无评分无人数): {int(mask.sum())} 行")
df = df[~mask].reset_index(drop=True)
print(f"剩余 {len(df)} 行 (原 {n0})")

df.to_csv(TARGET, index=False, encoding="utf-8-sig")
print("已写回:", TARGET)
