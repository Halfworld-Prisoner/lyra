# -*- coding: utf-8 -*-
"""部署后验证 AI 链路:错 Key 的提示 / 正确 Key 的提示 / 配置是否落盘。"""
import io
import json
import urllib.request

BASE = "http://127.0.0.1:8890"
BAK = r"D:\Unity阅读器\docs\_config_备份.json"
CFG = r"D:\Lyra\app\config.json"


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


bak = json.load(io.open(BAK, encoding="utf-8-sig"))
good = ((bak.get("ai") or {}).get("api_key") or "").strip()
url = (bak.get("ai") or {}).get("base_url") or "https://api.deepseek.com/v1/chat/completions"
model = (bak.get("ai") or {}).get("model") or "deepseek-chat"


def save(key, u=url, m=model):
    return post("/api/settings", {"ai": {"base_url": u, "model": m, "api_key": key,
                                         "price_in": 2.0, "price_out": 8.0, "enabled": True}})


print("① 故意存一个错的 Key,再看测试提示:")
save("sk-wrong-key-for-test-000000000000")
r = post("/api/ai/test", {})
print("   ->", json.dumps(r, ensure_ascii=False)[:220])

print("\n② 故意把接口地址写错(去掉 /chat/completions):")
save(good, "https://api.deepseek.com/v1")
r = post("/api/ai/test", {})
print("   ->", json.dumps(r, ensure_ascii=False)[:220])

print("\n③ 恢复正确配置:")
save(good)
r = post("/api/ai/test", {})
print("   ->", json.dumps(r, ensure_ascii=False)[:220])

cur = json.load(io.open(CFG, encoding="utf-8-sig")).get("ai") or {}
k = cur.get("api_key") or ""
print("\n④ 落盘确认:Key 长度 =", len(k), "| model =", cur.get("model"), "| enabled =", cur.get("enabled"))
print("   界面应显示:「已配置(" + str(cur.get("model")) + ");过滤词评审与文本翻译都用它」")
