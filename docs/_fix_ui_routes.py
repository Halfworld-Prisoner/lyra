# -*- coding: utf-8 -*-
"""修:4 个 POST 路由被插进了 GET 处理器(所以 404)。挪到 do_POST 里。"""
import io
import re
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

# 把这 4 段整体摘出来
names = ['"/api/ui/layout"', '"/api/ui/layout/reset"', '"/api/ui/layout/import"', '"/api/ui"']
blocks = []
for n in names:
    i = t.find("            if p == " + n + ":")
    assert i > 0, "找不到路由 " + n
    # 到下一条同缩进的 if p == 为止
    j = t.find("\n            if p == ", i + 10)
    if j < 0:
        j = t.find("\n\n", i)
    blocks.append(t[i:j])
    t = t[:i] + t[j:]
print("  已摘出 %d 段 POST 路由" % len(blocks))

# 插到 POST 处理器里(/api/settings 之前)
anchor = '            if p == "/api/settings":'
k = t.find(anchor)
assert k > 0, "找不到 POST 处理器里的 /api/settings"
t = t[:k] + "\n".join(blocks) + "\n\n" + t[k:]
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("  已插入到 POST 处理器")

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("  语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:250])
