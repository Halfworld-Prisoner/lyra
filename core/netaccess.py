# -*- coding: utf-8 -*-
r"""Lyra · 跨设备访问(局域网直连,不用任何外部服务器)

四种通道都能用,程序**自动识别 + 自动体检 + 给出最优路线**:
  · 电脑开热点   手机连 → 电脑侧地址固定 192.168.137.1(最可控,不受 WiFi 隔离影响)
  · 手机开热点   电脑连 → 电脑拿到手机网段地址(安卓常见 192.168.43.x,iPhone 172.20.10.x)
  · 同一 WiFi    路由器 → 电脑的 WLAN/以太网地址
  · USB 数据线   共享网络 → 共享网段的地址(常见 192.168.42.x)

本模块只做"探测与体检":列出候选地址、判断属于哪条通道、能不能用、打分排序。
真正的监听与鉴权在 webapp/server.py(远程端口 + 4 位安全码)。
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import time

# 通道定义:顺序即"推荐优先级"(分高的排前面)
KINDS = {
    "hotspot_pc":   {"label": "电脑开热点", "hint": "手机连电脑的热点后访问", "score": 100},
    "usb":          {"label": "USB 共享",  "hint": "手机开「USB 网络共享」后访问", "score": 95},
    "hotspot_phone": {"label": "手机开热点", "hint": "电脑连手机热点后访问", "score": 90},
    "wifi":         {"label": "同一 WiFi", "hint": "手机和电脑连同一个路由器时访问", "score": 70},
    "other":        {"label": "其它网卡",  "hint": "虚拟网卡/未知来源", "score": 30},
}

_SKIP_IFACE = re.compile(r"(bluetooth|蓝牙|loopback|vmware|virtualbox|hyper-v|vethernet|"
                         r"docker|wsl|tap|tun|zerotier|tailscale|meta|npcap)", re.I)


def _is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except Exception:
        return False
    return a.is_private and not a.is_loopback and not a.is_link_local


def classify(ip: str, iface: str) -> str:
    """这条地址最可能属于哪种连接方式。"""
    i = (iface or "").lower()
    if _SKIP_IFACE.search(iface or ""):
        return "other"
    # 电脑热点:Windows 移动热点固定 192.168.137.1
    if ip.startswith("192.168.137.") or "本地连接*" in (iface or "") or "local area connection*" in i:
        return "hotspot_pc"
    # 手机热点:安卓 192.168.43.x / 部分 192.168.137.x;iPhone 172.20.10.x
    if ip.startswith("192.168.43.") or ip.startswith("172.20.10."):
        return "hotspot_phone"
    # USB 网络共享:常见 192.168.42.x / RNDIS 网卡
    if ip.startswith("192.168.42.") or "rndis" in i or "usb" in i or "远程 ndis" in i:
        return "usb"
    if _is_private(ip):
        return "wifi"
    return "other"


def _iface_map() -> dict:
    """拿 ip -> 网卡名。优先用 PowerShell(Windows),失败就走 socket 兜底。"""
    out = {}
    try:
        ps = ("Get-NetIPAddress -AddressFamily IPv4 | "
              "Select-Object IPAddress,InterfaceAlias,PrefixOrigin | ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=12, errors="ignore",
                           creationflags=0x08000000)
        import json as _json
        data = _json.loads(r.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        for row in data:
            ip = str(row.get("IPAddress") or "")
            if ip:
                out[ip] = str(row.get("InterfaceAlias") or "")
    except Exception:
        pass
    if not out:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                out.setdefault(info[4][0], "")
        except Exception:
            pass
    return out


def probe(ip: str, port: int, timeout: float = 0.6) -> bool:
    """从本机连一次该地址:能连上说明"服务确实绑在这个网卡上"。

    注意:本机连自己的局域网地址**会绕过 Windows 防火墙的入站限制**,
    所以这一步只证明"绑定成功",不能证明"手机连得进来"(那要靠防火墙规则检查 + 手机实测)。
    """
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def firewall_rule(port: int) -> dict:
    """有没有放行这个端口的入站规则(读规则不需要管理员)。"""
    try:
        ps = ("Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction SilentlyContinue | "
              "Where-Object { $_.DisplayName -like '*Lyra*' -or $_.DisplayName -like '*聆阅*' } | "
              "Select-Object DisplayName,Action | ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=15, errors="ignore",
                           creationflags=0x08000000)
        if (r.stdout or "").strip() not in ("", "null", "[]"):
            return {"ok": True, "detail": (r.stdout or "").strip()[:200]}
    except Exception:
        pass
    # 退一步:试试端口规则查询
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule",
                            "name=Lyra 局域网访问"],
                           capture_output=True, text=True, timeout=12, errors="ignore",
                           creationflags=0x08000000)
        if "Lyra" in (r.stdout or ""):
            return {"ok": True, "detail": "已存在规则"}
    except Exception:
        pass
    return {"ok": False, "detail": "还没放行(手机可能连不进来)"}


def candidates(port: int, probe_self: bool = True) -> list:
    """列出所有可用地址,带通道、打分、自检结果。"""
    ifaces = _iface_map()
    rows = []
    seen = set()
    for ip, iface in ifaces.items():
        if (ip in seen or ip.startswith("127.") or ip.startswith("169.254.")
                or ip.startswith("198.18.") or ip.startswith("198.19.")):
            continue      # 127/169.254=没连上;198.18/19=测速用虚拟网段,都跳过
        seen.add(ip)
        kind = classify(ip, iface)
        if kind == "other":
            continue
        meta = KINDS[kind]
        row = {
            "ip": ip,
            "iface": iface,
            "kind": kind,
            "label": meta["label"],
            "hint": meta["hint"],
            "score": meta["score"],
            "url": "http://%s:%d/" % (ip, port),
            "bound": probe(ip, port) if probe_self else None,
        }
        rows.append(row)
    rows.sort(key=lambda r: (-(r["bound"] is True), -r["score"], r["ip"]))
    for i, r in enumerate(rows):
        r["best"] = (i == 0)
    return rows


def summary(port: int) -> dict:
    """给界面用的一份总览。"""
    rows = candidates(port)
    fw = firewall_rule(port)
    best = rows[0] if rows else None
    return {
        "ok": True,
        "port": port,
        "routes": rows,
        "best": best,
        "firewall": fw,
        "tips": [
            "手机和电脑要在同一个网络里(热点 / USB 共享 / 同一 WiFi 都行)",
            "首次需要在电脑上放行防火墙(程序会提示)",
            "公司或酒店的 WiFi 常开「客户端隔离」,同网段互相看不见 —— 这种情况用电脑热点或 USB 共享",
            "USB 共享最稳最快,其次电脑热点",
        ],
    }
