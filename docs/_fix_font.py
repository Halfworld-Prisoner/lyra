# -*- coding: utf-8 -*-
"""方框字(□)修复:把游戏里 XUnity 的字体指到系统中文字体。

背景:这游戏原文是**繁体**,繁转简后出现只在简体里存在的字(罗/请/设…),
游戏的字体是繁体字体 → 缺字形 → 显示成 □。
XUnity 支持用系统字体动态生成 UGUI 与 TextMeshPro 字体(OverrideFont /
OverrideFontTextMeshPro / FallbackFontTextMeshPro),这正是标准解法。

改动:
① server.py:新增 write_xunity_cfg()(幂等,只改变化行),并在
   /api/translate/on、/api/translate/state、新的 /api/translate/font 里使用;
② 翻译页:加一个「字体兜底」开关;
③ 两个架构的 XUnity 模板配置:填上默认字体名。
"""
import io
import os

SRC = r"D:\Unity阅读器"
SRV = os.path.join(SRC, "webapp", "server.py")

# ---------------- ① 后端 ----------------
t = io.open(SRV, encoding="utf-8").read()

if "def write_xunity_cfg" not in t:
    FUNC = '''
# ---------------------------------------------------------------- 游戏内字体兜底
# 繁转简之后,有些字(罗/请/设/说…)只在简体里有,而游戏的字体是繁体字体,
# 缺字形就显示成 □。解法是把游戏用的字体换成系统中文字体(系统字体有全字形)。
FONT_MAIN = "Microsoft YaHei"
FONT_FALLBACK = "Microsoft YaHei UI"


def _xunity_cfg_path(game: dict) -> str:
    d = (game or {}).get("dir") or ""
    return os.path.join(d, "BepInEx", "config", "AutoTranslatorConfig.ini") if d else ""


def write_xunity_cfg(game: dict = None, log: bool = False) -> dict:
    """把「接口地址 / 语言 / 字体兜底」写进游戏的 XUnity 配置(幂等)。

    只改我们自己关心的那几行,其余原样保留 —— 玩家自己改过的其它设置不会被动。
    文件没变化就不落盘,所以可以放心在设置变更时调用。
    """
    cfg = cfgm.get()
    if game is None:
        game = game_of(cfg["game"]) if cfg.get("game") else None
    path = _xunity_cfg_path(game)
    if not path or not os.path.isfile(path):
        return {"ok": False, "msg": "这个游戏还没装翻译插件"}
    tr = cfg.get("translate") or {}
    font_fix = bool(tr.get("font_fix", True))
    want = {
        "Url": "http://127.0.0.1:%d/api/translate" % PORT,
        "Language": "zh-CN",
        "FromLanguage": "auto",
        "OverrideFont": FONT_MAIN if font_fix else "",
        "OverrideFontTextMeshPro": FONT_MAIN if font_fix else "",
        "FallbackFontTextMeshPro": FONT_FALLBACK if font_fix else "",
        "EnableLog": "True" if log else "False",
    }
    try:
        raw = io.open(path, encoding="utf-8-sig").read()
    except Exception as e:
        return {"ok": False, "msg": "读不了配置:%s" % e}
    lines = raw.replace("\\r\\n", "\\n").split("\\n")
    seen = set()
    out = []
    for ln in lines:
        key = ln.split("=", 1)[0].strip() if "=" in ln and not ln.lstrip().startswith(";") else ""
        if key in want:
            new = "%s=%s" % (key, want[key])
            out.append(new)
            seen.add(key)
        else:
            out.append(ln)
    for key, val in want.items():
        if key not in seen:
            out.append("%s=%s" % (key, val))
    new_text = "\\n".join(out)
    if new_text != raw.replace("\\r\\n", "\\n"):
        try:
            io.open(path, "w", encoding="utf-8", newline="\\n").write(new_text)
        except Exception as e:
            return {"ok": False, "msg": "写不了配置:%s" % e}
        if font_fix:
            return {"ok": True, "msg": "已把游戏字体指向 %s(重启游戏后不再出现方框)" % FONT_MAIN, "changed": True}
        return {"ok": True, "msg": "已关闭字体兜底", "changed": True}
    return {"ok": True, "msg": "", "changed": False}


'''
    anchor = "def apply_translate_cfg():"
    assert anchor in t
    t = t.replace(anchor, FUNC.lstrip("\n") + anchor, 1)

    # 开机时同步一次(游戏已装翻译插件的话)
    t = t.replace("apply_translate_cfg()\n_voice_notes = migrate_voice_cfg()",
                  "apply_translate_cfg()\ntry:\n    write_xunity_cfg()          # 已装插件的游戏:开机同步字体兜底与接口地址\nexcept Exception:\n    pass\n_voice_notes = migrate_voice_cfg()", 1)

    # 打开翻译时同步
    t = t.replace('''                tr["on"] = on
                cfgm.save()
                apply_translate_cfg()''',
                  '''                tr["on"] = on
                cfgm.save()
                apply_translate_cfg()
                if on and g:
                    w = write_xunity_cfg(g)          # 顺手把字体兜底与接口地址写进去
                    if w.get("msg"):
                        add_log(w["msg"], "info")''', 1)

    # state 里带上 font_fix
    t = t.replace('''                    "prefetch": bool(tr.get("prefetch", True)),''',
                  '''                    "prefetch": bool(tr.get("prefetch", True)),
                    "font_fix": bool(tr.get("font_fix", True)),''', 1)

    # 新接口
    t = t.replace('''            if p == "/api/translate/clear":''',
                  '''            if p == "/api/translate/font":
                tr = _tr_cfg()
                tr["font_fix"] = bool(d.get("on"))
                cfgm.save()
                cfg_ = cfgm.get()
                g_ = game_of(cfg_["game"]) if cfg_.get("game") else None
                r = write_xunity_cfg(g_)
                add_log(r.get("msg") or "", "info") if r.get("msg") else None
                return self._json({"ok": bool(r.get("ok")), "msg": r.get("msg") or "已保存",
                                   "font_fix": tr["font_fix"]})

            if p == "/api/translate/clear":''', 1)

    io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
    print("① server.py 已加 write_xunity_cfg + /api/translate/font")
else:
    print("① server.py 已有 write_xunity_cfg")

# ---------------- ③ 两个模板配置 ----------------
for arch in ("mono_x64", "il2cpp_x64"):
    p = os.path.join(SRC, "payload", "translate", arch, "BepInEx", "config", "AutoTranslatorConfig.ini")
    if not os.path.isfile(p):
        print("   -- 模板不存在:", p)
        continue
    txt = io.open(p, encoding="utf-8-sig").read()
    for key, val in (("OverrideFont", "Microsoft YaHei"),
                     ("OverrideFontTextMeshPro", "Microsoft YaHei"),
                     ("FallbackFontTextMeshPro", "Microsoft YaHei UI")):
        out = []
        for ln in txt.replace("\r\n", "\n").split("\n"):
            k = ln.split("=", 1)[0].strip() if "=" in ln and not ln.lstrip().startswith(";") else ""
            out.append("%s=%s" % (key, val) if k == key else ln)
        txt = "\n".join(out)
    io.open(p, "w", encoding="utf-8", newline="\n").write(txt)
    print("   模板已填字体兜底:", arch)
print("完成")
