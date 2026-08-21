# -*- coding: utf-8 -*-
"""
豆瓣高分电影基础信息爬虫
========================
采集豆瓣「选电影→豆瓣高分」四个地区（华语/欧美/日本/韩国）全量电影，并保留
历史采集的高分经典（任务清单取并集），共 14 个基础字段，
并自动下载海报到 data/posters/，数据保存到 data/movies.csv。
注：网页榜单是动态的，每次运行 --stage list 会增量补入新上榜影片。

用法：
    python crawler_movie.py --stage login             # 阶段0：登录并保存cookie
    python crawler_movie.py --stage list              # 阶段1：采集电影ID任务清单
    python crawler_movie.py --stage detail            # 阶段2：详情页字段 + 海报下载
    python crawler_movie.py --stage detail --limit 5  # 小批量试跑5部
    python crawler_movie.py --stage check             # 阶段3：质检报告
    python crawler_movie.py --stage all               # 串行执行 list -> detail -> check
"""

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ----------------------------- 全局配置 -----------------------------
BASE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = BASE_DIR / "cookies" / "douban_state.json"
TASK_FILE = BASE_DIR / "data" / "task" / "movie_tasks.csv"
MOVIES_CSV = BASE_DIR / "data" / "movies.csv"
POSTER_DIR = BASE_DIR / "data" / "posters"
LOG_DIR = BASE_DIR / "logs"
FAILED_CSV = LOG_DIR / "failed_tasks.csv"
CHECK_REPORT = LOG_DIR / "check_report.txt"

# 采集地区（榜单动态变化，数量以接口 total 为准）
REGIONS = ["华语", "欧美", "日本", "韩国"]

# 请求节奏
PAGE_DELAY = (3.0, 6.0)        # 每部电影间隔（秒）
LIST_DELAY = (2.0, 4.0)        # 列表翻页间隔（秒）
LONG_REST_EVERY = 20           # 每采集N部长休一次
LONG_REST = (60, 90)           # 长休时长（秒）
MAX_RETRY = 3                  # 单部电影最大重试次数

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

CSV_FIELDS = ["movie_id", "poster_url", "title", "year", "director", "writer",
              "actors", "genres", "countries", "languages", "runtime",
              "rating", "rating_count", "summary"]

TASK_FIELDS = ["movie_id", "title", "region", "status", "error"]

# ----------------------------- 日志 -----------------------------
def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("douban")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / "spider.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

log = setup_logger()


def sleep_random(lo_hi):
    t = random.uniform(*lo_hi)
    time.sleep(t)


# ----------------------------- 浏览器工厂 -----------------------------
def launch_browser(p, headless=True, use_cookie=True):
    """启动带反检测参数的浏览器上下文"""
    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--disable-infobars"],
    )
    ctx_kwargs = dict(
        user_agent=USER_AGENT,
        viewport={"width": 1366, "height": 850},
        locale="zh-CN",
    )
    if use_cookie and COOKIE_FILE.exists():
        ctx_kwargs["storage_state"] = str(COOKIE_FILE)
    context = browser.new_context(**ctx_kwargs)
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    context.set_default_timeout(30000)
    return browser, context


def is_logged_in(context):
    return any(c["name"] == "dbcl2" for c in context.cookies())


def is_blocked(page):
    """检测人机验证/封锁页面"""
    url = page.url
    if "sec.douban.com" in url or "accounts.douban.com" in url:
        return True
    title = page.title() or ""
    return ("禁止访问" in title) or ("异常请求" in title)


def wait_unblock(page):
    """触发人机验证时暂停，等待人工在浏览器中处理"""
    log.warning("!! 触发豆瓣人机验证/封锁: %s", page.url)
    log.warning("!! 请在弹出的浏览器窗口中手动完成验证，程序每10秒自动检测一次...")
    for _ in range(60):  # 最多等10分钟
        time.sleep(10)
        if not is_blocked(page):
            log.info("验证已通过，继续采集")
            return True
    return False


# ----------------------------- 阶段0：登录 -----------------------------
def stage_login():
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=False, use_cookie=True)
        page = context.new_page()
        page.goto("https://www.douban.com/", wait_until="domcontentloaded")
        if is_logged_in(context):
            log.info("已检测到有效登录态，无需重新登录")
            context.storage_state(path=str(COOKIE_FILE))
            browser.close()
            return True
        log.info("=" * 50)
        log.info("请在弹出的浏览器窗口中登录豆瓣（扫码或账号密码均可）")
        log.info("登录成功后程序会自动检测并保存cookie，请勿关闭窗口")
        log.info("=" * 50)
        for _ in range(150):  # 最长等待5分钟
            time.sleep(2)
            try:
                if is_logged_in(context):
                    context.storage_state(path=str(COOKIE_FILE))
                    log.info("登录成功，cookie已保存到 %s", COOKIE_FILE)
                    browser.close()
                    return True
            except Exception:
                pass
        log.error("等待登录超时（5分钟），请重新运行 --stage login")
        browser.close()
        return False


# ----------------------------- 阶段1：列表采集 -----------------------------
def fetch_region_list(context, region, seen_ids, ck):
    """「选电影→豆瓣高分」页面同款接口 subject/recent_hot，按 total 拉取该地区全量名单"""
    items, start, total = [], 0, None
    while total is None or start < total:
        url = ("https://m.douban.com/rexxar/api/v2/subject/recent_hot/movie"
               f"?start={start}&limit=20&category=豆瓣高分&type={region}&ck={ck}")
        try:
            resp = context.request.get(url, headers={
                "Referer": "https://movie.douban.com/explore",
                "Accept": "application/json"})
        except Exception as e:
            log.error("[%s] 列表接口异常: %s，中止", region, e)
            break
        if not resp.ok:
            log.error("[%s] 列表接口 HTTP %d，中止", region, resp.status)
            break
        data = resp.json()
        total = data.get("total", 0)
        subjects = data.get("items", [])
        if not subjects:
            break
        for s in subjects:
            mid = str(s.get("id", "")).strip()
            if not mid or mid in seen_ids:
                continue
            seen_ids.add(mid)
            items.append({"movie_id": mid, "title": s.get("title", ""),
                          "region": region, "status": "pending", "error": ""})
        start += len(subjects)
        log.info("[%s] 进度 %d/%d（其中新增 %d 部）", region, start, total, len(items))
        sleep_random(LIST_DELAY)
    return items


def stage_list():
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 与已有任务清单取并集：老片保留，新上榜的增量补入
    old_tasks, seen_ids = [], set()
    if TASK_FILE.exists():
        df_old = pd.read_csv(TASK_FILE, dtype=str).fillna("")
        old_tasks = df_old.to_dict("records")
        seen_ids = set(df_old["movie_id"])
        log.info("检测到已有任务清单 %d 条，与网页榜单取并集增量补入", len(old_tasks))

    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=True)
        page = context.new_page()
        page.goto("https://movie.douban.com/explore", wait_until="domcontentloaded")
        if is_blocked(page):
            log.error("列表页被封锁，请先运行 --stage login 或稍后再试")
            browser.close()
            return False
        if not is_logged_in(context):
            log.warning("当前为未登录状态，建议先运行 --stage login")
        ck = next((c["value"] for c in context.cookies() if c["name"] == "ck"), "")

        all_tasks = list(old_tasks)
        for region in REGIONS:
            added = fetch_region_list(context, region, seen_ids, ck)
            all_tasks.extend(added)
            log.info("[%s] 本次新增 %d 部", region, len(added))
        browser.close()

    df = pd.DataFrame(all_tasks, columns=TASK_FIELDS).drop_duplicates("movie_id")
    save_tasks(df.to_dict("records"))
    log.info("任务清单已保存: %s（共 %d 部）", TASK_FILE, len(df))
    for region in REGIONS:
        log.info("  %s: %d 部", region, (df["region"] == region).sum())
    return True


# ----------------------------- 阶段2：详情采集 -----------------------------
EXTRACT_JS = r"""
() => {
    const txt = (el) => el ? el.textContent.trim() : "";
    const info = document.querySelector("#info");
    const infoText = info ? info.innerText : "";
    const pick = (label) => {
        const m = infoText.match(new RegExp(label + ":\\s*(.+)"));
        return m ? m[1].trim() : "";
    };
    // 主演（限前10位）
    const actors = Array.from(document.querySelectorAll('#info a[rel="v:starring"]'))
        .slice(0, 10).map(a => a.textContent.trim()).join("|");
    // 类型
    const genres = Array.from(document.querySelectorAll('#info span[property="v:genre"]'))
        .map(s => s.textContent.trim()).join("|");
    // 片长
    const runtimeEl = document.querySelector('#info span[property="v:runtime"]');
    // 简介：优先隐藏的完整版
    let summary = txt(document.querySelector('#link-report-intra span.all.hidden')) ||
                  txt(document.querySelector('span.all.hidden')) ||
                  txt(document.querySelector('span[property="v:summary"]'));
    summary = summary.replace(/\s*\n\s*/g, " ").replace(/\u3000/g, "").trim();
    // 海报
    const posterEl = document.querySelector("#mainpic img");
    return {
        title: txt(document.querySelector('h1 span[property="v:itemreviewed"]')),
        year: txt(document.querySelector("h1 span.year")).replace(/[()]/g, ""),
        director: Array.from(document.querySelectorAll('#info a[rel="v:directedBy"]'))
            .map(a => a.textContent.trim()).join("|"),
        writer: pick("编剧").split("/").map(s => s.trim()).filter(Boolean).join("|"),
        actors: actors,
        genres: genres,
        countries: pick("制片国家/地区").split("/").map(s => s.trim()).filter(Boolean).join("|"),
        languages: pick("语言").split("/").map(s => s.trim()).filter(Boolean).join("|"),
        runtime: runtimeEl ? runtimeEl.textContent.trim() : pick("片长"),
        rating: txt(document.querySelector('strong[property="v:average"]')),
        rating_count: txt(document.querySelector('span[property="v:votes"]')),
        summary: summary,
        poster_url: posterEl ? posterEl.src : ""
    };
}
"""

def load_done_ids():
    """从 movies.csv 读取已完成的电影ID（断点续爬 + 去重）"""
    if not MOVIES_CSV.exists():
        return set()
    df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    return set(df["movie_id"])


def retry_on_lock(func, desc, attempts=100, wait=6):
    """文件被Excel等程序占用时自动等待重试，避免整轮采集中断"""
    for i in range(1, attempts + 1):
        try:
            return func()
        except PermissionError:
            log.warning("%s 文件被占用(第%d次)，请关闭Excel/WPS中打开的该文件，%ds后重试...",
                        desc, i, wait)
            time.sleep(wait)
    raise PermissionError(f"{desc} 文件持续被占用，放弃写入")


def append_movie_row(row):
    """逐条追加写入CSV，进程中断不丢数据"""
    MOVIES_CSV.parent.mkdir(parents=True, exist_ok=True)

    def _write():
        new_file = not MOVIES_CSV.exists()
        with open(MOVIES_CSV, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
            if new_file:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    retry_on_lock(_write, str(MOVIES_CSV.name))


def save_tasks(tasks):
    retry_on_lock(
        lambda: pd.DataFrame(tasks, columns=TASK_FIELDS).to_csv(
            TASK_FILE, index=False, encoding="utf-8-sig"),
        str(TASK_FILE.name))


def download_poster(context, movie_id, poster_url):
    """用浏览器上下文的request API下载海报（自动带cookie）"""
    if not poster_url:
        return False
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    dest = POSTER_DIR / f"{movie_id}.jpg"
    if dest.exists() and dest.stat().st_size > 1024:
        return True
    # 小图升级为大图
    url = poster_url.replace("s_ratio_poster", "l_ratio_poster")
    for u in (url, poster_url):
        try:
            resp = context.request.get(u, headers={"Referer": "https://movie.douban.com/"})
            if resp.ok:
                body = resp.body()
                if len(body) > 1024:
                    dest.write_bytes(body)
                    return True
        except Exception:
            continue
    return False


def crawl_one_movie(context, page, task):
    """采集单部电影，返回 (row 或 None, 错误信息)"""
    mid = task["movie_id"]
    url = f"https://movie.douban.com/subject/{mid}/"
    resp = page.goto(url, wait_until="domcontentloaded")
    if resp and resp.status == 404:
        return None, "404页面不存在"
    if is_blocked(page):
        if not wait_unblock(page):
            return None, "人机验证未通过"
        page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#info", timeout=15000)
    except PWTimeoutError:
        return None, "页面结构异常(#info缺失)"

    data = page.evaluate(EXTRACT_JS)
    if not data.get("title"):
        return None, "标题为空，疑似异常页面"

    row = {"movie_id": mid, **data}
    # 海报下载
    ok = download_poster(context, mid, data.get("poster_url", ""))
    if not ok:
        log.warning("  [%s] 海报下载失败: %s", mid, data.get("poster_url"))
    return row, ""


def stage_detail(limit=0, headless=False):
    if not TASK_FILE.exists():
        log.error("任务清单不存在，请先运行 --stage list")
        return False
    tasks = pd.read_csv(TASK_FILE, dtype=str).fillna("").to_dict("records")
    done_ids = load_done_ids()
    # 修正状态：已在csv里的直接标done
    for t in tasks:
        if t["movie_id"] in done_ids:
            t["status"] = "done"
    todo = [t for t in tasks if t["status"] != "done"]
    if limit > 0:
        todo = todo[:limit]
    log.info("任务总数 %d，已完成 %d，本次待采 %d", len(tasks), len(done_ids), len(todo))
    if not todo:
        log.info("没有待采任务")
        save_tasks(tasks)
        return True

    with sync_playwright() as p:
        browser, context = launch_browser(p, headless=headless)
        if not is_logged_in(context):
            log.warning("未检测到登录cookie，建议先运行 --stage login（未登录易被封）")
        page = context.new_page()
        # 屏蔽视频等重资源，加快加载（保留图片以便海报解析）
        page.route(re.compile(r"\.(mp4|webm|flv)(\?|$)"), lambda r: r.abort())

        count = 0
        for t in todo:
            mid = t["movie_id"]
            row, err = None, ""
            for attempt in range(1, MAX_RETRY + 1):
                try:
                    row, err = crawl_one_movie(context, page, t)
                    if row:
                        break
                    if err == "404页面不存在":
                        break  # 无需重试
                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                if attempt < MAX_RETRY:
                    wait = 5 * (2 ** (attempt - 1))
                    log.warning("  [%s] 第%d次失败(%s)，%ds后重试", mid, attempt, err, wait)
                    time.sleep(wait)

            if row:
                append_movie_row(row)
                t["status"], t["error"] = "done", ""
                count += 1
                log.info("(%d/%d) [%s] %s (%s) 评分%s 完成",
                         count, len(todo), mid, row["title"], row["year"], row["rating"])
            else:
                t["status"], t["error"] = "failed", err
                log.error("(%s) [%s] %s 采集失败: %s", "x", mid, t["title"], err)
                with open(FAILED_CSV, "a", newline="", encoding="utf-8-sig") as f:
                    csv.writer(f).writerow([mid, t["title"], err, time.strftime("%F %T")])
            save_tasks(tasks)  # 每部电影落盘一次任务状态

            if count and count % LONG_REST_EVERY == 0:
                rest = random.uniform(*LONG_REST)
                log.info("已连续采集%d部，长休 %.0f 秒...", LONG_REST_EVERY, rest)
                time.sleep(rest)
            else:
                sleep_random(PAGE_DELAY)
        browser.close()

    failed = sum(1 for t in tasks if t["status"] == "failed")
    log.info("本轮结束：成功 %d，失败 %d（失败清单见 %s）", count, failed, FAILED_CSV)
    return True


# ----------------------------- 阶段3：质检 -----------------------------
def stage_check():
    if not MOVIES_CSV.exists():
        log.error("movies.csv 不存在，请先运行 --stage detail")
        return False
    df = pd.read_csv(MOVIES_CSV, dtype=str).fillna("")
    lines = ["=" * 60, "豆瓣电影数据质检报告  " + time.strftime("%F %T"), "=" * 60,
             f"总行数: {len(df)}"]

    # 1. 重复检查
    dup = df[df.duplicated("movie_id", keep=False)]
    lines.append(f"\n[1] 重复 movie_id: {dup['movie_id'].nunique()} 个")
    if len(dup):
        lines += [f"    {r.movie_id}  {r.title}" for r in dup.itertuples()]
        df = df.drop_duplicates("movie_id", keep="first")
        df.to_csv(MOVIES_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
        lines.append(f"    -> 已自动去重，保留 {len(df)} 行")

    # 2. 缺失字段
    lines.append("\n[2] 各字段缺失情况:")
    for col in CSV_FIELDS:
        miss = (df[col].str.strip() == "").sum()
        mark = "  <-- 注意" if miss > 0 else ""
        lines.append(f"    {col:<14} 缺失 {miss:>4} 行{mark}")

    # 3. 异常值
    bad_year = df[~df["year"].str.match(r"^(19|20)\d{2}$", na=False)]
    bad_rating = df[~df["rating"].str.match(r"^\d(\.\d)?$|^10(\.0)?$", na=False)]
    lines.append(f"\n[3] 年份异常: {len(bad_year)} 行")
    lines += [f"    {r.movie_id}  {r.title}  year='{r.year}'" for r in bad_year.itertuples()]
    lines.append(f"    评分异常: {len(bad_rating)} 行")
    lines += [f"    {r.movie_id}  {r.title}  rating='{r.rating}'" for r in bad_rating.itertuples()]

    # 4. 海报文件
    no_poster = [r.movie_id for r in df.itertuples()
                 if not (POSTER_DIR / f"{r.movie_id}.jpg").exists()]
    lines.append(f"\n[4] 海报缺失: {len(no_poster)} 部")
    lines += [f"    {m}" for m in no_poster]

    # 5. 地区配额
    if TASK_FILE.exists():
        tk = pd.read_csv(TASK_FILE, dtype=str).fillna("")
        lines.append("\n[5] 地区完成度:")
        for region in REGIONS:
            sub = tk[tk["region"] == region]
            got = sub["movie_id"].isin(set(df["movie_id"])).sum()
            lines.append(f"    {region}: {got}/{len(sub)}")

    report = "\n".join(lines)
    CHECK_REPORT.parent.mkdir(parents=True, exist_ok=True)
    CHECK_REPORT.write_text(report, encoding="utf-8")
    print(report)
    log.info("质检报告已保存: %s", CHECK_REPORT)
    return True


# ----------------------------- 入口 -----------------------------
def main():
    parser = argparse.ArgumentParser(description="豆瓣高分电影基础信息爬虫")
    parser.add_argument("--stage", required=True,
                        choices=["login", "list", "detail", "check", "all"])
    parser.add_argument("--limit", type=int, default=0, help="detail阶段最多采集N部（0=不限）")
    parser.add_argument("--headless", action="store_true", help="detail阶段使用无头模式")
    args = parser.parse_args()

    if args.stage == "login":
        stage_login()
    elif args.stage == "list":
        stage_list()
    elif args.stage == "detail":
        stage_detail(limit=args.limit, headless=args.headless)
    elif args.stage == "check":
        stage_check()
    elif args.stage == "all":
        if stage_list():
            stage_detail(limit=args.limit, headless=args.headless)
            stage_check()


if __name__ == "__main__":
    main()
