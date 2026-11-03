# -*- coding: utf-8 -*-
"""读取流水线端到端自测(不启动游戏、不动玩家目录)。

覆盖:
  1. 正常三步:台词 → 名字 → 旁白(名字要被记住、旁白不能被污染)
  2. 黑名单:含该词的行彻底不读
  3. 白名单:本该被丢掉的行(短词/界面词/噪音)要能读出来
  4. 静默推进:请求文件写出去、回执读回来(用假回执模拟插件)
  5. 译文替换:开了「朗读译文」后,XUnity 回写的中文要顶掉日文原文
用法: python docs/_reader_test.py
"""
import os
import shutil
import sys
import time

sys.path.insert(0, r"D:\Unity阅读器")
from core import storyhook as sh          # noqa: E402

FAKE = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "ly_reader_test")
OK, BAD = [], []


def check(name, cond, detail=""):
    (OK if cond else BAD).append(name)
    print(("  [OK]   " if cond else "  [FAIL] ") + name + (("   " + detail) if detail else ""))


def feed(h, method, text, wait=0.5):
    """喂一行并等打字机定稿,返回这次读出来的行。"""
    out = list(h.filter.feed(text, method))
    time.sleep(wait)
    out += list(h.filter.tick())
    return out


def main():
    shutil.rmtree(FAKE, ignore_errors=True)
    os.makedirs(os.path.join(FAKE, "BepInEx"), exist_ok=True)
    open(os.path.join(FAKE, "G.exe"), "wb").write(b"MZ")
    log = os.path.join(FAKE, "BepInEx", "storyhook.log")
    open(log, "w", encoding="utf-8").close()

    got = []
    status = []
    h = sh.HookManager(payload_dir=os.path.join(r"D:\Unity阅读器", "payload"),
                       hooks_dir=os.path.join(r"D:\Unity阅读器", "hooks"),
                       on_line=got.append, on_status=status.append)
    h.set_game({"dir": FAKE, "exe": "KnightsCollege_2.exe", "name": "假游戏",
                "path": os.path.join(FAKE, "G.exe"), "payload": "mono_x64"})
    h.filter.min_cjk = 4
    h.filter.strict = True

    print("1) 专用规则识别")
    check("按 exe 名认出 UTAGE 专用规则", sh.ACTIVE_PROFILE == "utage",
          f"ACTIVE_PROFILE={sh.ACTIVE_PROFILE}")

    print("2) 正常三步")
    got.clear()
    h.start()
    time.sleep(0.5)                      # 先让读取端接上(接上之前的老内容按设计跳过)
    with open(log, "a", encoding="utf-8") as f:
        # 真实游戏里这两行是**同一帧**写出来的(实测日志顺序:先台词、后名字),
        # 所以要在一次追加里写完 —— 这也是"名字能被带上"的前提。
        f.write("Utage.AdvMessageWindow\tset_Text\t「你好啊,朋友。」\n")
        f.write("Utage.AdvMessageWindow\tset_NameText\t奧斯卡\n")
    time.sleep(1.0)
    with open(log, "a", encoding="utf-8") as f:
        # 旁白之前游戏会把名字框**清空**:插件写的是"末尾带制表符、第三段为空"的一行
        f.write("Utage.AdvMessageWindow\tset_NameText\t\n")
    time.sleep(0.4)
    with open(log, "a", encoding="utf-8") as f:
        f.write("Utage.AdvMessageWindow\tset_Text\t旁白一句话,没有名字。\n")
    time.sleep(1.4)
    h.stop()
    check("第一句带上了角色名", any("【奧斯卡】" in x for x in got), str(got[:2]))
    check("名字框清空后旁白不带名字", any(x.startswith("旁白一句话") for x in got), str(got))

    print("3) 黑名单")
    sh.add_rule("blacklist", "旁白一句话")
    h.filter.forget_recent()
    out = feed(h, "Utage.AdvMessageWindow.set_Text", "旁白一句话,没有名字。")
    check("黑名单的行不读", not out, str(out))
    check("原因是黑名单", h.filter.last_reason.startswith("黑名单"), h.filter.last_reason)
    sh.del_rule("blacklist", "旁白一句话")

    print("4) 白名单(本该被丢掉的行要能读)")
    h.filter.forget_recent()
    out = feed(h, "Utage.AdvMessageWindow.set_Text", "存档")
    check("白名单前:界面词「存档」不读", not out, str(out))
    sh.add_rule("whitelist", "存档")
    h.filter.forget_recent()
    out = feed(h, "Utage.AdvMessageWindow.set_Text", "存档")
    check("白名单后:同一句读出来了", bool(out), str(out))
    # 连"引擎噪音"关也要放行
    sh.add_rule("whitelist", "pos")
    h.filter.forget_recent()
    out = feed(h, "GetParamStr", "pos")
    check("白名单能过引擎噪音关", bool(out), str(out))
    sh.del_rule("whitelist", "存档")
    sh.del_rule("whitelist", "pos")

    print("5) 静默推进的请求/回执")
    h.set_game({"dir": FAKE, "exe": "KnightsCollege_2.exe", "name": "假游戏",
                "path": os.path.join(FAKE, "G.exe"), "payload": "mono_x64"})
    r = h.silent_advance()
    req = os.path.join(FAKE, "BepInEx", sh.CLICK_FILE)
    check("写出了点击请求文件", r.get("ok") and os.path.isfile(req),
          open(req, encoding="utf-8").read() if os.path.isfile(req) else r.get("msg", ""))
    # 模拟插件回执
    open(os.path.join(FAKE, "BepInEx", sh.CLICK_ACK), "w", encoding="utf-8").write("ok\tUTAGE 内部推进(鼠标没动)")
    ackfile = os.path.join(FAKE, "BepInEx", sh.CLICK_ACK)
    txt = open(ackfile, encoding="utf-8").read().strip().split("\t")
    check("回执可读且判定成功", txt[0] == "ok" and "鼠标没动" in txt[1], str(txt))

    print("6) 译文替换(朗读译文)")
    # 必须走**真实路径**:XUnity 的译文是 loop 里的 method 前缀识别的,不是直接喂给 filter
    h.say_translation = True
    h.filter.forget_recent()
    got.clear()
    h.start()
    time.sleep(0.6)
    with open(log, "a", encoding="utf-8") as f:
        f.write("Utage.AdvMessageWindow\tset_Text\t「こんなところで何をしているんだ。」\n")
    time.sleep(0.3)
    with open(log, "a", encoding="utf-8") as f:
        f.write("XUnity.AutoTranslator\tset_text\t「在这种地方干什么呢。」\n")
    time.sleep(1.8)
    h.stop()
    check("读出来的是中文译文", any("在这种地方" in x for x in got), str(got))
    check("日文原文没有被念", not any("こんなところ" in x for x in got), str(got))
    h.say_translation = False

    h.stop()
    shutil.rmtree(FAKE, ignore_errors=True)
    print()
    if status:
        print("读取端提示:", " | ".join(status[-6:]))
    print("通过 %d 项,失败 %d 项" % (len(OK), len(BAD)))
    if BAD:
        print("失败:", "、".join(BAD))
        sys.exit(1)


if __name__ == "__main__":
    main()
