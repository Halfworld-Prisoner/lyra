# -*- coding: utf-8 -*-
"""修「实时剧情里右键一句,它就消失」。

根因:state.js 给每条剧情绑了 li.oncontextmenu = markNotStory(ln) ——
      那是**加自绘右键菜单之前**的旧交互(右键直接"标成不是剧情")。
      现在 document 级的自绘菜单也会收到 contextmenu,于是:
      右键 = 既弹菜单、又立刻把这句话标成"不是剧情"并学成忽略规则 → 句子消失。

修法:去掉元素上的 oncontextmenu(菜单里已经有「标成"不是剧情"」这一项,想标记的人
      可以从菜单里点),避免"随手右键"误伤剧情。
"""
import io
import os
import subprocess

SRC = r"D:\Unity阅读器"
p = os.path.join(SRC, "webapp", "static", "js", "state.js")
t = io.open(p, encoding="utf-8").read()

old = """      /* 右键:标成"不是剧情"(学一条忽略规则) */
      li.oncontextmenu = (ev) => { ev.preventDefault(); markNotStory(ln); };
"""
new = """      /* ★不要再绑右键=标成"不是剧情"★
         那是自绘右键菜单上线之前的旧交互,结果与全局菜单冲突:
         随手右键一下就把这句学成忽略规则、句子当场从列表里消失(玩家反馈的 bug)。
         现在想标记请用右键菜单里的「标成"不是剧情"」。 */
"""
assert old in t, "没找到那段右键绑定"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("state.js 已去掉「右键=标成不是剧情」的绑定")
r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
print("node --check:", "通过" if r.returncode == 0 else r.stderr[:200])

# 顺手看看玩家这几下右键误学了什么(输出仅统计,不改动)
import json
import urllib.request
try:
    rl = json.loads(urllib.request.urlopen("http://127.0.0.1:8890/api/rules", timeout=8).read().decode())
    learned = (rl.get("learned") or {})
    texts = learned.get("texts") or []
    labels = learned.get("labels") or []
    print("\n  已学到的忽略规则: 具体句子 %d 条 | 面板标签 %d 条" % (len(texts), len(labels)))
    for x in texts[-8:]:
        print("     句:", str(x)[:60])
    for x in labels[-8:]:
        print("     标签:", str(x)[:40])
except Exception as e:
    print("  (读不到规则:", e, ")")
