# -*- coding: utf-8 -*-
"""验证:关掉开机动画 → 重启 → 不再播放;打开 → 又播放。"""
import json
import subprocess
import time
import urllib.request

B = "http://127.0.0.1:8890"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TMP = r"C:\Users\bgyLe\AppData\Local\Temp\ly_sp"


def post(p, o):
    r = urllib.request.Request(B + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=10).read().decode())


def shot(ms, name):
    out = TMP + "\\" + name
    subprocess.run([EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--disable-dev-shm-usage", "--no-first-run",
                    "--user-data-dir=" + TMP + "\\u_" + name, "--window-size=1180,820",
                    "--virtual-time-budget=%d" % ms, "--screenshot=" + out, B + "/"],
                   capture_output=True)
    return out


print("① 关闭开机动画:", post("/api/settings", {"splash_on": False}))
print("   接口回读 splash_on =", get("/api/state")["settings"].get("splash_on"))
p = shot(1500, "off_1500.png")
print("   1.5 秒时的截图已存:", p, "(应已是主界面)")

print("\n② 重新打开:", post("/api/settings", {"splash_on": True}))
print("   接口回读 splash_on =", get("/api/state")["settings"].get("splash_on"))
p = shot(1500, "on_1500.png")
print("   1.5 秒时的截图已存:", p, "(应还在动画里)")
