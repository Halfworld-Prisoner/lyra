# -*- coding: utf-8 -*-
"""验证:默认配音选女声 → 重启 → 还在吗?"""
import json
import subprocess
import time
import urllib.request

B = "http://127.0.0.1:8890"


def post(p, o):
    r = urllib.request.Request(B + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=10).read().decode())


print("① 把默认配音设成女声(慧慧):", post("/api/cast/default", {"voice": "sapi:Microsoft Huihui"}))
print("   再给一个角色也配女声:", post("/api/cast/set", {"name": "亞戈", "voice": "sapi:Microsoft Yaoyao"}))
time.sleep(1)
d = get("/api/state")["settings"]
print("   当前: cast_default=%r  cast=%s" % (d.get("cast_default"), json.dumps(d.get("cast") or {}, ensure_ascii=False)))

print("\n② 重启应用")
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-Process Lyra -ErrorAction SilentlyContinue | Stop-Process -Force; "
                "Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like 'D:\\Lyra\\*' } | Stop-Process -Force"],
               capture_output=True)
time.sleep(3)
subprocess.Popen([r"D:\Lyra\Lyra.exe"])
for _ in range(25):
    time.sleep(2)
    try:
        get("/api/state")
        break
    except Exception:
        pass
time.sleep(2)

print("\n③ 重启后:")
d = get("/api/state")["settings"]
cd = d.get("cast_default")
cast = d.get("cast") or {}
print("   cast_default = %r  %s" % (cd, "✓ 保住了" if "huihui" in (cd or "").lower() else "✗ 被改掉了"))
print("   cast =", json.dumps(cast, ensure_ascii=False))
ok = any("yaoyao" in ((v or {}).get("voice") or "").lower() for v in cast.values())
print("   角色配音:", "✓ 保住了" if ok else "✗ 被清掉了")
