# -*- coding: utf-8 -*-
"""悬浮窗自检:把 8 种状态 × 两种形态 × 4 套主题直接渲染成图(不开窗口,不抢焦点)。

用法: python docs/_float_test.py
输出: docs/_shots/悬浮窗_总览.png        ← 暗夜(和以前一样)
      docs/_shots/悬浮窗_总览_light.png  ← 明亮
      docs/_shots/悬浮窗_总览_sepia.png  ← 护眼
      docs/_shots/悬浮窗_总览_md3.png    ← Material 3

配色由 data["theme"] 驱动(server.py 的 _float_sample 已经把这个键带过来了),
所以这里只要在 data 里塞 theme,就能把四套配色一次看全。
"""
import os
import sys

sys.path.insert(0, r"D:\Unity阅读器")
from PIL import Image, ImageDraw          # noqa: E402

from core import floatwin as fw           # noqa: E402

OUT = r"D:\Unity阅读器\docs\_shots"
FAKE_TEXT = "「こんなところで何をしているんだ、アルゴ。」这句很长很长很长很长很长很长很长很长很长很长"

CASES = [
    ("reading", "读取中", "KnightsCollege_2"),
    ("speaking", "朗读中", "KnightsCollege_2"),
    ("idle", "待机", "KnightsCollege_2"),
    ("menu", "菜单中·暂停读", "KnightsCollege_2"),
    ("hookoff", "LDC 关", "KnightsCollege_2"),
    ("paused", "已暂停", "KnightsCollege_2"),
    ("norun", "游戏未运行", "KnightsCollege_2"),
    ("nogame", "未选择游戏", ""),
]

# 画布底色跟着主题走,才看得出卡片边缘(浅色主题的卡片是白的)
CANVAS = {"dark": (24, 26, 34), "light": (241, 243, 248),
          "sepia": (243, 234, 216), "md3": (20, 18, 24)}
LABEL = {"dark": (200, 206, 220), "light": (90, 100, 120),
         "sepia": (110, 95, 70), "md3": (200, 196, 208)}


def render_theme(theme, out_path):
    win = fw.FloatWin(data_getter=lambda: {}, on_action=lambda k: None)
    shots = []
    for state, label, game in CASES:
        data = {
            "state": state, "label": label, "theme": theme,
            "sub": "内存 173MB · 读取 1.2字/秒 · 已读 128",
            "game": game,
            "text": FAKE_TEXT if game else "",
            "count": 128,
            "cells": [("内存", "173 MB"), ("读取速度", "1.2 字/秒"),
                      ("朗读速度", "4.8 字/秒"), ("已读 / 过滤", "128 / 37")],
            "auto_say": True, "auto_next": False, "corner": 18,
        }
        accent = fw.state_color(theme, state)      # 浅色底要用更深的同义色
        pill = win._render_pill(data, label, accent, 18)
        card = win._render_expanded(data, label, accent, 18)
        shots.append((pill, card))

    pad, gap = 16, 12
    left_w = max(p.width for p, _ in shots)
    right_w = max(c.width for _, c in shots)
    col_h = sum(p.height for p, _ in shots) + gap * (len(shots) - 1)
    col2_h = sum(c.height for _, c in shots) + gap * (len(shots) - 1)
    W = pad * 2 + left_w + 28 + right_w
    H = pad * 2 + max(col_h, col2_h) + 26
    canvas = Image.new("RGB", (W, H), CANVAS.get(theme, CANVAS["dark"]))
    d = ImageDraw.Draw(canvas)
    fg = LABEL.get(theme, LABEL["dark"])
    d.text((pad, 6), "缩小态(胶囊) 246×58   [" + theme + "]",
           font=win._f(12, True), fill=fg)
    d.text((pad + left_w + 28, 6), "展开态(卡片) 392×302",
           font=win._f(12, True), fill=fg)
    y = 26
    for p, _ in shots:
        canvas.paste(p, (pad, y), p)
        y += p.height + gap
    y = 26
    for _, c in shots:
        canvas.paste(c, (pad + left_w + 28, y), c)
        y += c.height + gap
    canvas.save(out_path)
    return canvas.size


def main():
    os.makedirs(OUT, exist_ok=True)
    # dark 沿用老文件名,免得别人找不到
    plans = [("dark", "悬浮窗_总览.png"),
             ("light", "悬浮窗_总览_light.png"),
             ("sepia", "悬浮窗_总览_sepia.png"),
             ("md3", "悬浮窗_总览_md3.png")]
    for theme, name in plans:
        size = render_theme(theme, os.path.join(OUT, name))
        print("  %-6s -> %-26s %s" % (theme, name, size))
    print("已写出", OUT)


if __name__ == "__main__":
    main()
