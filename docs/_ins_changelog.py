# -*- coding: utf-8 -*-
"""把 1.1.1 小节插进仓库的 CHANGELOG(文件方式,避免 shell 引号问题)。"""
import io

p = r"C:\Users\bgyLe\Desktop\Lyra\CHANGELOG.md"
t = io.open(p, encoding="utf-8").read()
add = io.open(r"D:\Unity阅读器\docs\_changelog_111.md", encoding="utf-8").read()
if "1.1.1" in t:
    print("  已有 1.1.1")
else:
    i = t.find("## [1.1.0]")
    assert i > 0
    io.open(p, "w", encoding="utf-8", newline="\n").write(t[:i] + add + t[i:])
    print("  已插入 1.1.1 小节")
