# -*- coding: utf-8 -*-
"""
影灵 CINE 电影数据库构建（Phase-D 规则部分）
=============================================
按 reports/电影数据库构建方案_v1.md 执行（用户已签字）。
读取 movies.csv / movie_comments.csv / movie_reviews.csv + posters/，
产出 data/enriched/ 下的核心文件：
  movies_core.json（核心卡片库，LLM 字段本阶段置 null 待 D3 补充）
  core_dna.json / core_quotes.json（中间产物，留痕可复算）
  similarity.json / comments_fts.db / posters_thumb/*.webp
  _clean_stats.txt（清洗留痕）、sample_cards.md（D2 样张）
  logs/build_report_*.txt（构建质检报告）

用法：
    python build_core_db.py --stage load    # D0 清洗 + 留痕
    python build_core_db.py --stage dna     # D1.2 五维 DNA
    python build_core_db.py --stage quotes  # D1.1 摘录候选
    python build_core_db.py --stage similar # D1.3 相似片矩阵
    python build_core_db.py --stage fts     # D1.4 短评全文索引
    python build_core_db.py --stage thumbs  # D1.5 海报缩略图
    python build_core_db.py --stage sample  # D2 十部样张
    python build_core_db.py --stage build   # 组装 movies_core.json
    python build_core_db.py --stage report  # 构建质检报告
    python build_core_db.py --stage all     # 以上串行
LLM 加工（tags/citation/brief/warn/egg）属 D3，待 key 后另起 build_core_llm.py。
"""
import argparse
import json
import logging
import math
import re
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

from crawler_movie import BASE_DIR, LOG_DIR, MOVIES_CSV
from crawler_reviews import COMMENTS_CSV, REVIEWS_CSV

# ----------------------------- 全局配置 -----------------------------
ENRICHED = BASE_DIR / "data" / "enriched"
DNA_JSON = ENRICHED / "core_dna.json"
QUOTES_JSON = ENRICHED / "core_quotes.json"
SIMILAR_JSON = ENRICHED / "similarity.json"
FTS_DB = ENRICHED / "comments_fts.db"
THUMB_DIR = ENRICHED / "posters_thumb"
POSTER_DIR = BASE_DIR / "data" / "posters"
CORE_JSON = ENRICHED / "movies_core.json"
CLEAN_STATS = ENRICHED / "_clean_stats.txt"
SAMPLE_MD = ENRICHED / "sample_cards.md"
BUILD_REPORT = LOG_DIR / f"build_report_{time.strftime('%Y%m%d')}.txt"

# 方案 §3.5：4 部分类筛选被 403 封禁、走兜底通道的电影
FALLBACK_IDS = {"35267208", "2208890", "26709258", "26354572"}

DNA_DIMS = ["剧情", "演技", "情感", "视听", "节奏"]
# 方案 §7 种子词库 v2（用户审稿扩编：每维 40-55 词；删误伤词"戳/心里"，具体增删见 build log）
SEEDS = {
    "剧情": ["剧情", "故事", "情节", "叙事", "剧本", "编剧", "结构", "结局", "结尾", "反转",
             "伏笔", "铺垫", "逻辑", "主线", "支线", "主题", "立意", "悬念", "设定", "世界观",
             "人物弧光", "故事性", "人物塑造", "人物刻画", "群像", "角色成长", "戏剧冲突",
             "冲突", "命运", "宿命", "内核", "隐喻", "象征", "讽刺", "荒诞", "写实", "现实主义",
             "现实意义", "发人深省", "余味", "回味", "留白", "起承转合", "多线叙事", "时间线",
             "闪回", "倒叙", "插叙", "谜团", "真相", "角色动机", "悲剧", "史诗", "格局",
             "戏剧张力"],
    "演技": ["演技", "演得", "表演", "演员", "主演", "配角", "飙戏", "眼神", "表情", "台词功底",
             "台词", "台词功力", "诠释", "拿捏", "张力", "细腻", "入戏", "面瘫", "用力过猛",
             "教科书", "影帝", "影后", "戏骨", "老戏骨", "演技派", "实力派", "偶像派", "尬演",
             "演技在线", "演技炸裂", "演技封神", "表现力", "微表情", "情绪表达",
             "选角", "卡司", "演员阵容", "出演", "演绎", "人戏合一", "入木三分", "出戏",
             "跳戏", "配音", "声优"],
    "情感": ["感人", "催泪", "泪目", "哭了", "哭死", "哭成狗", "泪崩", "泪流满面", "嚎啕大哭",
             "看哭了", "感动", "温暖", "治愈", "治愈系", "被治愈", "暖心", "破防", "破大防",
             "心疼", "共鸣", "动容", "眼眶湿润", "眼角有泪", "鼻酸", "鼻头一酸", "心酸",
             "温情", "泪点", "揪心", "虐心", "意难平", "触动", "共情", "情绪价值", "后劲",
             "心碎", "难受", "戳心", "扎心", "久久不能平静", "泪眼", "感染力"],
    "视听": ["画面", "摄影", "配乐", "音乐", "原声", "原声带", "音效", "构图", "色彩", "色调",
             "镜头", "长镜头", "美术", "服化道", "特效", "视听", "美学", "光影", "运镜", "剪辑",
             "布景", "视觉", "IMAX", "银幕", "大银幕", "画面感", "质感", "电影感", "布光",
             "灯光", "光线", "氛围感", "调色", "滤镜", "慢动作", "蒙太奇", "转场", "手持",
             "航拍", "实景", "服装", "造型", "道具", "美术设计", "场景", "镜头语言",
             "声音设计", "BGM", "主题曲", "片尾曲", "插曲", "杜比", "环绕声", "视觉冲击",
             "分镜"],
    "节奏": ["节奏", "紧凑", "拖沓", "燃", "爽", "笑点", "名场面", "高潮", "一口气",
                  "一气呵成", "上头", "过瘾", "慢热", "沉闷", "乏味", "尿点", "娱乐性",
                  "爆米花", "下饭", "二刷", "三刷", "刷刷刷", "N刷", "节奏感", "叙事节奏",
                  "剧情张力", "张力", "节奏慢", "节奏快", "酣畅淋漓", "行云流水", "停不下来",
                  "欲罢不能", "上瘾", "笑点密集", "爆笑", "笑死", "搞笑", "幽默", "喜剧",
                  "笑中带泪", "燃点", "高能", "爽片", "解压", "轻松", "紧张刺激",
                  "扣人心弦", "高潮迭起", "快进", "进度条"],
}
STAR_X = {"1": 2, "2": 4, "3": 6, "4": 8, "5": 10}
BAYES_M = 20                    # 贝叶斯平滑伪数
CONF_HI, CONF_MID = 20, 8       # 置信档阈值（命中证据条数）
FALLBACK_WCAP = 7.0             # 兜底通道电影的评论权重上限
EMO_SHRINK = 0.95               # 情感维整体折扣（v2 校准：先验 8.54 溢价，压回与其他维齐平）

# 摘录过滤：联系方式/广告类剔除（非捕获组，避免 pandas str.contains 告警）
BAD_TEXT_PAT = re.compile(r"(?:https?://|www\.|weixin|微信|QQ|公众号|加我|引流)", re.I)
# 差评/吐槽类 warn 草稿种子（样张展示用，D3 由 LLM 聚合替换）
WARN_SEEDS = ["节奏慢", "太慢", "太长", "拖沓", "沉闷", "压抑", "虐心", "看不懂", "门槛",
              "铺垫长", "烂尾", "狗血", "尴尬", "俗套", "说教", "吹捧", "过誉", "失望",
              "老套", "催眠", "致郁", "沉重", "费脑子", "流水账"]

# ----------------------------- 日志 -----------------------------
def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cine_build")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / "build_db.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

log = setup_logger()


# ----------------------------- D0 加载与清洗 -----------------------------
def load_data(write_stats=True):
    """读三表 CSV + 清洗（方案 §3），返回 dict of DataFrame"""
    movies = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    comments = pd.read_csv(COMMENTS_CSV, dtype=str).fillna("")
    reviews = pd.read_csv(REVIEWS_CSV, dtype=str).fillna("")
    stats = [f"原始行数: movies={len(movies)} comments={len(comments)} reviews={len(reviews)}"]

    # 1) 剔除空壳短评（content 为空，方案 §3.1）
    n0 = len(comments)
    comments = comments[comments["content"].str.strip() != ""]
    stats.append(f"剔除空壳短评(content空): {n0 - len(comments)} 条")

    # 2) 空 author 兜底显示名（方案 §3.2）
    n_empty = int((comments["author"].str.strip() == "").sum())
    comments.loc[comments["author"].str.strip() == "", "author"] = "豆瓣用户"
    stats.append(f"短评空 author 改名'豆瓣用户': {n_empty} 条")
    n_empty_r = int((reviews["author"].str.strip() == "").sum())
    reviews.loc[reviews["author"].str.strip() == "", "author"] = "豆瓣影迷"
    stats.append(f"长评空 author 改名'豆瓣影迷': {n_empty_r} 条")

    # 3) 数值化
    for col in ("votes",):
        comments[col] = pd.to_numeric(comments[col], errors="coerce").fillna(0).astype(int)
    for col in ("useful", "useless", "replies"):
        reviews[col] = pd.to_numeric(reviews[col], errors="coerce").fillna(0).astype(int)
    movies["rating"] = pd.to_numeric(movies["rating"], errors="coerce")
    movies["rating_count"] = pd.to_numeric(movies["rating_count"], errors="coerce").fillna(0).astype(int)
    movies["runtime_min"] = movies["runtime"].str.extract(r"(\d+)")[0].astype(float)
    movies["first_lang"] = movies["languages"].str.split("|").str[0].str.strip()

    # 4) 长评时间戳截断（尾部「已编辑」等杂串）
    reviews["publish_time"] = reviews["publish_time"].str[:19]

    # 5) 兜底通道权重封顶标记（votes 值保留原样，DNA 计算时对 fallback 片 w 截断）
    stats.append(f"fallback 兜底通道电影: {FALLBACK_IDS}")

    # 6) region 并入（movies.csv 无该列，从任务清单 movie_tasks.csv 关联）
    task_file = BASE_DIR / "data" / "task" / "movie_tasks.csv"
    if task_file.exists():
        tk = pd.read_csv(task_file, dtype=str).fillna("")
        movies = movies.merge(tk[["movie_id", "region"]].drop_duplicates("movie_id"),
                              on="movie_id", how="left")
        movies["region"] = movies["region"].fillna("")
        stats.append(f"region 关联: {movies['region'].value_counts().to_dict()}")
    else:
        movies["region"] = ""
        stats.append("region 关联: movie_tasks.csv 不存在，置空")

    stats.append(f"用完行数: movies={len(movies)} comments={len(comments)} reviews={len(reviews)}")
    if LIMIT_IDS:
        movies = movies[movies["movie_id"].isin(LIMIT_IDS)].copy()
        stats.append(f"小批量试跑(--movies/--limit): 仅保留 {len(movies)} 部参与 DNA/摘录/组装")
    if write_stats:
        ENRICHED.mkdir(parents=True, exist_ok=True)
        CLEAN_STATS.write_text("\n".join(stats) + "\n", encoding="utf-8")
        log.info("D0 清洗完成，留痕: %s", CLEAN_STATS)
    return {"movies": movies, "comments": comments, "reviews": reviews}


_CODE = {}  # 本次进程内的 DataFrame 缓存
LIMIT_IDS = None   # 小批量试跑：--movies/--limit 指定的 movie_id 子集（None=全量）


def data():
    if not _CODE:
        _CODE.update(load_data())
    return _CODE


# ----------------------------- D1.2 五维 DNA -----------------------------
def _dna_frame(df, text_col, star_col, w_func, pattern_by_dim):
    """向量化：输出 (movie_id, dim) 级的 n / sumwx / sumw 聚合"""
    regions = {}   # (mid, dim) -> [n, sumwx, sumw]
    star_map = df[star_col].map(STAR_X)
    valid = star_map.notna()
    df = df.loc[valid]
    x = star_map[valid].astype(float).values
    mids = df["movie_id"].values
    texts = df[text_col].values
    ws = w_func(df).values
    for dim, pat in pattern_by_dim.items():
        print(f"  ... 扫描维度[{dim}]", flush=True)
        hit = pd.Series(texts).str.contains(pat, case=False, na=False, regex=True).values
        idx = hit.nonzero()[0]
        if idx.size == 0:
            continue
        agg = pd.DataFrame({
            "mid": mids[idx],
            "n": 1,
            "wx": x[idx] * ws[idx],
            "w": ws[idx],
        }).groupby("mid", sort=False).sum()
        for mid, row in agg.iterrows():
            r = regions.setdefault((mid, dim), [0, 0.0, 0.0])
            r[0] += int(row["n"])
            r[1] += float(row["wx"])
            r[2] += float(row["w"])
        print(f"    命中 {int(hit.sum())} 条", flush=True)
    return regions


def stage_dna():
    d = data()
    pattern_by_dim = {dim: "|".join(re.escape(w) for w in ws)
                      for dim, ws in SEEDS.items()}
    t0 = time.time()

    def w_comments(df):
        w = 1 + (1 + df["votes"].clip(lower=0)).map(math.log1p)
        # 兜底通道电影权重封顶（方案 §3.5）
        cap = df["movie_id"].isin(FALLBACK_IDS)
        w.loc[cap] = w.loc[cap].clip(upper=FALLBACK_WCAP)
        return w

    def w_reviews(df):
        w = 1.5 * (1 + (1 + df["useful"].clip(lower=0)).map(math.log1p))
        return w

    log.info("DNA 短评扫描（5 维 × %d 行）", len(d["comments"]))
    reg_c = _dna_frame(d["comments"], "content", "star", w_comments, pattern_by_dim)
    log.info("DNA 长评扫描（5 维 × %d 行）", len(d["reviews"]))
    reg_r = _dna_frame(d["reviews"], "content", "star", w_reviews, pattern_by_dim)

    # 合并短评/长评两套证据
    pool = {}
    for reg in (reg_c, reg_r):
        for key, (n, wx, w) in reg.items():
            p = pool.setdefault(key, [0, 0.0, 0.0])
            p[0] += n
            p[1] += wx
            p[2] += w

    # 先验 = 全库该维加权均值（情感维先验天然偏高 8.45≈说'感动'的评论星级高；
    # v3 校准：EMO_SHRINK 只压先验、不动逐片最终分，避免高分片情感维被系统性打折）
    prior = {}
    for dim in DNA_DIMS:
        tw = sum(v[2] for k, v in pool.items() if k[1] == dim)
        twx = sum(v[1] for k, v in pool.items() if k[1] == dim)
        prior[dim] = twx / tw if tw > 0 else 7.0
    prior["情感"] *= EMO_SHRINK

    movies = data()["movies"]
    result = {}
    for mid in movies["movie_id"]:
        dims, ns, confs = {}, {}, []
        for dim in DNA_DIMS:
            n, wx, w = pool.get((mid, dim), [0, 0.0, 0.0])
            raw = wx / w if w > 0 else 0.0
            score = (n * raw + BAYES_M * prior[dim]) / (n + BAYES_M) if n > 0 else prior[dim]
            dims[dim] = round(score, 1)
            ns[dim] = n
            confs.append("high" if n >= CONF_HI else "mid" if n >= CONF_MID else "low")
        conf = "low" if "low" in confs else "mid" if "mid" in confs else "high"
        result[mid] = {**dims, "_n": ns, "_conf": conf, "_prior": {k: round(v, 2) for k, v in prior.items()}}

    DNA_JSON.parent.mkdir(parents=True, exist_ok=True)
    DNA_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    el = time.time() - t0
    stats = pd.Series([r["_conf"] for r in result.values()]).value_counts().to_dict()
    log.info("DNA 完成: %d 部, 耗时 %.1fs, 置信分布 %s -> %s", len(result), el, stats, DNA_JSON)
    return True


# ----------------------------- D1.1 摘录候选 -----------------------------
def _pick_top(df_movie, strict_len=(30, 180)):
    """按 votes 降序，先严格长度过滤，取不到再放宽"""
    if len(df_movie) == 0:
        return None
    srt = df_movie.sort_values("votes", ascending=False)
    for lo, hi in (strict_len, (10, 300)):
        ok = srt[(srt["content"].str.len() >= lo) & (srt["content"].str.len() <= hi)
                 & (~srt["content"].str.contains(BAD_TEXT_PAT, na=False))]
        ok = ok[(ok["votes"] > 0) | (lo == 10)]  # 放宽档允许 0 票
        if len(ok):
            r = ok.iloc[0]
            return {"cid": r["comment_id"], "text": r["content"], "votes": int(r["votes"]),
                    "star": int(r["star"]) if str(r["star"]).isdigit() else None,
                    "author": r["author"]}
    return None


# 元信息/标题/噪声句：章节标题、编号列表项、作者信息、转载声明、无实质内容句
_QUOTE_NOISE = re.compile(
    r"^\s*\d+[.、．:]|^[（(【\[]|^第[一二三四五六七八九十0-9]+[章节部]|"
    r"(?:原创|作者|文/|来源|转载|版权|公众号|微博|豆瓣影评|出版社|"
    r"北京国际电影节|上海国际电影节|展映单元|发表于|发布于|编者按|未经授权)", re.I)


def _quote_bad(s):
    """判定切句候选是否为残句：超长截断 / 引号未闭合 / 元信息噪声"""
    if not (8 <= len(s) <= 50):
        return True
    if s.count("“") % 2 or s.count("”") % 2 or s.count("「") % 2 or s.count("」") % 2:
        return True
    if _QUOTE_NOISE.search(s):
        return True
    return False


def _quote_candidates(df_rev):
    """每部长评抽 1-2 句候选（程序切句，保证原文子串），全片池取 useful 前 5 候选"""
    cands = []
    for r in df_rev.sort_values("useful", ascending=False).head(5).itertuples():
        body = (r.content or "").strip()
        if len(body) < 50:
            continue
        sentences = [s.strip() for s in re.split(r"[。！？；!?;\n]+", body) if s.strip()]
        picked = []
        for s in sentences:
            if s not in picked and not _quote_bad(s):
                picked.append(s)
            if len(picked) >= 2:
                break
        # 首句优先（保留开头定调），但必须不是残句
        if picked and picked[0] != sentences[0]:
            if not _quote_bad(sentences[0]) and len(picked) < 2:
                picked.insert(0, sentences[0])
        for t in picked[:2]:
            cands.append({"rid": r.review_id, "text": t, "useful": int(r.useful)})
    return cands[:5]


def stage_quotes():
    d = data()
    comments, reviews = d["comments"], d["reviews"]
    result = {}
    for mid in data()["movies"]["movie_id"]:
        sub = comments[comments["movie_id"] == mid]
        good = sub[sub["category"] == "好评"]
        bad = sub[sub["category"] == "差评"]
        up1 = _pick_top(good)
        dn1, dn_from = _pick_top(bad), "差评"
        if dn1 is None:
            mid3 = sub[(sub["category"] == "一般") & (sub["star"] == "3")]
            dn1, dn_from = _pick_top(mid3), "一般"
        rv = reviews[reviews["movie_id"] == mid]
        result[mid] = {"up1": up1, "dn1": dn1, "dn1_from": dn_from if dn1 else "",
                       "citation_candidates": _quote_candidates(rv)}
    QUOTES_JSON.parent.mkdir(parents=True, exist_ok=True)
    QUOTES_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    miss_up = sum(1 for v in result.values() if not v["up1"])
    miss_dn = sum(1 for v in result.values() if not v["dn1"])
    miss_cd = sum(1 for v in result.values() if not v["citation_candidates"])
    log.info("摘录候选完成: up1 缺口 %d, dn1 缺口 %d, citation 候选缺口 %d -> %s",
             miss_up, miss_dn, miss_cd, QUOTES_JSON)
    return True


# ----------------------------- D1.3 相似片矩阵 -----------------------------
def stage_similar():
    d = data()
    movies = d["movies"]
    if not DNA_JSON.exists():
        log.error("缺少 core_dna.json，请先 --stage dna")
        return False
    dna = json.loads(DNA_JSON.read_text(encoding="utf-8"))

    # 向量准备（小批量时仅计算 dna 已覆盖的子集）
    ids = [m for m in movies["movie_id"] if m in dna]
    import numpy as np
    V = np.array([[dna[m][dim] for dim in DNA_DIMS] for m in ids])

    # 方案口径：dna_sim = 1 - dist/maxd（数据驱动最大值）
    from scipy.spatial.distance import pdist
    maxd = float(pdist(V).max()) if len(V) > 1 else 1.0
    G = movies["genres"].apply(lambda s: set(s.split("|")))
    gmap = dict(zip(ids, G))

    result = {}
    w_dna, w_genre = 0.65, 0.35   # D1 版：tags 未产出，D3 后按 §4.3 全权重重跑
    for i, mid in enumerate(ids):
        dist = np.sqrt(((V - V[i]) ** 2).sum(axis=1))
        dsim = 1 - dist / maxd
        sims = []
        gi = gmap[mid]
        for j in range(len(ids)):
            if j == i:
                continue
            gj = gmap[ids[j]]
            jacc = len(gi & gj) / len(gi | gj) if (gi | gj) else 0
            sims.append((w_dna * float(dsim[j]) + w_genre * jacc, ids[j]))
        sims.sort(reverse=True)
        result[mid] = [b for _, b in sims[:8]]
    SIMILAR_JSON.parent.mkdir(parents=True, exist_ok=True)
    SIMILAR_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    log.info("相似片完成: %d 部各 top8 -> %s（注意：tags 未产出，D3 后需 --stage similar 重跑）", len(result), SIMILAR_JSON)
    return True


# ----------------------------- D1.4 短评全文索引 -----------------------------
def stage_fts():
    d = data()
    ENRICHED.mkdir(parents=True, exist_ok=True)
    if FTS_DB.exists():
        FTS_DB.unlink()
    try:
        import jieba
        jieba.setLogLevel(60)
        def token(s):
            toks = [w for w in jieba.lcut(s) if w.strip()]
            bigs = [s[i:i + 2] for i in range(len(s) - 1)]
            seen, out = set(), []
            for t in toks + bigs:      # jieba 词 + 双字 bigram 兜底（任意2字子串可检索）
                if t not in seen:
                    seen.add(t)
                    out.append(t)
            return " ".join(out)
        mode = "jieba+bigram"
    except ImportError:
        token = lambda s: " ".join(s[i:i + 2] for i in range(len(s) - 1))
        mode = "bigram"
    log.info("FTS 分词模式: %s", mode)
    con = sqlite3.connect(FTS_DB)
    con.execute("CREATE VIRTUAL TABLE docs USING fts5("
                "body, cid UNINDEXED, movie_id UNINDEXED, category UNINDEXED,"
                " star UNINDEXED, votes UNINDEXED)")
    rows = []
    for r in d["comments"].itertuples():
        rows.append((token(r.content[:1200]), r.comment_id, r.movie_id,
                     r.category, r.star, int(r.votes)))
        if len(rows) >= 5000:
            con.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", rows)
            rows.clear()
    if rows:
        con.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    # 抽查 20 词
    probes = ["陀螺", "紫霞", "太空电梯", "治愈", "催泪", "演技", "运镜", "彩蛋", "烂尾",
              "名场面", "国粹", "二刷", "看不懂", "值得", "汉斯", "配乐", "力荐",
              "个人秀", "代入感", "封神"]
    hits = {}
    for w in probes:
        n = con.execute("SELECT count(*) FROM docs WHERE docs MATCH ?",
                        (f'"{w}"',)).fetchone()[0]
        if n > 0:
            hits[w] = n
            continue
        # 长词被分词切碎时：直接命中缺失，但要求其全部 2 字窗口均可命中
        bigs = [w[i:i + 2] for i in range(len(w) - 1)]
        ok = all(con.execute("SELECT count(*) FROM docs WHERE docs MATCH ?",
                             (f'"{b}"',)).fetchone()[0] > 0 for b in bigs)
        hits[w] = -1 if ok else 0
    ok = sum(1 for v in hits.values() if v > 0)
    miss = [k for k, v in hits.items() if v == 0]
    bigram_cover = [k for k, v in hits.items() if v == -1]
    con.close()
    log.info("FTS 完成: %d 行 -> %s ; 抽查20词直接命中 %d/20, bigram兜底 %s, 未覆盖 %s",
             len(d["comments"]), FTS_DB, ok, bigram_cover or "无", miss or "无")
    # 供 report 使用
    _CODE["fts_probes"] = hits
    return True


# ----------------------------- D1.5 海报缩略图 -----------------------------
def stage_thumbs():
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        log.error("缺少 Pillow，请先 pip install Pillow")
        return False
    done, fail = 0, 0
    for mid in data()["movies"]["movie_id"]:
        src = POSTER_DIR / f"{mid}.jpg"
        dst = THUMB_DIR / f"{mid}.webp"
        if dst.exists() and dst.stat().st_size > 1000:
            done += 1
            continue
        try:
            im = Image.open(src)
            im.thumbnail((340, 1000))
            im.save(dst, "WEBP", quality=80)
            done += 1
        except Exception as e:
            fail += 1
            log.warning("缩略图失败 %s: %s", mid, e)
    log.info("海报缩略图: 成功 %d / 失败 %d -> %s", done, fail, THUMB_DIR)
    return fail == 0


# ----------------------------- D2 样张 -----------------------------
SAMPLE_PICK = {  # 强制覆盖：华语/欧美/日本/韩国/新片/兜底/冷门
    "1291546": "中华语经典(霸王别姬)", "35267208": "兜底+2023(流浪地球2)",
    "26709258": "兜底+华语动画(罗小黑)", "26752088": "兜底样本对照(我不是药神)",
    "1292722": "欧美经典(泰坦尼克号)", "25662329": "欧美2016动画(疯狂动物城)",
    "1291561": "日本经典(千与千寻)", "27010768": "韩国2019(寄生虫)",
    "25986180": "韩国2016(釜山行)", "2208890": "冷门+兜底(姊姊妹妹站起来)",
}


def _warn_draft(sub_cont):
    counts = {}
    text = "\n".join(sub_cont)
    for w in WARN_SEEDS:
        c = text.count(w)
        if c:
            counts[w] = c
    return sorted(counts.items(), key=lambda x: -x[1])[:5]


def stage_sample():
    d = data()
    movies = d["movies"]
    dna = json.loads(DNA_JSON.read_text(encoding="utf-8"))
    quotes = json.loads(QUOTES_JSON.read_text(encoding="utf-8"))
    similar = json.loads(SIMILAR_JSON.read_text(encoding="utf-8")) if SIMILAR_JSON.exists() else {}
    title_of = dict(zip(movies["movie_id"], movies["title"]))
    lines = ["# D2 样张（10 部） · 生成时间 " + time.strftime("%F %T"),
             "说明：DNA 含命中条数 n 与置信档；warn 为规则词频草稿（D3 由 LLM 聚合替换）。\n"]
    for mid, why in SAMPLE_PICK.items():
        if mid not in dna:
            continue
        mv = movies[movies["movie_id"] == mid].iloc[0]
        dd = dna[mid]
        qq = quotes[mid]
        dna_line = " ".join(f"{dim}{dd[dim]}(n={dd['_n'][dim]})" for dim in DNA_DIMS)
        lines.append(f"\n===== 样张 《{mv['title']}》 {mv['year']} | {why} =====")
        lines.append(f"DNA [{dd['_conf']}]: {dna_line}")
        if qq["up1"]:
            u = qq["up1"]
            lines.append(f"up1 [{u['votes']}票·{u['star']}★·{u['author']}]: {u['text'][:70]}")
        else:
            lines.append("up1: [缺]")
        if qq["dn1"]:
            dn = qq["dn1"]
            lines.append(f"dn1 [{dn['votes']}票·{dn['star']}★·{dn['author']}] 来自{qq['dn1_from']}: {dn['text'][:70]}")
        else:
            lines.append("dn1: [缺]")
        lines.append("citation 候选:")
        for cd in qq["citation_candidates"]:
            lines.append(f"  [useful {cd['useful']}] {cd['text'][:58]}")
        neg = d["comments"][(d["comments"]["movie_id"] == mid)
                            & (d["comments"]["category"].isin(["差评", "一般"]))]
        wdraft = _warn_draft(neg["content"].tolist())
        lines.append("warn 词频草稿: " + ("、".join(f"{w}×{c}" for w, c in wdraft) or "无"))
        sim_names = "、".join(f"{title_of.get(s, s)}" for s in similar.get(mid, [])[:8])
        lines.append(f"相似片: {sim_names}")
    SAMPLE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    log.info("样张已生成 -> %s（共 %d 部）", SAMPLE_MD, sum(1 for k in SAMPLE_PICK if k in dna))
    return True


# ----------------------------- 组装 core -----------------------------
def stage_build():
    d = data()
    movies = d["movies"]
    dna = json.loads(DNA_JSON.read_text(encoding="utf-8"))
    quotes = json.loads(QUOTES_JSON.read_text(encoding="utf-8"))
    similar = json.loads(SIMILAR_JSON.read_text(encoding="utf-8"))
    cnt_c = d["comments"].groupby("movie_id").size()
    cnt_r = d["reviews"].groupby("movie_id").size()
    vote_c = d["comments"].groupby("movie_id")["votes"].sum()
    vote_r = d["reviews"].groupby("movie_id")["useful"].sum()

    out = []
    miss = {"up1": 0, "dn1": 0}
    for m in movies.itertuples():
        mid = m.movie_id
        q = quotes.get(mid, {})
        if not q.get("up1"):
            miss["up1"] += 1
        if not q.get("dn1"):
            miss["dn1"] += 1
        dd = dna[mid]
        out.append({
            "movie_id": mid, "title": m.title, "year": int(m.year) if str(m.year).isdigit() else None,
            "genres": m.genres.split("|"), "countries": m.countries.split("|"),
            "languages": m.languages.split("|"), "first_lang": m.first_lang,
            "region": m.region,
            "director": m.director.split("|"), "writer": m.writer.split("|") if m.writer else [],
            "actors": m.actors.split("|") if m.actors else [],
            "runtime_min": int(m.runtime_min) if pd.notna(m.runtime_min) else None,
            "rating": float(m.rating), "rating_count": int(m.rating_count),
            "summary": m.summary,
            "brief": None,            # D3 LLM
            "poster_thumb": f"posters_thumb/{mid}.webp",
            "poster_full": f"posters/{mid}.jpg",
            "dna": {**{dim: dd[dim] for dim in DNA_DIMS}, "_n": dd["_n"], "_conf": dd["_conf"]},
            "tags": {"mood": [], "scene": [], "_evidence": {}},   # D3 LLM
            "quotes": {"citation": None, "up1": q.get("up1"), "dn1": q.get("dn1"),
                       "dn1_from": q.get("dn1_from", ""),
                       "citation_candidates": q.get("citation_candidates", [])},
            "warn": None,             # D3 LLM
            "egg": None,              # D3 LLM
            "stats": {"comments_total": int(cnt_c.get(mid, 0)),
                      "reviews_total": int(cnt_r.get(mid, 0)),
                      "votes_sum": int(vote_c.get(mid, 0)),
                      "useful_sum": int(vote_r.get(mid, 0))},
            "source_channel": "fallback" if mid in FALLBACK_IDS else "normal",
            "similar_top": similar.get(mid, []),
            "build_version": f"core-D1-{time.strftime('%Y-%m-%d')}",
            "_pending_llm": True,
        })
    CORE_JSON.parent.mkdir(parents=True, exist_ok=True)
    CORE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("movies_core.json 组装完成: %d 部 %.1fMB; up1 缺 %d, dn1 缺 %d -> %s",
             len(out), CORE_JSON.stat().st_size / 1048576, miss["up1"], miss["dn1"], CORE_JSON)
    return True


# ----------------------------- 报告 -----------------------------
def stage_report():
    d = data()
    movies = d["movies"]
    dna = json.loads(DNA_JSON.read_text(encoding="utf-8"))
    quotes = json.loads(QUOTES_JSON.read_text(encoding="utf-8"))
    core = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    thumbs = list(THUMB_DIR.glob("*.webp")) if THUMB_DIR.exists() else []
    lines = ["=" * 64, "影灵电影数据库构建质检报告  " + time.strftime("%F %T"), "=" * 64]

    ids = [c["movie_id"] for c in core]
    lines.append(f"\n[1] core 对象 {len(core)} 部, 主键唯一 {len(set(ids))} (目标590/590)")
    lines.append(f"[2] DNA 覆盖: {sum(1 for m in ids if m in dna)}/590")
    confs = pd.Series([dna[m]['_conf'] for m in ids]).value_counts().to_dict()
    low_share = confs.get("low", 0) / len(ids)
    lines.append(f"    置信分布 {confs} ; low 占比 {low_share:.1%} (红线 ≤15%) {'✓' if low_share <= 0.15 else '✗'}")
    dmeans = pd.Series([sum(dna[m][k] for k in DNA_DIMS) / 5 for m in ids])
    rho = pd.Series(dmeans.values).corr(pd.Series(movies.set_index('movie_id')['rating'][ids].values), method="spearman")
    lines.append(f"    DNA 总均值 vs 豆瓣评分 Spearman = {rho:.3f} (红线 ≥0.4) {'✓' if rho >= 0.4 else '✗'}")
    lines.append("\n[3] 常识对照（样片 DNA 最高点，人工过一遍）:")
    for mid in SAMPLE_PICK:
        if mid in dna:
            dd = dna[mid]
            order = sorted(DNA_DIMS, key=lambda k: -dd[k])
            top, gap = order[0], dd[order[0]] - dd[order[1]]
            top_txt = f"{top}≈{order[1]}" if gap < 0.15 else top
            t = movies[movies['movie_id'] == mid].iloc[0]
            lines.append(f"    {t['title'][:12]:<14} 豆瓣{t['rating']} | 各维 { ' '.join(f'{k}{dd[k]}' for k in DNA_DIMS) } | 顶维: {top_txt}")
    lines.append(f"\n[4] 摘录: up1 非空 {sum(1 for m in ids if quotes[m]['up1'])}/590, "
                 f"dn1 非空 {sum(1 for m in ids if quotes[m]['dn1'])}/590 "
                 f"(其中来自'一般'类 {sum(1 for m in ids if quotes[m]['dn1_from']=='一般')} 部), "
                 f"citation 候选非空 {sum(1 for m in ids if quotes[m]['citation_candidates'])}/590")
    lines.append(f"[5] 海报缩略图: {len(thumbs)}/590 {'✓' if len(thumbs) == 590 else '✗'}")
    if "fts_probes" in _CODE:
        hp = _CODE["fts_probes"]
        direct = sum(1 for v in hp.values() if v > 0)
        cover = sum(1 for v in hp.values() if v == -1)
        miss = [k for k, v in hp.items() if v == 0]
        lines.append(f"[6] FTS 抽查 直接命中 {direct}/20 + bigram兜底 {cover} -> 未覆盖 {miss or '无'}")
    sim_all = json.loads(SIMILAR_JSON.read_text(encoding="utf-8")) if SIMILAR_JSON.exists() else {}
    lines.append(f"[7] 相似片: {sum(1 for m in ids if len(sim_all.get(m, [])) == 8)}/590 部满 8 条")
    lines.append(f"\n[注意] 阶段为 D1 规则版：tags/citation/brief/warn/egg 字段为 null，"
                 f"待 D3 LLM 加工；相似片为 dna+genres 版本，D3 后需重跑 similar。")
    text = "\n".join(lines)
    BUILD_REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)
    log.info("报告已保存: %s", BUILD_REPORT)
    return True


# ----------------------------- 入口 -----------------------------
def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="影灵电影数据库构建（规则部分）")
    parser.add_argument("--stage", required=True,
                        choices=["load", "dna", "quotes", "similar", "fts",
                                 "thumbs", "sample", "build", "report", "all"])
    parser.add_argument("--movies", help="小批量试跑：逗号分隔的 movie_id 子集（如 1291546,35267208）")
    parser.add_argument("--limit", type=int, help="小批量试跑：仅处理 movies.csv 前 N 部")
    args = parser.parse_args()

    global LIMIT_IDS
    if args.movies:
        LIMIT_IDS = [x.strip() for x in args.movies.split(",") if x.strip()]
    elif args.limit:
        movies_all = pd.read_csv(MOVIES_CSV, dtype=str)
        LIMIT_IDS = set(movies_all["movie_id"].head(args.limit))
    if LIMIT_IDS:
        log.info("小批量试跑模式：%d 部 (%s)", len(LIMIT_IDS), ",".join(LIMIT_IDS) if isinstance(LIMIT_IDS, list) else "前N部")

    ok = True
    if args.stage in ("load", "all"):
        df = load_data()
        print("\n".join(CLEAN_STATS.read_text(encoding="utf-8").splitlines()))
    if args.stage in ("dna", "all"):
        ok &= bool(stage_dna())
    if args.stage in ("quotes", "all"):
        ok &= bool(stage_quotes())
    if args.stage in ("similar", "all"):
        ok &= bool(stage_similar())
    if args.stage in ("fts", "all"):
        ok &= bool(stage_fts())
    if args.stage in ("thumbs", "all"):
        ok &= bool(stage_thumbs())
    if args.stage in ("sample", "all"):
        ok &= bool(stage_sample())
    if args.stage in ("build", "all"):
        ok &= bool(stage_build())
    if args.stage in ("report", "all"):
        ok &= bool(stage_report())
    log.info("===== 完成，整体状态 %s =====", "OK" if ok else "有失败环节")


if __name__ == "__main__":
    main()
