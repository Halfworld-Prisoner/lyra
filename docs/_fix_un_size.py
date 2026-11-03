# -*- coding: utf-8 -*-
"""卸载器窗口放大到能装下网页;页面本身禁止溢出(否则右栏被切、底部出横向滚动条)。"""
import io
import os

I = r"D:\Unity阅读器\installer"

p = os.path.join(I, "uninstall.c")
t = io.open(p, encoding="utf-8").read()
if "int w = 556, hgt = 452;" in t:
    t = t.replace("int w = 556, hgt = 452;", "int w = 680, hgt = 560;   /* 要装得下网页 */", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  uninstall.c 窗口 -> 680x560")
else:
    print("  --  uninstall.c 尺寸那行没匹配")

p = os.path.join(I, "ui_uninstall.html")
t = io.open(p, encoding="utf-8").read()
if "overflow:hidden" not in t:
    t = t.replace("html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);",
                  "html,body{margin:0;height:100%;overflow:hidden;background:var(--bg);color:var(--txt);", 1)
    t = t.replace(".cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}",
                  ".cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;min-width:0}\n"
                  "  .box{min-width:0}\n"
                  "  .box ul{padding-left:14px}", 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  ui_uninstall.html 禁止溢出 + 两栏 minmax(0,1fr)")
else:
    print("  --  页面已有 overflow:hidden")
