# -*- coding: utf-8 -*-
"""页面底部那条细滚动条:锁死 wrap 的高度与溢出(上一条命令的转义写坏了,这次用文件方式)。"""
import io
import os

I = r"D:\Unity阅读器\installer"
OLD = ".wrap{display:flex;flex-direction:column;height:100%;padding:16px 18px 14px}"
NEW = ".wrap{display:flex;flex-direction:column;height:100%;padding:14px 16px 12px;overflow:hidden}"

for fn in ("ui.html", "ui_uninstall.html"):
    p = os.path.join(I, fn)
    t = io.open(p, encoding="utf-8").read()
    if OLD in t:
        t = t.replace(OLD, NEW, 1)
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        print("  OK  %s 已锁死溢出" % fn)
    elif NEW in t:
        print("  --  %s 已经是新的" % fn)
    else:
        print("  !!  %s 没找到 .wrap 规则,请看:" % fn)
        for ln in t.split("\n"):
            if ".wrap{" in ln:
                print("      " + ln.strip()[:100])
