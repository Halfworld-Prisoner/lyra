# -*- coding: utf-8 -*-
r"""给《A Better Tomorrow》做适配:

实测(游戏日志 + Lyra 收到的行):
  · 引擎:Unity IL2CPP,文本全部走 TMPro.TMP_Text.set_text ✓
  · 档位必须 tmpro(tmpro 档挂上 14 个方法 ✓;gameonly 只挂到 2 个特效方法 ✗)
  · 对白能读到 ✓ 但:「隐藏」这个"隐藏对话框"按钮被当成了**角色名** ✗
    → 每条台词都变成「【隐藏】xxx」✗

适配内容:
  ① 新增游戏专用档(GAME_PROFILES):菜单词 + 名字黑名单(隐藏/自动/历史/存档…)
  ② 默认档位改成 tmpro(IL2CPP + TMP 游戏的标准档;gameonly 太窄会漏对白)
"""
import io
import os
import shutil
import subprocess

SRC, APP = r"D:\Unity阅读器", r"D:\Lyra\app"
SH = os.path.join(SRC, "core", "storyhook.py")

t = io.open(SH, encoding="utf-8").read()

PROFILE = '''    {
        "key": "abettertomorrow",
        "name": "A Better Tomorrow(Unity IL2CPP / TMP)",
        "note": "实测:文本全部走 TMPro.TMP_Text.set_text;菜单按钮(隐藏/自动/历史…)也会当文本送进来,"
                "而且「隐藏」这个按钮会被误当成角色名 —— 所以它们全进名字黑名单。",
        "match_exe": ("better tomorrow", "bettertomorrow", "tomorrow"),
        "match_method": ("tmpro.tmp_text",),
        "groups": {
            "menu_words": [
                "新游戏", "继续游戏", "读取存档", "存档", "读/存档", "历史", "自动",
                "隐藏", "设置", "关于", "退出", "返回主页", "返回标题", "跳过",
                "关闭", "确定", "取消", "音量", "全屏", "窗口化", "语言",
            ],
            "ui_keywords": [
                "继续游戏", "返回主页", "隐藏对话框", "自动播放", "读/存档",
            ],
            # ★最关键的一条★:这些按钮文字曾被当成角色名(【隐藏】xxx)
            "name_blacklist": [
                "隐藏", "自动", "历史", "存档", "读/存档", "设置", "关于", "退出",
                "新游戏", "继续游戏", "返回主页", "返回标题", "跳过", "关闭",
                "确定", "取消", "音量", "全屏", "窗口化", "语言", "上一页", "下一页",
            ],
            "junk_text": ["A Better Tomorrow", "ABetterTomorrow"],
        },
    },
'''
if '"key": "abettertomorrow"' not in t:
    anchor = "]\n\nPROFILE_BY_KEY = {p[\"key\"]: p for p in GAME_PROFILES}"
    assert anchor in t, "找不到 GAME_PROFILES 结束位置"
    t = t.replace(anchor, PROFILE + anchor, 1)
    io.open(SH, "w", encoding="utf-8", newline="\n").write(t)
    print("① 已加入《A Better Tomorrow》专用档")
else:
    print("① 专用档已存在")

# ② 默认档位 gameonly → tmpro
n = t.count('"gameonly"')
t2 = io.open(SH, encoding="utf-8").read()
t2 = t2.replace('self.profile = "gameonly"  # IL2CPP LDC 档位:gameonly / tmpro_setonly / tmpro / all',
                'self.profile = "tmpro"     # IL2CPP LDC 档位:gameonly / tmpro_setonly / tmpro / all'
                '  (gameonly 太窄会漏对白,实测 ABT 只挂到 2 个特效方法)')
io.open(SH, "w", encoding="utf-8", newline="\n").write(t2)
print("② storyhook.py 默认档位 → tmpro")

SV = os.path.join(SRC, "webapp", "server.py")
s = io.open(SV, encoding="utf-8").read()
n2 = s.count('cfgm.get().get("hook_profile") or "gameonly"') + s.count('cfg.get("hook_profile") or "gameonly"')
s = s.replace('cfgm.get().get("hook_profile") or "gameonly"', 'cfgm.get().get("hook_profile") or "tmpro"')
s = s.replace('cfg.get("hook_profile") or "gameonly"', 'cfg.get("hook_profile") or "tmpro"')
io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
print("② server.py 默认档位 → tmpro(%d 处)" % n2)

# ③ 配置里也直接写成 tmpro(玩家机器上生效)
import json
cp = os.path.join(APP, "config.json")
try:
    d = json.load(io.open(cp, encoding="utf-8-sig"))
    d["hook_profile"] = "tmpro"
    io.open(cp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
    print("③ 配置 hook_profile = tmpro ✓")
except Exception as e:
    print("③ 配置写入失败:", e)

for f in (SH, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-14s %s" % (os.path.basename(f), "通过 ✓" if r.returncode == 0 else (r.stderr or "")[-200:]))

for rel in ("core/storyhook.py", "webapp/server.py"):
    shutil.copy2(os.path.join(SRC, rel.replace("/", os.sep)), os.path.join(APP, rel.replace("/", os.sep)))
print("已部署")
