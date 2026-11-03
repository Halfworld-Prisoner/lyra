# -*- coding: utf-8 -*-
r"""修统计页在 MD3 / 明亮主题下的适配:

问题:
  · 大数字用了 background-clip:text 的渐变写法 → MD3 下字体行高不同,**数字被裁掉顶部**;
  · 浅色主题下渐变对比度不足;
  · 圆盘/波浪条的兜底色是写死的蓝紫,不跟主题。

改法:
  · 数字改成 **主题实色**(var(--accent)),不再用渐变裁切 → 不可能再被裁、且四套主题自动适配;
  · 显式给行高与上下内边距,杜绝裁切;
  · 兜底色改用主题变量(带安全回退)。
"""
import io
import os
import re
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"
CSS = os.path.join(STATIC, "css", "extra.css")
c = io.open(CSS, encoding="utf-8").read()

BLOCK = '''

/* ================= 阅读统计:主题适配修正(数字不再被裁) ================= */
/* 数字一律用主题实色,不用渐变裁切 —— 浅色主题也不会裁、对比度也够 */
.stat-big { display: flex; align-items: baseline; gap: 10px; overflow: visible !important; }
.stat-big b,
.stats-entry-num b {
  font-size: 44px;
  line-height: 1.24;                 /* 给足行高,避免数字顶部被裁 */
  padding: 2px 0 4px;
  font-weight: 700;
  color: var(--accent);              /* ★主题色★ */
  background: none !important;
  -webkit-text-fill-color: currentColor !important;
  background-clip: border-box !important;
  -webkit-background-clip: border-box !important;
  display: inline-block;
  overflow: visible !important;
}
.stat-big span { color: var(--muted); font-size: 14px; line-height: 1.4; }
.stat-big em { color: var(--muted); font-size: 12.5px; }

/* 迷你卡片里的数字:用主文字色,浅色主题下也清楚 */
.mini-stats > div > b, .stats-rank b { color: var(--text); }

/* 圆盘/波浪条:兜底色跟主题走(不再写死蓝紫) */
.stats-wave i { background: linear-gradient(180deg, var(--accent), var(--accent-soft, var(--accent))); }
.stats-rank .bar i { background: linear-gradient(90deg, var(--accent), var(--accent-soft, var(--accent))); }
.stats-donut .hole-t { fill: var(--text); }
.stats-donut .hole-s { fill: var(--muted); }
.stats-donut .ring-bg { stroke: var(--soft); }

/* 覆盖层在浅色主题下的层次:给卡片一点边,免得糊在一起 */
.stats-overlay .panel { border: 1px solid var(--line); }
.stats-top .btn, .stats-overlay .btn { color: var(--text); }
'''
if "主题适配修正" not in c:
    c += BLOCK
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("① 已追加主题适配样式")
else:
    print("① 已有修正样式")

# 部署
import shutil
shutil.copy2(CSS, r"D:\Lyra\app\webapp\static\css\extra.css")
print("② 已部署")
