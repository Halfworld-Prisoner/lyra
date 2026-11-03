# -*- coding: utf-8 -*-
"""小清理:contextmenu.js 里没用到的 import 去掉。"""
import io

p = r"D:\Unity阅读器\webapp\static\js\ui\contextmenu.js"
t = io.open(p, encoding="utf-8").read()
old = "import { $, $$, esc, toast, post, get, closeModals } from '../core.js';"
new = "import { esc, toast, post, closeModals } from '../core.js';"
assert old in t
io.open(p, "w", encoding="utf-8", newline="\n").write(t.replace(old, new, 1))
print("已精简 contextmenu.js 的 import")
