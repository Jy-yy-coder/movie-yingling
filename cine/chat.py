# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · 聊天层
意图规则 -> 程序检索（卡片字段 / FTS 证据）-> LLM 可选润色 -> 离线降级。
防幻觉铁律：事实与引用全部来自 enriched 数据；LLM 只改表述不改事实。
"""
from __future__ import annotations
import json
import logging
import re

from . import data, recommend, search, embed
from . import llm as llm_mod

log = logging.getLogger("cine.chat")

_SEARCH_HINT = re.compile(r"哪(?:部|些)电影|哪(?:部|些).*(?:有|提到|说过|台词|评论)|提到.{0,8}(陀螺|梗|名场面|台词)|哪个.{0,6}(说过|评论)")
_QA_HINT = re.compile(r"讲什么|讲了个|讲了个啥|剧情|简介|是什么|讲得|怎么样|好看吗|值得看|评价|介绍|说说")

# 评论意图：用户明确想看观众评论时才附评论依据卡，避免无关评论堆在回复下方
_QUOTE_INTENT = re.compile(r"评论|口碑|好评|差评|评价|评分|大家(怎么说|怎么评)|观众(怎么说|怎么评|觉得)|别人怎么[看评说]")

# 引导话题 chip 全集（与 _follow_ups_for / _answer_recommend 的文案保持一致）：
# 查询改写时跳过这类消息，避免拿 chip 文本当检索意图
_CHIP_TEXTS = {
    "大家最夸它哪一点？", "这部适合什么心情看？", "有什么要注意的雷点吗？",
    "聊聊结局的处理", "推荐几部类似的片",
    "再推荐几部", "有没有轻松一点的？", "有没有更知名的？",
}

# ================= 系统提示词（5 个场景集中定义） =================

SYSTEM_PROMPT_REC = """你是「影灵」，一位懂电影、懂人心的私人选片顾问，负责从候选清单里做最后的选片决策。

工作方式：
1. 用户描述想看电影的心情或需求（可能带地区/类型/情绪等约束）。
2. 每条用户消息后会附上【推荐清单】，来自590部高分电影库的检索结果（关键词规则 + 语义向量），是你唯一的信息来源。
3. 你是决策者：从清单中挑出最合适的 2~4 部，并明确交代你的取舍。

必须遵守：
- 只推荐清单中的电影，绝不提及清单之外的任何影片；编号必须是清单内序号。
- **先取舍、再推荐**：
  - 开头用 1~2 句说清你的选片判断：用户最在意什么、你按什么标准在清单里筛；
  - 每部推荐的理由要扣住用户原话里的条件（如"你说想要轻松+国产，这部节奏明快又是国产片"）；
  - 清单里若有明显不符合用户条件的候选，用一句话点出"另几部偏X，因为你说要Y所以没选"——展示你在真权衡，而不是见清单就推。
  - 未选中的影片**不要用《片名》指代**，用"清单里另几部"这类模糊说法（避免出现未被推荐的片名）。
- 推荐理由必须基于清单内容；引用观众评论时自然带出，不照抄整段。
- 清单中若附有"差评预警"，推荐该片时用一句贴心话提醒用户。
- 若用户消息后附有【你的观影偏好】（来自他最近收藏/点开的电影），推荐理由要自然地结合它
  （如"你最近常看爱情片，这部情感浓度也高"），让推荐显得更懂你；但只准引用给出的偏好，不得编造偏好之外的喜好。
- **格式硬性要求**：先写一段"选片理由"（1~2 句取舍说明），然后推荐的每部电影各自独立成段（段落之间空一行），每段先写《片名》+推荐理由，再用「简介：」给出忠于清单的完整简介，不得截断或用省略号缩写。输出纯文本，不要用 Markdown 符号（如 **、---、# 等）。
- **重要：结合对话历史理解用户意图**：
  - 用户说"换两部""不要这个""再推荐几个" → 指上一轮推荐的电影，要换不同的
  - 用户说"更短的""片长少一点" → 在上一轮条件基础上加片长约束
  - 用户说"要国产的""日本的" → 在上一轮心情/类型基础上加地区约束
  - 如果历史中已有明确条件，追问时不要重复问同样的问题
- 需求模糊且无历史上下文时，先追问 1 个最关键的问题（最多 2 个），不要强行推荐。
- 候选都不合适时，诚实说明，并指出最接近的一部差在哪里。
- 语气像熟悉的朋友：温暖、口语化，不用"综上所述"之类套话。
- 回复末尾附上你推荐的电影编号，格式：[推荐编号: 1,3]
"""

SYSTEM_PROMPT_REC_SAFE = SYSTEM_PROMPT_REC.replace(
    "每段先写《片名》+推荐理由，再用「简介：」给出忠于清单的完整简介，不得截断或用省略号缩写。",
    "每段先写《片名》+推荐理由（口碑、DNA、适合谁看），严禁写出剧情走向、结局或「简介：」段落。",
)

SYSTEM_PROMPT_MOVIE = """你是影灵CINE电影助手，正在回答用户关于某部电影的问题。
用户消息后会附上【该片事实】卡片，包含基本信息、剧情简介、观众口碑维度、高赞评论——这是你唯一的事实来源。
必须遵守：
- 只许改述事实，不许新增任何事实、评价或情节。
- 用户问剧情时基于简介回答；问口碑时基于DNA维度和评论回答。
- 若档案带"差评预警"，自然地提醒一句。
- **重要：结合对话历史理解追问**：
  - "它的导演还拍过什么" → 指上一轮聊的这部电影
  - "还有类似的吗" → 基于上一轮的电影推荐相似片
  - "为什么" "然后呢" → 延续上一轮的话题
- 简短自然，像朋友聊天，不写百科腔。
"""

SYSTEM_PROMPT_MOVIE_SAFE = """你是影灵CINE电影助手，用户开启了无剧透模式，正在了解某部电影。
必须遵守：
- 只讲口碑、DNA 维度、观众反馈与基本信息，严禁透露剧情走向、结局或任何具体情节。
- 用户问剧情时，说明"无剧透模式下先不聊剧情，看完欢迎回来找你聊"，并自然转向口碑话题。
- 只许改述事实卡片中的信息，不新增事实。
- 简短自然，像朋友聊天。
"""

SYSTEM_PROMPT_SEARCH = """你是影灵CINE电影助手。基于用户问题与检索命中的短评片段回答。
必须遵守：
- 只可改述检索结果中出现的电影名和评论原文，不可编造评论或新增电影。
- 按相关度组织回答，命中多部电影时分点列出。
- 简短。
"""

SYSTEM_PROMPT_TALK_SAFE = """你是影灵CINE电影助手，用户正在和你讨论一部还没看/正在看的电影。
这是看前导览场景，严禁剧透：只讲这部片口碑强项与观众反馈，不透露具体情节走向。
必须遵守：
- 只可润色提供的事实，不新增事实。
- 用好评与观众情绪引出期待感，语气像朋友安利。
- 结合对话历史延续话题。
- 简短。
"""

SYSTEM_PROMPT_TALK_FULL = """你是影灵CINE电影助手，正和用户自由讨论一部电影（用户已看过，允许提及剧情）。
用好评与差评的真实观点引出讨论，主动抛出有讨论价值的话题（不限于提供的观点，但不得虚构影评）。
必须遵守：
- 只可基于提供的好评/差评观点展开，不得虚构具体影评内容。
- 语气像聊得来的影友，有自己的态度。
- 结合对话历史延续话题，不要每轮都重新介绍电影。
- 简短。
"""

SYSTEM_PROMPT_OPENING = """你是影灵CINE电影助手，用户刚点开一部电影开始 AI 陪看，你要主动开启话题破冰。
必须遵守：
- 只可润色提供的事实，不新增事实，严禁剧透具体情节。
- 一句话说出这部片最吸引人的口碑亮点，语气像朋友陪着看电影。
- 结尾用一句轻松的问句把话头交给用户（只问一个问题）。
- 60 字以内。
"""

# ================= 多轮查询改写 =================

_FOLLOWUP_HINT = re.compile(r"^(换|再|来|有没有|另外|还有|不要|换掉|去掉|更|太|少一点|多一点|别|那|它|这|为什么|然后|但是|不过|怎么|如何|谁|哪里|什么|哪|为啥|结局|最后|导演|演员|拍|演)")
# 更广泛的追问模式（包含代词引用、省略式追问）
_BROAD_FOLLOWUP = re.compile(r"^(嗯|哦|啊|是|对|好的|那|好|行|可以|明白了|了解|谢谢|感谢|哈哈|确实|真的|同意|不一定|不太|其实|感觉|觉得|为什么|为啥|怎么)")


def _is_followup(msg: str) -> bool:
    """判断消息是否为追问/跟进。"""
    msg = msg.strip()
    if not msg:
        return False
    # 短消息（<20字）更可能是追问
    if len(msg) < 20 and (_FOLLOWUP_HINT.search(msg) or _BROAD_FOLLOWUP.search(msg)):
        return True
    # 含代词/省略式追问
    if re.search(r"(这个|那个|它|他|她|这部|这部片|这部电影|结局|最后|然后呢|什么意思|讲什么)", msg):
        return True
    return False


def _extract_last_rec_movies(history: list[dict]) -> list[str]:
    """从历史中提取上一轮推荐的电影标题（从 assistant 消息中解析书名号）。"""
    for h in reversed(history):
        if h.get("role") == "assistant":
            titles = re.findall(r'[《<]([^》>]{1,30})[》>]', h.get("content", ""))
            return titles[:5]
    return []


def _rewrite_query(msg: str, history: list[dict]) -> str:
    """多轮查询改写：跟进消息拼上最近一条真实意图做检索，让向量检索更准。"""
    if not history:
        return msg
    # 找最近一条非引导 chip 的用户消息（chip 本身不含检索意图）
    last_user = None
    for h in reversed(history):
        if h.get("role") != "user":
            continue
        txt = (h.get("content") or "").strip()
        if txt and txt not in _CHIP_TEXTS:
            last_user = txt
            break
    if not last_user:
        return msg
    # 短消息（<15字）或含跟进提示词 → 拼接上一轮意图
    if _FOLLOWUP_HINT.search(msg) or len(msg) < 15:
        # 避免重复拼接相同内容
        if msg not in last_user:
            return f"{last_user} {msg}"
    return msg


def _history_seen_ids(history: list[dict] | None) -> set[str]:
    """历史轮次已推荐过的电影 id（来自会话消息记录的 movie_ids），用于「再推荐」排重。"""
    seen = set()
    for h in history or []:
        raw = h.get("movie_ids")
        if not raw:
            continue
        try:
            seen.update(json.loads(raw))
        except (ValueError, TypeError):
            pass
    return seen


def _movie_card(m, safe: bool = False):
    """事实卡。safe=True（无剧透模式）时不下发剧情简介——prompt 层与输出层同时断掉剧透源。"""
    d = m["dna"]
    dims = " ".join(f"{k}{d[k]}" for k in recommend.DNA_DIMS)
    lines = [f"《{m['title']}》({m['year']}) 豆瓣 {m['rating']}"]
    lines.append(f"DNA: {dims}")
    if m.get("runtime_min"):
        lines.append(f"片长: {m['runtime_min']}分钟")
    if not safe and (m.get("summary") or m.get("brief")):
        lines.append("简介: " + (m.get("summary") or m.get("brief") or "").strip())
    up = (m.get("quotes") or {}).get("up1")
    if up:
        lines.append(f"好评高赞: 「{up['text'][:60]}」({up['votes']}票)")
    # 差评预警必须进素材，LLM 才能基于它提醒，而不是自编
    warn = m.get("warn")
    if warn and warn.get("text"):
        lines.append(f"差评预警: {warn['text']}")
    return "\n".join(lines)


def _top_dim(m):
    """返回该片 DNA 顶维 (维度名, 分数)。"""
    d = m["dna"]
    dim = max(recommend.DNA_DIMS, key=lambda k: d.get(k, 0) or 0)
    return dim, d.get(dim, 0)


def _rec_card(m, hint=None, idx=1):
    """聊天推荐卡：供前端渲染 海报/匹配环/迷你雷达/高赞引用。"""
    d = m["dna"]
    top_dim, top_val = _top_dim(m)
    match = round(min(98, 52 + (top_val - 7) * 13 + float(m.get("rating") or 7) * 0.8))
    reason = f"{top_dim}维度 {top_val} 分"
    up = (m.get("quotes") or {}).get("up1")
    if up:
        reason += f" —— 「{up['text'][:34]}」"
    return {"movie_id": m["movie_id"], "title": m["title"], "year": m["year"],
            "genres": m["genres"], "rating": m["rating"], "runtime_min": m["runtime_min"],
            "poster_thumb": ("/" + m["poster_thumb"]) if m.get("poster_thumb") else None,
            "dna": d, "top_dim": top_dim, "top_val": top_val, "match": match, "reason": reason}


def _citations_for(m, n=2, spoiler=True):
    out = []
    q = m.get("quotes") or {}
    keys = ("up1",) if spoiler else ("up1", "dn1")
    for key in keys:
        c = q.get(key)
        if c:
            out.append({"kind": "quote", "movie_id": m["movie_id"], "title": m["title"],
                        "text": c["text"], "votes": c["votes"], "star": c["star"], "author": c["author"]})
    return out[:n]


# 换片/再推荐：有电影上下文时让位给推荐链路（不含「想看」，避免「想看《X》」被当成换片）
_REC_CHIP_HINT = re.compile(r"推荐|来部|来点|换两部|换几部")
# 「类似《X》」走相似推荐，而不是被书名号解析成单片问答
_SIMILAR_HINT = re.compile(r"类似|同款|像这部|同类")


def build_reply(message: str, mode: str = "rec", spoiler: bool = True, history: list | None = None,
                movie_context: dict | None = None, user_profile: dict | None = None,
                like_genres: dict | None = None):
    """入口：返回 {text, offline, citations:[...], kind, movies?, movie?}。
    mode: "rec"(推荐选片) / "talk"(陪看讨论)；spoiler: 无剧透开关。
    history: 当前会话最近对话历史（由 main.py 加载传入）。
    movie_context: 当前讨论电影上下文（由 main.py 加载传入）。
    user_profile: 用户人格画像五维 DNA（0-100，由 main.py 加载传入），推荐候选重排用。
    like_genres: 行为信号类型亲和 {genre: 权重}（B4），推荐候选类型微调用。"""
    msg = (message or "").strip()
    if not msg:
        return {"text": "想聊点什么?试试「推荐一部催泪的日本电影」或「霸王别姬讲什么」。",
                "offline": True, "citations": [], "kind": "help"}

    history = history or []

    # —— 优先处理：有电影上下文时的追问（推荐/换片类 chip 让位给推荐链路）——
    if movie_context and _is_followup(msg) and not _REC_CHIP_HINT.search(msg):
        m = movie_context["data"]
        kind = "core" if "movie_id" in m and not m.get("ext") else "ext"
        return _answer_movie(kind, m, msg, mode, spoiler, history, movie_context)

    # —— 意图 1：电影名解析。弱匹配靠 ≥3 字阈值挡住《活着》《过年》；
    # 「类似《X》」即使解析到片名也走推荐，避免书名号劫持相似问句。——
    kind, m = search.resolve_title(msg, allow_weak=True)
    if m is not None:
        if _SIMILAR_HINT.search(msg):
            hint = recommend.parse_hint(msg)
            return _answer_recommend(msg, hint, spoiler, history, user_profile, like_genres)
        return _answer_movie(kind, m, msg, mode, spoiler, history, movie_context)

    # —— 意图 2：评论/梗检索 ——
    if _SEARCH_HINT.search(msg):
        return _answer_search(msg, history)

    # —— 陪看讨论模式：未点名电影，用上下文或引导报片名 ——
    if mode == "talk":
        if movie_context:
            # 有电影上下文，直接走电影问答
            m = movie_context["data"]
            kind = "core" if "movie_id" in m and not m.get("ext") else "ext"
            return _answer_movie(kind, m, msg, mode, spoiler, history, movie_context)
        return {"text": "陪看讨论模式 🍿 告诉我你准备看或刚看完哪部，比如「我看完《霸王别姬》了」或"
                        "「《千与千寻》想表达什么」。",
                "offline": True, "citations": [], "kind": "talk_prompt"}

    # —— 意图 3：推荐（关键词命中 维度/类型/地区，或命中推荐/心情类触发词）——
    hint = recommend.parse_hint(msg)
    if hint["dim"] or hint["genre"] or hint["region"] or re.search(r"推荐|来部|来点|想看|看点|有没有|好看|看看|适合|心情|无聊|片荒|烦", msg):
        return _answer_recommend(msg, hint, spoiler, history, user_profile, like_genres)

    # —— 意图 4：追问/跟进（无电影上下文时）——
    if _is_followup(msg) and history:
        # 从历史中找上一轮推荐的电影
        last_titles = _extract_last_rec_movies(history)
        if last_titles:
            # 尝试解析第一部电影
            for title in last_titles[:2]:
                kind, m = search.resolve_title(title)
                if m:
                    return _answer_movie(kind, m, msg, mode, spoiler, history, movie_context)

    # —— 有电影上下文且未命中其他意图 → 继续聊这部片（覆盖「最好玩的一点是什么」等自由追问）——
    if movie_context:
        m = movie_context["data"]
        kind = "core" if "movie_id" in m and not m.get("ext") else "ext"
        return _answer_movie(kind, m, msg, mode, spoiler, history, movie_context)

    # —— 兜底：帮助 ——
    return {"text": "我可以:\n· 推荐电影(比如「推荐一部燃的科幻片」)\n· 讲电影(比如「千与千寻讲什么」)\n"
                    "· 找评论(比如「哪部电影里提到\'陀螺\'」)",
            "offline": True, "citations": [], "kind": "help"}


def _build_enhanced_system(base_system: str, movie_context: dict | None = None, safe: bool = False) -> str:
    """构建增强版系统提示词，注入电影上下文。safe=True 时剔除上下文里的剧情简介行。"""
    if not movie_context:
        return base_system
    text = movie_context["prompt_text"]
    if safe:
        text = "\n".join(ln for ln in text.splitlines()
                         if not ln.startswith("简介：") and not ln.startswith("简介:"))
    return base_system + "\n\n" + text


def _answer_movie(kind, m, msg, mode="rec", spoiler=True, history=None, movie_context=None):
    if kind == "core":
        top_dim, top_val = _top_dim(m)
        up = (m.get("quotes") or {}).get("up1")
        dn = (m.get("quotes") or {}).get("dn1")
        warn = m.get("warn")
        # 无剧透开启时：事实卡与上下文注入都不含剧情简介（prompt 层断源）
        facts = _movie_card(m, safe=spoiler)
        # 构建增强版系统提示词；评论依据只在用户想看评论时附带，避免无关评论卡堆在回复下方
        want_quotes = bool(_QUOTE_INTENT.search(msg))
        if mode == "talk":
            if spoiler:
                cits = _citations_for(m, 2, spoiler=True) if want_quotes else []
                offline_txt = (f"《{m['title']}》看前导览（不含剧透）：{top_dim}维度 {top_val} 分是它最受好评的长板"
                               + (f"，好评区有人这么讲「{up['text'][:30]}…」" if up else "")
                               + (f"。提前打预防针：{warn['text']}" if warn else "。")
                               + "想深聊剧情的话，可以关掉无剧透模式～")
                system = _build_enhanced_system(SYSTEM_PROMPT_TALK_SAFE, movie_context, safe=True)
                offline, text, model = _polish(system,
                                               f"用户问：{msg}\n\n该片事实:\n{facts}", cits,
                                               offline_txt=offline_txt, history=history, temperature=0.7)
            else:
                cits = _citations_for(m, 2, spoiler=False) if want_quotes else []
                dn_txt = dn["text"] if dn else "差评区比较分散"
                up_txt = up["text"] if up else "好评区也有实力背书"
                offline_txt = (f"聊《{m['title']}》我不困了（已退出剧透保护）：观众吵得最凶的是「{dn_txt[:26]}…」，"
                               f"但好评区也用实力说话——{top_dim}维度 {top_val} 分，有人讲「{up_txt[:26]}…」。你站哪边？")
                system = _build_enhanced_system(SYSTEM_PROMPT_TALK_FULL, movie_context)
                offline, text, model = _polish(system,
                                               f"用户问：{msg}\n\n该片事实:\n{facts}", cits,
                                               offline_txt=offline_txt, history=history, temperature=0.7)
            return {"text": text, "offline": offline, "citations": cits, "kind": "talk",
                    "model": model, "movie_id": m["movie_id"], "movie": _rec_card(m),
                    "follow_ups": _follow_ups_for(m, spoiler)}
        # 默认（推荐模式）问答：卡片式陈述；无剧透开启时换安全提示词 + 简介不出
        cits = _citations_for(m, 2, spoiler) if want_quotes else []
        system = _build_enhanced_system(
            SYSTEM_PROMPT_MOVIE_SAFE if spoiler else SYSTEM_PROMPT_MOVIE,
            movie_context, safe=spoiler)
        offline, text, model = _polish(
            system,
            f"用户问：{msg}\n\n该片事实:\n{facts}", cits, offline_txt=facts, history=history)
        return {"text": text, "offline": offline, "citations": cits, "kind": "movie",
                "model": model, "movie_id": m["movie_id"],
                "follow_ups": _follow_ups_for(m, spoiler)}
    # 库外电影：轻字段
    line = f"《{m['title']}》({m.get('year') or '年份未知'}) 豆瓣 {m.get('rating') or '暂无'}"
    if m.get("genres"):
        line += f" | 类型: {m['genres']}"
    if m.get("summary") and not spoiler:
        line += f"\n简介: {m['summary'][:100]}"
    if not m.get("rating") and not m.get("summary"):
        line += "\n(这部片信息较简，仅收录了片名/年份)"
    return {"text": line, "offline": True, "citations": [], "kind": "movie_ext"}


def _follow_ups_for(m, spoiler=True):
    """按电影实际数据生成引导话题 chip（最多 3 个，无数据不出，防幻觉）。"""
    chips = []
    up = (m.get("quotes") or {}).get("up1")
    if up:
        chips.append("大家最夸它哪一点？")
    chips.append("这部适合什么心情看？")
    if spoiler and m.get("warn"):
        chips.append("有什么要注意的雷点吗？")
    if not spoiler:
        chips.append("聊聊结局的处理")
    chips.append("推荐几部类似的片")
    return chips[:3]


def watch_opening(movie_id: str, spoiler: bool = True):
    """陪看开场：LLM 生成主动破冰话题，失败降级模板文案；附引导 chip 与电影卡。"""
    m = data.movie(movie_id)
    if not m:
        return None
    top_dim, top_val = _top_dim(m)
    up = (m.get("quotes") or {}).get("up1")
    s = m.get("sentiment") or {}
    template = (f"今晚我陪你一起看《{m['title']}》🍿 它的{top_dim}最受好评（{top_val} 分）"
                + (f"，有人夸「{up['text'][:24]}…」" if up else "")
                + (f"。观众情绪温度 {s.get('temp')}，{'偏暖' if (s.get('temp') or 50) >= 50 else '偏冷'}。"
                   if s.get("temp") is not None else "。")
                + "你看到哪了？随时喊我聊～")
    offline, text, model = _polish(
        SYSTEM_PROMPT_OPENING, f"该片事实:\n{_movie_card(m, safe=spoiler)}", [],
        offline_txt=template, temperature=0.7)
    return {"text": text, "offline": offline, "model": model, "kind": "watch_opening",
            "citations": [], "chips": _follow_ups_for(m, spoiler),
            "movie_id": m["movie_id"], "movie": _rec_card(m)}


def _answer_search(msg, history=None):
    m = re.search(r"['\"“”「」]([^'\"“”「」]{2,20})['\"“”「」]|(陀螺|梗|名场面|台词|彩蛋|太空电梯|紫霞|一句话)", msg)
    q = m.group(1) or m.group(2) if m else None
    if not q:
        q = re.sub(r"哪(?:部|些)电影|哪(?:部|些).*(?:有|提到|说过|台词|评论)|提过|说过|评论", "", msg).strip() or ""
    hits = search.search_fts(q) if q else []
    if not hits:
        return {"text": f"没搜到与「{q or msg}」相关的短评。换个说法试试?", "offline": True,
                "citations": [], "kind": "search"}
    cits = [{"kind": "fts", "movie_id": h["movie_id"], "title": h["title"],
             "text": h["snip"], "votes": h["votes"]} for h in hits[:3]]
    names = "、".join(f"《{h['title']}》" for h in hits[:5])
    text = f"短评里搜到与「{q}」相关的内容,主要在这几部: {names}。引用见右侧卡片。"
    offline, polished, model = _polish(
        SYSTEM_PROMPT_SEARCH,
        f"用户问：{msg}\n\n检索命中电影: {names}\n评论片段: {' | '.join(c['text'] for c in cits)}",
        cits, offline_txt=text, history=history)
    return {"text": polished, "offline": offline, "citations": cits, "kind": "search", "model": model}


def _blend_by_profile(ms, profile):
    """候选集按人格画像重排：0.7 意图排序（原位置分）+ 0.3 画像相似度。
    无画像或候选为空时行为不变。"""
    u = {k: (profile.get(k) or 0) / 10.0 for k in recommend.DNA_DIMS}

    def sim(m):
        d = m["dna"]
        s, w = 0.0, 0.0
        for k in recommend.DNA_DIMS:
            wk = max(u[k], 0.01)
            s += wk * (1 - abs(u[k] - (d.get(k) or 0)) / 10)
            w += wk
        return s / w if w else 0.0

    n = max(len(ms), 1)
    scored = [(0.7 * (1 - i / n) + 0.3 * sim(m), m) for i, m in enumerate(ms)]
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored]


def _answer_recommend(msg, hint, spoiler=True, history=None, user_profile=None, like_genres=None):
    # 历史已推荐过的片子：「再推荐几部」等追问要排重，避免原样重复
    seen_hist = _history_seen_ids(history)

    # 第一优先：关键词规则推荐（快、准，适合明确需求）
    ms = recommend.recommend(msg, limit=4)
    if seen_hist:
        fresh = [m for m in ms if m["movie_id"] not in seen_hist]
        # 全排掉时清空，交给向量检索找新片（而不是原样返回旧片）
        ms = fresh

    # 第二优先：关键词没命中或结果不足（<2 部）→ 向量语义检索补位
    if len(ms) < 2:
        query = _rewrite_query(msg, history)      # 多轮查询改写
        hits = embed.retrieve(query, top_k=12)
        seen = {m["movie_id"] for m in ms}
        for mid, _score in hits:
            if mid not in seen and mid not in seen_hist:
                m = data.movie(mid)
                if m:
                    ms.append(m)
                    seen.add(mid)
        # 全被历史排掉时放宽：宁可重复也要保证有结果
        if len(ms) < 2:
            for mid, _score in hits:
                if mid not in seen:
                    m = data.movie(mid)
                    if m:
                        ms.append(m)
                        seen.add(mid)
                if len(ms) >= 2:
                    break
        ms = ms[:4]

    # 第三层：有人格画像时混合重排（意图优先，画像微调）
    if ms and user_profile:
        ms = _blend_by_profile(ms, user_profile)

    # B4：行为信号类型亲和微调（收藏/点卡的类型倾向；稳定排序保持同权重内原序）
    if ms and like_genres:
        def _genre_hit(m):
            return sum(like_genres.get(g, 0) for g in set(m.get("genres") or []))
        ms = sorted(ms, key=lambda m: -_genre_hit(m))

    if not ms:
        return {"text": "按这个条件没筛出合适的高分片，换个说法试试？",
                "offline": True, "citations": [], "kind": "recommend"}
    cits = []
    lines = []
    cards = []
    for i, m in enumerate(ms, 1):
        lines.append(f"{i}. {_movie_card(m, safe=spoiler)}")
        cards.append(_rec_card(m, hint, i))
        cits += _citations_for(m, 1, spoiler)
    facts = "\n".join(lines)
    if spoiler:
        plain = "\n\n".join(
            f"《{m['title']}》({m['year']}，豆瓣 {m['rating']})"
            for m in ms)
    else:
        plain = "\n\n".join(
            f"《{m['title']}》({m['year']}，豆瓣 {m['rating']})\n简介：{(m.get('summary') or m.get('brief') or '').strip()}"
            for m in ms)
    # B4：把用户行为偏好注入 prompt，让 AI 在推荐时自然引用（演示"越用越懂我"）
    rec_prompt = f"用户问：{msg}\n\n推荐清单:\n{facts}"
    if like_genres:
        taste = "、".join(like_genres.keys())
        rec_prompt = (f"用户问：{msg}\n\n"
                      f"【你的观影偏好（来自你最近收藏/点开的电影）】{taste}\n\n推荐清单:\n{facts}")
    rec_system = SYSTEM_PROMPT_REC_SAFE if spoiler else SYSTEM_PROMPT_REC
    offline, polished, model = _polish(
        rec_system, rec_prompt, cits, offline_txt=plain,
        history=history, temperature=0.7, max_tokens=2800)

    # —— 防幻觉校验 ——
    n_candidates = len(ms)
    if not offline and not _validate_rec_ids(polished, n_candidates):
        retry_system = rec_system + f"\n\n硬性要求：只推荐清单中的电影，推荐编号必须在1到{n_candidates}之间。"
        offline, polished, model = _polish(
            retry_system, rec_prompt, cits, offline_txt=plain,
            history=history, temperature=0.7, max_tokens=2800)
        if not offline and not _validate_rec_ids(polished, n_candidates):
            polished = plain       # 仍失败 → 降级用离线文案
            offline = True

    # 片名白名单校验
    if not offline and _check_foreign_titles(polished, ms):
        log.warning("推荐回复疑似含库外片名，降级离线文案")
        polished, offline = plain, True

    # 去掉 [推荐编号: x,y]（给用户看的版本不需要编号），并清洗 Markdown 符号（前端纯文本展示）
    polished = re.sub(r'\s*\[推荐编号:\s*[\d,\s]+\]\s*', '', polished)
    polished = polished.replace('**', '')
    polished = re.sub(r'(?m)^-{3,}\s*$', '', polished)

    # 有剧透时才把数据库完整简介贴进正文；无剧透模式禁止这步（否则必剧透）
    if not spoiler:
        polished = _enforce_summary(polished, ms)

    # 卡片与正文对齐：只保留正文里以《片名》形式出现的电影
    # （决策段可能提到被排除的候选，但那是不带《》的模糊说法，不能把其卡片带出来）
    if not offline:
        mentioned = [c for c in cards if f"《{c['title'].split(' ')[0]}" in polished]
        if mentioned:
            cards = mentioned

    # 口碑引用与最终卡片对齐：只保留最终推荐影片的评论，落选影片的引用不附上
    final_ids = {c["movie_id"] for c in cards}
    cits = [c for c in cits if c["movie_id"] in final_ids]

    return {"text": polished, "offline": offline, "citations": cits, "movies": cards,
            "kind": "recommend", "model": model,
            "follow_ups": ["再推荐几部", "有没有轻松一点的？", "有没有更知名的？"]}


def _polish(system, prompt, cits, offline_txt=None, history=None, temperature=0, max_tokens=700):
    """LLM 润色；失败返回 (离线文案, True, None)。
    temperature: 推荐用 0.7，问答/搜索用 0（默认 0，防幻觉）。
    max_tokens: 推荐场景需更长（多部影片的理由+完整简介），避免输出被截断。"""
    try:
        text, model = llm_mod.chat_reply(system, prompt, history=history, temperature=temperature,
                                         max_tokens=max_tokens)
    except Exception:
        text, model = None, None
    if text:
        return False, text, model
    if offline_txt is None:
        simp = [ln.strip() for ln in prompt.splitlines() if not ln.strip().startswith("DNA")]
        offline_txt = "\n".join(simp) if simp else prompt
    return True, offline_txt, None


def _enforce_summary(text: str, ms: list[dict]) -> str:
    """保证每部影片的简介完整且唯一：LLM 可能截断/改写简介，或把「简介」单独成段。
    逐段扫描并记住当前讨论的影片，含「简介：」的段落统一截断后接数据库完整简介；
    以《片名》开头的段落若在简介前被截断，也补上完整简介。
    同一部影片只允许出现一次完整简介——LLM 复述的第二段「简介：」丢弃。"""
    def brief_of(m):
        # summary 优先（完整）；brief 是库外片的截短版，仅作兜底
        return (m.get("summary") or m.get("brief") or "").strip()

    def match_movie(s):
        for m in ms:
            cn = m["title"].split(" ")[0] or "《"
            if cn != "《" and cn in s:
                return m
        return None

    paras = re.split(r"\n\s*\n", text)
    out, current = [], None
    emitted: set[str] = set()                  # 已补过完整简介的电影主名
    for p in paras:
        mm = match_movie(p)
        if mm:
            current = mm
        cn = current["title"].split(" ")[0] if current else ""
        brief = brief_of(current) if current else ""
        lead = p.lstrip().lstrip("*").lstrip()
        if re.search(r"简介[:：]", p):
            head = re.sub(r"[*]+", "", re.split(r"简介[:：]", p, 1)[0]).strip()
            if cn and cn in emitted:
                # 该片简介已补过：纯「简介：」段整段丢弃，夹在文中的只留简介前部分
                if head:
                    out.append(head)
                continue
            if brief:
                if cn:
                    emitted.add(cn)
                out.append((head + "\n简介：" + brief) if head else ("简介：" + brief))
            else:
                out.append(p)
        elif cn and cn != "《" and brief and lead.startswith("《" + cn):
            # 片名段在「简介：」前就被截断 → 直接补完整简介（同一部片只补一次）
            head = re.sub(r"[*]+", "", p).strip()
            if cn in emitted:
                out.append(head)
            else:
                emitted.add(cn)
                out.append(head + "\n简介：" + brief)
        else:
            out.append(p)
    # 兜底：合并连续完全相同的段落（LLM 复述防御）
    collapsed = []
    for p in out:
        if collapsed and p == collapsed[-1]:
            continue
        collapsed.append(p)
    return "\n\n".join(collapsed)


def _validate_rec_ids(text: str, n_candidates: int) -> bool:
    """校验回复中的 [推荐编号: x,y] 是否都在候选范围内。"""
    m = re.search(r'\[推荐编号:\s*([\d,\s]+)\]', text)
    if not m:
        return True  # 没有编号就不校验（宽松策略）
    ids = [int(x.strip()) for x in m.group(1).split(",")]
    return all(1 <= i <= n_candidates for i in ids)


def _check_foreign_titles(text: str, candidates: list[dict]) -> bool:
    """正文里出现书名号片名且不在候选清单 → True（有库外片名）。"""
    allowed = {m["title"].split(" ")[0] for m in candidates}
    found = re.findall(r'[《<]([^》>]{1,30})[》>]', text)
    return any(f.split(" ")[0] not in allowed for f in found)
