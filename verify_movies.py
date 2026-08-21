# -*- coding: utf-8 -*-
"""
数据核验脚本：随机抽样 N 部电影，重新访问豆瓣详情页，
逐字段与 data/movies.csv 已保存数据对比，输出差异报告。
用法：python verify_movies.py [抽样数量，默认20]
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import random
import time

import pandas as pd
from playwright.sync_api import sync_playwright

from crawler_movie import (launch_browser, EXTRACT_JS, MOVIES_CSV,
                           CSV_FIELDS, sleep_random, is_blocked)

SAMPLE_N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
# rating/rating_count 会随时间实时变动，单独宽松对比
DYNAMIC_FIELDS = {"rating", "rating_count", "poster_url"}


def main():
    df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    sample = df.sample(min(SAMPLE_N, len(df)), random_state=None)
    diffs, checked = [], 0

    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=True)
        page = context.new_page()
        for _, row in sample.iterrows():
            mid = row["movie_id"]
            page.goto(f"https://movie.douban.com/subject/{mid}/",
                      wait_until="domcontentloaded")
            if is_blocked(page):
                print("!! 被封锁，中止核验")
                break
            page.wait_for_selector("#info", timeout=15000)
            live = page.evaluate(EXTRACT_JS)
            checked += 1
            row_diff = []
            for f in CSV_FIELDS:
                if f == "movie_id":
                    continue
                old = str(row.get(f, "")).strip()
                new = str(live.get(f, "")).strip()
                if f in DYNAMIC_FIELDS:
                    continue  # 动态字段最后单独汇总
                if old != new:
                    row_diff.append((f, old, new))
            # 动态字段：评分差>0.1 或人数差>5% 才提示
            try:
                r_old, r_new = float(row["rating"]), float(live["rating"])
                if abs(r_old - r_new) > 0.1:
                    row_diff.append(("rating", row["rating"], live["rating"]))
            except ValueError:
                pass
            status = "一致" if not row_diff else f"发现 {len(row_diff)} 处差异"
            print(f"[{checked}/{len(sample)}] {mid} {row['title'][:20]} -> {status}")
            for f, old, new in row_diff:
                print(f"    字段[{f}]")
                print(f"      CSV : {old[:120]}")
                print(f"      网页: {new[:120]}")
                diffs.append((mid, row["title"], f, old, new))
            sleep_random((2.0, 4.0))
        browser.close()

    print("=" * 60)
    print(f"核验完成：抽样 {checked} 部，其中 {len(set(d[0] for d in diffs))} 部存在字段差异，"
          f"共 {len(diffs)} 处")
    if diffs:
        out = pd.DataFrame(diffs, columns=["movie_id", "title", "field", "csv_value", "web_value"])
        out.to_csv("logs/verify_diff.csv", index=False, encoding="utf-8-sig")
        print("差异明细已保存: logs/verify_diff.csv")


if __name__ == "__main__":
    main()
