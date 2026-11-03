# -*- coding: utf-8 -*-
"""清理"右键误学"的忽略规则。

留:訊息速度(确实是界面面板)
删:亞戈 / 伽米爾 / 菲力克斯 —— 这三个是**主角名字**,当成面板标签会把他们的台词整段跳过!
     以及 4 句被误标成"不是剧情"的剧情原文。
"""
import json
import urllib.request

B = "http://127.0.0.1:8890"


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=10).read().decode())


def post(p, o):
    r = urllib.request.Request(B + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())


rl = get("/api/rules")
print("  规则顶层键:", list(rl.keys()))
learned = rl.get("learned") or {}
print("  learned 结构:", {k: (len(v) if isinstance(v, list) else v) for k, v in learned.items()})
# 找出"学到的标签/句子"具体挂在哪个 key 下
for k, v in (rl.get("groups") or {}).items():
    if isinstance(v, list) and any(("亞戈" in str(x)) or ("伽米爾" in str(x)) for x in v):
        print("  命中分组:", k)

KEEP = {"訊息速度"}
DROP_LABELS = {"亞戈", "伽米爾", "菲力克斯"}
DROP_TEXT_HINT = ("「", "」")        # 误标的都是带引号的剧情句

cand_keys = []
for k in ("ignored_labels", "labels", "learned_labels"):
    if isinstance(learned.get(k), list):
        cand_keys.append(("learned." + k, learned[k]))
    if isinstance((rl.get("groups") or {}).get(k), list):
        cand_keys.append(("groups." + k, rl["groups"][k]))
for k in ("ignored_texts", "texts", "learned_texts"):
    if isinstance(learned.get(k), list):
        cand_keys.append(("learned." + k, learned[k]))
print("  可操作的列表:", [c[0] for c in cand_keys])

removed = 0
for name, items in cand_keys:
    for it in list(items):
        s = str(it)
        drop = False
        if s in DROP_LABELS:
            drop = True
        elif any(h in s for h in DROP_TEXT_HINT) and len(s) > 12:
            drop = True                      # 误标的剧情句
        if drop and s not in KEEP:
            key = name.split(".")[-1]
            r = post("/api/rules/del", {"key": key, "value": it})
            if r.get("ok"):
                removed += 1
                print("   已删除 [%s] %s" % (key, s[:48]))
            else:
                print("   删除失败:", key, s[:30], r)

print("\n  共删除 %d 条误学规则" % removed)
rl2 = get("/api/rules")
l2 = rl2.get("learned") or {}
print("  清理后: 句子 %d 条 | 标签 %s" %
      (len(l2.get("texts") or []), l2.get("labels") or []))
