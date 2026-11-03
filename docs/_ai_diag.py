# -*- coding: utf-8 -*-
"""实测:AI 配置的「保存 → 读取 → 测试」整条链路。
   Key 来自备份文件,只在本地使用,输出里一律打码。"""
import io
import json
import re
import urllib.request

BASE = "http://127.0.0.1:8890"
BAK = r"D:\Unity阅读器\docs\_config_备份.json"
CFG = r"D:\Lyra\app\config.json"


def mask(s):
    s = str(s or "")
    return (s[:6] + "…" + s[-4:]) if len(s) > 12 else ("(空)" if not s else "***")


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


bak = json.load(io.open(BAK, encoding="utf-8-sig"))
bai = bak.get("ai") or {}
key = (bai.get("api_key") or "").strip()
print("备份里的 Key:", mask(key), "| 长度", len(key))
print("当前配置里的 Key:", end=" ")
cur = json.load(io.open(CFG, encoding="utf-8-sig")).get("ai") or {}
print(mask(cur.get("api_key")), "| 长度", len(cur.get("api_key") or ""))

print("\n① 先测「没有 Key」时后端怎么说:")
try:
    r = post("/api/ai/test", {})
    print("   ->", json.dumps(r, ensure_ascii=False)[:160])
except Exception as e:
    print("   !! 请求失败:", e)

print("\n② 保存备份里的 AI 配置(走前端同一个接口 /api/settings):")
r = post("/api/settings", {"ai": {
    "base_url": bai.get("base_url") or "https://api.deepseek.com/v1/chat/completions",
    "model": bai.get("model") or "deepseek-chat",
    "api_key": key,
    "price_in": bai.get("price_in", 2.0),
    "price_out": bai.get("price_out", 8.0),
    "enabled": True,
}})
print("   返回:", json.dumps(r, ensure_ascii=False)[:200])

print("\n③ 读回来确认是否真的写进 config.json:")
cur2 = json.load(io.open(CFG, encoding="utf-8-sig")).get("ai") or {}
print("   config.json 里的 Key:", mask(cur2.get("api_key")), "| 长度", len(cur2.get("api_key") or ""),
      "| model =", cur2.get("model"), "| url =", cur2.get("base_url"))

print("\n④ 再点一次「测试连接」:")
try:
    r = post("/api/ai/test", {})
    print("   ->", json.dumps(r, ensure_ascii=False)[:300])
except Exception as e:
    print("   !! 请求失败:", e)
