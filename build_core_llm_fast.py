# -*- coding: utf-8 -*-
"""
影灵 D3 LLM 加工 · 并行加速版（2 路并发，保守限流）
=====================================================
限流策略：全局 12s 间隔（5 RPM），sleep 在锁外。
2 路并发以免触发 API 429（实测 3 路 + 10s 间隔仍有 429）。

用法：
  python build_core_llm_fast.py

断点续跑：中途退出后重跑自动跳过已完成的电影。
"""
import concurrent.futures
import threading
import time
import sys

import build_core_llm as llm

# ======================== 并行限流层 ========================

GLOBAL_INTERVAL = 12.0          # 全局任意两次 API 调用最小间隔（秒）
_last_call = 0.0
_lock = threading.Lock()


def _parallel_throttle():
    """替换 build_core_llm._throttle —— 线程安全、sleep 在锁外"""
    global _last_call
    while True:
        with _lock:
            now = time.time()
            wait = GLOBAL_INTERVAL - (now - _last_call)
            if wait <= 0:
                _last_call = now
                return
        time.sleep(wait)


# 写入文件互斥锁
_save_lock = threading.Lock()


def _safe_save(mid, res, partial):
    with _save_lock:
        partial[mid] = res
        llm.save_partial(partial)


def _safe_append_task(mid, task, status, note=""):
    with _save_lock:
        llm.append_task_row(mid, task, status, note)


# ======================== 待处理片单 ========================

def get_pending_list():
    partial = llm.load_partial()
    movies = llm.get_data()["movies"]
    all_ids = list(movies["movie_id"])
    pending = [mid for mid in all_ids
               if mid not in partial or llm._missing_core(partial[mid])]
    return pending, partial


# ======================== 单部处理 ========================

def process_one(mid, cfg, movies, comments, reviews, partial):
    try:
        cli = llm.client(cfg)
        res = llm.process_movie(cli, cfg, mid, movies, comments, reviews)
        if res:
            _safe_save(mid, res, partial)
            _safe_append_task(mid, "all", res["status"], "")
            nok = sum(1 for k in ("tags", "citation", "brief", "warn", "egg") if res[k])
            return mid, res, nok
        return mid, None, 0
    except Exception as e:
        llm.log.error("process_one %s 异常: %s", mid, str(e)[:120])
        return mid, None, 0


# ======================== 主流程 ========================

def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    llm._throttle = _parallel_throttle

    pending, partial = get_pending_list()
    total = len(pending)
    llm.log.info("=" * 60)
    llm.log.info("并行加速启动: 2 路并发, 全局间隔 %ss (5 RPM), 待处理 %d 部",
                 GLOBAL_INTERVAL, total)
    llm.log.info("=" * 60)

    if not pending:
        llm.log.info("全部完成，进入 merge 阶段")
        llm.stage_merge()
        return

    cfg = llm.load_cfg()
    movies, comments, reviews = llm.get_data().values()
    t0 = time.time()
    completed = ok_count = partial_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(process_one, mid, cfg, movies, comments, reviews, partial): mid
                   for mid in pending}
        for future in concurrent.futures.as_completed(futures):
            mid = futures[future]
            _, res, nok = future.result()
            completed += 1
            if res:
                if res["status"] == "ok":
                    ok_count += 1
                else:
                    partial_count += 1
                elapsed = time.time() - t0
                rate = elapsed / completed
                eta = (total - completed) * rate / 60
                llm.log.info("[%d/%d] %s %s (%d/5项) 平均%.0fs/部 预计剩余%.0fmin",
                             completed, total, mid, res["status"], nok, rate, eta)
            else:
                llm.log.warning("[%d/%d] %s 返回空结果", completed, total, mid)

            if completed % 10 == 0 or completed == total:
                rate = (time.time() - t0) / completed
                eta = (total - completed) * rate / 60
                llm.log.info("── 进度 %d/%d (%.0f%%) 平均%.0fs/部 预计剩余%.0fmin ──",
                             completed, total, completed / total * 100, rate, eta)

    elapsed = time.time() - t0
    llm.log.info("并行加工完成: %d 部, 耗时 %.1f min (%.0fs/部)",
                 completed, elapsed / 60, elapsed / completed if completed else 0)

    llm.log.info("进入 merge 阶段...")
    llm.stage_merge()
    llm.log.info("全部完工! 🎉")


if __name__ == "__main__":
    main()