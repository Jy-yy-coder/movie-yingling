# -*- coding: utf-8 -*-
"""影灵 CINE 平台 · 规则推荐层（DNA + 相似片，离线模式核心）"""
from __future__ import annotations
import re

from . import data

DNA_DIMS = ["剧情", "演技", "情感", "视听", "节奏"]

# 感觉/场景关键词 -> 规则口径（P1 无 tags，用 DNA + 类型近似）
_KEYMAP = [
    (re.compile(r"催泪|感人|泪|哭|治愈|温暖|温情|感动|暖心|亲情|母爱|父爱|家人|离别|怀念|父母|爸妈|全家|长辈|过年|亲子"), "情感", "high"),
    (re.compile(r"失恋|分手|孤独|难过|低落|郁闷|烦|emo|想哭|治愈系|心情不好|不开心"), "情感", "high"),
    (re.compile(r"文艺|诗意|细腻|安静|雨天|下雨|阴天|沙发|窝着|慢热"), "情感", "high"),
    (re.compile(r"燃|爽|刺激|过瘾|热血|爽快|搞笑|喜剧|幽默|笑|开心|快乐|高兴|欢乐|轻松|解压|下饭|沙雕|逗"), "节奏", "high"),
    (re.compile(r"悬疑|烧脑|反转|推理|剧情|故事|深刻|震撼|人性|现实"), "剧情", "high"),
    (re.compile(r"励志|梦想|奋斗|逆袭|成长|勇气|希望|振奋"), "剧情", "high"),
    (re.compile(r"画面|视觉|特效|摄影|配乐|美学|精美|美|大片|史诗"), "视听", "high"),
    (re.compile(r"演技|演员|飙戏|表演|实力派|老戏骨"), "演技", "high"),
]
# 心情/场景关键词 -> 类型兑底（没命中类型名时也能按感觉筛片）
_MOOD_GENRE = {
    "开心": "喜剧", "快乐": "喜剧", "高兴": "喜剧", "欢乐": "喜剧", "搞笑": "喜剧",
    "爆笑": "喜剧", "解压": "喜剧", "轻松": "喜剧", "下饭": "喜剧", "沙雕": "喜剧",
    "治愈": "家庭", "温暖": "家庭", "亲情": "家庭", "家人": "家庭", "暖心": "家庭",
    "父母": "家庭", "爸妈": "家庭", "全家": "家庭", "长辈": "家庭", "亲子": "家庭",
    "过年": "家庭", "孩子": "家庭",
    "失恋": "爱情", "恋爱": "爱情", "甜蜜": "爱情", "浪漫": "爱情", "心动": "爱情",
    "恐怖": "恐怖", "吓人": "恐怖", "惊悚": "惊悚", "刺激": "动作",
}
_GENRE_ALIAS = {
    "动画": "动画", "动漫": "动画", "科幻": "科幻", "恐怖": "恐怖", "惊悚": "惊悚",
    "喜剧": "喜剧", "爱情": "爱情", "动作": "动作", "犯罪": "犯罪", "悬疑": "悬疑",
    "剧情": "剧情", "战争": "战争", "纪录片": "纪录片", "音乐": "音乐",
}
_REGION_ALIAS = {"华语": "中国", "国产": "中国", "中国": "中国", "日本": "日本", "日": "日本",
                 "韩国": "韩国", "韩": "韩国", "美国": "美国", "欧美": "欧美", "西方": "欧美",
                 "欧洲": "欧洲", "法国": "欧洲", "英国": "欧洲", "德国": "欧洲", "意大利": "欧洲",
                 "日韩": "日韩",
                 # 常见非西方国家：按影片 countries 字段匹配（见 region_match）
                 "印度": "印度", "泰国": "泰国", "伊朗": "伊朗", "苏联": "苏联",
                 "俄罗斯": "俄罗斯", "巴西": "巴西"}
# 地区分组别名 → 底层数据地区名（底层六值：中国/日本/韩国/欧洲/美国/其他）
REGION_GROUPS = {"欧美": ("欧洲", "美国"), "日韩": ("日本", "韩国")}
# 地区显示名：旧值兼容映射（现数据已直接存六值，identity 为主）
REGION_LABEL = {"华语": "中国", "欧美": "欧美", "中国": "中国", "日本": "日本", "韩国": "韩国",
                "欧洲": "欧洲", "美国": "美国", "其他": "其他"}
# 具体国家词：region 命中这些词时按影片 countries 字段匹配，比笼统归「其他」更准
_COUNTRY_KEYWORDS = {"印度", "泰国", "伊朗", "苏联", "俄罗斯", "巴西"}


def region_match(m_region, region, countries=None):
    """地区筛选：支持六值地区名（中国/日本/韩国/欧洲/美国/其他）、
    复合词（欧美=欧洲+美国 / 日韩=日本+韩国）
    与具体国家名（印度/泰国/伊朗/苏联/俄罗斯/巴西，按影片 countries 字段匹配）。"""
    if not region:
        return True
    if region == "其他":
        return m_region == "其他"
    group = REGION_GROUPS.get(region)
    if group:
        return m_region in group
    if region in _COUNTRY_KEYWORDS:
        return bool(countries) and any(region in str(c) for c in countries)
    return m_region == region


# 否定词：出现在类型/地区关键词前 3 字内视为负向条件（不要爱情/别推恐怖/除了美国…）
_NEG_PAT = re.compile(r"(不要|不想|不喜|不喜欢|别|讨厌|排斥|排除|除了|不含|拒绝|不看|没心情|不看|不想看)$")

def _negated(text: str, kw: str) -> bool:
    """kw 在原文中出现时，其前方紧邻否定词则视为负向。"""
    start = 0
    while True:
        i = text.find(kw, start)
        if i < 0:
            return False
        if _NEG_PAT.search(text[max(0, i - 4):i]):
            return True
        start = i + 1

def parse_hint(text: str):
    """从用户描述里抽 感觉维度/类型/地区/年份 提示。
    支持否定条件（不要X/别X/除了X）：X 进入 exclude_genres / exclude_regions，
    且不作为正向条件参与筛选。"""
    hint = {"dim": None, "genre": None, "region": None, "year_min": None,
            "exclude_genres": [], "exclude_regions": []}
    for pat, dim, _ in _KEYMAP:
        if pat.search(text):
            hint["dim"] = dim
            break
    for kw, g in _GENRE_ALIAS.items():
        if kw in text:
            if _negated(text, kw):
                if g not in hint["exclude_genres"]:
                    hint["exclude_genres"].append(g)
            else:
                hint["genre"] = hint["genre"] or g
    if not hint["genre"]:
        for kw, g in _MOOD_GENRE.items():
            if kw in text:
                if _negated(text, kw):
                    if g not in hint["exclude_genres"]:
                        hint["exclude_genres"].append(g)
                else:
                    hint["genre"] = hint["genre"] or g
    for kw, rg in _REGION_ALIAS.items():
        if kw in text:
            if _negated(text, kw):
                if rg not in hint["exclude_regions"]:
                    hint["exclude_regions"].append(rg)
            else:
                hint["region"] = hint["region"] or rg
    for num in re.findall(r"(?:19|20)\d{2}", text):
        hint["year_min"] = int(num) if not hint["year_min"] else min(hint["year_min"], int(num))
    return hint


def recommend(text: str = "", region=None, genre=None, dim=None, limit=9,
              exclude_genres=None, exclude_regions=None):
    """规则推荐：按 DNA 顶维/地区/类型过滤后取 DNA 均值最高。text 优先做意图解析。
    否定条件（不要X）从候选池中剔除对应类型/地区。"""
    if text:
        h = parse_hint(text)
        region = region or h["region"]
        genre = genre or h["genre"]
        dim = dim or h["dim"]
        exclude_genres = list(exclude_genres or []) + list(h["exclude_genres"])
        exclude_regions = list(exclude_regions or []) + list(h["exclude_regions"])
    pool = []
    for m in data.all_movies():
        if region and not region_match(m["region"], region, m.get("countries")):
            continue
        if genre and not any(genre == g for g in m["genres"]):
            continue
        if exclude_genres and any(g in m["genres"] for g in exclude_genres):
            continue
        if exclude_regions and any(region_match(m["region"], r, m.get("countries"))
                                   for r in exclude_regions):
            continue
        d = m["dna"]
        if dim and d.get(dim, 0) < 7.5:
            continue
        mean = sum(d[k] for k in DNA_DIMS) / 5
        dim_score = d.get(dim, 0) if dim else 0
        pool.append((dim_score, mean, m))
    # 有心情维度时按该维排序（催泪看情感，而不是五维总分把「技术最好」排前面）
    if dim:
        pool.sort(key=lambda x: (-x[0], -x[1], -x[2]["rating"]))
    else:
        pool.sort(key=lambda x: (-x[1], -x[2]["rating"]))
    return [m for _, _, m in pool[:limit]]


def profile_rank(profile: dict):
    """全库按用户画像相似度打分排序，返回 [(score, movie), ...] 降序。供路线与聊天重排复用。"""
    u = {k: (profile.get(k) or 0) / 10.0 for k in DNA_DIMS}
    scored = []
    for m in data.all_movies():
        d = m["dna"]
        sim, wsum = 0.0, 0.0
        for k in DNA_DIMS:
            w = max(u[k], 0.01)                                 # 强偏好维度主导排序
            sim += w * (1 - abs(u[k] - (d.get(k) or 0)) / 10)
            wsum += w
        scored.append((sim / wsum + float(m.get("rating") or 0) * 0.01, m))
    scored.sort(key=lambda x: -x[0])
    return scored


def recommend_by_dna_profile(profile: dict, limit: int = 5):
    """按用户五维画像（0-100）推荐：用户偏好越强的维度权重越大，
    该维度上越贴近的电影得分越高；附少量豆瓣评分加成。供人格测试与个性化推荐复用。"""
    return [m for _, m in profile_rank(profile)[:limit]]


def explain_card(m: dict, dna: dict | None = None, keywords: list[str] | None = None) -> dict:
    """推荐解释（ExplainCard 数据源）：纯模板生成，只引用真实数据（防幻觉）。
    dna 为用户画像五维（0-100），缺失时退化为无画像版（影片强项+评分+好评）。"""
    d = m["dna"]
    dims = []
    bullets = []
    if dna:
        for k in DNA_DIMS:
            u = dna.get(k) or 0
            v = int(round((d.get(k) or 0) * 10))
            dims.append({"dim": k, "user": u, "movie": v, "fit": max(0, 100 - abs(u - v))})
        # 1) 强项维度契合：用户最强且最贴近的维度
        best = max(dims, key=lambda x: (x["user"], x["fit"]))
        bullets.append(f"你的「{best['dim']}」最突出（{best['user']} 分），这部片恰好 {best['movie']} 分，正对味")
    else:
        # 无画像：突出影片自身最强维度
        top = max(DNA_DIMS, key=lambda k: d.get(k) or 0)
        bullets.append(f"这部片的「{top}」最出彩（{int(round((d.get(top) or 0) * 10))} 分）")
    # 2) 评分背书
    rc = m.get("rating_count") or 0
    bullets.append(f"豆瓣 {m.get('rating')} 分" + (f" · {max(1, round(rc / 10000))} 万人评过，口碑稳" if rc else ""))
    # 3) 好评证据
    up = (m.get("quotes") or {}).get("up1")
    if up:
        bullets.append(f"好评区高赞：「{up['text'][:28]}…」")
    # 4) 关键词共鸣（人格测试选的词与影片标签有交集）
    tags = list((m.get("tags") or {}).get("mood") or []) + list((m.get("tags") or {}).get("scene") or [])
    echo = [k for k in (keywords or []) if any(k in t or t in k for t in tags)]
    if echo:
        bullets.append(f"你的关键词「{'、'.join(echo[:2])}」在这部片里有回响")
    return {"dims": dims, "bullets": bullets}


# ---------------- 四段式探索路线 ----------------
# 阶段文案均为模板生成，只引用真实数据字段，不引入 LLM（防幻觉）。
ROUTE_STAGES = (
    ("热身 · 最熟悉的味道", "从你最偏爱的维度出发，先看一部最对味的。"),
    ("深入 · 换个口味细品", "还是你喜欢的味道，但换个地区与类型，拓宽一点边界。"),
    ("跨界 · 半步舒适区", "往你的次强维度迈一步，那里藏着你还没发现的喜好。"),
    ("奇遇 · 隐藏的惊喜", "评价人数不多但口碑过硬，和你的画像暗暗合拍。"),
)


def _route_pick(ranked, dim, seen, extra=None):
    """从画像排序池里挑第一部满足 维度下限 + 去重 + 附加条件 的电影。"""
    for score, m in ranked:
        if m["movie_id"] in seen or (m["dna"].get(dim) or 0) < 7.5:
            continue
        if extra and not extra(m):
            continue
        return score, m
    return None


def build_route(profile: dict):
    """按人格画像生成四段式探索路线。返回 [{name, desc, movie, stage_reason}]，最多 4 段。"""
    dims = sorted(DNA_DIMS, key=lambda k: -(profile.get(k) or 0))
    top, second = dims[0], dims[1]
    ranked = profile_rank(profile)
    seen: set[str] = set()
    picks = []   # (stage_idx, movie, score)

    # ① 热身：最强偏好维度最贴合作品
    hit = _route_pick(ranked, top, seen)
    if hit:
        picks.append((0, hit[1], hit[0]))
        seen.add(hit[1]["movie_id"])
        first = hit[1]
        # ② 深入：同维度但换地区或类型
        hit = _route_pick(ranked, top, seen, extra=lambda m: (
            m["region"] != first["region"] or set(m["genres"]) != set(first["genres"])))
        if hit:
            picks.append((1, hit[1], hit[0]))
            seen.add(hit[1]["movie_id"])

    # ③ 跨界：次强维度
    hit = _route_pick(ranked, second, seen)
    if hit:
        picks.append((2, hit[1], hit[0]))
        seen.add(hit[1]["movie_id"])

    # ④ 奇遇：冷门高分（评价人数低于下四分位）且命中前二偏好维度
    def _gem(m):
        return (m.get("rating_count") or 0) < 250000 and (
            (m["dna"].get(top) or 0) >= 8.0 or (m["dna"].get(second) or 0) >= 8.0)
    hit = _route_pick(ranked, top, seen, extra=_gem) or _route_pick(ranked, second, seen, extra=_gem)
    if hit:
        picks.append((3, hit[1], hit[0]))

    out = []
    for si, m, _score in picks:
        name, desc = ROUTE_STAGES[si]
        d = m["dna"]
        if si == 0:
            why = f"你的「{top}」偏好最强烈，这部 {top} {d.get(top)} 分、豆瓣 {m['rating']}，最对味。"
        elif si == 1:
            why = f"同样是 {top} 高分（{d.get(top)} 分），换到{REGION_LABEL.get(m['region'], m['region'])}的{'/'.join(m['genres'][:2])}，风味不同。"
        elif si == 2:
            why = f"你的「{second}」也不弱，这部 {second} {d.get(second)} 分，是一次温和的跨界。"
        else:
            why = f"仅 {max(1, int((m.get('rating_count') or 0) / 10000))} 万人标记，豆瓣却有 {m['rating']}，和你的画像暗暗合拍。"
        out.append({"name": name, "desc": desc, "movie": m, "stage_reason": why})
    return out


def similar_movies(movie_id: str, limit=8):
    out = []
    for sid in data.similar(movie_id):
        m = data.movie(sid)
        if m:
            out.append(m)
        if len(out) >= limit:
            break
    return out
