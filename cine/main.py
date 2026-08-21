# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · FastAPI 入口
启动：python -m uvicorn platform.main:app --port 8000
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import chat as chat_mod
from . import data, personality, recommend, search

app = FastAPI(title="影灵 CINE", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = Path(__file__).resolve().parent / "web" / "dist"   # 电影宇宙前端构建产物
WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
# 电影宇宙前端构建产物存在时优先托管（旧 static 备份于 static_legacy）
if (WEB_DIST / "index.html").exists():
    STATIC_DIR = WEB_DIST
DB_PATH = Path(__file__).resolve().parent / "data" / "cine.db"

# ---------------- 启动 ----------------
@app.on_event("startup")
def _startup():
    data.load()
    _init_db()

def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def _init_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE, pass_hash TEXT, device_id TEXT,
            token TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sms_codes(
            phone TEXT, code TEXT, expires_at REAL);
        CREATE TABLE IF NOT EXISTS favorites(
            user_id INTEGER, movie_id TEXT, created_at TEXT,
            PRIMARY KEY(user_id, movie_id));
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT,
            content TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id TEXT,
            mode TEXT DEFAULT 'rec',
            title TEXT,
            created_at TEXT,
            updated_at TEXT);
        CREATE TABLE IF NOT EXISTS conversation_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            movie_ids TEXT,
            created_at TEXT,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id));
        CREATE TABLE IF NOT EXISTS user_personality(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dna TEXT NOT NULL,
            keywords TEXT,
            quiz_dims TEXT,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS user_signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT);
    """)
    con.close()

def _token(uid, phone):
    raw = hashlib.md5(f"{uid}|{phone}|{time.time()}".encode()).hexdigest()[:24]
    return raw

# ---------------- 电影 API ----------------
@app.get("/api/movies")
def api_movies(region: str = "", genre: str = "", year_min: int = 0, year_max: int = 0,
               dim: str = "", dim_min: float = 0, sort: str = "dna", q: str = "",
               page: int = 1, limit: int = 24):
    if q:
        # 搜索：标题/类型/导演/演员 归一化包含匹配
        qn = data.norm_title(q)
        rows = [m for m in data.all_movies()
                if qn and (qn in data.norm_title(m["title"])
                           or any(qn in g for g in m["genres"])
                           or any(qn in d for d in (m.get("director") or []))
                           or any(qn in a for a in (m.get("actors") or [])))]
        # 无匹配时保持空结果，前端显示「暂无推荐」（不拿规则推荐兜底，避免搜什么都有结果）
    else:
        rows = recommend.recommend(text=q, region=region or None, genre=genre or None,
                                   dim=dim or None, limit=100000)
    rows = [m for m in rows
            if (not region or m["region"] == region)
            and (not genre or any(genre == g for g in m["genres"]))
            and (not year_min or (m["year"] or 0) >= year_min)
            and (not year_max or (m["year"] or 0) <= year_max)
            and (not dim_min or (m["dna"].get(dim, 0) if dim else 0) >= dim_min)]
    if sort == "rating":
        rows.sort(key=lambda m: -m["rating"])
    elif sort in recommend.DNA_DIMS:
        rows.sort(key=lambda m: -(m["dna"].get(sort, 0) or 0))
    else:
        rows.sort(key=lambda m: -(sum(m["dna"][k] for k in recommend.DNA_DIMS) / 5))
    total = len(rows)
    start = (page - 1) * limit
    items = [card(m) for m in rows[start:start + limit]]
    return {"total": total, "page": page, "limit": limit, "items": items}

@app.get("/api/movies/{movie_id}")
def api_movie(movie_id: str):
    m = data.movie(movie_id)
    if m:
        result = {**card(m), "similar": [card(data.movie(s)) for s in data.similar(movie_id) if data.movie(s)],
                "sentiment": data.sentiment(movie_id) or None}
        # 添加好评/差评各 3 条
        top_c = data.top_comments(movie_id, limit=3)
        result["top_comments"] = top_c
        return result
    ext = data.ext_movie(movie_id)
    if ext:
        return ext   # 库外电影：基础信息，无 DNA/情绪/引用，前端自动降级
    raise HTTPException(404, "movie not found")

@app.get("/api/galaxy")
def api_galaxy():
    """电影星球：590 核心 + 库外精选，大小/亮度/颜色/情绪温度，前端只渲染。"""
    rows = data.galaxy_rows()
    return {"total": len(rows), "planets": rows}

def _card_any(movie_id: str):
    """核心片返回完整卡片，库外片返回基础信息，找不到返回 None。"""
    m = data.movie(movie_id)
    if m:
        return card(m)
    return data.ext_movie(movie_id)

def card(m):
    d = m["dna"]
    return {
        "movie_id": m["movie_id"], "title": m["title"], "year": m["year"],
        "genres": m["genres"], "region": m["region"], "countries": m["countries"],
        "languages": m["languages"], "director": m["director"], "writer": m["writer"],
        "actors": m["actors"], "runtime_min": m["runtime_min"], "rating": m["rating"],
        "rating_count": m["rating_count"], "summary": m["summary"], "brief": m["brief"],
        "poster_thumb": "/" + m["poster_thumb"] if m.get("poster_thumb") else None,
        "poster_full": "/" + m["poster_full"] if m.get("poster_full") else None,
        "dna": d, "tags": m.get("tags"), "quotes": m.get("quotes"),
        "warn": m.get("warn"), "egg": m.get("egg"), "stats": m.get("stats"),
        "source_channel": m.get("source_channel"), "build_version": m.get("build_version"),
    }

@app.get("/api/search")
def api_search(q: str = "", type: str = "all", limit: int = 12):
    res = {"titles": [], "fts": []}
    if type in ("all", "title") and q:
        res["titles"] = [{"movie_id": m["movie_id"], "title": m["title"], "year": m["year"],
                          "rating": m["rating"], "region": m["region"],
                          "poster_thumb": "/" + m["poster_thumb"] if m.get("poster_thumb") else None}
                         for m in search.search_titles(q, 8)]
    if type in ("all", "fts") and q:
        res["fts"] = search.search_fts(q, limit)
    return res

@app.get("/api/suggest")
def api_suggest(q: str = ""):
    return {"items": search.suggest(q) if q else []}

@app.get("/api/movie-lookup")
def api_lookup(title: str = ""):
    kind, m = search.resolve_title(title)
    if not m:
        raise HTTPException(404, "not found")
    if kind == "core":
        return {"type": "core", "title": m["title"], "year": m["year"], "rating": m["rating"],
                "genres": m["genres"], "summary": m["summary"], "movie_id": m["movie_id"]}
    return {"type": "ext", "title": m["title"], "year": m["year"], "rating": m["rating"],
            "genres": m["genres"], "summary": m["summary"]}

# ---------------- 聊天 API ----------------
class ChatIn(BaseModel):
    message: str
    device_id: str = "guest"
    mode: str = "rec"        # rec 推荐选片 / talk 陪看讨论
    spoiler: bool = True     # 无剧透开关
    conversation_id: int | None = None   # 会话 ID（可选，不传则自动创建）
    movie_id: str | None = None          # 当前讨论电影（从详情页带入）


def _create_conversation(uid: int, movie_id: str | None, mode: str, title: str) -> int:
    """创建新会话，返回 conversation_id。"""
    con = _conn()
    now = time.strftime("%F %T")
    cur = con.execute(
        "INSERT INTO conversations(user_id, movie_id, mode, title, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?)",
        (uid, movie_id, mode, title[:100], now, now))
    cid = cur.lastrowid
    con.commit(); con.close()
    return cid


def _conversation_owned(conversation_id: int, uid: int) -> bool:
    """校验会话是否属于当前用户（防止越权读写他人会话）。"""
    con = _conn()
    row = con.execute("SELECT 1 FROM conversations WHERE id=? AND user_id=?",
                      (conversation_id, uid)).fetchone()
    con.close()
    return row is not None


def _load_conversation_history(conversation_id: int, uid: int, limit: int = 24) -> list[dict]:
    """从 conversation_messages 表取当前会话最近消息（窗口放宽，支撑多轮推荐排重与上下文）。
    仅返回本人会话的历史，非本人会话一律视为无历史。"""
    if not conversation_id or not _conversation_owned(conversation_id, uid):
        return []
    try:
        con = _conn()
        rows = con.execute(
            "SELECT role, content, movie_ids FROM conversation_messages "
            "WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit)).fetchall()
        con.close()
        return [{"role": r[0], "content": r[1], "movie_ids": r[2]} for r in reversed(rows)]
    except Exception as e:
        import logging
        logging.getLogger("cine.chat").warning(f"加载会话历史失败: {e}")
        return []


def _load_movie_context(movie_id: str | None) -> dict | None:
    """加载电影上下文，供 Prompt 注入。"""
    if not movie_id:
        return None
    m = data.movie(movie_id)
    if not m:
        return None
    d = m["dna"]
    dims = " ".join(f"{k}{d[k]}" for k in recommend.DNA_DIMS)
    lines = [
        f"【当前讨论电影】",
        f"《{m['title']}》({m['year']}) 豆瓣 {m['rating']}",
    ]
    if m.get("director"):
        lines.append(f"导演：{' / '.join(m['director'])}")
    if m.get("actors"):
        lines.append(f"主演：{' / '.join(m['actors'][:4])}")
    if m.get("genres"):
        lines.append(f"类型：{' / '.join(m['genres'])} | 地区：{m['region']}")
    if m.get("summary"):
        lines.append(f"简介：{m['summary'][:120]}")
    lines.append(f"DNA：{dims}")
    # 好评
    up = (m.get("quotes") or {}).get("up1")
    if up:
        lines.append(f"好评：「{up['text'][:40]}」")
    # 差评预警
    warn = m.get("warn")
    if warn:
        lines.append(f"差评预警：{warn['text'][:60]}")
    return {"movie_id": movie_id, "prompt_text": "\n".join(lines), "data": m}


def _save_conversation_message(conversation_id: int, role: str, content: str, movie_ids: str | None = None):
    """保存消息到 conversation_messages 表。"""
    con = _conn()
    now = time.strftime("%F %T")
    con.execute(
        "INSERT INTO conversation_messages(conversation_id, role, content, movie_ids, created_at) "
        "VALUES(?,?,?,?,?)",
        (conversation_id, role, content[:2000], movie_ids, now))
    con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
    con.commit(); con.close()


@app.post("/api/chat")
def api_chat(body: ChatIn):
    uid = _resolve_user_id(body.device_id)

    # 会话管理：有 conversation_id 则用（校验归属，防越权读写他人会话），否则创建新会话
    conv_id = body.conversation_id
    if conv_id:
        if not _conversation_owned(conv_id, uid):
            raise HTTPException(404, "会话不存在")
    else:
        title = body.message[:50] if body.message else "新对话"
        conv_id = _create_conversation(uid, body.movie_id, body.mode, title)

    # 加载历史与电影上下文（movie_id 漏传时回落到会话绑定的电影）
    history = _load_conversation_history(conv_id, uid)
    movie_id = body.movie_id
    if not movie_id and conv_id:
        row = _conn().execute("SELECT movie_id FROM conversations WHERE id=?", (conv_id,)).fetchone()
        movie_id = row[0] if row else None
    movie_ctx = _load_movie_context(movie_id)

    # 加载人格画像（有则用于推荐候选重排，无则行为不变）
    user_profile = None
    prow = _personality_row(uid)
    if prow:
        try:
            user_profile = json.loads(prow[0])
        except (ValueError, TypeError):
            user_profile = None
    # B4：行为反馈隐式画像并入（收藏/浏览/点卡/换片信号逐步拉动画像）
    impl = _implicit_profile(uid)
    like_genres = None
    if impl:
        user_profile = _merge_profiles(user_profile, impl)
        like_genres = _signal_genres(uid)     # 类型亲和（供推荐微调，让效果可见）

    # 调用聊天层
    reply = chat_mod.build_reply(
        body.message, mode=body.mode, spoiler=body.spoiler,
        history=history, movie_context=movie_ctx, user_profile=user_profile,
        like_genres=like_genres)

    # 推荐解释：推荐卡始终附结构化解释（有画像用画像版，无画像退化为影片自身数据版）
    kws = json.loads(prow[1]) if (prow and prow[1]) else []
    for c in (reply.get("movies") or []) + ([reply["movie"]] if reply.get("movie") else []):
        mm = data.movie(c.get("movie_id") or "")
        if mm:
            c["explain"] = recommend.explain_card(mm, user_profile, kws)

    # 会话未绑定电影且本轮命中电影 → 回填，后续消息能持续拿到上下文
    if not movie_id and reply.get("movie_id"):
        con = _conn()
        con.execute("UPDATE conversations SET movie_id=? WHERE id=?", (reply["movie_id"], conv_id))
        con.commit(); con.close()

    # 保存消息到 conversation_messages
    _save_conversation_message(conv_id, "user", body.message)
    # assistant 消息，记录推荐的 movie_ids
    rec_movie_ids = None
    if reply.get("movies"):
        rec_movie_ids = json.dumps([m["movie_id"] for m in reply["movies"]])
    elif reply.get("movie_id"):
        rec_movie_ids = json.dumps([reply["movie_id"]])
    _save_conversation_message(conv_id, "assistant", reply["text"][:2000], rec_movie_ids)

    # 同时写入旧 chats 表（兼容账号页历史展示）
    con = _conn()
    con.execute("INSERT INTO chats(user_id,role,content,created_at) VALUES(?,?,?,?)",
                (uid, "user", body.message[:1000], time.strftime("%F %T")))
    con.execute("INSERT INTO chats(user_id,role,content,created_at) VALUES(?,?,?,?)",
                (uid, "assistant", reply["text"][:2000], time.strftime("%F %T")))
    con.commit(); con.close()

    # 返回结果，附带 conversation_id
    reply["conversation_id"] = conv_id
    return reply

def _resolve_user_id(device_id):
    con = _conn()
    # 同 device_id 可能出现游客行 + 注册行并存：优先取已注册（有手机号）的行
    row = con.execute("SELECT id FROM users WHERE device_id=? "
                      "ORDER BY (phone IS NOT NULL) DESC, id", (device_id,)).fetchone()
    if row:
        uid = row[0]
    else:
        cur = con.execute("INSERT INTO users(device_id,token,created_at) VALUES(?,?,?)",
                          (device_id, _token(0, device_id), time.strftime("%F %T")))
        uid = cur.lastrowid
    con.commit(); con.close()
    return uid

# ---------------- 探索档案（等级/徽章） ----------------
LEVELS = [("Lv.5", "银河领主", 60), ("Lv.4", "宇宙收藏家", 30), ("Lv.3", "星系开拓者", 15),
          ("Lv.2", "星河漫游者", 5), ("Lv.1", "电影旅人", 0)]

def _level(n):
    for tag, name, th in LEVELS:
        if n >= th:
            return {"tag": tag, "name": name, "threshold": th}
    return {"tag": "Lv.1", "name": "电影旅人", "threshold": 0}

def _badges(movies):
    regions = [m["region"] for m in movies]
    genres = [g for m in movies for g in (m["genres"] or [])]
    years = [m["year"] or 0 for m in movies]
    east = sum(1 for r in regions if r in ("华语", "日本", "韩国"))
    got = []
    add = lambda key, name, icon, desc: got.append({"key": key, "name": name, "icon": icon, "desc": desc})
    if movies:
        add("traveler", "初入银河", "🌌", "收藏了第一部电影")
    if east >= 3:
        add("east", "东方电影探索者", "🏮", "收藏华语 / 日韩电影 ≥ 3 部")
    if regions.count("日本") >= 3:
        add("jp", "日本治愈收藏家", "🌸", "收藏日本电影 ≥ 3 部")
    if regions.count("韩国") >= 2:
        add("kr", "韩国品鉴师", "🎭", "收藏韩国电影 ≥ 2 部")
    if regions.count("欧美") >= 5:
        add("west", "欧美经典漫游者", "🏛️", "收藏欧美电影 ≥ 5 部")
    if sum(1 for y in years if 0 < y <= 1990) >= 3:
        add("classic", "影史深度党", "🎞️", "收藏 1990 年前经典 ≥ 3 部")
    if sum(1 for g in genres if g in ("科幻", "奇幻", "动作")) >= 3:
        add("vfx", "视觉大片收藏家", "🚀", "收藏科幻 / 奇幻 / 动作 ≥ 3 部")
    if len(set(regions)) >= 3:
        add("galaxy", "跨域漫游者", "✨", "足迹覆盖 3 个星域")
    if len(movies) >= 30:
        add("lord", "银河征服者", "👑", "收藏 30 部以上")
    return got

@app.get("/api/explorer")
def api_explorer(token: str = ""):
    con = _conn()
    row = con.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
    if not row:
        con.close(); raise HTTPException(401, "未登录")
    favs = [r[0] for r in con.execute(
        "SELECT movie_id FROM favorites WHERE user_id=? ORDER BY created_at DESC", (row[0],)).fetchall()]
    con.close()
    movies = [data.movie(f) for f in favs if data.movie(f)]
    n = len(movies)
    return {"total": len(data.core()), "discovered": n, "progress": round(n / max(len(data.core()), 1) * 100, 1),
            "level": _level(n), "badges": _badges(movies),
            "favorites": [c for c in (_card_any(f) for f in favs) if c]}

# ---------------- 电影人格测试 ----------------
class PersonalityIn(BaseModel):
    answers: list[dict]            # [{q: 题号, o: 选项号}, ...]
    device_id: str = "guest"


def _personality_result(dna: dict, keywords: list[str], created_at: str | None = None) -> dict:
    """组装人格画像返回体：DNA + 关键词 + 按画像推荐的电影卡（附推荐解释）。"""
    ms = recommend.recommend_by_dna_profile(dna, limit=5)
    cards = []
    for m in ms:
        c = chat_mod._rec_card(m)
        c["explain"] = recommend.explain_card(m, dna, keywords)
        cards.append(c)
    return {"dna": dna, "keywords": keywords,
            "movies": cards,
            "created_at": created_at}


@app.get("/api/personality/questions")
def api_personality_questions():
    """下发题库（不含 dim/score/tags，防止前端自行计分）。"""
    return {"questions": [{"q": q["q"], "opts": [{"em": o["em"], "t": o["t"]} for o in q["opts"]]}
                          for q in personality.QUIZ]}


@app.post("/api/personality/test")
def api_personality_test(body: PersonalityIn):
    if not body.answers or len(body.answers) < len(personality.QUIZ):
        raise HTTPException(400, "答案不完整")
    dna = personality.compute_dna(body.answers)
    keywords = personality.collect_keywords(body.answers)
    quiz_dims = personality.accumulate(body.answers)
    # 保存：每用户仅保留最新一份（游客经 device_id 关联）
    uid = _resolve_user_id(body.device_id)
    con = _conn()
    now = time.strftime("%F %T")
    con.execute("DELETE FROM user_personality WHERE user_id=?", (uid,))
    con.execute(
        "INSERT INTO user_personality(user_id,dna,keywords,quiz_dims,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?)",
        (uid, json.dumps(dna, ensure_ascii=False), json.dumps(keywords, ensure_ascii=False),
         json.dumps(quiz_dims), now, now))
    con.commit(); con.close()
    return _personality_result(dna, keywords, created_at=now)


@app.get("/api/personality/profile")
def api_personality_profile(token: str = "", device_id: str = ""):
    """读取已存画像：优先 token，游客回落 device_id。"""
    uid = _personality_uid(token, device_id)
    if uid is None:
        raise HTTPException(404, "尚未完成测试")
    row = _personality_row(uid)
    if not row:
        raise HTTPException(404, "尚未完成测试")
    return _personality_result(json.loads(row[0]), json.loads(row[1] or "[]"), created_at=row[2])


def _personality_uid(token: str, device_id: str):
    """按 token / device_id 解析用户 id（人格画像共用）。"""
    con = _conn()
    uid = None
    if token:
        row = con.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
        if row:
            uid = row[0]
    if uid is None and device_id:
        # 同 device_id 多行时优先取已注册（有手机号）的行，避免游客行残留抢路由
        row = con.execute("SELECT id FROM users WHERE device_id=? "
                          "ORDER BY (phone IS NOT NULL) DESC, id", (device_id,)).fetchone()
        if row:
            uid = row[0]
    con.close()
    return uid


def _personality_row(uid: int):
    con = _conn()
    row = con.execute(
        "SELECT dna, keywords, created_at FROM user_personality "
        "WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    con.close()
    return row


@app.get("/api/personality/route")
def api_personality_route(token: str = "", device_id: str = ""):
    """按已存画像生成四段式 AI 电影探索路线（纯规则模板，无 LLM）。"""
    uid = _personality_uid(token, device_id)
    if uid is None:
        raise HTTPException(404, "尚未完成测试")
    row = _personality_row(uid)
    if not row:
        raise HTTPException(404, "尚未完成测试")
    dna = json.loads(row[0])
    kws = json.loads(row[1]) if row[1] else []
    stages = []
    for i, s in enumerate(recommend.build_route(dna)):
        card = chat_mod._rec_card(s["movie"])
        card["reason"] = s["stage_reason"]          # 阶段化推荐理由替换默认文案
        card["explain"] = recommend.explain_card(s["movie"], dna, kws)
        stages.append({"seq": i + 1, "name": s["name"], "desc": s["desc"], "movie": card})
    return {"dna": dna, "stages": stages}


# ---------------- AI 陪看 ----------------
@app.get("/api/watch/opening")
def api_watch_opening(movie_id: str, spoiler: bool = True):
    """陪看开场话题：LLM 生成 + 模板兜底，附引导 chip 与电影卡。"""
    r = chat_mod.watch_opening(movie_id, spoiler)
    if not r:
        raise HTTPException(404, "电影不存在")
    return r


# ---------------- 账号 API ----------------
class GuestIn(BaseModel):
    device_id: str

@app.post("/api/auth/guest")
def api_guest(body: GuestIn):
    uid = _resolve_user_id(body.device_id)
    con = _conn()
    tok = _token(uid, f"d{body.device_id}")
    con.execute("UPDATE users SET token=? WHERE id=?", (tok, uid))
    con.commit(); con.close()
    return {"token": tok, "device_id": body.device_id, "is_guest": True}

class SmsIn(BaseModel):
    phone: str

@app.post("/api/auth/sms")
def api_sms(body: SmsIn):
    if not re.fullmatch(r"1\d{10}", body.phone):
        raise HTTPException(400, "手机号格式不对")
    code = "246810"   # 演示期固定验证码
    con = _conn()
    con.execute("INSERT OR REPLACE INTO sms_codes(phone,code,expires_at) VALUES(?,?,?)",
                (body.phone, code, time.time() + 600))
    con.commit(); con.close()
    return {"message": "验证码已发送(演示期固定 246810)", "dev_code": code}

class RegisterIn(BaseModel):
    phone: str
    code: str
    password: str
    device_id: str = ""

@app.post("/api/auth/register")
def api_register(body: RegisterIn):
    con = _conn()
    row = con.execute("SELECT code,expires_at FROM sms_codes WHERE phone=?",
                      (body.phone,)).fetchone()
    if not row or row[0] != body.code or row[1] < time.time():
        con.close()
        raise HTTPException(400, "验证码错误或过期")
    if con.execute("SELECT 1 FROM users WHERE phone=?", (body.phone,)).fetchone():
        con.close()
        raise HTTPException(400, "该手机号已注册")
    if len(body.password) < 6:
        con.close()
        raise HTTPException(400, "密码至少 6 位")
    ph = hashlib.sha256(body.password.encode()).hexdigest()
    cur = con.execute("INSERT INTO users(phone,pass_hash,device_id,created_at) VALUES(?,?,?,?)",
                      (body.phone, ph, body.device_id or None, time.strftime("%F %T")))
    uid = cur.lastrowid
    tok = _token(uid, body.phone)
    con.execute("UPDATE users SET token=? WHERE id=?", (tok, uid))
    # 游客历史合并：把 device_id 名下「游客行」（phone IS NULL）的数据并入正式账号
    # （聊天 + 收藏 + 人格 + 行为信号 + 会话），并删除游客行，避免同 device_id 双行
    # 导致后续路由错乱（聊天/人格/信号写到旧游客行）。已注册账号行不受影响。
    if body.device_id:
        guest_sub = "(SELECT id FROM users WHERE device_id=? AND id!=? AND phone IS NULL)"
        gargs = (body.device_id, uid)
        con.execute(f"UPDATE chats SET user_id=? WHERE user_id IN {guest_sub}", (uid, *gargs))
        con.execute(f"INSERT OR IGNORE INTO favorites(user_id,movie_id,created_at) "
                    f"SELECT ?,movie_id,created_at FROM favorites WHERE user_id IN {guest_sub}",
                    (uid, *gargs))
        con.execute(f"DELETE FROM favorites WHERE user_id IN {guest_sub}", gargs)
        # 人格画像：正式账号已有则保留（更可能为新测），否则搬游客的
        if not con.execute("SELECT 1 FROM user_personality WHERE user_id=? LIMIT 1", (uid,)).fetchone():
            con.execute(f"UPDATE user_personality SET user_id=? WHERE user_id IN {guest_sub}", (uid, *gargs))
        con.execute(f"DELETE FROM user_personality WHERE user_id IN {guest_sub}", gargs)
        # 行为信号 / 会话（无唯一约束，直接改属主）
        con.execute(f"UPDATE user_signals SET user_id=? WHERE user_id IN {guest_sub}", (uid, *gargs))
        con.execute(f"UPDATE conversations SET user_id=? WHERE user_id IN {guest_sub}", (uid, *gargs))
        # 数据已全部迁移，删除游客行，杜绝同 device_id 双行
        con.execute("DELETE FROM users WHERE device_id=? AND id!=? AND phone IS NULL",
                    (body.device_id, uid))
    con.commit(); con.close()
    return {"token": tok, "user_id": uid, "merged": bool(body.device_id)}

class LoginIn(BaseModel):
    phone: str
    password: str = ""
    code: str = ""

@app.post("/api/auth/login")
def api_login(body: LoginIn):
    con = _conn()
    if body.code:
        row = con.execute("SELECT code,expires_at FROM sms_codes WHERE phone=?",
                          (body.phone,)).fetchone()
        if not row or row[0] != body.code or row[1] < time.time():
            con.close(); raise HTTPException(400, "验证码错误或过期")
        if not con.execute("SELECT 1 FROM users WHERE phone=?", (body.phone,)).fetchone():
            con.close(); raise HTTPException(400, "该手机号尚未注册，请先注册")
    else:
        ph = hashlib.sha256(body.password.encode()).hexdigest()
        if not con.execute("SELECT 1 FROM users WHERE phone=? AND pass_hash=?",
                           (body.phone, ph)).fetchone():
            con.close(); raise HTTPException(400, "手机号或密码不对")
    row = con.execute("SELECT id FROM users WHERE phone=?", (body.phone,)).fetchone()
    tok = _token(row[0], body.phone)
    con.execute("UPDATE users SET token=? WHERE id=?", (tok, row[0]))
    con.commit(); con.close()
    return {"token": tok, "user_id": row[0]}

@app.get("/api/account")
def api_account(token: str = ""):
    con = _conn()
    row = con.execute("SELECT id,phone,device_id,created_at FROM users WHERE token=?",
                      (token,)).fetchone()
    if not row:
        con.close(); raise HTTPException(401, "未登录")
    uid, phone, dev, created = row
    favs = [r[0] for r in con.execute(
        "SELECT movie_id FROM favorites WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()]
    fav_cards = [c for c in (_card_any(f) for f in favs) if c]
    history = [{"role": r[0], "content": r[1]} for r in con.execute(
        "SELECT role,content FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()]
    con.close()
    return {"id": uid, "phone": phone, "is_guest": phone is None, "device_id": dev,
            "created_at": created, "favorites": fav_cards, "history": history}

class FavIn(BaseModel):
    movie_id: str

@app.post("/api/favorites")
def api_fav(body: FavIn, token: str = ""):
    con = _conn()
    row = con.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
    if not row:
        con.close(); raise HTTPException(401, "未登录")
    con.execute("INSERT OR IGNORE INTO favorites(user_id,movie_id,created_at) VALUES(?,?,?)",
                (row[0], body.movie_id, time.strftime("%F %T")))
    con.commit(); con.close()
    return {"ok": True}

@app.delete("/api/favorites")
def api_unfav(movie_id: str, token: str = ""):
    con = _conn()
    row = con.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
    if row:
        con.execute("DELETE FROM favorites WHERE user_id=? AND movie_id=?", (row[0], movie_id))
        con.commit()
    con.close()
    return {"ok": True}

# ---------------- 行为反馈（B4：收藏/浏览/点卡/换片 → 隐式画像） ----------------
class FeedbackIn(BaseModel):
    movie_id: str
    kind: str          # fav / unfav / view / pick

@app.post("/api/feedback")
def api_feedback(body: FeedbackIn, token: str = ""):
    con = _conn()
    row = con.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
    if not row:
        con.close(); raise HTTPException(401, "未登录")
    kind = body.kind if body.kind in ("fav", "unfav", "view", "pick") else "view"
    con.execute("INSERT INTO user_signals(user_id,movie_id,kind,created_at) VALUES(?,?,?,?)",
                (row[0], body.movie_id, kind, time.strftime("%F %T")))
    con.commit(); con.close()
    return {"ok": True}


def _implicit_profile(uid: int) -> dict | None:
    """按行为信号计算隐式五维画像（0-100）：fav/pick/view 为正、unfav 为负，
    各信号电影的五维 DNA 加权均值，从中性 50 拉动。无有效信号返回 None。"""
    con = _conn()
    rows = con.execute(
        "SELECT movie_id, kind FROM user_signals WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    con.close()
    if not rows:
        return None
    weights = {"fav": 2.0, "pick": 1.0, "view": 0.8, "unfav": -2.0}
    pos = {k: 0.0 for k in recommend.DNA_DIMS}
    neg = {k: 0.0 for k in recommend.DNA_DIMS}
    tp = tn = 0.0
    for mid, kind in rows:
        m = data.movie(mid)
        if not m:
            continue
        d = m.get("dna") or {}
        w = weights.get(kind, 0.0)
        if w > 0:
            for k in recommend.DNA_DIMS:
                pos[k] += w * (d.get(k) or 7.0) * 10
            tp += w
        else:
            for k in recommend.DNA_DIMS:
                neg[k] += abs(w) * (d.get(k) or 7.0) * 10
            tn += abs(w)
    if not tp and not tn:
        return None
    out = {}
    for k in recommend.DNA_DIMS:
        v = 50.0
        if tp:
            v += (pos[k] / tp - 50) * 0.8
        if tn:
            v -= (neg[k] / tn - 50) * 0.8
        out[k] = max(40, min(96, round(v)))
    return out


def _merge_profiles(quiz: dict | None, impl: dict | None) -> dict | None:
    """人格画像(quiz)与隐式画像(impl)融合：无隐式用 quiz；无 quiz 用隐式；
    都有则 0.55 quiz + 0.45 impl，让行为信号逐步拉动画像。"""
    if not impl:
        return quiz
    if not quiz:
        return impl
    out = {}
    for k in recommend.DNA_DIMS:
        q = quiz.get(k) or 50
        im = impl.get(k) or 50
        out[k] = max(40, min(96, round(0.55 * q + 0.45 * im)))
    return out


def _signal_genres(uid: int) -> dict | None:
    """按行为信号统计类型亲和 {genre: 权重}：fav/pick/view 为正、unfav 为负，
    取正权重 top5。供推荐做类型微调，让"越用越懂我"可见。"""
    con = _conn()
    rows = con.execute(
        "SELECT movie_id, kind FROM user_signals WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    con.close()
    if not rows:
        return None
    weights = {"fav": 2.0, "pick": 1.0, "view": 0.8, "unfav": -2.0}
    cnt: dict[str, float] = {}
    for mid, kind in rows:
        m = data.movie(mid)
        if not m:
            continue
        gw = weights.get(kind, 0.0)
        for g in (m.get("genres") or []):
            cnt[g] = cnt.get(g, 0.0) + gw
    pos = {g: v for g, v in cnt.items() if v > 0}
    return dict(sorted(pos.items(), key=lambda x: -x[1])[:5]) or None

# ---------------- 静态资源 ----------------
BASE = Path(__file__).resolve().parent.parent
app.mount("/posters_thumb", StaticFiles(directory=str(BASE / "data" / "enriched" / "posters_thumb")), name="thumbs")
app.mount("/posters", StaticFiles(directory=str(BASE / "data" / "posters")), name="posters")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
