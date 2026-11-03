# -*- coding: utf-8 -*-
r"""把 note_short_line 的挂钩从"空文本提前返回"挪到 commit() 真正返回台词的地方。"""
import io
import os
import re
import subprocess
import time

SH = r"D:\Unity阅读器\core\storyhook.py"
SV = r"D:\Unity阅读器\webapp\server.py"
APP = r"D:\Lyra\app"
t = io.open(SH, encoding="utf-8").read()

# ① 删掉插错的那段
bad = """        if not text:
            try:
                    self.note_short_line(text)
            except Exception:
                    pass
            return \"\""""
if bad in t:
    t = t.replace(bad, """        if not text:
            return \"\"""", 1)
    print("① 已移除插错位置的挂钩")
else:
    print("① !! 没找到插错的那段")

# ② 在 commit() 的**最后一个 return** 前插入
i = t.find("def commit(")
j = t.find("\n    def ", i + 10)
body = t[i:j]
rets = list(re.finditer(r"\n(        )return (.+)", body))
if rets:
    last = rets[-1]
    indent = last.group(1)
    ins = ("\n%s# 这一句要被读出来 → 拿它判定是不是在选择/卡牌画面" % indent
           + "\n%stry:" % indent
           + "\n%s    self.note_short_line(%s)" % (indent, last.group(2).strip().rstrip(";").replace("return ", ""))
           + "\n%sexcept Exception:" % indent
           + "\n%s    pass" % indent)
    body2 = body[:last.start()] + ins + body[last.start():]
    t = t[:i] + body2 + t[j:]
    print("② 已挂到 commit 的最后一个 return 之前:", last.group(2).strip()[:48])
else:
    print("② !! commit 里没找到 return")

io.open(SH, "w", encoding="utf-8", newline="\n").write(t)

# ③ 打印核对
i = t.find("def commit(")
j = t.find("\n    def ", i + 10)
seg = t[i:j]
k = seg.find("note_short_line")
print("--- 挂钩处上下文 ---")
print(seg[max(0, k - 200):k + 120])

# ④ 语法
for f in (SH, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-16s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else (r.stderr or "")[:200]))

# ⑤ 功能自测:连着喂三条短句,看会不会进入"选择中"
sys_path = r"D:\Unity阅读器"
import sys
sys.path.insert(0, sys_path)
import importlib
import core.storyhook as sh
importlib.reload(sh)
f = sh.StoryFilter()
print("  初始 choice_active =", f.choice_active())
for x in ("攻击", "防御", "使用道具"):
    f.note_short_line(x)
print("  喂了三条短句后 choice_active =", f.choice_active())
f2 = sh.StoryFilter()
for x in ("「今天的天气真不错呢。」", "「我们出发吧!」", "「路上小心。」"):
    f2.note_short_line(x)
print("  三条带引号台词(不该触发) =", f2.choice_active())

# ⑥ 部署
for rel in (r"core\storyhook.py", r"webapp\server.py"):
    s, d = os.path.join(sys_path, rel), os.path.join(APP, rel)
    if os.path.isfile(s):
        import shutil
        shutil.copy2(s, d)
print("⑥ 已同步到应用")
