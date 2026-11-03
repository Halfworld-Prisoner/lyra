# -*- coding: utf-8 -*-
r"""按游戏选 LDC 档位,别一刀切:
   · UTAGE 系(Knights College 等)自己的文本系统 → 必须 gameonly(挂 TMP 会闪退)
   · 其它 IL2CPP + TMP 游戏(A Better Tomorrow 等) → tmpro(否则只挂到特效方法,漏对白)
   给每个 GAME_PROFILES 加 "ldc_tier",匹配到哪款就用哪档;没匹配到用默认 tmpro。
"""
import io
import os
import re
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
SH = os.path.join(SRC, "core", "storyhook.py")
SV = os.path.join(SRC, "webapp", "server.py")

t = io.open(SH, encoding="utf-8").read()

# ① 给 UTAGE 档加 gameonly 标记
if '"ldc_tier"' not in t:
    t = t.replace('''        "key": "utage",
        "name": "UTAGE ADV(Knights College 1 / 2)",''',
                  '''        "key": "utage",
        "ldc_tier": "gameonly",          # ★UTAGE 自己的文本系统:只能 gameonly★
        "name": "UTAGE ADV(Knights College 1 / 2)",''', 1)
    t = t.replace('''        "key": "abettertomorrow",
        "name": "A Better Tomorrow(Unity IL2CPP / TMP)",''',
                  '''        "key": "abettertomorrow",
        "ldc_tier": "tmpro",             # ★TMP 系:必须 tmpro,否则漏对白★
        "name": "A Better Tomorrow(Unity IL2CPP / TMP)",''', 1)
    print("① 两个档已标注 ldc_tier")

# ② 提供查询函数
if "def tier_for(" not in t:
    t = t.replace("def match_profile(game_path: str, methods_seen=None):",
                  '''def tier_for(key) -> str:
    """这款游戏该用哪个 LDC 档位(没说就按默认)。"""
    p = PROFILE_BY_KEY.get(key or "")
    if p and p.get("ldc_tier"):
        return p["ldc_tier"]
    return "tmpro"


def match_profile(game_path: str, methods_seen=None):''', 1)
    print("② 已加 tier_for()")
io.open(SH, "w", encoding="utf-8", newline="\n").write(t)

# ③ server.py:匹配到游戏后应用它的档位
s = io.open(SV, encoding="utf-8").read()
if "tier_for" not in s:
    old = '''            key = match_profile(g.get("exe") or g.get("dir") or "", self._methods_seen)
            if key != ACTIVE_PROFILE:
                set_active_profile(key)'''
    new = '''            key = match_profile(g.get("exe") or g.get("dir") or "", self._methods_seen)
            if key != ACTIVE_PROFILE:
                set_active_profile(key)
                # ★按游戏切 LDC 档位★(UTAGE→gameonly;TMP 系→tmpro)
                try:
                    want_tier = storyhook.tier_for(key)
                    if want_tier and HOOK.profile != want_tier:
                        HOOK.profile = want_tier
                        HOOK.write_mode()
                        self.on_status("已把 LDC 档位切到 %s(适配这款游戏)" % want_tier)
                except Exception:
                    pass'''
    if old in s:
        s = s.replace(old, new, 1)
        io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
        print("③ 匹配游戏时自动应用档位 ✓")
    else:
        print("③ !! 没匹配到 _sync_profile 的那段")
else:
    print("③ 已有档位切换")

for f in (SH, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-14s %s" % (os.path.basename(f), "通过 ✓" if r.returncode == 0 else (r.stderr or "")[-220:]))

# ④ 自测:两款的档位
r = subprocess.run(["python", "-c",
                    "import sys;sys.path.insert(0,r'D:\\Unity阅读器');"
                    "from core import storyhook as s;"
                    "print('  utage →', s.tier_for('utage'));"
                    "print('  abt   →', s.tier_for('abettertomorrow'));"
                    "print('  none  →', s.tier_for(None))"],
                   capture_output=True, text=True, errors="ignore")
print(r.stdout.strip() or (r.stderr or "")[-200:])

for rel in ("core/storyhook.py", "webapp/server.py"):
    shutil.copy2(os.path.join(SRC, rel.replace("/", os.sep)), os.path.join(APP, rel.replace("/", os.sep)))
print("已部署")
