# -*- coding: utf-8 -*-
"""微调:日志框与说明块严格重合;「显示详情」按钮挪到状态行右侧。"""
import io

p = r"D:\Unity阅读器\installer\setup.c"
t = io.open(p, encoding="utf-8").read()
before = t

# 日志框:与说明块同一矩形(说明块起点 = y-184,高度 176)
t = t.replace("                                 18, y - 132, 530, 176, h, (HMENU)IDC_LOG, g_hInst, NULL);",
              "                                 18, y - 184, 530, 176, h, (HMENU)IDC_LOG, g_hInst, NULL);")

# 详情按钮:找实际那一行,按行替换
lines = t.split("\n")
for i, ln in enumerate(lines):
    if "IDC_DETAIL, g_hInst" in ln and "CreateWindowW" not in ln:
        lines[i] = "                                  432, y - 2, 116, 24, h, (HMENU)IDC_DETAIL, g_hInst, NULL);"
        print("  详情按钮位置已改:line", i + 1)
        break
t = "\n".join(lines)

if t != before:
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("setup.c 已微调")
else:
    print("setup.c 没有变化(检查一下)")
for i, ln in enumerate(t.split("\n"), 1):
    if "IDC_LOG, g_hInst" in ln or "IDC_DETAIL, g_hInst" in ln or "530, 176, h, NULL" in ln:
        print("  %4d %s" % (i, ln.strip()))
