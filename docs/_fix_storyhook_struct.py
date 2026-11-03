# -*- coding: utf-8 -*-
"""修复上一步插错位置导致的结构损坏:
   · bare_for_list 必须是**模块级**函数(server.py 里用 storyhook.bare_for_list 调用);
   · list_verdict 必须留在 StoryFilter **类里**(缩进 4)。
"""
import io
import re
import subprocess

SH = r"D:\Unity阅读器\core\storyhook.py"
t = io.open(SH, encoding="utf-8").read()

# ① 把插错位置的那段整体摘掉(它现在夹在类中间,而且缩进是坏的)
broken = re.search(
    r"    def bare_for_list\(s: str\) -> str:\n"
    r'    """把"界面显示的那一行".*?\n'
    r"    return s\.strip\(\)\n\n\n", t, re.S)
assert broken, "找不到插错的那段"
t = t[:broken.start()] + t[broken.end():]
print("① 已摘掉插错位置的 bare_for_list")

# ② 把 list_verdict 的 def 行恢复成类方法(缩进 4)
t = t.replace("\ndef list_verdict(self, text: str) -> str:\n",
              "\n    def list_verdict(self, text: str) -> str:\n", 1)
print("② list_verdict 已恢复为类方法")

# ③ 在模块级(class StoryFilter 之前)插入正确的 bare_for_list
FUNC = '''def bare_for_list(s: str) -> str:
    """把"界面显示的那一行"还原成"游戏原文",用于黑/白名单比对。

    界面上我们会在句首拼 `【角色名】`(便于阅读),日志行还可能有 `[标签]` 前缀;
    而游戏原文两者都没有。名单比对必须把这两层剥掉,否则永远对不上
    (玩家反馈:把一句拉进黑名单,它照样被读出来)。
    """
    s = (s or "").strip()
    s = re.sub(r"^\\[[^\\]]{0,24}\\]\\s*", "", s)      # [标签]
    s = re.sub(r"^【[^】]{1,14}】\\s*", "", s)          # 【角色名】
    return s.strip()


'''
anchor = "class StoryFilter"
i = t.find(anchor)
assert i > 0, "找不到 StoryFilter 类"
t = t[:i] + FUNC + t[i:]
print("③ bare_for_list 已在模块级定义")

io.open(SH, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SH],
                   capture_output=True, text=True)
print("   语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:300])
