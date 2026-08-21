# -*- coding: utf-8 -*-
"""
豆瓣高分电影 短评/长评采集
==========================
基于 data/movies.csv 已采集的电影清单，为每部电影采集：
  · 短评：好评/一般/差评 三类各 50 条热门短评（按"有用数"排序），目标合计 150 条
  · 长评：热门影评列表前 50 篇的完整正文
不足目标条数的按网站实际可采数量为准（任务表记录实际存量，不产生重复行）。

用法：
    python crawler_reviews.py --stage comments                     # 阶段1：短评采集
    python crawler_reviews.py --stage reviews                      # 阶段2：长评采集（列表+正文）
    python crawler_reviews.py --stage check                        # 阶段3：质检报告
    python crawler_reviews.py --stage all                          # 串行 comments -> reviews -> check
    python crawler_reviews.py --stage comments --limit 5           # 小批量试跑前5部
    python crawler_reviews.py --stage reviews --movie 1291546      # 单部调试

断点续采：comment_id / review_id 以 data/*.csv 为准去重；任务表记录每部电影存量与状态
（done/failed/gone），中断后重跑仅补采缺口内容。
节奏（温和提速档）：每个实际请求间隔 1.5-3s，每 200 次请求长休 60-120s；
触发人机验证时暂停等待人工处理。
兜底：个别电影被豆瓣按电影级策略禁止分类筛选（/comments?percent_type= 一律403），
此时自动改走「最热短评」无参数页，按星级归归类（4-5好评/3一般/1-2差评），
任务表 error 标注"分类筛选403，按星级归类"。
"""
import argparse
import csv
import hashlib
import logging
import random
import re
import sys
import time

import pandas as pd
from playwright.sync_api import sync_playwright

from crawler_movie import (BASE_DIR, LOG_DIR, MOVIES_CSV,
                           launch_browser, is_blocked, wait_unblock,
                           sleep_random, retry_on_lock)

# ----------------------------- 全局配置 -----------------------------
COMMENTS_CSV = BASE_DIR / "data" / "movie_comments.csv"
REVIEWS_CSV = BASE_DIR / "data" / "movie_reviews.csv"
COMMENT_TASK_FILE = BASE_DIR / "data" / "task" / "comment_tasks.csv"
REVIEW_TASK_FILE = BASE_DIR / "data" / "task" / "review_tasks.csv"
CHECK_REPORT = LOG_DIR / "check_report_reviews.txt"

SHORT_PER_CAT = 50                     # 每类短评目标条数
LONG_REVIEWS = 50                      # 每部长评目标篇数
PAGE_SIZE = 20                         # 豆瓣列表分页固定 20 条
MAX_MIXED_PAGES = 25                   # 分类筛选被禁时，最热页兜底最多翻25页
# (percent_type, 页面筛选标签名, CSV存储类别名)：豆瓣页面标签为「好评/中评/差评」
CATEGORIES = [("h", "好评", "好评"), ("m", "中评", "一般"), ("l", "差评", "差评")]

PAGE_DELAY = (1.5, 3.0)                # 温和提速档：请求间隔（秒）
LONG_REST_EVERY = 200                  # 每200次请求长休一次
LONG_REST = (60, 120)
MAX_RETRY = 3                          # 单页最大重试次数（验证通过重访不耗次数）
DONE_STATUSES = {"done", "gone"}       # 可跳过的任务终态

COMMENT_FIELDS = ["movie_id", "title", "category", "comment_id", "author",
                  "author_url", "star", "time", "location", "votes", "content"]
REVIEW_FIELDS = ["movie_id", "title", "review_id", "review_title", "author",
                 "author_url", "star", "publish_time", "useful", "useless",
                 "replies", "content"]
COMMENT_TASK_FIELDS = ["movie_id", "title", "c_h", "c_m", "c_l",
                       "total", "status", "error"]
REVIEW_TASK_FIELDS = ["movie_id", "title", "targets", "fetched", "status", "error"]

STAR_MAP = {"力荐": 5, "推荐": 4, "还行": 3, "较差": 2, "很差": 1}

# ----------------------------- 日志 -----------------------------
def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("douban_review")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / "review_spider.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

log = setup_logger()


# ----------------------------- 通用工具 -----------------------------
class Pacer:
    """统一计数真实请求节奏：每100次请求长休一次，其余随机小憩"""

    def __init__(self):
        self.pages = 0

    def tick(self):
        self.pages += 1
        if self.pages % LONG_REST_EVERY == 0:
            rest = random.uniform(*LONG_REST)
            log.info("已发送 %d 次请求，长休 %.0f 秒...", self.pages, rest)
            time.sleep(rest)
        else:
            sleep_random(PAGE_DELAY)


def goto_page(page, url, pacer, desc="", wait_selector=None):
    """带重试的页面访问；触发人机验证时暂停等待人工处理（重访不耗重试次数）。
    返回错误信息，空串=成功；只有加载并确认目标结构后才算成功。"""
    attempt, err = 0, ""
    while attempt < MAX_RETRY:
        try:
            resp = page.goto(url, wait_until="domcontentloaded")
            pacer.tick()
            if resp and resp.status == 404:
                return "404页面不存在"
            if (resp and resp.status == 403) or "没有访问权限" in (page.title() or ""):
                return "403没有访问权限"
            if is_blocked(page):
                if not wait_unblock(page):
                    return "人机验证未通过"
                continue  # 通过验证后重访本页（不消耗 attempt）
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=15000)
            return ""
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            attempt += 1
            if attempt < MAX_RETRY:
                wait = 5 * (2 ** (attempt - 1))
                log.warning("  [%s] 第%d次访问失败(%s)，%ds后重试",
                            desc, attempt, err, wait)
                time.sleep(wait)
    return err or "重试次数耗尽"


def append_row(path, fields, row):
    """逐条追加写入CSV，进程中断不丢数据"""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _write():
        new_file = not path.exists()
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
            if new_file:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in fields})
    retry_on_lock(_write, path.name)


def load_done_ids(path, key):
    """从已存CSV读取已完成的主键集合（断点续采去重）"""
    if not path.exists():
        return set()
    df = pd.read_csv(path, dtype=str).fillna("")
    if key not in df.columns:
        return set()
    return set(df[key].astype(str))


def load_comment_counts():
    """已存短评按 (movie_id, category) 聚合存量，用于续采口径与整类跳过"""
    if not COMMENTS_CSV.exists():
        return {}
    df = pd.read_csv(COMMENTS_CSV, dtype=str).fillna("")
    if df.empty:
        return {}
    g = df.groupby(["movie_id", "category"]).size()
    return {str(m): {str(c): int(n) for c, n in sub.items()}
            for m, sub in g.groupby("movie_id")}


def load_review_counts():
    """已存长评按 movie_id 聚合存量"""
    if not REVIEWS_CSV.exists():
        return {}
    df = pd.read_csv(REVIEWS_CSV, dtype=str).fillna("")
    if df.empty:
        return {}
    return {str(m): int(n) for m, n in df.groupby("movie_id").size().items()}


def load_movies(movie_id=""):
    if not MOVIES_CSV.exists():
        log.error("data/movies.csv 不存在，请先运行 crawler_movie.py --stage detail")
        return []
    df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    rows = [{"movie_id": r.movie_id, "title": r.title}
            for r in df[["movie_id", "title"]].itertuples()]
    if movie_id:
        rows = [r for r in rows if r["movie_id"] == movie_id]
        if not rows:
            log.error("movies.csv 中不存在 movie_id=%s", movie_id)
    return rows


def load_tasks(path):
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("").to_dict("records")
    return []


def upsert_task(tasks, task):
    for t in tasks:
        if t["movie_id"] == task["movie_id"]:
            t.update(task)
            return
    tasks.append(task)


def save_tasks(path, fields, tasks):
    path.parent.mkdir(parents=True, exist_ok=True)
    retry_on_lock(
        lambda: pd.DataFrame(tasks, columns=fields).to_csv(
            path, index=False, encoding="utf-8-sig"),
        path.name)


def parse_count(text):
    """从 '有用 1234' / '1234有用' / '' 中提取数字"""
    m = re.search(r"(\d+)", str(text))
    return m.group(1) if m else ""


# ----------------------------- 阶段1：短评 -----------------------------
EXTRACT_COMMENTS_JS = r"""
() => {
    const q = (el, sel) => el ? el.querySelector(sel) : null;
    const txt = el => el ? el.textContent.trim() : "";
    const STAR = {"力荐":5,"推荐":4,"还行":3,"较差":2,"很差":1};
    const starOf = el => {
        if (!el) return "";
        const m = el.className.match(/allstar(\d)0/);
        if (m) return String(Number(m[1]));
        return String(STAR[el.title] || "");
    };
    const items = Array.from(document.querySelectorAll('#comments .comment-item'));
    const rows = items.map(it => {
        const cidEl = it.getAttribute('data-cid') ? it : q(it, '[data-cid]');
        const authorEl = q(it, '.comment-info a') || q(it, '.comment-avatar a')
                         || q(it, '.avatar a');
        const timeEl = q(it, '.comment-time');   // <a class="comment-time" title="完整时间">
        const votesEl = q(it, '.vote-count') || q(it, '.comment-vote .votes');
        const shortEl = q(it, '.comment-content .short')
                        || q(it, 'p.comment-content span');
        return {
            cid: cidEl ? (cidEl.getAttribute('data-cid') || "") : "",
            author: txt(authorEl),
            author_url: authorEl ? authorEl.href : "",
            star: starOf(q(it, '.comment-info span[class*="allstar"]')
                         || q(it, 'span[class*="allstar"]')),
            time: timeEl ? (timeEl.getAttribute("title") || txt(timeEl)) : "",
            location: txt(q(it, 'span.comment-location')),
            votes: txt(votesEl),
            content: shortEl ? shortEl.textContent.replace(/\s+/g, " ").trim() : ""
        };
    });
    return {rows: rows};
}
"""


def comment_key(it):
    """短评去重主键；data-cid 缺失时回退为稳定字段哈希"""
    cid = (it.get("cid") or "").strip()
    if cid:
        return cid
    raw = f"{it.get('author', '')}|{it.get('time', '')}|{it.get('content', '')}"
    return "md5_" + hashlib.md5(raw.encode("utf-8")).hexdigest()


def star_to_category(star):
    """星级归归类：4-5星→好评(h)，3星→一般(m)，1-2星→差评(l)；无星返回None"""
    return {"5": "h", "4": "h", "3": "m", "2": "l", "1": "l"}.get(str(star).strip())


def fetch_mixed_comments(page, pacer, mid, mtitle, counts, done_ids):
    """分类筛选被电影级403封禁时的兜底：拉取「最热短评」无参数页，按星级三路归类。
    counts 为 {'h','m','l'} 存量字典（原地累加）。返回 (notes, ok)"""
    notes = []

    def full():
        return all(counts[c] >= SHORT_PER_CAT for c in "hml")

    cat_names = {c_key: s for c_key, _, s in CATEGORIES}
    for start_ in range(0, PAGE_SIZE * MAX_MIXED_PAGES, PAGE_SIZE):
        if full():
            break
        # 注意：不带 percent_type / status 参数，否则会触发同一电影级403
        url = (f"https://movie.douban.com/subject/{mid}/comments"
               f"?start={start_}&limit={PAGE_SIZE}")
        err = goto_page(page, url, pacer, desc=f"{mid}/混合短评/{start_}",
                        wait_selector="#comments, .no-comments")
        if err:
            log.error("[%s] %s 混合页 start=%d 失败: %s", mid, mtitle, start_, err)
            notes.append(f"混合页失败:{err[:30]}")
            return notes, False
        try:
            data = page.evaluate(EXTRACT_COMMENTS_JS)
        except Exception as e:
            notes.append(f"混合页异常:{type(e).__name__}")
            return notes, False
        for it in data["rows"]:
            if full():
                break
            cat = star_to_category(it["star"])
            if not cat or counts[cat] >= SHORT_PER_CAT:
                continue
            cid = comment_key(it)
            if cid in done_ids:
                continue
            done_ids.add(cid)
            append_row(COMMENTS_CSV, COMMENT_FIELDS, {
                "movie_id": mid, "title": mtitle, "category": cat_names[cat],
                "comment_id": cid, "author": it["author"],
                "author_url": it["author_url"], "star": it["star"],
                "time": it["time"], "location": it["location"],
                "votes": it["votes"], "content": it["content"]})
            counts[cat] += 1
        if len(data["rows"]) < PAGE_SIZE:
            break  # 网站存量不足下一页
    for c_key, _, s in CATEGORIES:
        if counts[c_key] < SHORT_PER_CAT:
            notes.append(f"{s}归并{counts[c_key]}条")
    notes.append("分类筛选403，按星级归类")
    return notes, True


def stage_comments(limit=0, movie_id="", headless=False):
    movies = load_movies(movie_id)
    if not movies:
        return False
    tasks = load_tasks(COMMENT_TASK_FILE)
    done_movies = {t["movie_id"] for t in tasks if t.get("status") in DONE_STATUSES}
    done_ids = load_done_ids(COMMENTS_CSV, "comment_id")
    cat_counts = load_comment_counts()
    todo = [m for m in movies if m["movie_id"] not in done_movies]
    if limit > 0:
        todo = todo[:limit]
    log.info("电影总数 %d，短评已完成 %d，本次待采 %d", len(movies), len(done_movies), len(todo))
    if not todo:
        log.info("没有待采任务")
        return True

    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=headless)
        if not any(c["name"] == "dbcl2" for c in context.cookies()):
            log.warning("未检测到登录cookie，建议先运行 crawler_movie.py --stage login")
        page = context.new_page()
        pacer = Pacer()

        for i, mv in enumerate(todo, 1):
            mid, mtitle = mv["movie_id"], mv["title"]
            existing = cat_counts.get(mid, {})
            counts = {"h": int(existing.get("好评", 0)),
                      "m": int(existing.get("一般", 0)),
                      "l": int(existing.get("差评", 0))}
            notes, movie_ok, gone_cnt = [], True, 0
            mixed = False  # 分类筛选被403 → 切最热页按星级归类兜底
            for cat, nav_name, store_name in CATEGORIES:
                if counts[cat] >= SHORT_PER_CAT:
                    continue  # 已采满，整类跳过不耗请求
                cat_err = ""
                for start_ in (0, PAGE_SIZE, PAGE_SIZE * 2):
                    if counts[cat] >= SHORT_PER_CAT:
                        break
                    # 注意：URL 不带 sort 参数——douban 对 sort=score/update_score 直接 403，
                    # 默认顺序即"热门"（近似有用数降序），实测 200 可达
                    url = (f"https://movie.douban.com/subject/{mid}/comments"
                           f"?percent_type={cat}&start={start_}&limit={PAGE_SIZE}&status=P")
                    err = goto_page(page, url, pacer,
                                    desc=f"{mid}/短评{cat}/{start_}",
                                    wait_selector="#comments, .no-comments")
                    if err == "404页面不存在":
                        notes.append(f"{store_name}页404")
                        gone_cnt += 1
                        break
                    if err == "403没有访问权限":
                        log.warning("(%d/%d) [%s] %s 分类筛选被禁(403)，"
                                    "切换最热页按星级归类兜底", i, len(todo), mid, mtitle)
                        mixed = True
                        break
                    if err:
                        log.error("(%d/%d) [%s] %s %s类 start=%d 访问失败: %s",
                                  i, len(todo), mid, mtitle, store_name, start_, err)
                        cat_err, movie_ok = err, False
                        break
                    try:
                        data = page.evaluate(EXTRACT_COMMENTS_JS)
                    except Exception as e:
                        log.error("(%d/%d) [%s] %s 短评提取异常: %s",
                                  i, len(todo), mid, mtitle, e)
                        cat_err, movie_ok = f"evaluate:{type(e).__name__}", False
                        break
                    if start_ == 0 and not data["rows"]:
                        log.warning("(%d/%d) [%s] %s %s类首页提取0条，请人工确认",
                                    i, len(todo), mid, mtitle, store_name)
                        notes.append(f"{store_name}首页提取0条")
                    for it in data["rows"]:
                        if counts[cat] >= SHORT_PER_CAT:
                            break
                        cid = comment_key(it)
                        if cid in done_ids:
                            continue
                        done_ids.add(cid)
                        append_row(COMMENTS_CSV, COMMENT_FIELDS, {
                            "movie_id": mid, "title": mtitle,
                            "category": store_name,
                            "comment_id": cid, "author": it["author"],
                            "author_url": it["author_url"], "star": it["star"],
                            "time": it["time"], "location": it["location"],
                            "votes": it["votes"], "content": it["content"]})
                        counts[cat] += 1
                    if len(data["rows"]) < PAGE_SIZE:
                        break  # 本类别不足下一页
                if cat_err or mixed:
                    break

            if mixed:
                fb_notes, movie_ok = fetch_mixed_comments(
                    page, pacer, mid, mtitle, counts, done_ids)
                notes.extend(fb_notes)

            status = "done" if movie_ok else "failed"
            if movie_ok and gone_cnt == len(CATEGORIES):
                status = "gone"
            t = {"movie_id": mid, "title": mtitle,
                 "c_h": str(counts["h"]), "c_m": str(counts["m"]),
                 "c_l": str(counts["l"]),
                 "total": str(counts["h"] + counts["m"] + counts["l"]),
                 "status": status, "error": "; ".join(notes + ([cat_err] if cat_err else []))}
            upsert_task(tasks, t)
            save_tasks(COMMENT_TASK_FILE, COMMENT_TASK_FIELDS, tasks)
            log.info("(%d/%d) [%s] %s 短评存量：好评%s 一般%s 差评%s 合计%s %s",
                     i, len(todo), mid, mtitle, t["c_h"], t["c_m"], t["c_l"],
                     t["total"], ("备注:" + t["error"]) if t["error"] else "")
        browser.close()

    total_done = sum(1 for t in tasks if t.get("status") in DONE_STATUSES)
    log.info("本轮结束：短评完成电影 %d/%d（断点续采可直接重跑）", total_done, len(movies))
    return True


# ----------------------------- 阶段2：长评 -----------------------------
EXTRACT_REVIEW_LIST_JS = r"""
() => {
    const txt = el => el ? el.textContent.trim() : "";
    const STAR = {"力荐":5,"推荐":4,"还行":3,"较差":2,"很差":1};
    const starOf = el => {
        if (!el) return "";
        const m = el.className.match(/allstar(\d)0/);
        if (m) return String(Number(m[1]));
        return String(STAR[el.title] || "");
    };
    const cntOf = sel => {
        const btn = document.querySelector(sel);
        return btn ? (btn.getAttribute("data-count") || txt(btn)) : "";
    };
    const out = [], seen = new Set();
    document.querySelectorAll('#content .review-list > div, #content .tlst').forEach(root => {
        const a = root.querySelector('h2 a[href*="/review/"]');
        if (!a) return;
        const m = a.href.match(/review\/(\d+)\//);
        if (!m || seen.has(m[1])) return;
        seen.add(m[1]);
        const upBtn = root.querySelector('.action-btn.up');
        const downBtn = root.querySelector('.action-btn.down');
        out.push({
            rid: m[1],
            list_title: txt(a),
            author: txt(root.querySelector('.main-hd .name')
                        || root.querySelector('.main-hd a[href*="/people/"]')),
            star: starOf(root.querySelector('.main-hd [class*="allstar"]')),
            up: upBtn ? (upBtn.getAttribute("data-count")
                         || txt(root.querySelector('.action-btn.up .count'))
                         || txt(upBtn)) : "",
            down: downBtn ? (downBtn.getAttribute("data-count")
                             || txt(root.querySelector('.action-btn.down .count'))
                             || txt(downBtn)) : "",
            reply: txt(root.querySelector('.reply'))
        });
    });
    return out;
}
"""

EXTRACT_REVIEW_DETAIL_JS = r"""
() => {
    const txt = el => el ? el.textContent.trim() : "";
    const STAR = {"力荐":5,"推荐":4,"还行":3,"较差":2,"很差":1};
    const titleEl = document.querySelector('#content h1');
    const authorEl = document.querySelector('.article .main-hd a.name')
                     || document.querySelector('.article .main-hd a[href*="/people/"]')
                     || document.querySelector('.article a.author-avatar');
    const metaEl = document.querySelector('.article .main-hd .main-meta');
    const starEl = document.querySelector('.article .main-hd [class*="allstar"]');
    const sm = starEl ? starEl.className.match(/allstar(\d)0/) : null;
    const star = sm ? String(Number(sm[1])) : String(STAR[starEl ? starEl.title : ""] || "");
    const usefulEl = document.querySelector('button.useful_count')
                     || document.querySelector('[id^="useful_count"]');
    const uselessEl = document.querySelector('button.useless_count')
                      || document.querySelector('[id^="useless_count"]');
    const numOf = el => el ? (el.getAttribute("data-count") || txt(el)) : "";
    // 正文容器 id 现行为 link-report-<rid>
    const body = document.querySelector('[id^="link-report"]');
    let content = "";
    if (body) {
        const clone = body.cloneNode(true);
        // 展开「涉嫌剧透」等折叠隐藏部分，避免正文被截短
        clone.querySelectorAll('#fold_unfold_wrap, [style*="display: none"], [style*="display:none"]')
             .forEach(e => e.style.display = "");
        clone.querySelectorAll("br").forEach(br => br.replaceWith("\n"));
        content = clone.innerText.replace(/[ \t]+\n/g, "\n")
                                 .replace(/\n{3,}/g, "\n\n").trim();
    }
    return {
        review_title: txt(titleEl),
        author: txt(authorEl),
        author_url: authorEl ? authorEl.href : "",
        publish_time: metaEl ? (txt(metaEl) || metaEl.getAttribute("content") || "") : "",
        star: star,
        useful: numOf(usefulEl),
        useless: numOf(uselessEl),
        content: content
    };
}
"""


def stage_reviews(limit=0, movie_id="", headless=False):
    movies = load_movies(movie_id)
    if not movies:
        return False
    tasks = load_tasks(REVIEW_TASK_FILE)
    done_movies = {t["movie_id"] for t in tasks if t.get("status") in DONE_STATUSES}
    done_rids = load_done_ids(REVIEWS_CSV, "review_id")
    rev_counts = load_review_counts()
    todo = [m for m in movies if m["movie_id"] not in done_movies]
    if limit > 0:
        todo = todo[:limit]
    log.info("电影总数 %d，长评已完成 %d，本次待采 %d", len(movies), len(done_movies), len(todo))
    if not todo:
        log.info("没有待采任务")
        return True

    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=headless)
        if not any(c["name"] == "dbcl2" for c in context.cookies()):
            log.warning("未检测到登录cookie，建议先运行 crawler_movie.py --stage login")
        page = context.new_page()
        page.route(re.compile(r"\.(mp4|webm|flv)(\?|$)"), lambda r: r.abort())
        pacer = Pacer()

        for i, mv in enumerate(todo, 1):
            mid, mtitle = mv["movie_id"], mv["title"]
            existing = int(rev_counts.get(mid, 0))
            notes, movie_ok = [], True

            # --- 影评列表：按"最受欢迎"顺序取前 LONG_REVIEWS 篇名单（含历史已采）---
            targets, seen_page_rids = [], set()
            gone = False
            for start_ in (0, PAGE_SIZE, PAGE_SIZE * 2):
                if len(targets) >= LONG_REVIEWS:
                    break
                url = (f"https://movie.douban.com/subject/{mid}/reviews"
                       f"?sort=hotest&start={start_}")
                err = goto_page(page, url, pacer,
                                desc=f"{mid}/影评列表/{start_}",
                                wait_selector="#content")
                if err == "404页面不存在" and start_ == 0:
                    gone = True
                    break
                if err:
                    log.error("(%d/%d) [%s] %s 影评列表 start=%d 访问失败: %s",
                              i, len(todo), mid, mtitle, start_, err)
                    movie_ok = False
                    break
                try:
                    items = page.evaluate(EXTRACT_REVIEW_LIST_JS)
                except Exception as e:
                    log.error("(%d/%d) [%s] %s 影评列表提取异常: %s",
                              i, len(todo), mid, mtitle, e)
                    movie_ok = False
                    break
                if start_ == 0 and not items:
                    log.warning("(%d/%d) [%s] %s 影评列表首页提取0条，请人工确认",
                                i, len(todo), mid, mtitle)
                    notes.append("影评首页提取0条")
                for it in items:
                    if len(targets) >= LONG_REVIEWS:
                        break
                    if it["rid"] not in seen_page_rids:
                        seen_page_rids.add(it["rid"])
                        targets.append(it)
                if not items:
                    break  # 首页条数可能18/20浮动，不足页仅按空页收尾
            if gone:
                upsert_task(tasks, {"movie_id": mid, "title": mtitle,
                                    "targets": "0", "fetched": str(existing),
                                    "status": "gone", "error": "影评页404"})
                save_tasks(REVIEW_TASK_FILE, REVIEW_TASK_FIELDS, tasks)
                continue
            if not movie_ok:
                upsert_task(tasks, {"movie_id": mid, "title": mtitle,
                                    "targets": "0", "fetched": str(existing),
                                    "status": "failed", "error": "影评列表访问失败"})
                save_tasks(REVIEW_TASK_FILE, REVIEW_TASK_FIELDS, tasks)
                continue

            # --- 逐篇正文（已采的跳过请求；非404失败置 failed 以便重跑补采）---
            n_new, n_skip = 0, 0
            for t in targets:
                rid = t["rid"]
                if rid in done_rids:
                    n_skip += 1
                    continue
                err = goto_page(page, f"https://movie.douban.com/review/{rid}/",
                                pacer, desc=f"review/{rid}",
                                wait_selector='[id^="link-report"]')
                if err == "404页面不存在":
                    notes.append(f"{rid}已删除")
                    continue
                if err:
                    log.warning("(%d/%d) [%s] 影评 %s 正文访问失败: %s",
                                i, len(todo), mid, rid, err)
                    notes.append(f"正文{rid}失败:{err[:40]}")
                    movie_ok = False
                    continue
                try:
                    d = page.evaluate(EXTRACT_REVIEW_DETAIL_JS)
                except Exception as e:
                    log.warning("(%d/%d) [%s] 影评 %s 正文提取异常: %s",
                                i, len(todo), mid, rid, e)
                    notes.append(f"正文{rid}异常:{type(e).__name__}")
                    movie_ok = False
                    continue
                append_row(REVIEWS_CSV, REVIEW_FIELDS, {
                    "movie_id": mid, "title": mtitle, "review_id": rid,
                    "review_title": d["review_title"] or t["list_title"],
                    "author": d["author"] or t["author"],
                    "author_url": d["author_url"],
                    "star": d["star"] or t["star"],
                    "publish_time": d["publish_time"],
                    "useful": parse_count(d["useful"]) or parse_count(t["up"]),
                    "useless": parse_count(d["useless"]) or parse_count(t["down"]),
                    "replies": parse_count(t["reply"]),
                    "content": d["content"]})
                done_rids.add(rid)
                n_new += 1

            t = {"movie_id": mid, "title": mtitle,
                 "targets": str(len(targets)),
                 "fetched": str(existing + n_new),
                 "status": "done" if movie_ok else "failed",
                 "error": "; ".join(notes)}
            upsert_task(tasks, t)
            save_tasks(REVIEW_TASK_FILE, REVIEW_TASK_FIELDS, tasks)
            log.info("(%d/%d) [%s] %s 长评：名单%d篇，新采%d，跳过已采%d，存量%d%s",
                     i, len(todo), mid, mtitle, len(targets), n_new, n_skip,
                     existing + n_new,
                     (" 备注:" + t["error"]) if t["error"] else "")
        browser.close()

    total_done = sum(1 for t in tasks if t.get("status") in DONE_STATUSES)
    log.info("本轮结束：长评完成电影 %d/%d（断点续采可直接重跑）", total_done, len(movies))
    return True


# ----------------------------- 阶段3：质检 -----------------------------
def stage_check():
    if not MOVIES_CSV.exists():
        log.error("data/movies.csv 不存在")
        return False
    movies = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    n_movies = len(movies)
    lines = ["=" * 60, "短评/长评数据质检报告  " + time.strftime("%F %T"), "=" * 60]

    if COMMENTS_CSV.exists():
        df = pd.read_csv(COMMENTS_CSV, dtype=str).fillna("")
        lines.append(f"\n【短评 {COMMENTS_CSV.name}】")
        lines.append(f"总行数: {len(df)}，覆盖电影 {df['movie_id'].nunique()}/{n_movies}")
        if len(df):
            dup = df[df.duplicated("comment_id", keep=False)]
            lines.append(f"重复 comment_id: {dup['comment_id'].nunique()} 个 / {len(dup)} 行")
            lines.append("类别分布: " + ", ".join(
                f"{c}: {(df['category'] == c).sum()}" for _, _, c in CATEGORIES))
            lines.append("字段缺失:")
            for col in COMMENT_FIELDS:
                miss = (df[col].str.strip() == "").sum()
                mark = "  <-- 注意" if miss > 0 else ""
                lines.append(f"    {col:<12} 缺失 {miss:>5} 行{mark}")
            cnt = df.groupby(["movie_id", "category"]).size().unstack(fill_value=0)
            under = cnt[(cnt < SHORT_PER_CAT).any(axis=1)]
            lines.append(f"不足 {SHORT_PER_CAT} 条的电影（含类别）: {len(under)} 部")
            for m, r in under.head(30).iterrows():
                lines.append(f"    {m}  " + " ".join(
                    f"{c}{int(r[c]) if c in r.index else 0}" for _, _, c in CATEGORIES))
            if len(under) > 30:
                lines.append(f"    ... 其余 {len(under) - 30} 部略")
    else:
        lines.append("\n【短评】movie_comments.csv 不存在，未采集")

    if REVIEWS_CSV.exists():
        df = pd.read_csv(REVIEWS_CSV, dtype=str).fillna("")
        lines.append(f"\n【长评 {REVIEWS_CSV.name}】")
        lines.append(f"总行数: {len(df)}，覆盖电影 {df['movie_id'].nunique()}/{n_movies}")
        if len(df):
            dup = df[df.duplicated("review_id", keep=False)]
            lines.append(f"重复 review_id: {dup['review_id'].nunique()} 个 / {len(dup)} 行")
            lines.append("字段缺失:")
            for col in REVIEW_FIELDS:
                miss = (df[col].str.strip() == "").sum()
                mark = "  <-- 注意" if miss > 0 else ""
                lines.append(f"    {col:<14} 缺失 {miss:>5} 行{mark}")
            short_body = (df["content"].str.len() < 100).sum()
            lines.append(f"正文长度<100字: {short_body} 行")
            cnt = df.groupby("movie_id").size()
            under = cnt[cnt < LONG_REVIEWS]
            lines.append(f"不足 {LONG_REVIEWS} 篇的电影: {len(under)} 部")
            for m, n in under.head(30).items():
                lines.append(f"    {m}  {n}篇")
            if len(under) > 30:
                lines.append(f"    ... 其余 {len(under) - 30} 部略")
    else:
        lines.append("\n【长评】movie_reviews.csv 不存在，未采集")

    report = "\n".join(lines)
    CHECK_REPORT.parent.mkdir(parents=True, exist_ok=True)
    CHECK_REPORT.write_text(report, encoding="utf-8")
    print(report)
    log.info("质检报告已保存: %s", CHECK_REPORT)
    return True


# ----------------------------- 入口 -----------------------------
def main():
    try:
        sys.stdout.reconfigure(errors="replace")  # Windows cp936 控制台打不出罕用字时不刷屏
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="豆瓣高分电影 短评/长评采集")
    parser.add_argument("--stage", required=True,
                        choices=["comments", "reviews", "check", "all"])
    parser.add_argument("--limit", type=int, default=0,
                        help="仅采集前N部电影（0=不限）")
    parser.add_argument("--movie", default="", help="仅采集指定movie_id（调试用）")
    parser.add_argument("--headless", action="store_true",
                        help="无头模式（长任务不建议：触发验证需人工在窗口处理）")
    args = parser.parse_args()

    if args.stage == "comments":
        stage_comments(limit=args.limit, movie_id=args.movie, headless=args.headless)
    elif args.stage == "reviews":
        stage_reviews(limit=args.limit, movie_id=args.movie, headless=args.headless)
    elif args.stage == "check":
        stage_check()
    elif args.stage == "all":
        if stage_comments(limit=args.limit, movie_id=args.movie, headless=args.headless):
            stage_reviews(limit=args.limit, movie_id=args.movie, headless=args.headless)
            stage_check()


if __name__ == "__main__":
    main()
