# -*- coding: utf-8 -*-
"""把源码树同步到已安装目录 D:\\聆阅\\app(不碰玩家的 config.json),然后重启应用。

用法: python docs/_deploy.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

SRC = r"D:\Unity阅读器"
DST = r"D:\Lyra\app"
ITEMS = ["core", "webapp", "hooks", "payload", "voices", "config.py", "requirements.txt"]
KEEP = {"config.json", "server.port"}          # 玩家数据,绝对不动


def log(*a):
    print(*a, flush=True)


def sync():
    for it in ITEMS:
        s = os.path.join(SRC, it)
        if not os.path.exists(s):
            continue
        d = os.path.join(DST, it)
        if os.path.isdir(s):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        log("  同步 %s" % it)
    # 清掉 __pycache__(旧字节码)
    for dp, dn, fn in os.walk(DST):
        if os.path.basename(dp) == "__pycache__":
            shutil.rmtree(dp, ignore_errors=True)
    # 顺带更新窗口宿主(新 player.exe 支持"窗口底色跟主题变")
    pe = os.path.join(SRC, "installer", "player.exe")
    if os.path.isfile(pe):
        for name in ("Lyra.exe", "聆阅.exe"):
            tgt = os.path.join(os.path.dirname(DST), name)
            if os.path.isfile(tgt):
                try:
                    shutil.copy2(pe, tgt)
                    log("  更新窗口宿主 %s" % name)
                except Exception as e:
                    log("  !! 更新 %s 失败(可能正在运行):%s" % (name, e))


def kill_old():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
          "Where-Object { $_.CommandLine -like '*聆阅\\app\\webapp\\server.py*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process -Name 'Lyra','聆阅' -ErrorAction SilentlyContinue | "
                    "Stop-Process -Force"], capture_output=True)
    time.sleep(2)


def start_app():
    exe = os.path.join(os.path.dirname(DST), "Lyra.exe")
    if not os.path.isfile(exe):
        exe = os.path.join(os.path.dirname(DST), "聆阅.exe")
    log("  启动 %s" % exe)
    subprocess.Popen([exe], cwd=os.path.dirname(DST))


def wait_port(timeout=40):
    """等后端起来,返回它的端口。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for port in range(8890, 8912):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port, timeout=1) as r:
                    if r.status == 200:
                        return port
            except Exception:
                continue
        time.sleep(1.5)
    return 0


def verify(port):
    with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port, timeout=5) as r:
        st = json.loads(r.read().decode("utf-8"))
    cfg = st.get("settings") or {}
    log("  状态      : %s" % st.get("status"))
    log("  全局语音  : %s" % st.get("voice_label"))
    log("  角色数    : %d" % len(st.get("cast") or {}))
    log("  专用规则  : %s" % (st.get("rules_profile") or {}).get("name"))
    log("  声音数    : %d(其中女声 %d)" % (
        len(st.get("voices") or []),
        len([v for v in (st.get("voices") or []) if v.get("gender") == "female"])))
    log("  翻译      : %s" % json.dumps(st.get("translate") or {}, ensure_ascii=False))
    for path in ("/api/rules", "/api/translate/state", "/api/ai/usage", "/api/logs", "/"):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
                log("  %-22s HTTP %s (%d B)" % (path, r.status, len(r.read())))
        except Exception as e:
            log("  %-22s 失败: %s" % (path, e))


if __name__ == "__main__":
    log("== 部署到 %s ==" % DST)
    sync()
    log("== 重启应用 ==")
    kill_old()
    start_app()
    port = wait_port()
    if not port:
        log("!! 后端没起来")
        sys.exit(1)
    log("== 后端在 %d,验证接口 ==" % port)
    verify(port)
    log("完成")
