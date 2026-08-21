# -*- coding: utf-8 -*-
"""数据清洗：删除非电影条目（剧集特辑/舞台录像/中短片/异常合集）
删除前自动备份 movies.csv 与 movie_tasks.csv 到 logs/backup_清洗前/
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import shutil
from datetime import datetime

import pandas as pd

from crawler_movie import MOVIES_CSV, TASK_FILE, POSTER_DIR, LOG_DIR

# 待删除的 16 部（A剧集特辑 / B舞台录像 / C中短片 / D异常合集）
REMOVE = {
    # A类：剧集单集 / 电视特辑
    "25798411": "神探夏洛克：福至如归",
    "25804790": "神探夏洛克：最后的誓言",
    "26725031": "是，大臣 1984圣诞特辑",
    "35432352": "万物生灵：2021圣诞特别集",
    "34908189": "老友记重聚特辑",
    "10583098": "十二怒汉（电视版）",
    # B类：舞台剧 / 音乐剧现场录像
    "35861791": "初步举证 NT Live",
    "37293378": "非穷尽列举 NT Live",
    "34795703": "伦敦生活 NT Live: Fleabag",
    "24751811": "剧院魅影：25周年纪念演出",
    "34961898": "汉密尔顿 Hamilton",
    # C类：中短片
    "1303408": "福尔摩斯二世",
    "5989818": "萤火之森",
    "20470074": "言叶之庭",
    "25861610": "熊出没之年货",
    # D类：异常合集
    "26972694": "狐妖小红娘剧场版：月红篇",
    # E类：精选辑/合集重剪版（第二轮清洗）
    "5133063": "憨豆先生精选辑（电视片段合集）",
    "4860078": "无间道(正序版)（三部曲重剪，原版已在库）",
    "10756537": "杀死比尔：血色全传（Vol.1+2合并，原版已在库）",
}


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = LOG_DIR / f"backup_清洗前_{ts}"
    backup.mkdir(parents=True, exist_ok=True)

    # 1. 备份
    shutil.copy(MOVIES_CSV, backup / "movies.csv")
    if TASK_FILE.exists():
        shutil.copy(TASK_FILE, backup / "movie_tasks.csv")
    print(f"已备份到: {backup}")

    # 2. 过滤 movies.csv
    df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    before = len(df)
    hit = df[df["movie_id"].isin(REMOVE)]
    print(f"\n命中待删 {len(hit)}/{len(REMOVE)} 部：")
    for r in hit.itertuples():
        print(f"  - {r.movie_id} {r.title[:40]}")
    df = df[~df["movie_id"].isin(REMOVE)]
    df.to_csv(MOVIES_CSV, index=False, encoding="utf-8-sig")
    print(f"\nmovies.csv: {before} -> {len(df)} 部")

    # 3. 同步过滤任务清单
    if TASK_FILE.exists():
        tk = pd.read_csv(TASK_FILE, dtype=str).fillna("")
        tb = len(tk)
        tk = tk[~tk["movie_id"].isin(REMOVE)]
        tk.to_csv(TASK_FILE, index=False, encoding="utf-8-sig")
        print(f"movie_tasks.csv: {tb} -> {len(tk)} 部")

    # 4. 删除海报文件
    removed = 0
    for mid in REMOVE:
        p = POSTER_DIR / f"{mid}.jpg"
        if p.exists():
            p.unlink()
            removed += 1
    print(f"海报文件: 删除 {removed} 张")


if __name__ == "__main__":
    main()
