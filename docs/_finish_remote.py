# -*- coding: utf-8 -*-
r"""一次做完并**逐项验证**:
   ① 路由挪到 POST(锚点用只在 POST 里存在的 /api/stop)
   ② 删掉设置里重复的旧「跨设备访问」面板
   ③ source → 应用目录 全量同步
   ④ 重启并**发真实请求**验证 /api/remote 200
   ⑤ 重新打包安装器 → 复制到桌面(用户要的最新版)
"""
import io
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
SV = os.path.join(SRC, "webapp", "server.py")
IDX = os.path.join(SRC, "webapp", "static", "index.html")

# ---------- ① 路由挪到 POST ----------
t = io.open(SV, encoding="utf-8").read()
m = re.search(r'\n            if p\.startswith\("/api/remote"\):\n(?:.*\n)*?\n', t)
if m:
    hook = m.group(0)
    t = t[:m.start()] + "\n" + t[m.end():]
    anchor = '            if p == "/api/stop":'
    if anchor not in t:
        anchor = '            if p == "/api/speak":'
    assert anchor in t, "找不到 POST 锚点"
    t = t.replace(anchor, hook.strip("\n") + "\n\n" + anchor, 1)
    io.open(SV, "w", encoding="utf-8", newline="\n").write(t)
    print("① 路由已挪到 POST(锚点 %s)" % anchor.strip()[:34])
else:
    print("① !! 没找到 remote 路由")

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % SV],
                   capture_output=True, text=True)
print("   server.py 语法:", "通过 ✓" if r.returncode == 0 else (r.stderr or "")[-200:])

# ---------- ② 删掉重复旧面板 ----------
h = io.open(IDX, encoding="utf-8").read()
removed = 0
for marker in ('id="remotePinBtn"', 'id="remoteCheck"', 'id="remotePanel"', 'id="remoteBox"'):
    while True:
        i = h.find(marker)
        if i < 0:
            break
        start = h.rfind('\n      <div class="panel"', 0, i)
        end = h.find('\n      </div>\n', i)
        if start > 0 and end > i:
            h = h[:start] + h[end + len('\n      </div>\n'):]
            removed += 1
        else:
            break
if removed:
    io.open(IDX, "w", encoding="utf-8", newline="\n").write(h)
print("② 已删除 %d 个重复旧面板 | 现在还有 remotePinBtn: %s" % (removed, 'remotePinBtn' in h))

# ---------- ③ 全量同步到应用 ----------
n = 0
for rel in ("core/remote.py", "core/netaccess.py", "webapp/server.py", "webapp/static/index.html",
            "webapp/static/m.html", "webapp/static/css/extra.css", "webapp/static/js/boot.js",
            "webapp/static/js/views/device.js"):
    s = os.path.join(SRC, rel.replace("/", os.sep)); d = os.path.join(APP, rel.replace("/", os.sep))
    if os.path.isfile(s):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        n += 1
print("③ 已同步 %d 个文件" % n)

# ---------- ④ 重启 + 真实验证 ----------
for nm in ("Lyra", "聆听"):
    subprocess.run(["taskkill", "/F", "/IM", nm + ".exe"], capture_output=True)
subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)
time.sleep(4)
subprocess.Popen([r"D:\Lyra\Lyra.exe"])
for _ in range(20):
    time.sleep(2)
    try:
        urllib.request.urlopen("http://127.0.0.1:8890/api/state", timeout=5)
        break
    except Exception:
        pass


def call(p, o=None, base="http://127.0.0.1:8890", cookie=None):
    hd = {"Content-Type": "application/json"}
    if cookie:
        hd["Cookie"] = cookie
    data = json.dumps(o).encode() if o is not None else None
    r = urllib.request.Request(base + p, data=data, headers=hd, method=("POST" if o is not None else "GET"))
    try:
        return urllib.request.urlopen(r, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        return "HTTP %d" % e.code
    except Exception as e:
        return "ERR " + str(e)[:40]


print("④ 验证:")
try:
    s = json.loads(call("/api/state"))
    print("   应用运行 ✓ 累计 %s 字" % (s.get("stats") or {}).get("chars"))
except Exception as e:
    print("   应用未起来 ✗", e)
st = call("/api/remote", {})
print("   /api/remote →", (st[:70] if st.startswith("HTTP") or st.startswith("ERR") else "200 ✓ " + st[:80]))
if not st.startswith("HTTP") and not st.startswith("ERR"):
    d = json.loads(st)
    if not d.get("on"):
        d = json.loads(call("/api/remote", {"on": True}))
    print("   开启后: on=%s port=%s pin=%s" % (d.get("on"), d.get("port"), d.get("pin")))
    ck = json.loads(call("/api/remote/check", {})).get("msg", "")
    print("   体检:", ck[:70])
    call("/api/remote", {"allow_ctl": False})

# ---------- ⑤ 打包安装器 + 桌面 ----------
print("⑤ 打包安装器(约 3-4 分钟)…")
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", os.path.join(SRC, "installer", "build.ps1")],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
tail = [x for x in ((r.stdout or "") + (r.stderr or "")).splitlines() if x.strip()][-2:]
print("   " + " | ".join(x.strip()[:70] for x in tail))
exe = os.path.join(SRC, "Lyra 安装程序.exe")
if os.path.isfile(exe):
    dst = os.path.join(os.path.expanduser("~"), "Desktop", "Lyra 安装程序.exe")
    shutil.copy2(exe, dst)
    print("   桌面安装包已更新: %.1f MB  %s" %
          (os.path.getsize(dst) / 1048576, time.strftime("%H:%M", time.localtime(os.path.getmtime(dst)))))
else:
    print("   !! 安装器没生成")
