# -*- coding: utf-8 -*-
r"""把"累计阅读统计"接进后端:
   ① import readstats
   ② 每读到一句( _on_line )就累加
   ③ 接口:/api/stats(取)、/api/stats/reset(清零)
   ④ /api/state 里带出 stats,实时剧情页直接用
   ⑤ 退出时落盘(flush)
"""
import io
import re
import subprocess

SV = r"D:\Unity阅读器\webapp\server.py"
t = io.open(SV, encoding="utf-8").read()

# ① import
if "import readstats" not in t:
    t = t.replace("from core import storyhook", "from core import storyhook\nfrom core import readstats", 1)
    print("① import ✓")

# ② _on_line 里累加
i = t.find("def _on_line(")
assert i > 0, "没找到 _on_line"
j = t.find("\ndef ", i + 10)
body = t[i:j]
if "readstats.note" not in body:
    m = re.search(r"\n(    )(\w[\w\.\[\]\"']*)\s*=\s*text", body)
    ins = ("\n    # ★累计阅读统计★(永久保存,见 core/readstats.py)\n"
           "    try:\n"
           "        readstats.note(HOOK.game or {}, text)\n"
           "    except Exception:\n"
           "        pass\n")
    # 插到函数体开头(取到 text 之后最稳:直接放函数第一行之后)
    k = body.find("\n", body.find(":"))
    body2 = body[:k + 1] + ins + body[k + 1:]
    t = t[:i] + body2 + t[j:]
    print("② _on_line 已接入统计")

# ③④ 接口 + state
if "/api/stats" not in t:
    t = t.replace('            if p == "/api/ui/schema":',   # 若存在则插它前面,不存在则用后面的锚点
                  '            if p == "/api/stats":\n'
                  '                g = HOOK.game or {}\n'
                  '                return self._json({"ok": True, "game": readstats.for_game(g),\n'
                  '                                   "top": readstats.top(8),\n'
                  '                                   "path": readstats.PATH})\n\n'
                  '            if p == "/api/ui/schema":', 1)
    if "/api/stats" not in t:      # 回滚过,没有 ui 接口 → 换个锚点
        t = t.replace('            if p == "/api/rules":',
                      '            if p == "/api/stats":\n'
                      '                g = HOOK.game or {}\n'
                      '                return self._json({"ok": True, "game": readstats.for_game(g),\n'
                      '                                   "top": readstats.top(8),\n'
                      '                                   "path": readstats.PATH})\n\n'
                      '            if p == "/api/rules":', 1)
    print("③ /api/stats ✓")

if '"/api/stats/reset"' not in t:
    t = t.replace('            if p == "/api/stop":',
                  '            if p == "/api/stats/reset":\n'
                  '                r = readstats.reset(HOOK.game or {})\n'
                  '                if r.get("ok"):\n'
                  '                    add_log("已清零累计阅读记录", "info")\n'
                  '                return self._json(r)\n\n'
                  '            if p == "/api/stop":', 1)
    print("③ /api/stats/reset ✓")

if '"stats": readstats.for_game' not in t:
    t = t.replace('                    "metrics": metrics(),',
                  '                    "metrics": metrics(),\n'
                  '                    "stats": readstats.for_game(HOOK.game or {}),   # 累计阅读(永久)', 1)
    print("④ /api/state 带出 stats ✓")

# ⑤ 退出前落盘
if "readstats.flush()" not in t:
    t = t.replace("def _quit_all():", "def _quit_all():\n    try:\n        readstats.flush()\n    except Exception:\n        pass", 1)
    print("⑤ 退出落盘 ✓")

io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SV],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:250])
for key in ("readstats.note", "/api/stats", '"stats": readstats'):
    print("  含 %-20s %s" % (key, "✓" if key in t else "✗"))
