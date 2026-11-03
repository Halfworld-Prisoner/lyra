# -*- coding: utf-8 -*-
"""滑条彻底隐藏:提高选择器优先级,压过主题里带 html[data-theme=...] 前缀的规则。"""
import io

p = r"D:\Unity阅读器\webapp\static\css\extra.css"
t = io.open(p, encoding="utf-8").read()

HEAD = '/* ---------------- 滑条:全部只保留拖动,不要任何可视外观 ---------------- */'
i = t.index(HEAD)
j = t.index('/* ---------------- 启动失败提示条')
old = t[i:j]

new = '''/* ---------------- 滑条:全部只保留拖动,不要任何可视外观 ---------------- */
/* 玩家要求「删掉所有的滑动条显示」。★必须用 html[data-theme] 前缀提高优先级★ ——
   主题文件里有 `html[data-theme="md3"] input[type=range]` 这类规则,普通 `input[type=range]`
   会被它盖掉(玩家实测:改了但界面上还是能看到轨道和圆点)。 */
html[data-theme] input[type="range"],
html[data-theme] .field input[type="range"],
html[data-theme] input[type="range"].bare {
  -webkit-appearance: none !important; appearance: none !important;
  width: 100%; height: 26px !important; background: transparent !important;
  cursor: ew-resize; margin: 2px 0 0 !important; border: 0 !important;
  outline: none; box-shadow: none !important;
}
html[data-theme] input[type="range"]::-webkit-slider-runnable-track {
  height: 26px !important; background: transparent !important; border: 0 !important;
  box-shadow: none !important;
}
html[data-theme] input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none !important; appearance: none !important;
  width: 26px !important; height: 26px !important; border-radius: 50% !important;
  background: transparent !important; border: 0 !important; box-shadow: none !important;
}
html[data-theme] input[type="range"]::-moz-range-track {
  height: 26px !important; background: transparent !important; border: 0 !important;
}
html[data-theme] input[type="range"]::-moz-range-progress { background: transparent !important; }
html[data-theme] input[type="range"]::-moz-range-thumb {
  width: 26px !important; height: 26px !important; background: transparent !important; border: 0 !important;
}
html[data-theme] input[type="range"]:hover { background: var(--soft) !important; border-radius: 8px; }
html[data-theme] input[type="range"]:focus-visible {
  box-shadow: 0 0 0 2px var(--accent-soft) !important; border-radius: 8px;
}

'''
t = t[:i] + new + t[j:]
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("extra.css 滑条规则已加固(带 !important + html[data-theme] 前缀)")
