# -*- coding: utf-8 -*-
"""为 Vercel serverless 部署瘦身两个大库（本地完整库不受影响：lookup 优先用 lookup.db）。

1. data/enriched/comments_fts.db：每部电影只保留高赞 Top-N 评论（默认 15），
   经典台词/梗几乎都在高赞评论里，长尾低赞评论对检索价值低但体积占 9 成。
   同时附建 raw_comments 原文表（docs.body 是分词文本，详情页好评/差评读原文表）。
2. cine/data/lookup_slim.db：poster/rating_count/countries 三个运行时未使用字段置空。
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FTS_DB = ROOT / "data" / "enriched" / "comments_fts.db"
COMMENTS_CSV = ROOT / "data" / "movie_comments.csv"
LOOKUP_SLIM = ROOT / "cine" / "data" / "lookup_slim.db"
TOP_N_PER_MOVIE = 15


def slim_fts() -> None:
    src = sqlite3.connect(str(FTS_DB))
    rows = src.execute(
        "SELECT movie_id, body, cid, category, star, votes FROM docs ORDER BY movie_id, votes DESC"
    ).fetchall()
    src.close()
    kept, seen = [], {}
    for movie_id, *rest in rows:
        n = seen.get(movie_id, 0)
        if n >= TOP_N_PER_MOVIE:
            continue
        seen[movie_id] = n + 1
        kept.append((movie_id, *rest))
    FTS_DB.unlink()
    dst = sqlite3.connect(str(FTS_DB))
    dst.execute("CREATE VIRTUAL TABLE docs USING fts5("
                "body, cid UNINDEXED, movie_id UNINDEXED, category UNINDEXED,"
                " star UNINDEXED, votes UNINDEXED)")
    dst.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)",
                    [(body, cid, movie_id, category, star, votes)
                     for movie_id, body, cid, category, star, votes in kept])
    _build_raw_table(dst)
    dst.commit()
    dst.execute("VACUUM")
    dst.close()
    print(f"comments_fts.db: {len(rows)} -> {len(kept)} 条（每部 Top{TOP_N_PER_MOVIE}），"
          f"新大小 {FTS_DB.stat().st_size / 1e6:.1f} MB")


def _build_raw_table(con: sqlite3.Connection) -> None:
    """从 CSV 附建高赞评论原文表（详情页好评/差评展示用，含作者）。"""
    if not COMMENTS_CSV.exists():
        print("raw_comments: CSV 缺失，跳过（详情页将退回分词文本）")
        return
    con.execute("DROP TABLE IF EXISTS raw_comments")
    con.execute("CREATE TABLE raw_comments("
                "cid TEXT PRIMARY KEY, movie_id TEXT, star INTEGER, votes INTEGER,"
                " author TEXT, text TEXT)")
    seen: dict[str, list[tuple]] = {}
    with open(COMMENTS_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            seen.setdefault(r["movie_id"], []).append(
                (int(r["votes"] or 0), r["comment_id"], int(r["star"] or 0),
                 (r.get("author") or "")[:30], (r.get("content") or "")[:400]))
    for mid, rows in seen.items():   # CSV 内票数非严格降序，按票数取每部 Top-N
        rows.sort(key=lambda x: -x[0])
        up = [r for r in rows if r[2] >= 4][:10]                 # 好评 Top10
        dn = [r for r in rows if r[2] <= 2][:5]                  # 差评 Top5（防止被好评挤掉）
        for votes, cid, star, author, text in up + dn:
            con.execute("INSERT OR IGNORE INTO raw_comments VALUES (?,?,?,?,?,?)",
                        (cid, mid, star, votes, author, text))
    n = con.execute("SELECT count(*) FROM raw_comments").fetchone()[0]
    print(f"raw_comments: {n} 条原文（每部按票数 Top{TOP_N_PER_MOVIE}）")


def slim_lookup() -> None:
    src = sqlite3.connect(str(LOOKUP_SLIM))
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT title, title_norm, year, genres, countries, rating,"
                       " rating_count, summary, poster FROM movies").fetchall()
    src.close()
    LOOKUP_SLIM.unlink()
    dst = sqlite3.connect(str(LOOKUP_SLIM))
    dst.execute("""CREATE TABLE movies(
        title TEXT, title_norm TEXT PRIMARY KEY, year TEXT, genres TEXT, countries TEXT,
        rating TEXT, rating_count TEXT, summary TEXT, poster TEXT)""")
    dst.executemany(
        "INSERT INTO movies VALUES(?,?,?,?,?,?,?,?,?)",
        [(r["title"], r["title_norm"], r["year"], r["genres"], "",
          r["rating"], "", r["summary"], "") for r in rows])
    dst.commit()
    dst.execute("VACUUM")
    dst.close()
    print(f"lookup_slim.db: {len(rows)} 行，新大小 {LOOKUP_SLIM.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    slim_fts()
    slim_lookup()
