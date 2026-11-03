# -*- coding: utf-8 -*-
"""实测:状态保存到底丢在哪一步。

步骤:读当前值 → 通过界面同款接口改两个开关和语音 → 看文件有没有变
      → 重启应用 → 再读,看是不是回到默认。
"""
import io
import json
import os
import subprocess
import time
import urllib.request

B = "http://127.0.0.1:8890"
CFG = r"D:\Lyra\app\config.json"


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=10).read().decode())


def post(p, o):
    r = urllib.request.Request(B + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode())


def snap(tag):
    d = json.load(io.open(CFG, encoding="utf-8-sig"))
    st = get("/api/state")
    print("  [%s] 文件: auto_say=%s voice=%s translate.on=%s hook.strict=%s | 大小 %d KB" %
          (tag, d.get("auto_say"), d.get("voice"), (d.get("translate") or {}).get("on"),
           (d.get("hook") or {}).get("strict"), os.path.getsize(CFG) // 1024))
    print("         接口: 语音=%s 自动朗读=%s" %
          (st.get("voice_label"), (st.get("settings") or {}).get("auto_say")))
    return d


print("① 改之前:")
snap("before")

print("\n② 通过界面同款接口改:auto_say=True, voice=sapi:Microsoft Kangkang, 严格模式=False")
post("/api/settings", {"auto_say": True, "voice": "sapi:Microsoft Kangkang", "hook": {"strict": False}})
time.sleep(1.0)
snap("after-set")

print("\n③ 重启应用(模拟你关掉再打开)")
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
print("\n④ 重启之后:")
snap("after-restart")
