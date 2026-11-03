# -*- coding: utf-8 -*-
"""① 隐藏所有滚动条(保留滚动);② 角色配音页下拉框不再被刷新掀掉。"""
import io
import re

# ---------- ① 滚动条:全线隐藏(玩家说的"滑动条"就是它) ----------
p = r"D:\Unity阅读器\webapp\static\css\extra.css"
t = io.open(p, encoding="utf-8").read()
CSS = '''

/* ---------------- 滚动条:全部隐藏(保留滚动功能) ---------------- */
/* 玩家原话「删掉所有的滑动条显示,保留滑动的功能」——指的其实是**滚动条**
   (截图里那条灰色竖条)。这里整条隐藏:滚轮/触控板/键盘/拖拽都能照常滚,
   只是不再画出那条杠。 */
html[data-theme] * { scrollbar-width: none; -ms-overflow-style: none; }
html[data-theme] *::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
html[data-theme] *::-webkit-scrollbar-track { background: transparent; }
html[data-theme] *::-webkit-scrollbar-thumb { background: transparent; }
html[data-theme] ::-webkit-scrollbar { width: 0; height: 0; }
'''
if "滚动条:全部隐藏" not in t:
    io.open(p, "w", encoding="utf-8", newline="\n").write(t + CSS)
    print("① 已加「隐藏全部滚动条」的规则")
else:
    print("① 已有滚动条规则,跳过")

# ---------- ② 角色配音页:下拉框展开时绝不重建 DOM ----------
p2 = r"D:\Unity阅读器\webapp\static\js\views\cast.js"
s = io.open(p2, encoding="utf-8").read()
m = re.search(r"function castBusy\(\) \{[\s\S]*?\n\}", s)
NEW = '''function castBusy() {
  /* 玩家正在这一页上操作时(下拉框展开着 / 焦点在输入框里)**绝不重建 DOM** ——
     一重建就会把已经展开的 <select> 掀掉,玩家反馈"压根点不到、一刷新就收起来"。
     处理完再多等 1.5 秒才允许重建,免得刚好在下拉收起的那一瞬闪一下。 */
  const ae = document.activeElement;
  const busy = !!(ae && ae.closest && ae.closest('#view-cast'));
  const now = Date.now();
  if (busy) { _castBusySince = now; return true; }
  if (_castBusySince && now - _castBusySince < 1500) return true;
  return false;
}'''
if m:
    s = s[:m.start()] + NEW + s[m.end():]
    io.open(p2, "w", encoding="utf-8", newline="\n").write(s)
    print("② castBusy() 已改成"焦点在本页就不重建"")
else:
    print("② !! 没找到 castBusy(),请人工检查")
# 确保 _castBusySince 有声明
if "_castBusySince" in s and not re.search(r"let _castBusySince", s):
    s = re.sub(r"(let _castSig = [^\n]*\n)", r"\1let _castBusySince = 0;\n", s, count=1)
    io.open(p2, "w", encoding="utf-8", newline="\n").write(s)
    print("   已补 let _castBusySince 声明")
