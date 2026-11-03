# -*- coding: utf-8 -*-
r"""修:权限拦截的代码被插到了错误位置(缩进错) → 后端起不来。
   改成把白名单写在 do_POST **函数内部**,不再作为类属性插入。"""
import io
import os
import re
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
P = os.path.join(SRC, "webapp", "server.py")
lines = io.open(P, encoding="utf-8").read().split("\n")

# ① 删掉插错位置的注释与 _ALLOW_ALWAYS 行
drop = []
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith("# 这些是") and "遥控播放" in s:
        drop.append(i)
    if s.startswith("_ALLOW_ALWAYS = ("):
        drop.append(i)
for i in sorted(set(drop), reverse=True):
    print("  删除第 %d 行: %s" % (i + 1, lines[i].strip()[:60]))
    del lines[i]

t = "\n".join(lines)

# ② 在 RemoteHandler.do_POST 里用局部元组做判断(不再依赖类属性)
t = t.replace('if not cfg.get("allow_ctl", False) and p not in self._ALLOW_ALWAYS:',
              'if not cfg.get("allow_ctl", False) and p not in ("/api/speak", "/api/stop", "/api/state"):')
if "_ALLOW_ALWAYS" in t:
    t = re.sub(r"\n\s*_ALLOW_ALWAYS[^\n]*", "", t)

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过 ✓" if r.returncode == 0 else (r.stderr or "")[-400:])

if r.returncode != 0:
    # 兜底:回退到仓库里可用的 server.py,保证程序能跑
    print("→ 仍失败,回退到仓库版本(会失去跨设备与浏览器跳转,但程序可用)")
    shutil.copy2(os.path.join(os.path.expanduser("~"), "Desktop", "Lyra", "webapp", "server.py"), P)
    shutil.copy2(P, os.path.join(APP, "webapp", "server.py"))
else:
    shutil.copy2(P, os.path.join(APP, "webapp", "server.py"))
    print("已部署")
    # 顺带把 hasattr 检查打印出来,确认拦截代码在 do_POST 里
    i = t.find("def do_POST(self):", t.find("_make_handler"))
    print("---- RemoteHandler.do_POST ----")
    print(t[i:i + 620])
