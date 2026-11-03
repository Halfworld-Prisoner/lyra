# -*- coding: utf-8 -*-
r"""把 /api/open_browser 从 GET 处理器挪到 POST 处理器(前端用的是 post ✗ → 之前 404)。"""
import io
import re
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

# ① 摘出这段路由
m = re.search(r'            if p == "/api/open_browser":\n(?:.*\n)*?\n', t)
assert m, "找不到已有路由"
block = m.group(0)
t = t[:m.start()] + t[m.end():]
print("① 已从原位置摘出")

# ② 插到 POST 处理器里(/api/stop 之前)
anchor = '            if p == "/api/stop":'
assert anchor in t, "找不到 POST 处理器里的 /api/stop"
t = t.replace(anchor, block.rstrip("\n") + "\n\n" + anchor, 1)
print("② 已插入 POST 处理器")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("   语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:250])

import shutil
shutil.copy2(P, r"D:\Lyra\app\webapp\server.py")
print("   已部署")
