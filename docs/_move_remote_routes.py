# -*- coding: utf-8 -*-
r"""把 /api/remote 三个 POST 路由从 GET 区挪到 POST 区(/api/settings 之前)。"""
import io
import shutil
import subprocess

SRC = r"D:\Unity阅读器"
P = SRC + r"\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

start = t.find('            if p == "/api/remote":')
assert start > 0, "找不到 remote 路由"
# 到下一个同级路由为止
nxt = t.find('\n            if p == "/api/stats"', start)
assert nxt > start, "找不到结束位置"
block = t[start:nxt]
t = t[:start] + t[nxt + 1:]
print("① 已摘出 %d 字符" % len(block))

anchor = '            if p == "/api/settings":'
assert anchor in t, "找不到 POST 处理器锚点"
t = t.replace(anchor, block.rstrip("\n") + "\n\n" + anchor, 1)
print("② 已插入 POST 处理器(/api/settings 之前)")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("   语法:", "通过" if r.returncode == 0 else (r.stderr or "")[-250:])
if r.returncode == 0:
    shutil.copy2(P, r"D:\Lyra\app\webapp\server.py")
    print("   已部署")
