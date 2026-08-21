# -*- coding: utf-8 -*-
"""
影灵 D3 全量 · 限流感知自动续跑
================================
背景：平台（sensenova deepseek-v4-flash）长跑 1.5h 后进入严格限流期，
几乎所有请求 429，单部耗时 30+ 分钟，无意义空转。

本脚本替代手工重启：
  1. 启动 build_core_llm.py --stage full（继承 llm_partial.json 断点）
  2. 每 20s 检查日志完成行是否增长；STALL_MIN 分钟无新完成 -> 判定限流/卡死，终止进程
  3. 冷却 COOLDOWN 分钟后再试，直到探测通过后持续运行至 full 自然结束

用法（后台常驻）：
    python llm_autoresume.py
退出方式：full 完成后自动退出；或手动结束进程（断点无损，随时可再启）。
"""
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
LLM_LOG = BASE / "logs" / "build_llm.log"
PY = r"D:\anaconda\python.exe"
STALL_MIN = 12        # 连续无新完成（分钟）即判定限流/卡死
COOLDOWN = 15         # 判定限流后的冷却（分钟）
POLL = 20             # 检查间隔（秒）


def done_pos():
    """日志最后一条含 [INFO] 的「完成(」字节位置（用于判断是否有新完成）"""
    if not LLM_LOG.exists():
        return 0
    data = LLM_LOG.read_bytes()
    idx = data.rfind(b"\xe5\xae\x8c\xe6\x88\x90(")   # 「完成(」UTF-8 字节
    if idx < 0:
        return 0
    # 只认 [INFO] 行内的完成(，否则向前找上一条
    line_start = data.rfind(b"\n", 0, idx) + 1
    if b"[INFO]" not in data[line_start:idx]:
        return done_pos_prev(data, idx)
    return idx


def done_pos_prev(data, idx):
    """从 idx 向前找上一条含 [INFO] 的完成(位置"""
    while idx > 0:
        idx = data.rfind(b"\xe5\xae\x8c\xe6\x88\x90(", 0, idx - 1)
        if idx < 0:
            return 0
        line_start = data.rfind(b"\n", 0, idx) + 1
        if b"[INFO]" in data[line_start:idx]:
            return idx
    return 0


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    last = done_pos()
    cycle = 0
    while True:
        cycle += 1
        print(f"[autoresume] 第 {cycle} 轮: 启动 full（基准完成位 {last}）", flush=True)
        proc = subprocess.Popen([PY, "build_core_llm.py", "--stage", "full"],
                                cwd=str(BASE),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        no_progress = time.time()
        while True:
            time.sleep(POLL)
            if proc.poll() is not None:
                print("[autoresume] full 进程已自然结束 ✔（全量完成或素材耗尽）", flush=True)
                return
            p = done_pos()
            if p > last:
                last = p
                no_progress = time.time()
            elif time.time() - no_progress > STALL_MIN * 60:
                print(f"[autoresume] 连续 {STALL_MIN} 分钟无新完成，判定限流/卡死，终止进程", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except Exception:
                    proc.kill()
                print(f"[autoresume] 冷却 {COOLDOWN} 分钟后重试", flush=True)
                time.sleep(COOLDOWN * 60)
                break


if __name__ == "__main__":
    main()
