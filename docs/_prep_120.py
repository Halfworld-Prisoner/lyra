# -*- coding: utf-8 -*-
"""同步 v1.2.0 的改动到仓库 + 写 CHANGELOG(文件方式,避免 shell 引号问题)。"""
import io
import os
import shutil

SRC = r"D:\Unity阅读器"
REPO = os.path.join(os.path.expanduser("~"), "Desktop", "Lyra")

FILES = [
    "webapp/static/index.html",
    "webapp/static/css/splash.css",
    "webapp/static/js/splash.js",
    "webapp/static/js/state.js",
    "webapp/static/js/boot.js",
    "webapp/static/js/views/settings.js",
    "webapp/static/img/logo.png",
    "webapp/server.py",
    "config.py",
    "installer/ui.html",
    "installer/ui_uninstall.html",
    "installer/setup.c",
]

for rel in FILES:
    s = os.path.join(SRC, rel.replace("/", os.sep))
    d = os.path.join(REPO, rel.replace("/", os.sep))
    if not os.path.isfile(s):
        print("  !! 缺:", rel)
        continue
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)
    print("  同步 %-42s %7.1f KB" % (rel, os.path.getsize(d) / 1024))

# CHANGELOG
p = os.path.join(REPO, "CHANGELOG.md")
t = io.open(p, encoding="utf-8").read()
add = io.open(os.path.join(SRC, "docs", "_changelog_120.md"), encoding="utf-8").read()
if "1.2.0" in t:
    print("  CHANGELOG 已有 1.2.0")
else:
    i = t.find("## [1.1.1]")
    io.open(p, "w", encoding="utf-8", newline="\n").write(t[:i] + add + t[i:])
    print("  CHANGELOG 已插入 1.2.0")
