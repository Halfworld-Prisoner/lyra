# -*- coding: utf-8 -*-
"""把 webapp/static/style.css 拆成 5 个文件,并删掉"没人用的类"所在的整条规则。

拆分按原文件的分段注释来(行号区间),不重写内容 —— 只是搬运 + 删死规则。
用法: python docs/_split_css.py
"""
import io
import os
import re

STATIC = r"D:\Unity阅读器\webapp\static"
SRC = os.path.join(STATIC, "style.css")
HTML = io.open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
JS = io.open(os.path.join(STATIC, "app.js"), encoding="utf-8").read()

# 行号区间(1 基,含两端)→ 目标文件
PLAN = [
    ("css/tokens.css", "设计令牌:颜色 / 圆角 / 阴影 / 动效。改主题色先看这里。",
     [(1, 33), (1081, 1092)]),
    ("css/themes.css", "主题:明亮 / 护眼 / Google Material 3(其余主题只覆盖变量)。",
     [(34, 71), (1093, 1157)]),
    ("css/layout.css", "骨架布局:app 外壳、侧栏、顶栏、内容区、底栏、自适应断点。",
     [(72, 259), (500, 521), (1299, 1372)]),
    ("css/components.css", "通用组件:输入、按钮、开关、分段开关、弹窗、提示、面板、列表、芯片。",
     [(260, 349), (522, 606), (794, 864), (951, 1080), (1158, 1298)]),
    ("css/views.css", "各页专属:游戏库、实时剧情、添加游戏、动画。",
     [(350, 499), (607, 793), (865, 950)]),
]


def dead_classes():
    body = re.sub(r"/\*.*?\*/", "", io.open(SRC, encoding="utf-8").read(), flags=re.S)
    out = set()
    for c in set(re.findall(r"\.([a-zA-Z][\w-]*)", body)):
        if re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", HTML):
            continue
        if re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", JS):
            continue
        out.add(c)
    return out


def split_blocks(text):
    """把 CSS 切成块:@media 整块算一块,普通规则到 '}' 结束。"""
    blocks, cur, depth = [], [], 0
    for line in text.split("\n"):
        cur.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0 and ("}" in line or "{" not in line):
            if "{" in "".join(cur):
                blocks.append("\n".join(cur))
                cur, depth = [], 0
    if cur and "".join(cur).strip():
        blocks.append("\n".join(cur))
    return blocks


def selector_of(block):
    i = block.find("{")
    return block[:i] if i >= 0 else block


def keep(block, dead):
    sel = selector_of(block)
    cls = re.findall(r"\.([a-zA-Z][\w-]*)", sel)
    if cls and all(c in dead for c in cls):
        return False
    return True


def main():
    lines = io.open(SRC, encoding="utf-8").read().split("\n")
    dead = dead_classes()
    os.makedirs(os.path.join(STATIC, "css"), exist_ok=True)
    dropped_total = 0
    for rel, desc, ranges in PLAN:
        chunks = []
        for a, b in ranges:
            chunks.append("\n".join(lines[a - 1:b]))
        text = "\n".join(chunks)
        blocks = split_blocks(text)
        kept = [b for b in blocks if keep(b, dead)]
        dropped = len(blocks) - len(kept)
        dropped_total += dropped
        head = ("/* %s\n   由 style.css 拆分而来(内容未改写)。\n   %s */\n\n"
                % (rel.split('/')[-1], desc))
        out = head + "\n".join(k.rstrip() for k in kept).strip() + "\n"
        io.open(os.path.join(STATIC, rel), "w", encoding="utf-8", newline="\n").write(out)
        print("  %-20s %5d 行  (删掉 %d 条死规则)" % (rel, out.count("\n"), dropped))
    print("合计删掉 %d 条死规则;死类 %d 个" % (dropped_total, len(dead)))


if __name__ == "__main__":
    main()
