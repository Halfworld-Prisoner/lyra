# -*- coding: utf-8 -*-
"""Lyra · 累计阅读统计(永久保存)

记录"这个游戏一共读了多少字/多少句/读了多久",**关游戏、关软件、重装都不丢**:
  · 存在 %LOCALAPPDATA%\\Lyra\\readstats.json(用户目录,卸载程序不会删这里);
  · 按游戏分开记(用游戏 exe 路径做键),换游戏互不影响;
  · 每次读到一句就累加,写盘做了节流(每 5 秒或每 20 句落一次),不拖慢朗读;
  · 文件坏了/读不出来也不影响主流程(统计永远是"附加"功能)。
"""
from __future__ import annotations

import json
import os
import threading
import time

_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Lyra")
PATH = os.path.join(_DIR, "readstats.json")
SAVE_EVERY = 1.0          # 至少隔这么久落一次盘(1 秒:强杀进程最多丢 1 秒)
SAVE_LINES = 3            # 攒够这么多句立刻落盘

_lock = threading.Lock()
_CACHE: dict | None = None
_dirty = False
_last_save = 0.0
_pending_lines = 0


def _now() -> float:
    return time.time()


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    d = {"version": 1, "games": {}}
    try:
        if os.path.isfile(PATH):
            with open(PATH, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("games"), dict):
                d = raw
    except Exception:
        d = {"version": 1, "games": {}}
    _CACHE = d
    return d


def _save(force: bool = False) -> None:
    global _dirty, _last_save, _pending_lines
    now = _now()
    if not force and not _dirty:
        return
    if not force and (now - _last_save) < SAVE_EVERY and _pending_lines < SAVE_LINES:
        return
    d = _load()
    try:
        os.makedirs(_DIR, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PATH)
        _dirty = False
        _last_save = now
        _pending_lines = 0
    except Exception:
        pass


def _flusher():
    """后台每秒检查:有脏数据就写盘。

    为什么要它:玩家可能直接关窗口或用任务管理器杀进程,那种情况走不到"退出保存"。
    有它兜底,最多丢最后 1 秒的字,不会出现"读了一大段、重启就没了"。
    """
    while True:
        try:
            time.sleep(1.0)
            with _lock:
                if _dirty:
                    _save(force=True)
        except Exception:
            pass


threading.Thread(target=_flusher, daemon=True).start()


def key_of(game: dict) -> str:
    """一台游戏的稳定标识:优先 exe 全路径,退而用目录名。"""
    g = game or {}
    k = (g.get("exe") or "").strip() or (g.get("dir") or "").strip()
    if not k:
        return ""
    return os.path.normcase(os.path.abspath(k))


def note(game: dict, text: str, chars: int | None = None) -> None:
    """读到一句:累加句数 / 字数 / 活跃时长,并记到"今天"这一格。"""
    k = key_of(game)
    if not k:
        return
    body = (text or "").strip()
    if not body:
        return
    if chars is None:
        # 字数按"实际念出来的文字"算:去掉【角色名】前缀与空白
        s = body
        if s.startswith("【"):
            i = s.find("】")
            if 0 < i <= 18:
                s = s[i + 1:]
        chars = len([c for c in s if not c.isspace()])
    now = _now()
    with _lock:
        d = _load()
        g = d["games"].get(k)
        if not isinstance(g, dict):
            g = {"name": (game or {}).get("name") or "", "chars": 0, "lines": 0,
                 "seconds": 0.0, "first": now, "last": now, "days": {}}
            d["games"][k] = g
        g["name"] = (game or {}).get("name") or g.get("name") or ""
        g["chars"] = int(g.get("chars") or 0) + max(0, int(chars))
        g["lines"] = int(g.get("lines") or 0) + 1
        g["last"] = now
        # 活跃时长:与上一句间隔 < 5 分钟才计入(避免挂着不动也涨时间)
        prev = float(g.get("_t") or 0)
        if prev and (now - prev) < 300:
            g["seconds"] = float(g.get("seconds") or 0) + (now - prev)
        g["_t"] = now
        days = g.setdefault("days", {})
        day = _today()
        days[day] = int(days.get(day) or 0) + max(0, int(chars))
        if len(days) > 400:                       # 只留最近 400 天
            for old in sorted(days)[:-400]:
                days.pop(old, None)
        global _dirty, _pending_lines
        _dirty = True
        _pending_lines += 1
        _save()


def flush() -> None:
    with _lock:
        _save(force=True)


def for_game(game: dict) -> dict:
    """这台游戏的累计数据(给界面用)。"""
    k = key_of(game)
    d = _load()
    g = (d["games"].get(k) or {}) if k else {}
    days = g.get("days") or {}
    today = _today()
    recent = [(day, int(days.get(day) or 0)) for day in sorted(days)[-7:]]
    return {
        "key": k,
        "name": g.get("name") or (game or {}).get("name") or "",
        "chars": int(g.get("chars") or 0),
        "lines": int(g.get("lines") or 0),
        "seconds": int(g.get("seconds") or 0),
        "first": float(g.get("first") or 0),
        "last": float(g.get("last") or 0),
        "today": int(days.get(today) or 0),
        "days": recent,
        "total_chars_all": sum(int(v.get("chars") or 0) for v in d["games"].values()
                               if isinstance(v, dict)),
        "games": len(d["games"]),
    }


def reset(game: dict) -> dict:
    k = key_of(game)
    with _lock:
        d = _load()
        if k and k in d["games"]:
            d["games"].pop(k, None)
            _save(force=True)
            return {"ok": True, "msg": "这台游戏的累计记录已清零"}
        return {"ok": False, "msg": "还没有记录可清零"}


def top(n: int = 8) -> list:
    """读得最多的几台游戏(界面里可以顺手展示)。"""
    d = _load()
    rows = []
    for k, v in (d.get("games") or {}).items():
        if isinstance(v, dict):
            rows.append({"name": v.get("name") or os.path.basename(k), "chars": int(v.get("chars") or 0),
                         "lines": int(v.get("lines") or 0), "last": float(v.get("last") or 0)})
    rows.sort(key=lambda x: -x["chars"])
    return rows[:n]
