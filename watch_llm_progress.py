# -*- coding: utf-8 -*-
"""
影灵 D3 LLM 全量进度监视
=========================
每 60 秒读取 llm_partial.json + build_llm.log，刷新简洁进度文件
logs/llm_progress.txt，供随时查看（记事本 / Get-Content 均可）。

用法：
    python watch_llm_progress.py         # 常驻，每 60s 刷新一次
    python watch_llm_progress.py --once  # 只刷新一次后退出（手动查一次）
"""
import argparse
import json
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENRICHED = BASE / "data" / "enriched"
LLM_LOG = BASE / "logs" / "build_llm.log"
OUT = BASE / "logs" / "llm_progress.txt"
TOTAL = 590          # 全量片数
REFRESH = 60         # 刷新间隔（秒）
TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2})\s+\[INFO\]\s+(\[(\d+)/(\d+)\]\s+\S+\s+(加工中|完成))")
START_RE = re.compile(r"(\d{2}:\d{2}:\d{2})\s+\[INFO\] LLM 加工启动")


def _fmt_dur(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600}h {sec % 3600 // 60}m {sec % 60}s"


def refresh():
    partial = {}
    pf = ENRICHED / "llm_partial.json"
    if pf.exists():
        partial = json.loads(pf.read_text(encoding="utf-8"))
    ok = sum(1 for v in partial.values() if v.get("status") == "ok")
    ptn = sum(1 for v in partial.values() if v.get("status") == "partial")
    done = len(partial)

    # 本次运行起点：日志最后一条「LLM 加工启动」
    log_text = LLM_LOG.read_text(encoding="utf-8", errors="replace") if LLM_LOG.exists() else ""
    t_start = None
    for line in reversed(log_text.splitlines()):
        m = START_RE.search(line)
        if m:
            t_start = m.group(1)
            break
    start_ts = None
    if t_start:
        try:
            start_ts = time.mktime(time.strptime(time.strftime("%Y-%m-%d ") + t_start, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            start_ts = None

    # 本次运行已完成的部数（partial 里 at >= 启动时间）
    done_run = 0
    if start_ts:
        for v in partial.values():
            try:
                at = time.mktime(time.strptime(v.get("at", ""), "%Y-%m-%d %H:%M:%S"))
                if at >= start_ts:
                    done_run += 1
            except (ValueError, TypeError):
                pass

    now = time.time()
    lines = ["=" * 56, "影灵 D3 LLM 全量加工进度", "=" * 56,
             f"刷新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"进度: {done}/{TOTAL} ({done / TOTAL * 100:.1f}%)   落盘 {done} 部 (ok {ok}, partial {ptn})"]
    if start_ts:
        elapsed = now - start_ts
        lines.append(f"本次运行: 启动于 {t_start}, 已运行 {_fmt_dur(elapsed)}, 本次完成 {done_run} 部")
        if done_run > 0:
            rate = elapsed / done_run
            remain = (TOTAL - done) * rate
            lines.append(f"速率: {rate:.0f}s/部 | 剩余 {TOTAL - done} 部 | 预计还需 {_fmt_dur(remain)} "
                         f"-> 约 {time.strftime('%H:%M', time.localtime(now + remain))} 完成")
    else:
        lines.append("本次运行: 日志中未找到启动记录（尚未开始或日志被清）")

    # 最近完成与当前处理（从日志尾部向上取）
    cur, last_done = None, None
    for line in reversed(log_text.splitlines()):
        if last_done is None:
            m = re.search(r"\[(\d+)/(\d+)\]\s+(\S+)\s+完成\((\d) 项中 (\d) 项有值\)", line)
            if m:
                last_done = m.groups()
        if cur is None:
            m = re.search(r"\[(\d+)/(\d+)\]\s+(\S+)\s+加工中", line)
            if m:
                cur = m.groups()
        if cur and last_done:
            break
    if cur:
        lines.append(f"当前处理: 第 {cur[0]}/{cur[1]} 部 ({cur[2]})")
    if last_done:
        lines.append(f"最近完成: {last_done[2]}（5 项中 {last_done[4]}/{last_done[3]} 项有值）")

    # 最近日志尾部（细节）
    tail = [l for l in log_text.splitlines() if l.strip()][-6:]
    lines += ["--- 日志尾部 ---"] + [l for l in tail if not l.strip().startswith("PS")]

    text = "\n".join(lines) + "\n"
    # utf-8-sig 带 BOM：记事本 / PowerShell Get-Content 均能正确显示中文
    OUT.write_text(text, encoding="utf-8-sig")
    print(text)
    return text


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="影灵 D3 LLM 进度监视")
    p.add_argument("--once", action="store_true", help="只刷新一次后退出")
    args = p.parse_args()
    refresh()
    if args.once:
        return
    print(f"[watch] 常驻监视中，每 {REFRESH}s 刷新 {OUT}（Ctrl+C 退出）")
    while True:
        time.sleep(REFRESH)
        try:
            refresh()
        except Exception as e:
            print(f"[watch] 刷新失败: {e}")


if __name__ == "__main__":
    import sys
    main()
