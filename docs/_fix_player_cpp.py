# -*- coding: utf-8 -*-
"""把 player.cpp 里新加的主题函数/消息处理类挪到使用点之前(编译顺序问题)。"""
import io
import re

p = r"D:\Unity阅读器\installer\player.cpp"
t = io.open(p, encoding="utf-8").read()

start = t.index("/* 标题栏也做成深色/浅色,和界面统一")
end = t.index("int WINAPI wWinMain")
block = t[start:end]
t = t[:start] + t[end:]

# 插到 "WebView2 回调" 这一段之前
anchor = "/* ---------------------------------------------------------------- WebView2 回调 */"
assert anchor in t, "找不到插入点"
t = t.replace(anchor, block.rstrip() + "\n\n" + anchor, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("已把主题相关代码挪到回调段之前")
for i, ln in enumerate(t.split("\n"), 1):
    if "ApplyWindowTheme" in ln or "class WebMessageHandler" in ln or "ApplyDarkTitleBar" in ln:
        print("  %4d  %s" % (i, ln.strip()[:80]))
