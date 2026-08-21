# -*- coding: utf-8 -*-
"""
影灵 CINE 电影数据库构建 · D3 LLM 加工（v2 重做版）
=====================================================
按 reports/电影数据库构建方案_v1.md §6 严格执行（2026-08-05 重做：
修复与方案的偏离点 + 上轮 trial 暴露的质量/限流问题）。

任务与校验（2026-08-19 起按用户裁定调整：**跳过 tags**，只加工 citation/brief/warn/egg）：
  citation  从 D1 候选 5 句选序号 0-4                            -> 必为候选原文子串；垃圾候选不回退
  brief     summary 改写 ≤60 字                                  -> 长度 + 无新增专名（粗查）
  warn      差评池(votes 加权 top30 差评 + 3星 top10) 聚合        -> ≤30字一句话+≤3要点+每要点≥3证据；差评占比过半(强制)
  egg       长评片段池（片场/原型/拍摄/导演/背后命中段）挖掘       -> text 为所选片段近似子串(≥0.85)，挖不到 null
  tags      【已停用】13 标签（8 感觉 + 5 场景）无依据，2026-08-19 用户裁定不做

通用契约：每步只喂该片自家数据；证据 id 必填，程序回填校验；
断点按电影粒度存 build_task_llm.csv + llm_partial.json。

用法：
  python build_core_llm.py --stage trial        # 10 部试跑（含样卡）
  python build_core_llm.py --stage full         # 全量 590 部（断点续跑，--force 重跑）
  python build_core_llm.py --stage calib        # DNA 校准
  python build_core_llm.py --stage merge        # 回写 movies_core.json（tags 一律置空，不重算相似片）
key 配置: data/task/llm_config.json（base_url/api_key/models；api_key 走环境变量 CINE_LLM_API_KEY 或
本地 data/task/llm_key.local.txt，见 cine/llm.py 同款回退链）
"""
import argparse
import difflib
import json
import logging
import os
import random
import re
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
CORE_JSON = ENRICHED / "movies_core.json"
LLM_PARTIAL = ENRICHED / "llm_partial.json"
LLM_TASK_CSV = ENRICHED / "build_task_llm.csv"
LLM_CONFIG = BASE_DIR / "data" / "task" / "llm_config.json"
SAMPLE_MD_LLM = ENRICHED / "sample_cards_llm.md"
CALIB_JSON = ENRICHED / "dna_calib.json"

# 13 个偏好标签集（方案 §2，mood 8 + scene 5；用户 D2 已过审，改动走 §2 修订记录）
MOOD_TAGS = ["😭 催泪感人", "🎞 细品剧情", "🔥 燃爽过瘾", "😆 轻松爆笑",
             "🧠 烧脑高能", "😱 惊悚刺激", "💔 意难平", "🥰 治愈系"]
SCENE_TAGS = ["🌙 一个人深夜", "🎬 大银幕之选", "👨👩👧 合家欢", "💑 约会氛围", "🛋 周末躺平"]
ALL_TAGS = MOOD_TAGS + SCENE_TAGS

# 标签 -> 证据回填种子词（程序端证据召回，保证真实 cid 与语义相关）
TAG_KW = {
    "😭 催泪感人": r"催泪|泪目|哭了|哭死|看哭|感动|鼻酸|破防|哽咽|泪点|眼眶",
    "🎞 细品剧情": r"剧情|故事|情节|叙事|剧本|细节|人物|塑造|层次|深刻|回味",
    "🔥 燃爽过瘾": r"燃|爽|过瘾|热血|炸裂|燃爆|高潮|刺激|肾上腺素|痛快",
    "😆 轻松爆笑": r"笑|搞笑|好笑|轻松|喜剧|欢乐|笑点|幽默|喜感",
    "🧠 烧脑高能": r"烧脑|高能|反转|悬疑|智商|推理|脑洞|神作|细节控|伏笔",
    "😱 惊悚刺激": r"惊悚|恐怖|吓|害怕|毛骨悚然|头皮发麻|阴森|悬疑气氛|恐惧",
    "💔 意难平": r"意难平|遗憾|难过|心碎|悲剧|悲伤|唏嘘|宿命|哀伤|怅然",
    "🥰 治愈系": r"治愈|温暖|温馨|温柔|暖|抚慰|美好|治愈系|窝心",
    "🌙 一个人深夜": r"安静|深夜|孤独|独自|静谧|氛围|文艺|沉浸|适合一个人|夜里",
    "🎬 大银幕之选": r"大银幕|IMAX|视觉|特效|画面|音效|震撼|视听|场面|调度",
    "👨👩👧 合家欢": r"全家|亲子|孩子|家庭|合家欢|老少咸宜|小孩|家长|阖家",
    "💑 约会氛围": r"爱情|浪漫|甜蜜|情侣|约会|心动|恋爱|糖|少女心",
    "🛋 周末躺平": r"轻松|休闲|下饭|放松|周末|爆米花|不用动脑|解压|放松心情",
}

DNA_DIMS = ["剧情", "演技", "情感", "视听", "节奏"]
MAX_EVIDENCE = 10          # 每标签/每要点最多回填证据数
TRIAL_IDS = ["1291546", "26752088", "3742360", "35267208", "2208890",
             "26709258", "1292722", "1291561", "27010768", "1889243"]
CALIB_N = 30               # 校准抽样片数
MIN_INTERVAL = 12.0       # 全局限速：相邻两次请求最小间隔（秒）。网关实测 ~5 RPM 稳，
                          # 4s 会触发 429 指数退避反而更慢；429 有 RATE_BACKOFF 兜底。
RATE_BACKOFF = 20          # 429 基础退避（秒），随次数加长

BAD_PAT = re.compile(r"(?:https?://|www\.|weixin|微信|QQ|公众号|加我|引流|二维码|代购)", re.I)
EGG_KW = re.compile(r"(?:片场|原型|拍摄|导演|背后|轶事|彩蛋|灵感|真实|改编|创作|花絮|趣闻|幕后|杀青|选角|配乐|编剧)", re.I)
# 高分口碑片（≥8.5）不得出现的质量否定词（避雷只能写门槛/题材/风格/情绪强度类）
HIRATE_BAN = ["空洞", "难看", "烂片", "烂", "垃圾", "低劣", "糟", "失败", "尴尬",
              "无病呻吟", "莫名其妙", "不知所云", "混乱", "硬伤", "平庸", "低幼",
              "脑残", "俗套", "老套", "流水账", "辣眼睛", "翻车", "拉胯", "离谱",
              "难看透顶", "浪费", "敷衍", "粗制滥造", "弱智", "玛丽苏", "装逼",
              "浮夸", "过誉", "匠气", "名不副实", "盛名",
              "逻辑松散", "逻辑混乱", "逻辑跳跃", "画风怪异", "怪异", "无感", "失望", "乏味",
              "无聊", "平淡", "单薄", "肤浅", "浅薄", "做作", "矫情", "别扭",
              "出戏", "跳戏", "不伦不类", "四不像", "狗血", "媚俗", "恶心"]

# ----------------------------- 日志 -----------------------------
def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cine_llm")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / "build_llm.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


log = setup_logger()

# ----------------------------- 数据加载 -----------------------------
def load_data():
    movies = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    comments = pd.read_csv(COMMENTS_CSV, dtype=str).fillna("")
    reviews = pd.read_csv(REVIEWS_CSV, dtype=str).fillna("")
    comments["votes"] = pd.to_numeric(comments["votes"], errors="coerce").fillna(0).astype(int)
    reviews["useful"] = pd.to_numeric(reviews["useful"], errors="coerce").fillna(0).astype(int)
    return movies, comments, reviews


_CODE = {}


def get_data():
    if "comments" not in _CODE:
        _CODE.update(zip(("movies", "comments", "reviews"), load_data()))
    return _CODE


# ----------------------------- LLM 客户端 -----------------------------
_key_idx = [0]                     # 当前使用中的 key 下标（模块级，跨片保持，额度耗尽自动轮换）
_QUOTA_RE = re.compile(r"insufficient_quota|insufficient|quota|balance|credit|欠费|余额|配额|充值|billing", re.I)
_AUTH_RE = re.compile(r"401|invalid.*api.?key|authentication|Unauthorized", re.I)


def _read_backup_keys() -> list[str]:
    """本地备用 key 列表 data/task/llm_keys_backup.txt（每行一个）——不入库/不随提交物。"""
    try:
        p = LLM_CONFIG.parent / "llm_keys_backup.txt"
        if p.exists():
            return [k.strip() for k in p.read_text(encoding="utf-8").splitlines() if k.strip()]
    except Exception:
        pass
    return []


def load_cfg():
    if not LLM_CONFIG.exists():
        log.error("缺少 %s（base_url/api_key/models），D3 无法启动", LLM_CONFIG)
        raise SystemExit(1)
    cfg = json.loads(LLM_CONFIG.read_text(encoding="utf-8"))
    # 与 cine/llm.py 一致：环境变量 -> 本地主 key -> 本地备用 key 列表 -> 配置内联
    keys: list[str] = []
    for k in ([os.environ.get("CINE_LLM_API_KEY")] + [_read_local_key()]
              + _read_backup_keys() + [cfg.get("api_key")]):
        if k and k not in keys:
            keys.append(k)
    if not keys:
        log.error("缺少 api_key（请设置 CINE_LLM_API_KEY 环境变量或 llm_key.local.txt / llm_keys_backup.txt）")
        raise SystemExit(1)
    cfg["_keys"] = keys
    cfg["api_key"] = keys[0]
    log.info("可用 key %d 个（主 key #1 + 备用 %d 个）", len(keys), len(keys) - 1)
    return cfg


def _read_local_key() -> str | None:
    """本地密钥文件 data/task/llm_key.local.txt（单行）——不入库/不随提交物。"""
    try:
        p = LLM_CONFIG.parent / "llm_key.local.txt"
        if p.exists():
            k = p.read_text(encoding="utf-8").strip()
            return k or None
    except Exception:
        pass
    return None


def _make_cli(cfg, idx):
    from openai import OpenAI
    keys = cfg.get("_keys") or [cfg.get("api_key")]
    return OpenAI(api_key=keys[idx], base_url=cfg["base_url"], timeout=180)


def _rotate_key(cfg) -> bool:
    """换到下一个备用 key；已到末尾返回 False。"""
    keys = cfg.get("_keys") or [cfg.get("api_key")]
    if _key_idx[0] + 1 < len(keys):
        _key_idx[0] += 1
        log.warning("当前 key 额度/鉴权失败，轮换到备用 key #%d/%d", _key_idx[0] + 1, len(keys))
        return True
    return False


def _is_quota_or_auth(msg: str) -> bool:
    return bool(_QUOTA_RE.search(msg) or _AUTH_RE.search(msg))


_last_call = [0.0]
TOK = {"in": 0, "out": 0}   # 累计 tokens，供成本估算


def _throttle():
    """全局限速：min_interval 内不连发（缓解 rpm 限流）"""
    wait = MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _extract_json(text):
    """鲁棒提取 JSON 对象：剥围栏 -> 尝试每个 { 到平衡 } 的块（从末尾向前找，优先取最后一块）；
    截断时尝试修复；返回第一个合法解析或 None。"""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    # 收集所有 { 到平衡 } 的块
    blocks = []
    i = 0
    while True:
        i = text.find("{", i)
        if i < 0:
            break
        depth, end = 0, None
        for j in range(i, len(text)):
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        cand = text[i:end] if end else text[i:]
        blocks.append(cand)
        i = end or i + 1
    # 从末尾向前尝试解析
    for cand in reversed(blocks):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            # 截断修复尝试
            fixed = cand.rstrip()
            if not fixed.endswith("}"):
                fixed += "}"
            try:
                return json.loads(fixed)
            except Exception:
                continue
    return None


def chat_json(cfg, sys_prompt, user_prompt, max_tokens=1500, tries=3, max_rounds=4):
    """强制 JSON 输出。主模型 (JSON模式, 纯文本模式) 各 tries 次；
    fallback 仅在主模型全部失败后试一次（个别模型对大请求返回空，主模型优先）。
    429 / 窗口限流 / 额度类错误：轮换备用 key + 指数退避多轮重试（最多 max_rounds 轮）——
    网关对持续批量常返回窗口级限流，退避后即恢复，不能当永久额度耗尽直接放弃。
    每成功一次记录 token 数。返回 dict/None。"""
    main = cfg["models"].get("main", "deepseek-v4-flash")
    fall = cfg["models"].get("fallback")
    combos = [(main, True), (main, False)]
    if fall:
        combos += [(fall, True)]
    rate_hits = 0
    for rnd in range(max_rounds):
        for model, use_json in combos:
            # fallback 模型实测对任何请求都返回空，只象征性试 1 次
            tri = 1 if model != main else tries
            for i in range(tri):
                cli = _make_cli(cfg, _key_idx[0])
                try:
                    _throttle()
                    kw = dict(model=model, temperature=0,
                              messages=[{"role": "system", "content": sys_prompt},
                                        {"role": "user", "content": user_prompt}],
                              max_tokens=max_tokens)
                    if use_json:
                        kw["response_format"] = {"type": "json_object"}
                    r = cli.chat.completions.create(**kw)
                    if r.usage:
                        TOK["in"] += r.usage.prompt_tokens or 0
                        TOK["out"] += r.usage.completion_tokens or 0
                    text = (getattr(r.choices[0].message, "reasoning", None) or
                            r.choices[0].message.content or "").strip()
                    if not text:
                        raise ValueError("empty response")
                    obj = _extract_json(text)
                    if isinstance(obj, dict):
                        return obj
                    raise ValueError("non-dict json")
                except Exception as e:
                    msg = str(e)
                    if _is_quota_or_auth(msg):
                        if _rotate_key(cfg):
                            time.sleep(3)
                            break      # 换 key 后用下一 combo 重试
                        # 所有 key 都报额度类错误：窗口级限流概率大，退避后重置回主 key 整轮重试
                        _key_idx[0] = 0
                        wait = min(45 * (2 ** rnd), 240) + random.uniform(0, 5)
                        log.warning("全部 key 本轮额度类失败(第%d轮)，退避 %.0fs 后重试", rnd + 1, wait)
                        time.sleep(wait)
                        break
                    if "429" in msg or "rpm" in msg or "rate limit" in msg.lower():
                        rate_hits += 1
                        wait = min(RATE_BACKOFF * rate_hits, 120) + random.uniform(0, 5)
                        log.warning("chat_json 限流 429 (%s/%s) 第%d次，退避 %.0fs",
                                    model, "json" if use_json else "text", i + 1, wait)
                        time.sleep(wait)
                    elif "empty response" in msg:
                        wait = min(5 * (2 ** i), 60) + random.uniform(0, 5)
                        log.warning("chat_json %s/%s 第%d次 empty response，退避 %.0fs",
                                    model, "json" if use_json else "text", i + 1, wait)
                        time.sleep(wait)
                    else:
                        wait = 2 * (i + 1) + random.uniform(0, 2)
                        log.warning("chat_json %s/%s 第%d次失败: %s",
                                    model, "json" if use_json else "text", i + 1, msg[:120])
                        time.sleep(wait)
    log.error("chat_json 多轮重试仍失败，放弃本次调用")
    return None


SYS = ("你是电影数据库的加工助手。只依据用户提供的素材作答，不得编造事实。"
       "必须输出合法 JSON（不要 markdown 围栏），字段严格按用户要求。")

# ----------------------------- 素材准备 -----------------------------
def clip(s, n=120):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s[:n]


def prep_comments(comments, mid):
    """返回 (代表评论列表, 差评池, 3星池, 该片全部短评 df, 差评池 id 集, 素材行 id 集)
    方案 §6 tags 输入：20 条代表评论（好/中/差）+ 长评段；warn 输入：votes 加权差评 top30 + 3星 top10。"""
    sub = comments[comments["movie_id"] == mid].copy()
    sub = sub[sub["content"].str.strip() != ""]
    sub = sub[~sub["content"].str.contains(BAD_PAT, na=False)]
    good = sub[sub["category"] == "好评"].sort_values("votes", ascending=False)
    midc = sub[sub["category"] == "一般"].sort_values("votes", ascending=False)
    bad = sub[sub["category"] == "差评"].sort_values("votes", ascending=False)
    rep = []
    for g in good.head(12).itertuples():
        rep.append(f"[{g.comment_id}] {g.star}★ v{g.votes} {clip(g.author, 8)}: {clip(g.content, 110)}")
    for g in midc.head(4).itertuples():
        rep.append(f"[{g.comment_id}] {g.star}★ v{g.votes} {clip(g.author, 8)}: {clip(g.content, 110)}")
    for g in bad.head(4).itertuples():
        rep.append(f"[{g.comment_id}] {g.star}★ v{g.votes} {clip(g.author, 8)}: {clip(g.content, 110)}")
    bad_top30 = bad.head(30)
    bad_pool = [f"[{g.comment_id}] {g.star}★ v{g.votes}: {clip(g.content, 90)}"
                for g in bad_top30.itertuples()]
    bad_ids = set(str(g.comment_id) for g in bad_top30.itertuples())
    mid3_pool = [f"[{g.comment_id}] {g.star}★ v{g.votes}: {clip(g.content, 90)}"
                 for g in midc[midc["star"] == "3"].head(10).itertuples()]
    pool_ids = set()
    for m in rep + bad_pool + mid3_pool:
        mm = re.search(r"\[(\d+)\]", m)
        if mm:
            pool_ids.add(mm.group(1))
    return rep, bad_pool, mid3_pool, sub, bad_ids, pool_ids


def prep_reviews(reviews, mid, tag_seg_n=3):
    """返回 (该片长评 df, useful 排序 df, egg 片段池, tags 长评段素材)
    egg 片段：EGG_KW 命中段上下文 80+120 字并截到句号边界；
    tags 长评段：top 长评各取首句+关键词段（方案：好/中/差+长评段）。"""
    rv = reviews[reviews["movie_id"] == mid].copy()
    rv = rv[rv["content"].str.strip() != ""]
    top = rv.sort_values("useful", ascending=False)
    segs = []
    for r in top.head(8).itertuples():
        body = re.sub(r"\s+", " ", str(r.content))
        for mt in EGG_KW.finditer(body):
            s = max(0, mt.start() - 80)
            seg = body[s:mt.end() + 120]
            if len(seg) >= 20:
                segs.append({"rid": r.review_id, "seg": seg, "useful": int(r.useful)})
            break  # 每篇长评只取第一段命中
    tag_segs = []
    for r in top.head(tag_seg_n).itertuples():
        body = re.sub(r"\s+", " ", str(r.content))
        first = re.split(r"[。！？!?；;\n]+", body)[0][:60]
        kw_seg = ""
        for mt in EGG_KW.finditer(body):
            kw_seg = body[max(0, mt.start() - 40):mt.end() + 60]
            break
        tag_segs.append(f"[R{r.review_id}] u{r.useful} 首句: {first} | 片段: {kw_seg or body[:60]}")
    return rv, top, segs, tag_segs


# ----------------------------- 任务执行 -----------------------------
def _cids_from(lines):
    ids = set()
    for m in lines:
        mm = re.search(r"\[(\d+)\]", m)
        if mm:
            ids.add(mm.group(1))
    return ids


def _evidence_for(tag, pool_lines, sub_df, max_n=MAX_EVIDENCE):
    """证据回填：素材命中优先 -> 全片 top votes 召回补足；最终 <3 条则标签不成立。
    返回证据 cid 列表（真实存在）。"""
    kw = TAG_KW.get(tag)
    got = []
    for m in pool_lines:
        mm = re.search(r"\[(\d+)\]", m)
        if mm and kw and re.search(kw, m):
            got.append(mm.group(1))
    if len(got) < 3 and kw is not None and not sub_df.empty:
        for r in sub_df.sort_values("votes", ascending=False).itertuples():
            if r.comment_id in got:
                continue
            if re.search(kw, r.content):
                got.append(r.comment_id)
            if len(got) >= 3:
                break
    return got[:max_n]


def _parse_tags(obj, rep_lines, sub_df):
    """tags 解析校验（方案：mood≤3 + scene≤2 13 集内 + 每标签≥3 证据 cid）
    LLM 只选标签，证据由程序 TAG_KW 种子词回填（素材行优先 -> 全片 top votes 补足）。"""
    try:
        tags = obj["tags"]
    except (KeyError, TypeError):
        return None
    if not isinstance(tags, dict):
        return None
    mood = [t for t in tags.get("mood", []) if t in MOOD_TAGS][:3]
    scene = [t for t in tags.get("scene", []) if t in SCENE_TAGS][:2]
    out_ev = {}
    for t in mood + scene:
        cids = _evidence_for(t, rep_lines, sub_df)
        if len(cids) >= 3:
            out_ev[t] = cids
    mood = [t for t in mood if t in out_ev]
    scene = [t for t in scene if t in out_ev]
    if not mood and not scene:
        return None
    return {"mood": mood, "scene": scene, "_evidence": out_ev}


def _parse_warn(obj, movie, bad_pool, mid3_pool, sub_df, bad_ids):
    """warn 解析校验（方案：≤30字一句话 + ≤3 要点 + 每要点≥3 证据；
    强制差评占比≥0.5；高分片≥8.5 只许门槛/风格/情绪类）。
    LLM 只做聚合（text+points+佐证原句），证据由程序回填：佐证原句匹配优先 -> 关键词补足。"""
    w = obj.get("warn") if isinstance(obj, dict) else None
    if not isinstance(w, dict):
        return None
    rating = float(movie.get("rating") or 0)
    text = str(w.get("text") or "").strip()
    # 高分片保护：text 出现质量否定词则弃用该句（降级为用首个合法要点替代，不整体否决）
    banned = [w0 for w0 in HIRATE_BAN if w0 in text] if rating >= 8.5 else []
    if banned:
        log.warning("warn 弃用含否决词句: %s (%s)", movie["title"], banned)
        text = ""
    points, all_ev, neg_cnt, tot = [], [], 0, 0
    mid3_ids = {m.group(1) for m in (re.match(r"\[(\d+)\]", x) for x in mid3_pool) if m}
    # 高分片(≥8.5)差评池偏薄，而 prompt 明确让 3星中性评论代表"真实门槛"并权重更高——
    # 故高分片把 差评+3星 合并计为负向证据（防编造的铁律仍在：证据必须真实命中池内评论）；
    # 普通片维持 差评证据 ≥0.5。
    neg_ids = bad_ids | mid3_ids if rating >= 8.5 else bad_ids
    for p in w.get("points") or []:
        if not isinstance(p, dict):
            continue
        pt = clip(p.get("point", ""), 30)
        if not pt:
            continue
        # 高分片保护：含质量否定词的要点直接丢弃（不连累其它合法要点）
        if rating >= 8.5 and any(b0 in pt for b0 in HIRATE_BAN):
            log.warning("warn 要点被高分否决词丢弃: %s (%s)", movie["title"], pt)
            continue
        cids = _warn_evidence(pt, p.get("quote"), bad_pool, mid3_pool, sub_df, bad_ids)
        if len(cids) >= 3:
            points.append({"point": pt, "cids": cids})
            all_ev += cids
            neg_cnt += sum(1 for c in cids if c in neg_ids)
            tot += len(cids)
    if not points:
        return None
    neg_ratio = neg_cnt / tot if tot else 0
    thr = 0.3 if rating >= 8.5 else 0.5
    if neg_ratio < thr:
        log.warning("warn 负向证据占比 %.2f < %.1f 未过校验: %s", neg_ratio, thr, movie["title"])
        return None
    if not text or not 1 <= len(text) <= 30:
        text = points[0]["point"][:30]
    return {"text": text, "points": points, "_neg_ratio": round(neg_ratio, 2),
            "_evidence": all_ev}


# warn 要点证据回填关键词（LLM 聚合 + 程序从差评池/3星池按词召回真实 cid）
WARN_MATCH_KW = ["时长", "冗长", "拖沓", "节奏", "慢", "长", "沉闷", "压抑", "沉重", "煽情",
                 "说教", "俗套", "老套", "平淡", "单薄", "空洞", "混乱", "硬伤", "逻辑",
                 "剧情", "剧本", "演技", "演员", "画风", "人设", "三观", "价值观", "争议",
                 "套路", "刻意", "强行", "突兀", "无聊", "乏味", "爆米花", "粉丝", "路人",
                 "门槛", "看不懂", "3D", "IMAX", "特效", "配乐", "音效", "画面", "剪辑",
                 "结局", "台词", "字幕", "翻译", "配音", "历史", "政治", "改编", "删减",
                 "浮夸", "尴尬", "低幼", "幼稚", "莫名其妙", "不知所云", "鸡汤", "彩蛋",
                 "尿点", "全程", "台词功底", "故事", "情感", "哭", "笑点",
                 "过誉", "匠气", "媚俗", "恶心", "狗血", "自我感动", "暴力", "恐怖",
                 "欣赏不来", "不喜欢", "失望", "盛名", "题材", "情绪", "平复", "烂大街",
                 "没意思", "平庸", "中规中矩", "用力过猛", "尴尬癌", "劝退", "猎奇", "压抑感",
                 "小时", "片长", "历史背景", "不了解", "原作", "原著", "观影门槛", "入戏", "沉浸"]


def _warn_evidence(point, quote, bad_pool, mid3_pool, sub_df, bad_ids):
    """warn 要点证据回填：佐证原句全文匹配优先 -> 关键词召回（双字词优先，池行）
    -> 全片兜底（差评原文优先 -> 3星 -> 其余，votes 排序）。"""
    got = []
    q = re.sub(r"\s+", " ", str(quote or "")).strip()
    if len(q) >= 6 and not sub_df.empty:
        hit = sub_df[sub_df["content"].str.contains(re.escape(q), na=False, regex=True)]
        for g in hit.sort_values("votes", ascending=False).itertuples():
            if g.comment_id not in got:
                got.append(g.comment_id)
            if len(got) >= 3:
                break
    kws = [w for w in WARN_MATCH_KW if w in point]
    if len(got) < 3 and kws:
        # 双字及以上词优先（避免单字词 长/慢/哭 捞入无关评论），不足再退单字
        for kword_set in ([w for w in kws if len(w) >= 2], kws):
            if not kword_set or len(got) >= 3:
                continue
            pat = re.compile("|".join(map(re.escape, kword_set)))
            for line in bad_pool + mid3_pool:
                mm = re.search(r"\[(\d+)\]", line)
                if mm and mm.group(1) not in got and pat.search(line):
                    got.append(mm.group(1))
                if len(got) >= 3:
                    break
    if len(got) < 3 and kws:
        # 全片兜底：差评原文 -> 3星 -> 其余（votes 降序），同样双字词优先
        for kword_set in ([w for w in kws if len(w) >= 2], kws):
            if not kword_set or len(got) >= 3:
                continue
            pat = re.compile("|".join(map(re.escape, kword_set)))
            df = sub_df.copy()
            df["_bad"] = df["comment_id"].isin(bad_ids)
            df["_mid"] = df["category"] == "一般"
            for r in df.sort_values(["_bad", "_mid", "votes"], ascending=False).itertuples():
                if r.comment_id in got:
                    continue
                if pat.search(r.content):
                    got.append(r.comment_id)
                if len(got) >= 3:
                    break
    return got[:MAX_EVIDENCE]


def do_tags(cfg, movie, rep, tag_segs, sub_df):
    """tags（已停用，2026-08-19 用户裁定 13 标签无依据不做；仅保留函数供参考）"""
    rating = float(movie.get("rating") or 0)
    user = (f"电影《{movie['title']}》(豆瓣{rating}分, 类型:{movie['genres']})。\n"
            f"【代表评论】该片好评/一般/差评代表评论(共20条):\n" + "\n".join(rep) +
            f"\n【长评摘录】该片高赞长评首句/关键段:\n" + "\n".join(tag_segs) +
            f"\n\n从标签集选择最贴切的标签（mood 最多3个, scene 最多2个）:\n"
            f"mood 可选: {' / '.join(MOOD_TAGS)}\nscene 可选: {' / '.join(SCENE_TAGS)}\n"
            f"输出 JSON: {{\"tags\": {{\"mood\": [\"标签1\",...], \"scene\": [\"标签2\",...]}}}}")
    obj = chat_json(cfg, SYS, user, max_tokens=1200)
    if not obj:
        return None
    return _parse_tags(obj, rep, sub_df)


def do_warn(cfg, movie, bad_pool, mid3_pool, sub_df, bad_ids):
    """warn（方案 §6：差评池 votes 加权 top30 + 3星 top10）
    LLM 聚合 text+points（可附佐证原句），证据由程序回填；
    强制差评占比≥0.5；高分片（≥8.5）只许门槛/风格/情绪类。"""
    rating = float(movie.get("rating") or 0)
    hint = _warn_hint(bad_pool, mid3_pool)
    rule = ("注意：该片豆瓣评分≥8.5，是公认口碑片，避雷要点只能写「观看门槛/题材/风格/情绪强度」"
            "类（如时长长、情绪沉重、题材门槛），禁止写质量否定（如空洞/难看/烂/逻辑差）。"
            if rating >= 8.5 else
            "若差评占主导，可直接写质量槽点。")
    user = (f"电影《{movie['title']}》(豆瓣{rating}分)。\n"
            f"【差评池】该片前30差评:\n" + "\n".join(bad_pool) +
            f"\n【3星】该片一般(3星)评论:\n" + "\n".join(mid3_pool) +
            f"\n\n聚合观影前避雷: 一句话(≤30字) + 最多3个要点；每个要点可附一句素材评论中的佐证原句"
            f"（原样引用，不引用就留空）。要点措辞尽量复用评论中的原词（如'时长/门槛/沉重'），"
            f"避免自行发明生僻表述。优先采纳票数高的评论，"
            f"3星中性评论代表多数观众的真实门槛，权重可更高。{rule}\n"
            f"规则词频提示（仅供参考，答案必须依据评论原文）: {hint}\n"
            f"没有明显槽点就 \"warn\": {{\"text\": null, \"points\": []}}。\n"
            f"输出 JSON: {{\"warn\": {{\"text\": \"≤30字\", "
            f"\"points\": [{{\"point\": \"要点\", \"quote\": \"佐证原句(可空)\"}}]}}}}")
    obj = chat_json(cfg, SYS, user, max_tokens=1200)
    if not obj:
        return None
    return _parse_warn(obj, movie, bad_pool, mid3_pool, sub_df, bad_ids)


def do_tags_warn(cfg, movie, rep, tag_segs, bad_pool, mid3_pool, sub_df, bad_ids):
    """已废弃：拆分为 do_tags + do_warn 两个独立调用（大 prompt 易触发空响应）。"""
    raise RuntimeError("do_tags_warn 已废弃，请使用 do_tags + do_warn")


# ------------------------- citation + brief -------------------------
_HARD_NOISE = re.compile(r"(?:已被和谐|该影评|影评已被|本文已|图片|截图|未经授权|"
                         r"公众号|删除|审核|作者|原创|转载|版权|来源|出版社|展映单元|"
                         r"发表于|发布于|编者按|文/|http|www\.)", re.I)
_SOFT_NOISE = re.compile(r"^\s*\d+[.、．:]|豆瓣|评分|IMDB|TOP|剧透分割|调亮")


def _noisy(c, soft=False):
    t = c["text"]
    if len(t) > 60 or len(t) < 6:
        return True
    if re.match(r"^\s*\d+[.、．:]", t):
        return True
    if _HARD_NOISE.search(t):
        return True
    if not soft and _SOFT_NOISE.search(t):
        return True
    # 引号不配平 = 句子被切残（D1 切句已按句号/感叹号分界，正文句末标点会被吞掉，故不查收尾）
    if t.count("“") % 2 or t.count("”") % 2 or t.count("「") % 2 or t.count("」") % 2:
        return True
    return False


def _pick_candidates(cands):
    """分层过滤：strict 通过则用之；全滤空则只滤硬垃圾；仍空返回 []（不硬回退）"""
    strict = [c for c in cands if not _noisy(c)]
    if strict:
        return strict
    soft = [c for c in cands if not _noisy(c, soft=True)]
    return soft or []


def do_citation_brief(cfg, movie, cands):
    """一次调用产出 citation（选句）+ brief（改写），分别独立校验；
    无合格候选时 citation 置 null，仅跑 brief。"""
    brief = None
    cands = _pick_candidates(cands)
    if cands:
        lines = [f"[{i}] {c['text']}（出自长评 {c['rid']}，有用 {c['useful']}）"
                 for i, c in enumerate(cands)]
        summary = str(movie.get("summary") or "").strip()
        user = (f"电影《{movie['title']}》。\n"
                f"===== 任务一 一句话影评 =====\n"
                f"以下候选句是从该片高赞长评中切出的原句，"
                f"选 1 句最能代表这部电影气质、最打动人的:\n" + "\n".join(lines) +
                f"\n只许选候选原文（返回序号即可），不许改写；避开技术性说明/剧情摘要式/"
                f"反讽玩梗/自我引用句；优先选完整通顺、有金句感（含比喻/意象/情感）的句子。\n"
                f"===== 任务二 一句话简介 =====\n"
                f"把下面剧情简介改写成 ≤60 字的一句话简介"
                f"（保留核心看点，通俗口语，不要出现简介里没有的人名/事件）:\n{summary}\n"
                f"输出 JSON: {{\"index\": 序号(0-{len(cands) - 1}), \"brief\": \"≤60字\"}}")
        obj = chat_json(cfg, SYS, user, max_tokens=1200)
        if obj:
            try:
                idx = int(obj["index"])
                if 0 <= idx < len(cands):
                    return cands[idx], _parse_brief(obj, movie)
            except (KeyError, TypeError, ValueError):
                pass
            brief = _parse_brief(obj, movie)
            return None, brief
    brief = do_brief(cfg, movie)
    return None, brief


def _name_tokens(text):
    return set(re.findall(r"[《「“]([^》」”]{1,12})[》」”]", text))


def _check_brief_names(movie, summary, brief):
    """专名粗查（方案 §6 brief 校验）：
    ① 书名号/引号词不得出现 summary 没有的新专名；
    ② brief 不得含 summary 中未出现的演员全名。"""
    if _name_tokens(brief) - _name_tokens(summary):
        return False
    for a in movie.get("actors", []):
        if a and len(a) >= 2 and a in brief and a not in summary:
            return False
    return True


def _parse_brief(obj, movie=None):
    b = str(obj.get("brief") or "").strip()
    b = re.sub(r"^“|”$", "", b).strip()
    if not 8 <= len(b) <= 60:
        return None
    if movie is not None:
        summary = str(movie.get("summary") or "")
        if summary and not _check_brief_names(movie, summary, b):
            log.warning("brief 含 summary 外新增专名，拒绝: %s", b[:40])
            return None
    return b


def do_brief(cfg, movie):
    if not str(movie.get("summary") or "").strip():
        return None
    user = (f"电影《{movie['title']}》。把下面剧情简介改写成 ≤60 字的一句话简介"
            f"（保留核心看点，通俗口语，不要出现简介里没有的人名/事件）:\n{movie['summary']}\n"
            f"输出 JSON: {{\"brief\": \"...\"}}")
    obj = chat_json(cfg, SYS, user, max_tokens=300)
    if not obj:
        return None
    return _parse_brief(obj, movie)


# ----------------------------- warn 锚点 -----------------------------
WARN_HINT_SEEDS = ["时长", "长", "慢", "拖沓", "沉闷", "压抑", "门槛", "看不懂", "沉重",
                   "煽情", "说教", "俗套", "逻辑", "剧本", "配乐", "结局", "台词", "3D",
                   "IMAX", "彩蛋", "字幕", "翻译", "配音", "节奏", "冗长", "无聊", "鸡汤"]


def _warn_hint(bad_pool, mid3_pool):
    """规则词频锚点：差评+3星池中高频槽点词 top5"""
    text = "\n".join(bad_pool + mid3_pool)
    cnt = {}
    for w in WARN_HINT_SEEDS:
        c = text.count(w)
        if c >= 2:
            cnt[w] = c
    return "、".join(f"{w}×{c}" for w, c in sorted(cnt.items(), key=lambda x: -x[1])[:5]) or "无"


# ----------------------------- egg -----------------------------
def do_egg(cfg, movie, segs, rv):
    if not segs:
        return None
    lines = [f"[S{i}] (rid {s['rid']} u{s['useful']}) {s['seg']}" for i, s in enumerate(segs)]
    user = (f"电影《{movie['title']}》。以下片段来自该片高赞长评（可能含幕后/原型/创作信息）:"
            f"\n" + "\n".join(lines) +
            "\n若有可确认的「冷知识」（片场轶事/原型出处/创作背景/演员幕后等，必须是片段原文支持的）："
            "你要做的是1) 直接选中一个片段号 S#；2) 从该片段里**逐字摘录**一句原话（不允许改写、"
            "不允许拼接，只可去掉首尾标点/编号）作为冷知识文本；"
            f"3) rid 填该片段标注的 rid。没有就输出 null。禁止编造。\n"
            "输出 JSON: {\"egg\": {\"sid\": \"S0..Sn\", \"text\": \"逐字摘录\", \"rid\": \"...\"}} 或 {\"egg\": null}")
    obj = chat_json(cfg, SYS, user)
    if not obj or not obj.get("egg"):
        return None
    e = obj["egg"]
    text = str(e.get("text") or "").strip()
    text = re.sub(r"^\s*\d+[.、．:]\s*", "", text).strip()
    text = re.sub(r"^[S＄]\d+\s*[:：]?\s*", "", text).strip()
    rid = str(e.get("rid") or "").strip()
    if not (text and rid and 8 <= len(text) <= 60):
        return None
    ids = [s["rid"] for s in segs]
    if rid not in ids:
        return None
    seg = next((s["seg"] for s in segs if s["rid"] == rid), "")
    if not seg:
        return None
    # 校验：text 必须为所选片段（近似）子串（方案阈值 0.85；逐字摘录时直接通过）
    if text in seg:
        return {"text": text, "rid": rid}
    if difflib.SequenceMatcher(None, text, seg).ratio() >= 0.85:
        return {"text": text, "rid": rid}
    log.warning("egg 校验失败: 文本非片段子串(相似度<0.85): %s", text[:40])
    return None


# ----------------------------- DNA 校准 -----------------------------
def do_calib(cfg, movie, rep):
    user = (f"电影《{movie['title']}》。根据以下评论样本，给五维口碑打分(1-10, 一位小数):"
            f" 剧情/演技/情感/视听/节奏。只依据评论内容。\n" + "\n".join(rep) +
            "\n输出 JSON: {\"剧情\": x.x, \"演技\": x.x, \"情感\": x.x, \"视听\": x.x, \"节奏\": x.x}")
    obj = chat_json(cfg, SYS, user, max_tokens=300)
    if not obj:
        return None
    try:
        return {d: float(obj[d]) for d in DNA_DIMS}
    except (KeyError, TypeError, ValueError):
        return None


# ----------------------------- 单部流水线 -----------------------------
def process_movie(cfg, mid, movies, comments, reviews):
    movie = movies[movies["movie_id"] == mid]
    if movie.empty:
        return None
    m = movie.iloc[0]
    rep, bad_pool, mid3_pool, sub_df, bad_ids, _ = prep_comments(comments, mid)
    rv, rv_top, segs, tag_segs = prep_reviews(reviews, mid)
    quotes = json.loads(QUOTES_JSON.read_text(encoding="utf-8")).get(mid, {})
    cands = quotes.get("citation_candidates") or []

    res = {"movie_id": mid, "title": m["title"], "status": "ok", "at": time.strftime("%F %T"),
           "tags": None, "citation": None, "brief": None, "warn": None, "egg": None}

    # 3 次调用：warn / citation+brief / egg（tags 已停用，2026-08-19 用户裁定无依据不做）
    res["warn"] = do_warn(cfg, m, bad_pool, mid3_pool, sub_df, bad_ids)
    log.info("  %s warn %s", mid, "ok" if res["warn"] else "None")
    time.sleep(1)
    res["citation"], res["brief"] = do_citation_brief(cfg, m, cands)
    log.info("  %s citation %s / brief %s", mid, "ok" if res["citation"] else "None",
             "ok" if res["brief"] else "None")
    time.sleep(1)
    res["egg"] = do_egg(cfg, m, segs, rv)
    log.info("  %s egg %s", mid, "ok" if res["egg"] else "None")
    # 状态：citation/brief/warn 核心 3 项缺任意一项记 partial（egg 允许 null），供断点补跑
    missing = [k for k in ("citation", "brief", "warn") if not res[k]]
    res["status"] = "ok" if not missing else "partial"
    return res


# ----------------------------- 断点 / 落盘 -----------------------------
def load_partial():
    if LLM_PARTIAL.exists():
        return json.loads(LLM_PARTIAL.read_text(encoding="utf-8"))
    return {}


def save_partial(partial):
    LLM_PARTIAL.write_text(json.dumps(partial, ensure_ascii=False, indent=1), encoding="utf-8")


def append_task_row(mid, task, status, note=""):
    import csv
    new = not LLM_TASK_CSV.exists()
    with open(LLM_TASK_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["movie_id", "task", "status", "note", "ts"])
        w.writerow([mid, task, status, note, time.strftime("%F %T")])


# ----------------------------- 主流程 -----------------------------
INCLUDE_EGG = False          # --include-egg 时断点判定把 egg 也计入必需项（补跑没挖到 egg 的片）


def _missing_core(r):
    """断点判定缺项：citation/brief/warn 必需；tags 已停用；egg 默认允许 null，
    INCLUDE_EGG 时 egg 也计入必需（用于补跑挖不到冷知识的片，再给一次机会）。"""
    need = ["citation", "brief", "warn"]
    if INCLUDE_EGG:
        need.append("egg")
    return [k for k in need if not (r or {}).get(k)]


def run_fill(ids, force=False):
    cfg = load_cfg()
    model = cfg["models"].get("main", "deepseek-v4-flash")
    log.info("LLM 加工启动: 模型=%s 片数=%d force=%s", model, len(ids), force)
    movies, comments, reviews = get_data().values()
    partial = {} if force else load_partial()
    t0 = time.time()
    for i, mid in enumerate(ids, 1):
        if not force and mid in partial and not _missing_core(partial[mid]):
            continue
        log.info("[%d/%d] %s 加工中...", i, len(ids), mid)
        res = process_movie(cfg, mid, movies, comments, reviews)
        if res is None:
            log.warning("[%d/%d] %s 处理失败(素材不足)", i, len(ids), mid)
            continue
        # 补跑保底：本次某字段生成失败时保留旧的非空值，避免覆盖掉已有成果
        old = partial.get(mid) or {}
        for k in ("tags", "citation", "brief", "warn", "egg"):
            if not res.get(k) and old.get(k):
                res[k] = old[k]
        partial[mid] = res
        save_partial(partial)
        append_task_row(mid, "all", res["status"], "")
        nok = sum(1 for k in ("citation", "brief", "warn", "egg") if res[k])
        log.info("[%d/%d] %s 完成(4 项中 %d 项有值) 累计耗时 %.1fs",
                 i, len(ids), mid, nok, time.time() - t0)
    cost = TOK["in"] * 0.5 / 1e6 + TOK["out"] * 1.5 / 1e6   # 粗估 ¥/1M tokens
    log.info("===== LLM 加工结束: %d 部, 耗时 %.1f min, tokens in=%d out=%d (粗估 ¥%.1f) =====",
             len(ids), (time.time() - t0) / 60, TOK["in"], TOK["out"], cost)


def stage_trial(force=False):
    run_fill(TRIAL_IDS, force)
    write_trial_cards()


def write_trial_cards():
    partial = load_partial()
    movies = get_data()["movies"]
    quotes = json.loads(QUOTES_JSON.read_text(encoding="utf-8"))
    lines = ["# D3 样卡（10 部）· 生成时间 " + time.strftime("%F %T")]
    for mid in TRIAL_IDS:
        r = partial.get(mid)
        if not r:
            continue
        m = movies[movies["movie_id"] == mid].iloc[0]
        q = quotes.get(mid, {})
        lines.append(f"\n===== 《{m['title']}》 {mid} =====")
        t = r["tags"]
        if t:
            ev = t["_evidence"]
            lines.append("tags: " + json.dumps({"mood": t["mood"], "scene": t["scene"]},
                                               ensure_ascii=False) +
                         f" (证据数 {dict((k, len(v)) for k, v in ev.items())})")
        else:
            lines.append("tags: null")
        c = r["citation"]
        lines.append(f"citation: {c['text'][:50]} (rid {c['rid']})" if c else "null")
        lines.append(f"brief: {r['brief']}" if r["brief"] else "null")
        w = r["warn"]
        if w:
            lines.append(f"warn: {w['text']} | 差评占比 {w['_neg_ratio']}")
            for p in w["points"]:
                lines.append(f"   - {p['point']} (证据{len(p['cids'])}条)")
        else:
            lines.append("warn: null")
        e = r["egg"]
        lines.append(f"egg: {e['text']} (rid {e['rid']})" if e else "null")
    SAMPLE_MD_LLM.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("D3 样卡已生成: %s", SAMPLE_MD_LLM)


def stage_full():
    movies = get_data()["movies"]
    run_fill(list(movies["movie_id"]))


def stage_calib():
    cfg = load_cfg()
    movies, comments, reviews = get_data().values()
    dna = json.loads(DNA_JSON.read_text(encoding="utf-8"))
    ids = [m for m in movies["movie_id"] if m in dna]
    random.seed(42)
    sample = random.sample(ids, min(CALIB_N, len(ids)))
    out = {}
    for mid in sample:
        rep, *_ = prep_comments(comments, mid)
        llm = do_calib(cfg, movies[movies["movie_id"] == mid].iloc[0], rep)
        if llm:
            d1 = dna[mid]
            out[mid] = {"d1": {k: d1[k] for k in DNA_DIMS}, "llm": llm}
    from scipy import stats as st
    rows = [(out[mid]["d1"][d], out[mid]["llm"][d]) for mid in out for d in DNA_DIMS]
    rho, p = st.spearmanr([a for a, _ in rows], [b for _, b in rows]) if rows else (None, None)
    CALIB_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("DNA 校准: %d 片 × 5 维, Spearman=%.3f (红线 ≥0.6) %s",
             len(out), rho if rho is not None else -1, "✓" if (rho or 0) >= 0.6 else "✗ 需调规则重跑")


def stage_merge():
    """回写 LLM 字段进 movies_core.json。
    2026-08-19 起：tags 一律置空（用户裁定 13 标签无依据不做）；相似片沿用
    build_core_db 的 0.65dna+0.35genres 版本（tags 空时全权重重算会退化为更弱权重，故不重算）。"""
    core = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    partial = load_partial()
    filled = 0
    for c in core:
        r = partial.get(c["movie_id"])
        if not r:
            continue
        filled += 1
        c["tags"] = {"mood": [], "scene": [], "_evidence": {}}     # 标签停用，一律空
        c["quotes"]["citation"] = r["citation"]
        c["brief"] = r["brief"]
        c["warn"] = r["warn"]
        c["egg"] = r["egg"]
        c["_pending_llm"] = False
        c["build_version"] = f"core-{time.strftime('%Y-%m-%d')}"
    CORE_JSON.write_text(json.dumps(core, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("merge 完成: 回写 %d 部（tags 已置空，相似片沿用既有版）-> %s", filled, CORE_JSON)


def main():
    global INCLUDE_EGG
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="影灵 D3 LLM 加工 v2（按方案 §6 重做）")
    p.add_argument("--stage", required=True, choices=["trial", "full", "calib", "merge"])
    p.add_argument("--force", action="store_true", help="忽略断点全部重跑")
    p.add_argument("--movies", help="指定 movie_id 列表（逗号分隔），供 trial/full 使用")
    p.add_argument("--include-egg", action="store_true",
                   help="断点判定把 egg 也计入必需项（补跑没挖到冷知识的片）")
    args = p.parse_args()
    INCLUDE_EGG = args.include_egg
    if args.stage == "trial":
        stage_trial(args.force)
    elif args.stage == "full":
        if args.movies:
            run_fill([x.strip() for x in args.movies.split(",") if x.strip()], args.force)
        else:
            stage_full()
    elif args.stage == "calib":
        stage_calib()
    elif args.stage == "merge":
        stage_merge()


if __name__ == "__main__":
    main()
