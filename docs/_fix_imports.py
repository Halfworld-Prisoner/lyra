# -*- coding: utf-8 -*-
"""补齐几个模块缺的 import(自动审计出来的)。"""
import io
import os
import re

d = r"D:\Unity阅读器\webapp\static\js\views"

FIX = {
    "library.js": {
        "import { $, $$, esc, toast, get, post, choose, dialog } from '../core.js';":
            "import { $, $$, esc, toast, get, post, choose, dialog, closeModals, backendTag } from '../core.js';",
    },
    "logs.js": {
        "import { $, $$, esc, toast, get, post, dialog, closeModals, lsRow } from '../core.js';":
            "import { $, $$, esc, toast, get, post, dialog, closeModals, lsRow } from '../core.js';\n"
            "import { loadRules } from './rules.js';",
    },
}

for f, pairs in FIX.items():
    p = os.path.join(d, f)
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs.items():
        if old in t:
            t = t.replace(old, new)
            print("  %-14s 已补" % f)
        elif new.split("\n")[-1].strip() in t or "loadRules" in t and f == "logs.js":
            print("  %-14s 看起来已经补过" % f)
        else:
            print("  %-14s !! 没找到目标行:%s" % (f, old[:50]))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)

# logs.js 里 view === 'rules' 要改成 store.view
p = os.path.join(d, "logs.js")
t = io.open(p, encoding="utf-8").read()
if "if (view === 'rules')" in t:
    t = t.replace("if (view === 'rules')", "if (store.view === 'rules')")
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  logs.js      store.view 已修")
print("完成")
