# -*- coding: utf-8 -*-
r"""一行修复:stats.js 里取覆盖层用的 id 要跟 index.html 一致(statsOverlay)。"""
import io
import shutil
import subprocess

D = chr(36)                     # "$"
P = r"D:\Unity阅读器\webapp\static\js\views\stats.js"
t = io.open(P, encoding="utf-8").read()

old = "const ov = " + D + "('view-stats');"
new = "const ov = " + D + "('statsOverlay');"

if old in t:
    t = t.replace(old, new, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("  已改:", new)
elif new in t:
    print("  已经是新写法")
else:
    print("  !! 两种都没找到,打印现状:")
    for i, l in enumerate(t.split("\n")):
        if "const ov" in l:
            print("   ", i + 1, repr(l))

r = subprocess.run(["node", "--check", P], capture_output=True, text=True)
print("  node --check:", "通过" if r.returncode == 0 else r.stderr[:200])

shutil.copy2(P, r"D:\Lyra\app\webapp\static\js\views\stats.js")
a = io.open(r"D:\Lyra\app\webapp\static\index.html", encoding="utf-8").read()
b = io.open(r"D:\Lyra\app\webapp\static\js\views\stats.js", encoding="utf-8").read()
print("  核对 → HTML 有 statsOverlay:", "statsOverlay" in a,
      "| JS 取 statsOverlay:", ("statsOverlay" in b and "view-stats" not in b))
