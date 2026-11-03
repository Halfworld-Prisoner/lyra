# -*- coding: utf-8 -*-
"""还原 player.cpp → 只做三处最必要的、可验证的改动:
   ① 解析 --designer
   ② 设计窗口 = 全屏 + 标题「Lyra · UI 创作」
   ③ 打开 /designer 而不是 /
   (window.close 的钩子先不做:主窗口的关闭按钮也能退出,避免再改坏。)"""
import io
import os
import re
import shutil
import subprocess

SRC = r"D:\Unity阅读器"
REPO = os.path.join(os.path.expanduser("~"), "Desktop", "Lyra")
SOURCE_PC = os.path.join(REPO, "installer", "player.cpp")   # 上一版可编译的副本
TARGET_PC = os.path.join(SRC, "installer", "player.cpp")

# ① 还原
shutil.copy2(SOURCE_PC, TARGET_PC)
print("① 已从仓库副本还原 player.cpp")

t = io.open(TARGET_PC, encoding="utf-8").read()

# 找到 wWinMain 与窗口创建、导航的确切写法,打印出来(便于精确改)
for pat in (r"int WINAPI wWinMain[^\n]*", r"g_hInst = hInst;[^\n]*", r"int w = [^\n]*",
            r"CreateWindowExW\(0, wc\.lpszClassName[^\n]*", r"Navigate[^\n]*"):
    for m in re.finditer(pat, t):
        print("   命中:", m.group(0)[:110])
