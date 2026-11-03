# -*- coding: utf-8 -*-
"""把搬去设置页的那几块代码从旧模块里删掉(一次性脚本)。"""
import io
import os
import re

d = r"D:\Unity阅读器\webapp\static\js"


def rw(rel, f):
    p = os.path.join(d, rel)
    t = io.open(p, encoding="utf-8").read()
    t2 = f(t)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t2)
    print("  %-22s %s" % (rel, "改过" if t2 != t else "没变化"))


def fix_cast(t):
    t = re.sub(r"export function renderVoiceNow\(\) \{.*?\n\}\n", "", t, flags=re.S)
    t = re.sub(r"(let _voiceSig = .*\n)?export function renderVoices\(\) \{.*?\n\}\n", "", t, flags=re.S)
    t = re.sub(r"\$\('testVoice'\)\.onclick.*?nudgePitch\(-Number\(\$\('pitch'\)\.value\)\);\n", "", t, flags=re.S)
    t = re.sub(r"\$\('pitchTry'\)\.onclick = .*?\n", "", t)
    t = t.replace("registerRender(renderVoiceNow);\n", "").replace("registerRender(renderVoices);\n", "")
    t = t.replace("import { $, $$, esc, toast, post, get, pitchText } from '../core.js';",
                  "import { $, $$, esc, toast, post, get } from '../core.js';")
    return t


def fix_rules(t):
    t = re.sub(r"\$\('aiSave'\)\.onclick = async \(\) => \{.*?\n\};\n", "", t, flags=re.S)
    t = re.sub(r"\$\('aiTest'\)\.onclick = async \(\) => \{.*?\n\};\n", "", t, flags=re.S)
    return t


def fix_tr(t):
    t = re.sub(r"  /\* AI 配置回填[^\n]*\n(?:.*?\n)*?  if \(ak && document\.activeElement !== ak\) ak\.value = ai\.api_key \|\| '';\n",
               "", t)
    t = re.sub(r"\$\('trSave'\)\.onclick = async \(\) => \{.*?\n\};\n", "", t, flags=re.S)
    t = re.sub(r"\$\('trPing'\)\.onclick = async \(\) => \{.*?\n\};\n", "", t, flags=re.S)
    return t


rw("views/cast.js", fix_cast)
rw("views/rules.js", fix_rules)
rw("views/translate.js", fix_tr)
print("完成")
