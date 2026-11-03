# -*- coding: utf-8 -*-
"""bare_for_list:前缀可能连着出现(【角色名】[标签]原文),改成循环剥离。"""
import io
import subprocess

P = r"D:\Unity阅读器\core\storyhook.py"
t = io.open(P, encoding="utf-8").read()

OLD = '''    s = (s or "").strip()
    s = re.sub(r"^\\[[^\\]]{0,24}\\]\\s*", "", s)      # [标签]
    s = re.sub(r"^【[^】]{1,14}】\\s*", "", s)          # 【角色名】
    return s.strip()'''

NEW = '''    s = (s or "").strip()
    # 循环剥:前缀可能连着出现(【角色名】[标签]原文),剥一层不够
    for _ in range(4):
        nxt = re.sub(r"^\\[[^\\]]{0,24}\\]\\s*", "", s)     # [标签]
        nxt = re.sub(r"^【[^】]{1,14}】\\s*", "", nxt)       # 【角色名】
        if nxt == s:
            break
        s = nxt
    return s.strip()'''

assert OLD in t, "没找到函数体"
t = t.replace(OLD, NEW, 1)
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("已改为循环剥离")

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:200])

import sys
sys.path.insert(0, r"D:\Unity阅读器")
from core.storyhook import bare_for_list  # noqa: E402
for x in ("【亞戈】[set_Text]「台詞」", "[set_Text]【亞戈】「台詞」", "【訊息速度】開啟後…", "「普通台詞」"):
    print("  %-32s -> %s" % (x, bare_for_list(x)))
