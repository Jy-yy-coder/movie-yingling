# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · 检索层（FTS 短评 + 标题模糊 + 联想）"""
from __future__ import annotations
import logging
import re

from . import data

log = logging.getLogger("cine.search")
_NORM = data.norm_title


def _bigrams(s: str):
    return [s[i:i + 2] for i in range(len(s) - 1)]


def search_titles(q: str, limit=8):
    """590 库内标题模糊匹配（归一化后包含匹配，含简繁）。"""
    qn = _NORM(q)
    if not qn:
        return []
    hits = []
    for m in data.all_movies():
        tn = _NORM(m["title"])
        if tn == qn:
            return [m]
        if qn in tn:
            hits.append(m)
            if len(hits) >= limit:
                break
    return hits


def search_fts(q: str, limit=20):
    """短评全文检索。中文按双字 bigram 构造 AND 查询近似子串匹配。"""
    qn = _NORM(q)
    if not qn or len(qn) < 2:
        return []
    con = data.fts()
    if con is None:
        return []
    # 英文/单 token 直接短语匹配；中文用全部 2 字窗口 AND
    if re.fullmatch(r"[a-z0-9 ]+", qn):
        query = f'"{qn}"'
    else:
        grams = _bigrams(qn)
        query = " AND ".join(f'"{g}"' for g in grams)
    try:
        cur = con.execute(
            "SELECT cid, movie_id, votes, snippet(docs, 0, '', '', '…', 16) AS snip "
            "FROM docs WHERE docs MATCH ? ORDER BY votes DESC LIMIT ?",
            (query, limit))
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        log.warning("FTS 检索失败 q=%r query=%r: %s", q, query, str(e)[:120])
        return []
    # 按电影聚合，取每片最高票的一条
    by_mid: dict[str, dict] = {}
    for r in rows:
        if r["movie_id"] not in by_mid:
            by_mid[r["movie_id"]] = r
    out = []
    for r in sorted(by_mid.values(), key=lambda x: -x["votes"]):
        m = data.movie(r["movie_id"])
        out.append({**r, "title": m["title"] if m else "", "year": m["year"] if m else None})
        if len(out) >= 12:
            break
    return out


def suggest(q: str, limit=8):
    """标题联想（590 库 + 库外库前缀匹配）。"""
    qn = _NORM(q)
    if not qn:
        return []
    res = []
    for m in data.all_movies():
        if _NORM(m["title"]).startswith(qn):
            res.append({"type": "core", "title": m["title"], "movie_id": m["movie_id"], "year": m["year"]})
            if len(res) >= limit:
                return res
    for r in data.lookup_rows():
        if r["title_norm"].startswith(qn):
            res.append({"type": "ext", "title": r["title"], "year": r["year"]})
            if len(res) >= limit:
                return res
    return res


def resolve_title(name: str, allow_weak: bool = True):
    """把一句话里的电影名解析到 590 库内或库外电影（聊天用）。
    豆瓣标题常带外文后缀（如「千与千寻 千と千尋の神隠し」），故同时按"主名"（空格前段）匹配。
    匹配强度分级：精确 > 前向包含（输入是标题子串）> 弱反向包含（句子含完整片名）。
    allow_weak=False 时关闭弱反向包含——口语推荐句（如「活着好累想看治愈的」）不再被
    2~3 字短标题（《活着》《过年》）劫持成单片问答。"""
    nn = _NORM(name)
    if not nn:
        return (None, None)
    # 《》显式引用优先：书名号内的名字按精确/前向匹配
    qm = re.search(r"[《<]([^》>]{1,30})[》>]", name)
    if qm:
        qn = _NORM(qm.group(1))
        if qn:
            for m in data.all_movies():
                tn = _NORM(m["title"])
                sn = _NORM(m["title"].split(" ", 1)[0])
                if qn == tn or qn == sn or qn in tn:
                    return ("core", m)
    ms = data.all_movies()
    # 第一遍：精确匹配（整名或主名）
    for m in ms:
        tn = _NORM(m["title"])
        sn = _NORM(m["title"].split(" ", 1)[0])
        if nn == tn or nn == sn:
            return ("core", m)
    # 第二遍：前向包含（输入 ⊂ 标题）
    for m in ms:
        tn = _NORM(m["title"])
        sn = _NORM(m["title"].split(" ", 1)[0])
        if (nn in tn or nn in sn) and nn:
            return ("core", m)
    # 第三遍：弱反向包含（句子 ⊃ 完整片名），仅 ≥3 字标题且显式允许
    if allow_weak:
        for m in ms:
            tn = _NORM(m["title"])
            sn = _NORM(m["title"].split(" ", 1)[0])
            if (len(tn) >= 3 and tn in nn) or (len(sn) >= 3 and sn in nn):
                return ("core", m)
    # 库外
    for r in data.lookup_rows():
        if nn == r["title_norm"]:
            return ("ext", r)
    return (None, None)
