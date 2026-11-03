# -*- coding: utf-8 -*-
"""① /api/translate 记录"最近请求过的短文案"(诊断菜单有没有被送来翻译);
   ② 把字体兜底 + 接口地址 + XUnity 日志 写进已装插件的游戏配置(立即生效,重启游戏)。"""
import io
import os

SRC = r"D:\Unity阅读器"
SRV = os.path.join(SRC, "webapp", "server.py")
t = io.open(SRV, encoding="utf-8").read()

# ---------- ① 最近请求环形缓冲 ----------
if "_RECENT_REQ" not in t:
    t = t.replace(
        "TRANSLATOR = translate_mod.Translator(",
        "# 诊断用:记录 XUnity 最近来问过哪些文案(短句优先,看菜单有没有被送来翻译)\n"
        "_RECENT_REQ = []\n"
        "_RECENT_LOCK = threading.Lock()\n\n\n"
        "def _note_req(src: str, out: str) -> None:\n"
        "    s = (src or '').strip().replace('\\n', ' ')\n"
        "    if not s or len(s) > 40:\n"
        "        return\n"
        "    try:\n"
        "        with _RECENT_LOCK:\n"
        "            _RECENT_REQ.append({'src': s, 'out': (out or '').strip()[:40],\n"
        "                                'changed': (out or '').strip() != s})\n"
        "            del _RECENT_REQ[:-40]\n"
        "    except Exception:\n"
        "        pass\n\n\n"
        "TRANSLATOR = translate_mod.Translator(", 1)

    t = t.replace('''                try:
                    out = TRANSLATOR.get(src, cfgm.get().get("ai") or {})
                except Exception:
                    out = src
                return self._text(out)''',
                  '''                try:
                    out = TRANSLATOR.get(src, cfgm.get().get("ai") or {})
                except Exception:
                    out = src
                _note_req(src, out)
                return self._text(out)''', 1)

    t = t.replace('''                    "stats": st,
                })''',
                  '''                    "stats": st,
                    "recent": list(_RECENT_REQ)[-20:],
                })''', 1)
    io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
    print("① server.py 已加“最近请求”诊断(翻译页可见)")
else:
    print("① 已有诊断缓冲")

# ---------- ② 写进游戏配置 ----------
import json
import subprocess

CFG = r"D:\Lyra\app\config.json"
games = []
for gdir in (r"D:\Steam\steamapps\common\KnightsCollege",
             r"D:\Steam\steamapps\common\Knights College 2 -ナイツカレッジ2-"):
    ini = os.path.join(gdir, "BepInEx", "config", "AutoTranslatorConfig.ini")
    if os.path.isfile(ini):
        games.append((gdir, ini))

PORT = 8890
for gdir, ini in games:
    raw = io.open(ini, encoding="utf-8-sig").read()
    want = {
        "Url": "http://127.0.0.1:%d/api/translate" % PORT,
        "Language": "zh-CN",
        "FromLanguage": "auto",
        "OverrideFont": "Microsoft YaHei",
        "OverrideFontTextMeshPro": "Microsoft YaHei",
        "FallbackFontTextMeshPro": "Microsoft YaHei UI",
        "EnableLog": "True",          # 先打开日志,好查菜单为什么没被翻译
    }
    seen, out = set(), []
    for ln in raw.replace("\r\n", "\n").split("\n"):
        k = ln.split("=", 1)[0].strip() if ("=" in ln and not ln.lstrip().startswith(";")) else ""
        if k in want:
            out.append("%s=%s" % (k, want[k]))
            seen.add(k)
        else:
            out.append(ln)
    for k, v in want.items():
        if k not in seen:
            out.append("%s=%s" % (k, v))
    io.open(ini, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("② 已更新:", os.path.basename(gdir))
print("完成")
