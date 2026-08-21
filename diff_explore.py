# -*- coding: utf-8 -*-
"""拉取「选电影→豆瓣高分」全量名单，与已采集的 movies.csv 对比差异"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import time

import pandas as pd
from playwright.sync_api import sync_playwright

from crawler_movie import launch_browser, sleep_random, MOVIES_CSV, BASE_DIR

REGIONS = ["华语", "欧美", "日本", "韩国"]
OUT = BASE_DIR / "data" / "task" / "explore_list.csv"


def main():
    rows = []
    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=True)
        page = context.new_page()
        page.goto("https://movie.douban.com/explore", wait_until="domcontentloaded")
        ck = next((c["value"] for c in context.cookies() if c["name"] == "ck"), "")
        for region in REGIONS:
            start, total = 0, None
            while total is None or start < total:
                url = ("https://m.douban.com/rexxar/api/v2/subject/recent_hot/movie"
                       f"?start={start}&limit=20&category=豆瓣高分&type={region}&ck={ck}")
                resp = context.request.get(url, headers={
                    "Referer": "https://movie.douban.com/explore",
                    "Accept": "application/json"})
                if not resp.ok:
                    print(f"[{region}] HTTP {resp.status}，中止")
                    break
                data = resp.json()
                total = data.get("total", 0)
                items = data.get("items", [])
                if not items:
                    break
                for it in items:
                    rows.append({"movie_id": str(it["id"]), "title": it.get("title", ""),
                                 "region": region})
                start += len(items)
                sleep_random((1.0, 2.0))
            print(f"[{region}] 拉取 {sum(1 for r in rows if r['region']==region)}/{total}")
        browser.close()

    web = pd.DataFrame(rows).drop_duplicates("movie_id")
    web.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n网页名单已保存: {OUT}（共 {len(web)} 部）")

    local = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    web_ids = set(web["movie_id"])
    local_ids = set(local["movie_id"])
    missing = web_ids - local_ids     # 网页有、本地没采
    extra = local_ids - web_ids       # 本地采了、网页没有
    print(f"\n已采集: {len(local_ids)} 部 | 网页名单: {len(web_ids)} 部")
    print(f"两者重合: {len(web_ids & local_ids)} 部")
    print(f"\n>> 需要补采（网页有但本地缺）: {len(missing)} 部")
    print(web[web.movie_id.isin(missing)][["movie_id", "title", "region"]]
          .to_string(index=False))
    print(f"\n>> 多采的（本地有但网页没有）: {len(extra)} 部")
    print(local[local.movie_id.isin(extra)][["movie_id", "title"]]
          .head(60).to_string(index=False))


if __name__ == "__main__":
    main()
