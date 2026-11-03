# -*- coding: utf-8 -*-
"""build.ps1:$wvInc(WebView2 SDK 头文件目录)要放在 $inst 之后。"""
import io

p = r"D:\Unity阅读器\installer\build.ps1"
lines = io.open(p, encoding="utf-8").read().split("\n")
lines = [l for l in lines if "wvInc" not in l.split("#")[0] or "-I" not in l]
out = []
inserted = False
for l in lines:
    out.append(l)
    if (not inserted) and l.strip().startswith("$inst = Join-Path"):
        out.append('$wvInc = Join-Path $inst "build\\webview2\\build\\native\\include"'
                   '   # WebView2 SDK 头文件(安装器/卸载器要用)')
        inserted = True
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("inserted =", inserted)
for i, l in enumerate(io.open(p, encoding="utf-8").read().split("\n"), 1):
    if "wvInc" in l:
        print("  %4d %s" % (i, l.strip()[:96]))
