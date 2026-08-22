# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · 数据层
启动时加载 movies_core.json / similarity.json / comments_fts.db / sentiment.json（只读），
并从 movies_info_clean.csv 预建"库外电影"轻索引（platform/data/lookup.db，首次约 10-15s）。
"""
from __future__ import annotations
import json
import math
import re
import sqlite3
import threading
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent          # 项目根
ENRICHED = BASE / "data" / "enriched"
INFO_CSV = BASE / "data" / "movies_info_clean.csv"
LOOKUP_DB = Path(__file__).resolve().parent / "data" / "lookup.db"
FTS_DB = ENRICHED / "comments_fts.db"
CORE_JSON = ENRICHED / "movies_core.json"
SIMILAR_JSON = ENRICHED / "similarity.json"
SENTIMENT_JSON = ENRICHED / "sentiment.json"

_core: list[dict] = []
_by_id: dict[str, dict] = {}
_similar: dict[str, list[str]] = {}
_lookup_rows: list[dict] = []      # 库外电影轻行（title_norm 归一化）
_ext_rows: list[dict] = []          # 库外精选星球（评分≥6.0、去重、按热度截取）
_ext_by_id: dict[str, dict] = {}
_sentiment: dict[str, dict] = {}
_comments_by_movie: dict[str, list[dict]] = {}   # {movie_id: [{cid,text,votes,star,author},...]} 预加载短评索引
_fts_local = threading.local()                    # 每线程一只读 FTS 连接（避免跨线程共用）

EXT_LIMIT = 4410                    # 库外星球数：590 核心 + 4410 库外 = 5000 颗

# 标题归一化：去空白/标点/括号后缀，小写
_NORM_PAT = re.compile(r"[\s:：·,.!?。！？、'’\"“”（）()【】\[\]\-—～~×/|《》]+")
def norm_title(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"\([^)]*\)$", "", str(s).strip())   # 去尾部括号（如 霸王别姬(1993)）
    return _NORM_PAT.sub("", s).lower()


def load():
    global _core, _by_id, _similar, _lookup_rows, _sentiment
    _core = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    # 地区严谨化（六分组：中国/日本/韩国/欧洲/美国/其他）：
    # 旧口径把全部西方国家笼统记为「欧美」、非西方国家兜底进「欧美」。
    # 按 countries 第一制片国重判：欧美拆分为 美国/欧洲/其他；华语统一改称中国。
    # （华语/日本/韩国的人工口径与 countries 完全一致，直接重命名。）
    for m in _core:
        r = m.get("region")
        if r == "欧美":
            nr = _region_of(m.get("countries") or [])
            m["region"] = nr if nr in ("美国", "欧洲", "其他") else "欧洲"
        elif r == "华语":
            m["region"] = "中国"
    _by_id = {m["movie_id"]: m for m in _core}
    _similar = json.loads(SIMILAR_JSON.read_text(encoding="utf-8"))
    _load_lookup()
    _build_ext()
    _load_comments_index()
    try:
        _sentiment = json.loads(SENTIMENT_JSON.read_text(encoding="utf-8"))
    except Exception:
        _sentiment = {}


def _load_lookup():
    """库外电影轻索引：lookup.db 已建则直接读，否则从 CSV 一次性构建。"""
    global _lookup_rows
    if LOOKUP_DB.exists():
        con = sqlite3.connect(str(LOOKUP_DB))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT title, title_norm, year, genres, countries, rating, rating_count, summary, poster "
            "FROM movies").fetchall()
        con.close()
        _lookup_rows = [dict(r) for r in rows]
        return
    if not INFO_CSV.exists():
        _lookup_rows = []
        return
    LOOKUP_DB.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INFO_CSV, dtype=str).fillna("")
    con = sqlite3.connect(str(LOOKUP_DB))
    con.execute("DROP TABLE IF EXISTS movies")
    con.execute("""CREATE TABLE movies(
        title TEXT, title_norm TEXT PRIMARY KEY, year TEXT, genres TEXT, countries TEXT,
        rating TEXT, rating_count TEXT, summary TEXT, poster TEXT)""")
    seen: dict[str, dict] = {}
    for d in df.to_dict("records"):
        title = str(d["片名"]).strip()
        if not title:
            continue
        tn = norm_title(title)
        if not tn or tn in seen:
            continue
        seen[tn] = dict(title=title, title_norm=tn, year=str(d["年份"]).strip(),
                        genres=str(d["类型"]).strip(), countries=str(d["制片国家/地区"]).strip(),
                        rating=str(d["豆瓣评分"]).strip(), rating_count=str(d["评价人数"]).strip(),
                        summary=str(d["剧情简介"]).strip(), poster=str(d["海报URL"]).strip())
    con.executemany(
        "INSERT OR IGNORE INTO movies VALUES(:title,:title_norm,:year,:genres,:countries,:rating,:rating_count,:summary,:poster)",
        list(seen.values()))
    con.commit()
    con.close()
    _lookup_rows = list(seen.values())


def core() -> list[dict]:
    return _core

def _build_ext():
    """库外精选星球：评分≥6.0，与核心 590 部按片名首词去重，
    按评分→评价人数降序取前 EXT_LIMIT 部，编号 x00001…（确定性）。"""
    global _ext_rows, _ext_by_id
    core_first = {norm_title((m.get("title") or "").split()[0]) for m in _core if m.get("title")}
    cands = []
    for d in _lookup_rows:
        try:
            rating = float(d["rating"])
        except (TypeError, ValueError):
            continue
        if rating < 6.0:
            continue
        if norm_title(d["title"].split()[0]) in core_first:
            continue
        try:
            rc = int(float(d["rating_count"] or 0))
        except ValueError:
            rc = 0
        cands.append((rating, rc, d))
    cands.sort(key=lambda x: (-x[0], -x[1]))
    _ext_rows, _ext_by_id = [], {}
    for i, (rating, rc, d) in enumerate(cands[:EXT_LIMIT]):
        eid = f"x{i + 1:05d}"
        row = dict(d)
        row["ext_id"] = eid
        row["_rating"] = rating
        row["_rc"] = rc
        _ext_rows.append(row)
        _ext_by_id[eid] = row

def ext_movie(ext_id: str) -> dict | None:
    """库外电影详情（基础信息，无 DNA/情绪/引用数据，前端自动降级）。"""
    d = _ext_by_id.get(ext_id)
    if not d:
        return None
    genres = [g.strip() for g in d["genres"].split("/") if g.strip()]
    countries = [c.strip() for c in d["countries"].split("/") if c.strip()]
    try:
        year = int(float(d["year"])) if d["year"] else None
    except ValueError:
        year = None
    poster = d["poster"] if d["poster"].startswith("http") and "dummyimage" not in d["poster"] else ""
    return {
        "movie_id": ext_id, "title": d["title"], "year": year,
        "rating": d["_rating"], "rating_count": d["_rc"],
        "genres": genres, "countries": countries, "region": _region_of(countries),
        "summary": d["summary"], "brief": d["summary"][:80],
        "poster_full": poster, "poster_thumb": poster, "ext": True,
    }

# 欧洲白名单：欧洲各国 + 加拿大/澳新（广义西方英语国家，数量极少，并入欧洲口径）
_EURO_KWS = (
    "英国", "爱尔兰", "法国", "德国", "西德", "东德", "意大利", "西班牙", "葡萄牙",
    "荷兰", "比利时", "卢森堡", "瑞士", "奥地利", "瑞典", "挪威", "丹麦", "芬兰", "冰岛",
    "波兰", "捷克", "斯洛伐克", "匈牙利", "希腊", "克罗地亚", "南斯拉夫", "塞尔维亚", "斯洛文尼亚",
    "罗马尼亚", "保加利亚", "阿尔巴尼亚", "乌克兰", "白俄罗斯", "摩尔多瓦", "爱沙尼亚", "拉脱维亚",
    "立陶宛", "马耳他", "加拿大", "澳大利亚", "新西兰",
)

def _region_of(countries: list[str]) -> str:
    """地区判定（按第一制片国）：中国(含港澳台) > 日本 > 韩国 > 美国 > 欧洲 > 其他。
    第一制片国不在已知范围（如苏联/俄罗斯/印度/泰国/巴西）即归「其他」，
    不向后扫合拍国，避免非西方主导的合拍片被并入欧美；countries 为空同样归「其他」。"""
    cs = [c for c in (countries or []) if c and str(c).strip()]
    if not cs:
        return "其他"
    first = str(cs[0])
    if any(k in first for k in ("中国", "香港", "台湾")):
        return "中国"
    if "日本" in first:
        return "日本"
    if "韩国" in first:
        return "韩国"
    if "美国" in first:
        return "美国"
    if any(k in first for k in _EURO_KWS):
        return "欧洲"
    return "其他"

def movie(movie_id: str) -> dict | None:
    return _by_id.get(movie_id)

def all_movies() -> list[dict]:
    return list(_by_id.values())

def similar(movie_id: str) -> list[str]:
    return _similar.get(movie_id, [])

def fts() -> sqlite3.Connection | None:
    """线程专属只读 FTS 连接（每线程惰性建一次，避免跨线程共用同一连接）。"""
    if not FTS_DB.exists():
        return None
    con = getattr(_fts_local, "con", None)
    if con is None:
        con = sqlite3.connect(str(FTS_DB), check_same_thread=False)
        con.execute("PRAGMA query_only=1")
        con.row_factory = sqlite3.Row
        _fts_local.con = con
    return con

def lookup_rows() -> list[dict]:
    return _lookup_rows


def comments_indexed() -> bool:
    """短评索引是否可用（启动体检用）。"""
    return bool(_comments_by_movie)


# ---------------- 观众情绪 / 电影银河 ----------------
_COLD = (88, 118, 255)      # 冷：蓝紫
_WARM = (255, 190, 90)      # 暖：金

def sentiment(movie_id: str) -> dict:
    return _sentiment.get(movie_id) or {}


def _load_comments_index():
    """预加载短评原文索引 {movie_id: [{cid,text,votes,star,author}, ...]}，
    top_comments 直接内存取用（避免每次详情请求重读 30MB CSV）。"""
    global _comments_by_movie
    csv_path = BASE / "data" / "movie_comments.csv"
    if not csv_path.exists():
        _comments_by_movie = {}
        return
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str).fillna("")
    votes = pd.to_numeric(df["votes"], errors="coerce").fillna(0).astype(int).tolist()
    stars = pd.to_numeric(df["star"], errors="coerce").fillna(0).astype(int).tolist()
    mids, cids = df["movie_id"].tolist(), df["comment_id"].tolist()
    texts, authors = df["content"].tolist(), df["author"].tolist()
    idx: dict[str, list[dict]] = {}
    for i, mid in enumerate(mids):
        row = idx.get(mid)
        if row is None:
            row = []
            idx[mid] = row
        row.append({
            "cid": str(cids[i]),
            "text": (texts[i] or "")[:200],
            "votes": votes[i],
            "star": stars[i],
            "author": authors[i] or "",
        })
    _comments_by_movie = idx


def top_comments(movie_id: str, limit: int = 3) -> dict:
    """获取指定电影的好评/差评各 limit 条（按 votes 降序）。
    返回 {"up": [...], "dn": [...]}，每条含 cid/text/votes/star/author。
    数据来自启动时预加载的短评索引（不再每次请求重读 CSV）。"""
    comments = _comments_by_movie.get(movie_id)
    if not comments:
        return {"up": [], "dn": []}
    up = sorted((c for c in comments if c["star"] >= 4), key=lambda c: -c["votes"])[:limit]
    dn = sorted((c for c in comments if c["star"] <= 2), key=lambda c: -c["votes"])[:limit]
    if not up and not dn:
        return {"up": [], "dn": []}
    return {"up": up, "dn": dn}

def galaxy_rows() -> list[dict]:
    """590 颗电影星球：大小(评分+热度+评论数综合权重)、亮度(log 评价人数)、
    颜色(情绪温度百分位→冷暖渐变)。全部确定性计算，前端只管渲染。"""
    ws = []
    for m in _core:
        rc = m.get("rating_count") or 0
        ctotal = (m.get("stats") or {}).get("comments_total") or 0
        ws.append((m.get("rating") or 0) * 0.5 + math.log10(max(rc, 1)) * 0.4
                  + math.log10(max(ctotal, 1)) * 0.1)
    wmin, wmax = min(ws), max(ws)
    brs = sorted(math.log10(max(m.get("rating_count") or 0, 1)) for m in _core)
    bmin, bmax = brs[0], brs[-1]
    rows = []
    for m, w in zip(_core, ws):
        s = _sentiment.get(m["movie_id"]) or {}
        t = (w - wmin) / (wmax - wmin)                      # 0-1 权重
        radius = round(0.5 + 1.7 * t, 3)                    # 0.5 ~ 2.2
        b = (math.log10(max(m.get("rating_count") or 0, 1)) - bmin) / (bmax - bmin)
        brightness = round(0.3 + 0.7 * b, 3)                # 0.3 ~ 1.0
        temp = (s.get("temp") or 50) / 100.0
        r = round(_COLD[0] + (_WARM[0] - _COLD[0]) * temp)
        g = round(_COLD[1] + (_WARM[1] - _COLD[1]) * temp)
        bl = round(_COLD[2] + (_WARM[2] - _COLD[2]) * temp)
        rows.append({
            "id": m["movie_id"], "t": m["title"], "y": m["year"], "rating": m["rating"],
            "region": m["region"], "genres": (m["genres"] or [])[:3],
            "r": radius, "b": brightness, "c": f"#{r:02x}{g:02x}{bl:02x}",
            "temp": s.get("temp") or 50, "rc": m.get("rating_count") or 0,
            "p": m.get("poster_thumb") or None, "k": 1.0,
        })
    # 库外精选星球：稍暗稍小（k=0.55 亮度系数，半径口径 0.5~1.1）
    for d in _ext_rows:
        rating, rc = d["_rating"], d["_rc"]
        countries = [c.strip() for c in d["countries"].split("/") if c.strip()]
        try:
            year = int(float(d["year"])) if d["year"] else None
        except ValueError:
            year = None
        rows.append({
            "id": d["ext_id"], "t": d["title"], "y": year, "rating": rating,
            "region": _region_of(countries),
            "genres": [g.strip() for g in d["genres"].split("/") if g.strip()][:3],
            "r": round(0.5 + min(1.0, max(rating - 6.0, 0.0) / 4.0) * 0.6, 3),
            "b": 0.3, "c": "#cfd6e8",
            "temp": 50, "rc": rc, "p": None, "k": 0.55, "ext": 1,
        })
    return rows
