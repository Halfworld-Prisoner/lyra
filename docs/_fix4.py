# -*- coding: utf-8 -*-
"""本轮四条小改:滑条全隐 / 本机女声加回 / 右键菜单配色 / 悬浮窗拿到主题。"""
import io

def rw(p, pairs, must=True):
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new)
            print("  OK   %s" % old[:52].replace("\n", "\\n"))
        elif must:
            print("  !!   没找到:%s" % old[:52].replace("\n", "\\n"))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


# 1) 悬浮窗数据里带上主题(子代理要用)
rw(r"D:\Unity阅读器\webapp\server.py", [(
    '        "auto_next": bool(cfg.get("auto_next")),\n        "corner": int(cfg.get("float_corner", 18) or 0),',
    '        "auto_next": bool(cfg.get("auto_next")),\n'
    '        "corner": int(cfg.get("float_corner", 18) or 0),\n'
    '        "theme": cfg.get("theme") or "dark",      # 悬浮窗按主题换配色\n'
    '        "md3": (cfg.get("theme") or "") == "md3",'
)])

# 2) 所有滑条都不显示外观(以前只对 .bare 生效)
rw(r"D:\Unity阅读器\webapp\static\css\extra.css", [(
    '/* ---------------- 滑条:只保留拖动,不要那条轨道和圆点 ---------------- */',
    '''/* ---------------- 滑条:全部只保留拖动,不要任何可视外观 ---------------- */
/* 玩家要求「删掉所有的滑动条显示」:不限 .bare,页面上任何 range 都变成
   一条看不见的可拖区域(拖动仍然有效,数值旁边一直有文字显示)。 */
input[type="range"] {
  -webkit-appearance: none; appearance: none;
  width: 100%; height: 26px; background: transparent; cursor: ew-resize;
  margin: 2px 0 0; border: 0; outline: none; box-shadow: none;
}
input[type="range"]::-webkit-slider-runnable-track {
  height: 26px; background: transparent; border: 0; box-shadow: none;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none;
  width: 26px; height: 26px; border-radius: 50%;
  background: transparent; border: 0; box-shadow: none;
}
input[type="range"]::-moz-range-track { height: 26px; background: transparent; border: 0; }
input[type="range"]::-moz-range-thumb { width: 26px; height: 26px; background: transparent; border: 0; }
input[type="range"]:hover { background: var(--soft); border-radius: 8px; }
input[type="range"]:focus-visible { box-shadow: 0 0 0 2px var(--accent-soft); border-radius: 8px; }

/* 旧写法(只对 .bare)保留着,免得别处引用 */'''
)])

# 3) 右键菜单配色:以前用 --toast-bg(MD3 下是浅色的 inverse-surface)+ --text(浅色)= 看不见
rw(r"D:\Unity阅读器\webapp\static\css\extra.css", [(
    '''.ctx-menu {
  position: fixed; z-index: 9999; min-width: 176px; padding: 5px;
  border-radius: 10px; border: 1px solid var(--line-2);
  background: var(--toast-bg); box-shadow: 0 12px 32px rgba(0, 0, 0, .45);
}''',
    '''.ctx-menu {
  /* ★配色必须用「面板色 + 正文色」这一对★
     以前写的是 --toast-bg + --text:在 MD3 主题里 --toast-bg 映射到 inverse-surface(浅色),
     而 --text 是浅色的 on-surface → 浅字浅底,菜单文字直接看不见(玩家反馈)。
     panel-2 / text 在所有主题里都是"深底浅字"或"浅底深字"的成对值,永远不会撞。 */
  position: fixed; z-index: 9999; min-width: 184px; padding: 6px;
  border-radius: var(--radius-sm, 10px); border: 1px solid var(--line-2);
  background: var(--panel-2); color: var(--text);
  box-shadow: 0 12px 32px rgba(0, 0, 0, .38);
}'''
)])

# 4) 本机(Windows SAPI)语音:不再按性别过滤 —— 玩家要把系统自带的那个女声加回来
rw(r"D:\Unity阅读器\core\tts.py", [(
    '''    try:
        voices = list(SpeechSynthesizer.all_voices)
        voices.sort(key=lambda v: 0 if v.language.lower().startswith("zh") else 1)
        out += [("sapi:" + v.display_name, v.language) for v in voices
                if _winrt_male(v)]''',
    '''    try:
        voices = list(SpeechSynthesizer.all_voices)
        voices.sort(key=lambda v: 0 if v.language.lower().startswith("zh") else 1)
        # ★本机语音不再按性别过滤★:玩家要求把系统自带的女声(慧慧/瑶瑶)加回来。
        #   "只留男声"只针对我们自己提供的语音包与在线音色。
        out += [("sapi:" + v.display_name, v.language) for v in voices]'''
)])
print("完成")
