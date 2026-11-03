# -*- coding: utf-8 -*-
r"""让累计统计"读完立刻落盘":
   · 节流 5 秒 → 1 秒
   · 攒够 3 句也立刻写
   · 加一个后台线程每秒兜底 —— 玩家直接杀进程/关窗口也不会丢一大段
"""
import io
import os
import subprocess
import sys
import time

P = r"D:\Unity阅读器\core\readstats.py"
t = io.open(P, encoding="utf-8").read()

t = t.replace("SAVE_EVERY = 5.0          # 至少隔这么久落一次盘",
              "SAVE_EVERY = 1.0          # 至少隔这么久落一次盘(1 秒:强杀进程最多丢 1 秒)")
t = t.replace("SAVE_LINES = 20           # 或者攒够这么多句",
              "SAVE_LINES = 3            # 攒够这么多句立刻落盘")

FLUSHER = '''def _flusher():
    """后台每秒检查:有脏数据就写盘。

    为什么要它:玩家可能直接关窗口或用任务管理器杀进程,那种情况走不到"退出保存"。
    有它兜底,最多丢最后 1 秒的字,不会出现"读了一大段、重启就没了"。
    """
    while True:
        try:
            time.sleep(1.0)
            with _lock:
                if _dirty:
                    _save(force=True)
        except Exception:
            pass


threading.Thread(target=_flusher, daemon=True).start()


'''
if "_flusher" not in t:
    t = t.replace("def key_of(game: dict) -> str:", FLUSHER + "def key_of(game: dict) -> str:", 1)
    print("  已加后台落盘线程")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("  语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:200])

# ---- 模块层验证:写完不等 5 秒,看磁盘上有没有 ----
sys.path.insert(0, r"D:\Unity阅读器")
import importlib
import core.readstats as R
importlib.reload(R)
g = {"exe": r"D:\games\flush-test\g.exe", "name": "落盘测试"}
R.reset(g)
time.sleep(0.1)
for s in ("「第一句测试。」", "「第二句测试。」"):
    R.note(g, s)
time.sleep(1.4)                     # 只等后台兜底线程一轮
import json
d = json.load(io.open(R.PATH, encoding="utf-8-sig"))
key = R.key_of(g)
got = int((d["games"].get(key) or {}).get("chars") or 0)
print("  刚写完 1.4 秒后磁盘上的字数 = %d → %s" % (got, "立刻落盘 ✓" if got > 0 else "还没落盘 ✗"))
R.reset(g)
print("  测试数据已清理")
subprocess.run(["cmd", "/c", "copy", "/Y", P, r"D:\Lyra\app\core\readstats.py"], capture_output=True)
print("  已部署到应用")
