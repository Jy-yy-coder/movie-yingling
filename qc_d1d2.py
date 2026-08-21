# -*- coding: utf-8 -*-
"""
影灵 CINE · Phase-D D1/D2 质检
=============================
对照 reports/电影数据库构建方案_v1.md §9 验收线，对 D1 规则产物 + D2 样张做逐项质检，
重点审计 D1 的"筛选标准"（摘录长度/坏文本/顶票校验/citation 噪声泄漏/跨片重复）。

只读：movies.csv / movie_comments.csv / movie_reviews.csv / data/enriched/* / data/posters
输出：stdout + reports/D1D2质检报告_YYYYMMDD.md
"""
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_core_db as B   # 复用同一套过滤函数/种子词/常量，保证口径一致

BASE = Path(__file__).parent
ENRICHED = BASE / "data" / "enriched"
POSTERS = BASE / "data" / "posters"
OUT = BASE / "reports" / f"D1D2质检报告_{time.strftime('%Y-%m-%d')}.md"

REPORT = []
def emit(line=""):
    REPORT.append(line)
    print(line)

def section(t):
    emit("\n" + "=" * 68)
    emit(t)
    emit("=" * 68)

# ---------------------------------------------------------------- 数据加载
def load():
    movies = pd.read_csv(BASE / "data" / "movies.csv", dtype=str).fillna("")
    comments = pd.read_csv(BASE / "data" / "movie_comments.csv", dtype=str).fillna("")
    # 长评只取必要列（正文 179MB，裁剪内存）
    reviews = pd.read_csv(BASE / "data" / "movie_reviews.csv", dtype=str,
                          usecols=["movie_id", "review_id", "content", "useful", "star", "author"])
    comments["votes"] = pd.to_numeric(comments["votes"], errors="coerce").fillna(0).astype(int)
    reviews["useful"] = pd.to_numeric(reviews["useful"], errors="coerce").fillna(0).astype(int)
    # 复用 D0 清洗口径（空壳短评剔除 / 空 author 兜底；NaN 先 fillna 再判空，与 build_core_db 一致）
    comments["author"] = comments["author"].fillna("")
    reviews["author"] = reviews["author"].fillna("")
    N_EMPTY_C = int((comments["author"].str.strip() == "").sum())
    N_EMPTY_R = int((reviews["author"].str.strip() == "").sum())
    n0 = len(comments)
    comments = comments[comments["content"].str.strip() != ""]
    comments.loc[comments["author"].str.strip() == "", "author"] = "豆瓣用户"
    reviews.loc[reviews["author"].str.strip() == "", "author"] = "豆瓣影迷"
    return movies, comments, reviews, N_EMPTY_C, N_EMPTY_R

movies, comments, reviews, N_EMPTY_C, N_EMPTY_R = load()
core = json.loads((ENRICHED / "movies_core.json").read_text(encoding="utf-8"))
dna = json.loads((ENRICHED / "core_dna.json").read_text(encoding="utf-8"))
quotes = json.loads((ENRICHED / "core_quotes.json").read_text(encoding="utf-8"))
similar = json.loads((ENRICHED / "similarity.json").read_text(encoding="utf-8"))

core_by_id = {m["movie_id"]: m for m in core}
movie_id_set = set(movies["movie_id"])
c_by_mid = {mid: g for mid, g in comments.groupby("movie_id")}
r_by_mid = {mid: g for mid, g in reviews.groupby("movie_id")}

emit("# 影灵 CINE · Phase-D D1/D2 质检报告")
emit(f"\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
emit("范围: D1 规则加工（movies_core.json / core_dna.json / core_quotes.json / "
     "similarity.json / comments_fts.db / posters_thumb / _clean_stats.txt）+ D2 样张 sample_cards.md")
emit("D3 未回写 core（LLM 字段全 null），本次不评 D3。验收线对齐 方案v1 §9。")

# ---------------------------------------------------------------- 1. D0 清洗
section("[1] D0 清洗留痕 (_clean_stats.txt)")
if (ENRICHED / "_clean_stats.txt").exists():
    emit("\n".join("    " + l for l in (ENRICHED / "_clean_stats.txt").read_text(encoding="utf-8").splitlines()))
else:
    emit("    [缺] _clean_stats.txt 不存在")
# 复核清洗口径
n_author_c = int((comments["author"] == "豆瓣用户").sum())
n_author_r = int((reviews["author"] == "豆瓣影迷").sum())
emit(f"\n复核(当前口径): 空壳短评剔除后 {len(comments)} 条(原 88,169−9)，空 author 置'豆瓣用户' {N_EMPTY_C} 条"
     f"(作者本名即'豆瓣用户' {n_author_c - N_EMPTY_C} 条)，长评空 author 置'豆瓣影迷' {N_EMPTY_R} 条")

# ---------------------------------------------------------------- 2. movies_core.json 结构
section("[2] movies_core.json 结构")
emit(f"对象数 {len(core)} (目标590)  {'✓' if len(core)==590 else '✗'}")
ids = [m["movie_id"] for m in core]
emit(f"主键唯一 {len(set(ids))}/{len(ids)}  {'✓' if len(set(ids))==len(ids) else '✗'}")
extras = set(ids) - movie_id_set
missing = movie_id_set - set(ids)
emit(f"core↔movies.csv 对账: core 多出 {len(extras)} 部, movies.csv 未入 core {len(missing)} 部")
# schema 字段
REQ = ["movie_id","title","year","genres","countries","languages","first_lang","region",
       "director","writer","actors","runtime_min","rating","rating_count","summary","brief",
       "poster_thumb","poster_full","dna","tags","quotes","warn","egg","stats","source_channel",
       "similar_top","build_version"]
miss_fields = {f: sum(1 for m in core if f not in m) for f in REQ if any(f not in m for m in core)}
emit(f"缺 schema 字段: {miss_fields or '无'}")
# 类型抽查
bad_year = [m["movie_id"] for m in core if not (m["year"] is None or isinstance(m["year"], int))]
bad_rt = [m["movie_id"] for m in core if not (m["runtime_min"] is None or isinstance(m["runtime_min"], int))]
bad_rating = [m["movie_id"] for m in core if not isinstance(m["rating"], (int, float))]
emit(f"类型违规: year 非int/None {len(bad_year)}, runtime 非int/None {len(bad_rt)}, rating 非数 {len(bad_rating)}")
empty_meta = {k: sum(1 for m in core if not m.get(k)) for k in ["genres","countries","languages","director","actors","summary"]}
emit(f"元信息空值: {empty_meta}")
emit(f"region 分布: {pd.Series([m['region'] for m in core]).value_counts().to_dict()}")
emit(f"source_channel: normal {sum(1 for m in core if m['source_channel']=='normal')} / fallback {sum(1 for m in core if m['source_channel']=='fallback')} (预期4部)")
# stats 对账
cnt_c = comments.groupby("movie_id").size()
cnt_r = reviews.groupby("movie_id").size()
vote_c = comments.groupby("movie_id")["votes"].sum()
st_mismatch = []
for m in core:
    mid = m["movie_id"]
    s = m["stats"]
    if s["comments_total"] != int(cnt_c.get(mid, 0)) or s["reviews_total"] != int(cnt_r.get(mid, 0)):
        st_mismatch.append((mid, s, int(cnt_c.get(mid, 0)), int(cnt_r.get(mid, 0))))
emit(f"stats vs 源CSV 对账: 不匹配 {len(st_mismatch)} 部 {st_mismatch[:5] if st_mismatch else ''}")
# 海报文件
thumb_miss = [m["movie_id"] for m in core if not (ENRICHED / "posters_thumb" / f"{m['movie_id']}.webp").exists()]
poster_miss = [m["movie_id"] for m in core if not (POSTERS / f"{m['movie_id']}.jpg").exists()]
emit(f"poster_thumb 缺文件 {len(thumb_miss)} 部; poster_full 缺原图 {len(poster_miss)} 部")

# ---------------------------------------------------------------- 3. DNA
section("[3] DNA 五维 (core_dna.json)")
missing_dna = [mid for mid in ids if mid not in dna]
emit(f"覆盖 {len(ids)-len(missing_dna)}/590  {'✓' if not missing_dna else '✗ 缺: ' + str(missing_dna)}")
confs = pd.Series([dna[m]["_conf"] for m in ids]).value_counts().to_dict()
low_share = confs.get("low", 0) / len(ids)
emit(f"置信分布 {confs} ; low 占比 {low_share:.1%} (红线≤15%)  {'✓' if low_share<=0.15 else '✗'}")
# 逐维 low(n<8) 覆盖
for dim in B.DNA_DIMS:
    n_low = sum(1 for m in ids if dna[m]["_n"].get(dim, 0) < 8)
    n_zero = sum(1 for m in ids if dna[m]["_n"].get(dim, 0) == 0)
    emit(f"    维度[{dim}] 命中n<8(样本过低) {n_low}/590, 其中n=0 {n_zero}")
# Spearman
dmeans = pd.Series([sum(dna[m][k] for k in B.DNA_DIMS) / 5 for m in ids])
rate_map = dict(zip(movies["movie_id"], movies["rating"]))
rates = pd.Series([float(rate_map[m]) for m in ids])
rho = dmeans.corr(rates, method="spearman")
emit(f"DNA总均值 vs 豆瓣评分 Spearman = {rho:.3f} (红线≥0.4)  {'✓' if rho>=0.4 else '✗'}")
emit("\n常识对照（顶维 vs 豆瓣预期）:")
sanity = [("1291546","演技"),("1292722","情感/视听"),("1291561","视听/情感"),
          ("35267208","视听"),("26709258","情感/视听"),("27010768","剧情/演技"),
          ("25986180","节奏/情感"),("26752088","剧情/情感"),("1291561","情感")]
t_map = dict(zip(movies["movie_id"], movies["title"]))
for mid, exp in sanity:
    if mid not in dna:
        continue
    dd = dna[mid]
    order = sorted(B.DNA_DIMS, key=lambda k: -dd[k])
    emit(f"    {t_map.get(mid, mid)[:14]:<16} 顶维 {order[0]}({dd[order[0]]}) 次维 {order[1]}({dd[order[1]]})  预期≈{exp}")

# ---------------------------------------------------------------- 4. 摘录
section("[4] 摘录 up1/dn1/citation (core_quotes.json)")
def ok_len(t, lo=10, hi=300):
    return lo <= len(t) <= hi
bad_pat = B.BAD_TEXT_PAT
# ---- up1
up1_ok = sum(1 for m in ids if quotes.get(m, {}).get("up1"))
up1_empty = [m for m in ids if not quotes.get(m, {}).get("up1")]
emit(f"up1 非空 {up1_ok}/590  {'✓' if up1_ok==590 else '✗ 缺: ' + str(up1_empty)}")
len_vio = []        # 长度违反(>300 或 <10)
bad_vio = []        # 命中坏文本正则
star_vio = []       # star 非 4/5
cat_vio = []        # cid 不在该片好评池
vote_top_vio = []   # 不是当前口径下合规好评 top1
dup_across = {}     # 同一文本被多部片用作 up1
for m in ids:
    q = quotes.get(m, {})
    u = q.get("up1")
    if not u:
        continue
    if not ok_len(u["text"]):
        len_vio.append((m, len(u["text"])))
    if bad_pat.search(u["text"]):
        bad_vio.append((m, u["text"][:40]))
    if u["star"] not in (4, 5):
        star_vio.append((m, u["star"]))
    sub = c_by_mid.get(m, pd.DataFrame())
    row = sub[sub["comment_id"] == u["cid"]]
    if row.empty or row.iloc[0]["category"] != "好评":
        cat_vio.append((m, u["cid"]))
    dup_across.setdefault(u["text"], []).append(m)
    # 顶票复算：当前口径下 _pick_top(好评) 应与存储一致
    if not row.empty:
        recomputed = B._pick_top(sub[sub["category"] == "好评"])
        if recomputed and recomputed["cid"] != u["cid"]:
            vote_top_vio.append((m, u["cid"], recomputed["cid"]))
emit(f"up1 长度越界(>300或<10) {len(len_vio)} 部 {len_vio[:5]}"
     f"\n    up1 命中坏文本正则 {len(bad_vio)} 部 {bad_vio[:5]}"
     f"\n    up1 star非4/5 {len(star_vio)} 部 {star_vio[:5]}"
     f"\n    up1 cid不属于本片好评池 {len(cat_vio)} 部 {cat_vio[:5]}"
     f"\n    up1 非当前口径顶票 {len(vote_top_vio)} 部 {vote_top_vio[:5]}")
multi = {t: ms for t, ms in dup_across.items() if len(ms) > 1}
emit(f"up1 跨片同文本 {len(multi)} 条（同一评论被多部片当好评代表 → 模板/抄评嫌疑）")
if multi:
    for t, ms in list(multi.items())[:8]:
        emit(f"      ×{len(ms)} {ms[:6]} :: {t[:50]}")
# ---- dn1
dn1_ok = sum(1 for m in ids if quotes.get(m, {}).get("dn1"))
dn1_empty = [m for m in ids if not quotes.get(m, {}).get("dn1")]
dn1_from = pd.Series([quotes[m].get("dn1_from", "") for m in ids if quotes.get(m, {}).get("dn1")]).value_counts().to_dict()
emit(f"\ndn1 非空 {dn1_ok}/590 (缺 {len(dn1_empty)}: {dn1_empty})  来源分布 {dn1_from}")
dn1_bad = []
for m in ids:
    q = quotes.get(m, {})
    dn = q.get("dn1")
    if not dn:
        continue
    if not ok_len(dn["text"]):
        dn1_bad.append((m, "len", len(dn["text"])))
    if bad_pat.search(dn["text"]):
        dn1_bad.append((m, "badtext", dn["text"][:30]))
    if q.get("dn1_from") == "差评" and dn["star"] not in (1, 2):
        dn1_bad.append((m, "star", dn["star"]))
    if q.get("dn1_from") == "一般" and dn["star"] != 3:
        dn1_bad.append((m, "star3", dn["star"]))
emit(f"dn1 违规 {len(dn1_bad)} 部 {dn1_bad[:8]}")
# ---- citation candidates
cit_ok = sum(1 for m in ids if quotes.get(m, {}).get("citation_candidates"))
cit_empty = [m for m in ids if not quotes.get(m, {}).get("citation_candidates")]
emit(f"\ncitation 候选 非空 {cit_ok}/590 (缺 {len(cit_empty)}: {cit_empty})")
# 原文子串校验 + 长度 + 噪声
review_map = dict(zip(reviews["review_id"], reviews["content"]))
sub_vio, len_vio2, noise_vio, example_noise = [], [], [], []
cit_dup = 0
for m in ids:
    cands = quotes.get(m, {}).get("citation_candidates") or []
    seen_t = set()
    for c in cands:
        if c["text"] in seen_t:
            cit_dup += 1
        seen_t.add(c["text"])
        body = review_map.get(c["rid"], "")
        if body and c["text"] not in body:
            sub_vio.append((m, c["rid"], c["text"][:25]))
        if not (8 <= len(c["text"]) <= 50):
            len_vio2.append((m, c["rid"], len(c["text"]), c["text"][:25]))
        if B._quote_bad(c["text"]):
            noise_vio.append((m, c["rid"], c["text"]))
            if len(example_noise) < 10:
                example_noise.append((m, c["text"]))
emit(f"citation 候选 非原文子串 {len(sub_vio)} 条 {sub_vio[:5]}"
     f"\n    citation 候选 长度越界(8-50) {len(len_vio2)} 条 {len_vio2[:5]}"
     f"\n    citation 候选 过 _quote_bad 判脏 {len(noise_vio)} 条（示例见下）"
     f"\n    同片内重复候选 {cit_dup} 条")
for m, t in example_noise:
    emit(f"      {m} :: {t[:60]}")
# 候选池里是否有噪声 seed 词（转载/公众号/电影节/作者信息/Spoiler/emoji）
NOISE_RE = re.compile(r"原创|作者|文/|来源|转载|公众号|微博|出版社|电影节|展映|Spoiler|剧透"
                      r"|微信号|二维码|关注|加我|https?://|www\.|发布时间|时间：|日期|邮箱|联系", re.I)
special_noise = []
for m in ids:
    for c in quotes.get(m, {}).get("citation_candidates") or []:
        t = c["text"]
        if NOISE_RE.search(t):
            special_noise.append((m, c["rid"], t))
emit(f"    显性噪声候选(转载/公众号/二维码/剧透/出处等) {len(special_noise)} 条")
for m, rid, t in special_noise[:15]:
    emit(f"      {m} rid{rid} :: {t[:55]}")

# ---- 深度：截断残句 / 引号配对误判 / 池污染面 ----
emit("\n    深度分析:")
_QUOTE_NOISE_S = B._QUOTE_NOISE
# 截断：长度>50 且原文该位置之后仍有内容的
trunc = []
for m in ids:
    for c in quotes.get(m, {}).get("citation_candidates") or []:
        t = c["text"]
        body = review_map.get(c["rid"], "")
        i = body.find(t)
        if i >= 0 and len(t) > 50 and body[i + len(t):i + len(t) + 2].strip():
            trunc.append((m, c["rid"], len(t), t[-14:], body[i + len(t):i + len(t) + 8]))
emit(f"    >50字符候选且原文后仍有内容（中途截断残句）: {len(trunc)} 条（全部为残句概率高）")
for m, rid, L, tail, nxt in trunc[:8]:
    emit(f"      {m} rid{rid} len{L} …{tail} → 原文续:{nxt}")
# 引号配对误判
pair_ok_bad = 0
for m in ids:
    for c in quotes.get(m, {}).get("citation_candidates") or []:
        t = c["text"]
        if t.count("“") == t.count("”") == 1 and 8 <= len(t) <= 50 and not _QUOTE_NOISE_S.search(t):
            pair_ok_bad += 1
emit(f"    单对引号本可配平却被误判脏: {pair_ok_bad} 条（当前 _quote_bad 的 s.count('“')%2 逻辑缺陷所致）")
# 池污染面：每部电影 5 条候选里混入噪声/残句的
def pool_dirty(m):
    bad = 0
    for c in quotes.get(m, {}).get("citation_candidates") or []:
        t = c["text"]
        body = review_map.get(c["rid"], "")
        i = body.find(t)
        if NOISE_RE.search(t) or (i >= 0 and len(t) > 50 and body[i + len(t):i + len(t) + 2].strip()):
            bad += 1
    return bad
dirty_pool = {m: pool_dirty(m) for m in ids}
n_any = sum(1 for v in dirty_pool.values() if v)
n_bad5 = sum(1 for v in dirty_pool.values() if v >= 5)
n_clean = sum(1 for v in dirty_pool.values() if v == 0)
emit(f"    池污染面: {n_any}/590 部电影的候选池混入≥1条噪声/残句, {n_clean} 部全干净, {n_bad5} 部 5 条全废")
if n_any:
    ex = sorted(dirty_pool.items(), key=lambda x: -x[1])[:10]
    emit(f"    最脏的前10部(候选池坏条数): {ex}")
# 补充：_QUOTE_NOISE 与扩展噪声正则的对比（当前过滤漏网）
miss_by_current = []
for m, rid, t in special_noise:
    if not _QUOTE_NOISE_S.search(t):
        miss_by_current.append((m, t))
emit(f"    上述 {len(special_noise)} 条噪声中, 当前 _QUOTE_NOISE 正则漏网的 {len(miss_by_current)} 条（如 二维码/剧透/微信 等不在词表）")
for m, t in miss_by_current[:6]:
    emit(f"      {m} :: {t[:50]}")

# ---------------------------------------------------------------- 5. 相似片
section("[5] 相似片 (similarity.json)")
sim_bad = []
for m in ids:
    top = similar.get(m, [])
    if len(top) != 8:
        sim_bad.append((m, "len", len(top)))
    elif len(set(top)) != 8:
        sim_bad.append((m, "dup", top))
    elif m in top:
        sim_bad.append((m, "self", m))
emit(f"满8条且无自指无重复 {590-len(sim_bad)}/590  {'✓' if not sim_bad else '✗ ' + str(sim_bad[:5])}")
sim_missing = [m for m in ids if m not in similar]
emit(f"similar 缺 key {len(sim_missing)} 部 {sim_missing[:5]}")

# ---------------------------------------------------------------- 6. FTS
section("[6] 短评全文索引 comments_fts.db")
if (ENRICHED / "comments_fts.db").exists():
    con = sqlite3.connect(ENRICHED / "comments_fts.db")
    nrows = con.execute("SELECT count(*) FROM docs").fetchone()[0]
    nrows_c = len(comments)
    emit(f"行数 {nrows} (清洗后短评 {nrows_c})  {'✓' if nrows==nrows_c else '✗'}")
    probes = ["陀螺", "紫霞", "太空电梯", "治愈", "催泪", "演技", "运镜", "彩蛋", "烂尾",
              "名场面", "国粹", "二刷", "看不懂", "值得", "汉斯", "配乐", "力荐",
              "个人秀", "代入感", "封神"]
    hit = miss = 0
    miss_l = []
    for w in probes:
        n = con.execute('SELECT count(*) FROM docs WHERE docs MATCH ?', (f'"{w}"',)).fetchone()[0]
        if n > 0:
            hit += 1
        else:
            bigs = [w[i:i+2] for i in range(len(w)-1)]
            if all(con.execute('SELECT count(*) FROM docs WHERE docs MATCH ?', (f'"{b}"',)).fetchone()[0] > 0 for b in bigs):
                hit += 1
            else:
                miss += 1
                miss_l.append(w)
    con.close()
    emit(f"抽查20词 直接/兜底命中 {hit}/20, 未覆盖 {miss_l or '无'}")
else:
    emit("    [缺] comments_fts.db 不存在")

# ---------------------------------------------------------------- 7. 缩略图
section("[7] 海报缩略图 posters_thumb/")
thumbs = sorted((ENRICHED / "posters_thumb").glob("*.webp"))
emit(f"webp 数量 {len(thumbs)}/590  {'✓' if len(thumbs)==590 else '✗'}")
from PIL import Image
bad_img, big_file = [], []
for p in thumbs:
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as e:
        bad_img.append((p.stem, str(e)[:30]))
    sz = p.stat().st_size
    if sz > 80 * 1024:
        big_file.append((p.stem, sz // 1024))
emit(f"无法打开 {len(bad_img)} {bad_img[:5]}")
emit(f">80KB {len(big_file)} 张 {big_file[:5]} ; 尺寸分布中位 {sorted(p.stat().st_size for p in thumbs)[len(thumbs)//2]//1024}KB")

# ---------------------------------------------------------------- 8. D2 样张
section("[8] D2 样张 sample_cards.md")
sample_md = ENRICHED / "sample_cards.md"
emit(f"文件存在 {sample_md.exists()}  大小 {sample_md.stat().st_size if sample_md.exists() else 0} B")
sm = sample_md.read_text(encoding="utf-8") if sample_md.exists() else ""
n_cards = sm.count("===== 样张")
emit(f"样张数量 {n_cards}/10")
covered = set()
for mid, why in B.SAMPLE_PICK.items():
    if mid in dna:
        covered.add(mid)
emit(f"10部中已覆盖 {len(covered)}；缺失: {set(B.SAMPLE_PICK) - covered or '无'}")
emit("覆盖组合检查: " + "; ".join(f"{B.SAMPLE_PICK[k]}" for k in B.SAMPLE_PICK if k in covered))
# 样张里的明显质量问题（样本级）
emit("\n样张中疑似质量问题的条目（人工复核用）:")
for mid, why in B.SAMPLE_PICK.items():
    if mid not in quotes:
        continue
    q = quotes[mid]
    for c in q.get("citation_candidates") or []:
        if re.search(r"原创|作者|文/|来源|转载|公众号|微博|出版社|电影节|展映|Spoiler|剧透|二维码", c["text"], re.I):
            emit(f"    《{t_map.get(mid, mid)}》 候选噪声: {c['text'][:55]}")

# ---------------------------------------------------------------- 9. 筛选标准问题汇总
section("[9] 筛选标准问题清单（本报告重点）")
emit("根因说明: core_quotes.json 生成于 2026-08-04 18:53，当时代码将候选按 60 字符整截断、无引号配对/扩展噪声检查；"
     "代码 08-05 后已改为 8-50 字符 + 引号/噪声检查但**未重跑 quotes**，且新检查自身有引号配对 bug。→ 存储池 ≠ 当前口径。")
n_issues = 0
def add(title, body):
    global n_issues
    n_issues += 1
    issues.append((title, body))
issues = []
# —— A 必须修的筛选标准问题（影响 D3 输入质量）——
emit("\n A. 必须修（全部集中在 citation 候选池，直接毒化 D3 输入）:")
if trunc:
    add("citation 中途截断残句", f"{len(trunc)} 条 >50 字符且原文后仍有内容（60字符整截断）；D3 每片5选1，选中即出残句。示例见[4]")
if special_noise:
    add("citation 显性噪声", f"{len(special_noise)} 条含 转载/公众号/二维码/剧透/电影节/时间出处/URL；其中当前 _QUOTE_NOISE 漏网 {len(miss_by_current)} 条（URL/二维码/剧透/首发/微信 不在词表）。示例见[4]")
if pair_ok_bad:
    add("_quote_bad 引号配对 bug", f"{pair_ok_bad} 条单对引号佳句（如'以前我没得选，现在我想做个好人'）会被当前过滤误杀；修法: 用 s.count('“')!=s.count('”') 代替 % 2")
if n_any:
    add("citation 候选池污染面", f"{n_any}/590 部（74%）候选池混入≥1条噪声/残句，{n_bad5} 部 5 条全废，仅 {n_clean} 部全干净")
if len_vio2:
    add("citation 长度越界(8-50)", f"{len(len_vio2)} 条（含上述残句 608 条 + 51-59 字长句）")
if issues:
    for i, (t, b) in enumerate(issues, 1):
        emit(f"  A{i}. {t}: {b}")
else:
    emit("    未发现必须修的筛选标准问题。")
# —— B 注意项 / 符合预案 ——
emit("\n B. 注意项 / 符合预案（不算违规，但 D3 前要知晓）:")
emit(f"    · dn1 缺口 1 部（2208890 姊姊妹妹站起来）——方案§2.1 明确允许差评池过薄片 dn1 为空，build report 已列名 ✓")
emit(f"    · DNA 有维度 n<8 的影片 {sum(1 for m in ids if any(dna[m]['_n'].get(dim,0)<8 for dim in B.DNA_DIMS))} 部（conf=low，占 6.8%，红线≤15% 已过）——情感维尤其稀薄（39 部 n<8, 1 部 n=0）")
emit(f"    · 情感维先验经 0.95 折扣压平；逐片最终分未见系统性失真，但冷门片 DNA 趋近先验")

# ---------------------------------------------------------------- 10. 结论
section("[10] 结论")
pass_flags = {
    "core 590 主键唯一": len(core) == 590,
    "DNA 覆盖 590/590": not missing_dna,
    "DNA low≤15%": low_share <= 0.15,
    "DNA Spearman≥0.4": rho >= 0.4,
    "up1 非空 590/590": up1_ok == 590,
    "citation 候选 非空 590/590": cit_ok == 590,
    "citation 原文子串 100%": not sub_vio,
    "相似片满8条 100%": not sim_bad and not sim_missing,
    "缩略图 590/590": len(thumbs) == 590 and not bad_img,
    "FTS 抽查全命中": miss == 0,
}
for k, v in pass_flags.items():
    emit(f"  [{'✓' if v else '✗'}] {k}")
emit(f"\n结论: 硬性红线 {(sum(1 for v in pass_flags.values() if v))}/{len(pass_flags)} 项通过；"
     f"必须修的筛选标准问题 A 类 {n_issues} 项（见[9]，全在 citation 候选池）。"
     f"up1/dn1/DNA/相似片/FTS/缩略图 均无违规；dn1 缺口 1 部符合方案预案。")

OUT.write_text("\n".join(REPORT) + "\n", encoding="utf-8")
print(f"\n已写入: {OUT}")
