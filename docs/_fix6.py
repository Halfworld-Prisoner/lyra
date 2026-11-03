# -*- coding: utf-8 -*-
"""① 隐藏所有滚动条(保留滚动);② 找出是谁在刷新时重建角色配音页的下拉框。"""
import io
import re

# ① 滚动条
p = r"D:\Unity阅读器\webapp\static\css\extra.css"
t = io.open(p, encoding="utf-8").read()
CSS = '''

/* ---------------- 滚动条:全部隐藏(保留滚动功能) ---------------- */
/* 玩家原话「删掉所有的滑动条显示,保留滑动的功能」指的是**滚动条**
   (截图里那条灰色竖条)。整条隐藏:滚轮/触控板/键盘照常滚,只是不再画出那条杠。 */
html[data-theme] * { scrollbar-width: none; -ms-overflow-style: none; }
html[data-theme] *::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
html[data-theme] *::-webkit-scrollbar-thumb { background: transparent !important; }
html[data-theme] *::-webkit-scrollbar-track { background: transparent !important; }
'''
if "滚动条:全部隐藏" not in t:
    io.open(p, "w", encoding="utf-8", newline="\n").write(t + CSS)
    print("已加「隐藏全部滚动条」规则")
else:
    print("滚动条规则已存在")

# ② 谁在重建下拉框
d = r"D:\Unity阅读器\webapp\static\js"
for rel in ("views/cast.js", "views/settings_extra.js", "state.js", "boot.js"):
    fp = d + "\\" + rel.replace("/", "\\")
    try:
        s = io.open(fp, encoding="utf-8").read()
    except Exception:
        continue
    for i, ln in enumerate(s.split("\n"), 1):
        if "fillVoiceSelect" in ln or "castBusy" in ln or "castVoice" in ln:
            print("  %-22s %4d  %s" % (rel, i, ln.strip()[:88]))
