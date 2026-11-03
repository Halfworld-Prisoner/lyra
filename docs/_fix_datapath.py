# -*- coding: utf-8 -*-
"""游戏卡片补上 data-path(右键菜单要用它启动游戏/复制路径)。"""
import io

p = r"D:\Unity阅读器\webapp\static\js\views\library.js"
t = io.open(p, encoding="utf-8").read()
old = "  card.className = 'game-card' + (g.path === cur ? ' active' : '');"
new = ("  card.className = 'game-card' + (g.path === cur ? ' active' : '');\n"
       "  card.dataset.path = g.path || '';        /* 右键菜单要用 */\n"
       "  card.dataset.name = g.name || '';")
assert old in t, "没找到那行"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("已补 data-path")
for i, ln in enumerate(t.split("\n"), 1):
    if "dataset.path" in ln:
        print("  %4d %s" % (i, ln.strip()))
