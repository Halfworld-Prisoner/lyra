# -*- coding: utf-8 -*-
"""修「默认配音/角色配音选女声,重启后被改回全局默认」。

根因:migrate_voice_cfg() 是当初"下架女声"时写的一次性迁移,却**每次启动都跑**,
      里面有三处强制改写:
        ① voice 是女声 → 换成男声默认
        ② cast_default 是女声 → 清空(于是重启后回落到"跟随全局语音")  ← 玩家遇到的
        ③ 每个角色配的女声 → 清空
      女声早就加回来了,玩家也明确要能自选,所以这三处必须去掉。
保留:① 语音包已卸载/id 失效时回落到可用声音(这才是真正该修的);
      ② cast_seen 里的方法名/菜单词清理。
"""
import io

SRV = r"D:\Unity阅读器\webapp\server.py"
t = io.open(SRV, encoding="utf-8").read()

# ---- ① 全局语音:不再因为"女声"而改写 ----
old1 = '''    elif cur and _is_female_voice(cur):
        fixed = pick_default()
    if fixed != cur:'''
new1 = '''    # (曾经这里把"女声"一律换成男声默认 —— 已移除:女声早已加回,玩家可自由选择)
    if fixed != cur:'''
assert old1 in t, "① 没匹配"
t = t.replace(old1, new1, 1)

# ---- ② 默认配音:不再清空女声 ----
old2 = '''    cd = str(cfg.get("cast_default") or "")
    if cd and _is_female_voice(cd):
        cfg["cast_default"] = ""
        notes.append("默认配音里的女声(SAPI)已改回「跟随全局语音」")

    cast = cfg.get("cast") or {}
    changed = 0
    for name, item in list(cast.items()):
        if isinstance(item, dict) and item.get("voice") and _is_female_voice(item["voice"]):
            item["voice"] = ""
            changed += 1
    if changed:
        notes.append(f"{changed} 个角色原来配的是女声,已改成跟随全局语音")
'''
new2 = '''    # ★这里原来会把「默认配音」和「角色配音」里的女声清空★
    #   那是女声下架时的一次性迁移,女声早就加回来了 —— 玩家选的女声必须原样保留,
    #   否则每次重启都会看到自己的选择被改回"跟随全局语音"(实测玩家反馈)。
    #   现在只做一件事:把**已经不存在**的声音 id 清掉(语音包被卸载/id 写错)。
    cd = str(cfg.get("cast_default") or "")
    if cd and not _voice_exists(cd):
        cfg["cast_default"] = ""
        notes.append(f"默认配音 {cd} 已不存在,改回「跟随全局语音」")

    cast = cfg.get("cast") or {}
    changed = 0
    for name, item in list(cast.items()):
        if isinstance(item, dict) and item.get("voice") and not _voice_exists(item["voice"]):
            item["voice"] = ""
            changed += 1
    if changed:
        notes.append(f"{changed} 个角色配的声音已不存在,改回跟随全局语音")
'''
assert old2 in t, "② 没匹配"
t = t.replace(old2, new2, 1)

# ---- 加一个"这个声音还在不在"的判断 ----
if "def _voice_exists" not in t:
    t = t.replace('''def migrate_voice_cfg() -> list:''',
'''def _voice_exists(v: str) -> bool:
    """这个声音 id 现在还能用吗?(语音包被卸载 / id 写错时返回 False)"""
    v = (v or "").strip()
    if not v:
        return False
    try:
        if v.startswith("sherpa:"):
            pid = tts.sherpa_pack_of(v)
            return bool(pid) and voices.is_installed(pid)
        for vid, _lang in tts.list_voices():
            if vid == v:
                return True
        return False
    except Exception:
        return True          # 判断不了就别动玩家的设置


def migrate_voice_cfg() -> list:''', 1)

io.open(SRV, "w", encoding="utf-8", newline="\n").write(t)
print("已修:migrate_voice_cfg 不再改写玩家选的女声(只清理已失效的声音 id)")
import py_compile
py_compile.compile(SRV, doraise=True)
print("语法通过")
