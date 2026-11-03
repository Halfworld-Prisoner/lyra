# -*- coding: utf-8 -*-
"""让菜单文字也能被翻到:
   · EnableTextMesh=True(老式 TextMesh 组件,主菜单常用)
   · EnableSpriteRendererHooking=True(菜单若是贴图/精灵,至少让 XUnity 能接管)
   · 两个模板 + 已装的游戏配置 + 已部署的载荷一份都改。"""
import io
import os

WANT = {
    "EnableTextMesh": "True",
    "EnableSpriteRendererHooking": "True",
    "EnableLog": "True",
}

targets = []
for arch in ("mono_x64", "il2cpp_x64"):
    targets.append(os.path.join(r"D:\Unity阅读器", "payload", "translate", arch,
                                "BepInEx", "config", "AutoTranslatorConfig.ini"))
    targets.append(os.path.join(r"D:\Lyra", "app", "payload", "translate", arch,
                                "BepInEx", "config", "AutoTranslatorConfig.ini"))
for g in (r"D:\Steam\steamapps\common\Knights College 2 -ナイツカレッジ2-",
          r"D:\Steam\steamapps\common\KnightsCollege"):
    targets.append(os.path.join(g, "BepInEx", "config", "AutoTranslatorConfig.ini"))

for p in targets:
    if not os.path.isfile(p):
        print("  --  跳过(不存在):", p)
        continue
    raw = io.open(p, encoding="utf-8-sig").read()
    seen, out = set(), []
    for ln in raw.replace("\r\n", "\n").split("\n"):
        k = ln.split("=", 1)[0].strip() if ("=" in ln and not ln.lstrip().startswith(";")) else ""
        if k in WANT:
            out.append("%s=%s" % (k, WANT[k]))
            seen.add(k)
        else:
            out.append(ln)
    for k, v in WANT.items():
        if k not in seen:
            out.append("%s=%s" % (k, v))
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    tag = "模板" if "payload" in p else "游戏"
    print("  OK  [%s] %s" % (tag, p.replace(r"D:\Steam\steamapps\common", "…")))
print("完成")
