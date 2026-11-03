# -*- coding: utf-8 -*-
"""① 修掉 settings.js 里那行多余判断;② 三个 exe 改为全静态链接(-static)。

   为什么要静态:`player.exe` 与 `uninstall.exe` 依赖 libwinpthread-1.dll,
   而这只 DLL 只有装了 MinGW 的机器才有 —— 玩家机器上会「双击没反应」。
   `-static` 把 libgcc / libstdc++ / winpthread 全部链进 exe,单文件即可运行。
"""
import io
import os
import re

SRC = r"D:\Unity阅读器"

# ---------- ① ----------
p = os.path.join(SRC, "webapp", "static", "js", "views", "settings.js")
t = io.open(p, encoding="utf-8").read()
bad = "const el = $('id') && $(id);"
if bad in t:
    t = t.replace(bad, "const el = $(id);")
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("① settings.js 那行多余判断已修")
else:
    print("① 无需修(可能已好)")

# ---------- ② ----------
def add_static(path, label):
    if not os.path.isfile(path):
        print("   --  找不到", path)
        return
    s = io.open(path, encoding="utf-8").read()
    n = 0
    # 在每个 gcc / g++ 编译行后补 -static(已有就不重复加)
    lines = s.split("\n")
    for i, ln in enumerate(lines):
        if re.search(r"&\s*(gcc|g\+\+)\s", ln) or ln.strip().startswith("-O2"):
            if "-static" not in ln and ("-static-libgcc" in ln or "-O2" in ln):
                lines[i] = ln.replace("-static-libgcc", "-static-libgcc -static", 1)
                if "-static" not in lines[i]:
                    lines[i] = lines[i] + " -static"
                n += 1
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("   %s:%d 处已加 -static" % (label, n))


add_static(os.path.join(SRC, "installer", "build_player.ps1"), "build_player.ps1")
add_static(os.path.join(SRC, "installer", "build.ps1"), "build.ps1")
print("② 构建脚本已改为全静态链接")
