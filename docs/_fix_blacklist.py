# -*- coding: utf-8 -*-
"""修「把一句拉进黑名单,它还是被读出来」。

根因:黑名单/白名单是按**子串**比对的,但两侧的字符串不是同一种形态 ——
   · 玩家从界面上拉黑的是**显示行**:`【亞戈】「台詞」`
     (这个【名字】前缀是**我们自己拼上去的**,游戏原文里没有)
   · 而过滤器在 feed() 里比对的是**游戏原文**:`「台詞」`
  → 永远匹配不上,黑名单形同虚设。

修法:比对前把两侧都"归一化" —— 去掉开头的 [标签] 与 【角色名】,
      并且两种形态都试一遍(原文 / 去掉前缀)。名单里存的也统一存去掉前缀的形态。
"""
import io
import subprocess

SH = r"D:\Unity阅读器\core\storyhook.py"
SV = r"D:\Unity阅读器\webapp\server.py"

# ---------- ① storyhook.py:加归一化 + 用它比对 ----------
t = io.open(SH, encoding="utf-8").read()

if "def bare_for_list" not in t:
    t = t.replace("def list_verdict(self, text: str) -> str:",
'''def bare_for_list(s: str) -> str:
    """把"界面显示的那一行"还原成"游戏原文",用于名单比对。

    界面上我们会在句首拼 `【角色名】`(便于阅读),日志行还可能有 `[标签]` 前缀;
    而游戏原文两者都没有。名单比对必须把这两层剥掉,否则永远对不上
    (玩家反馈:把一句拉黑,它照样被读出来)。
    """
    s = (s or "").strip()
    s = re.sub(r"^\\[[^\\]]{0,24}\\]\\s*", "", s)          # [标签]
    s = re.sub(r"^【[^】]{1,14}】\\s*", "", s)              # 【角色名】
    return s.strip()


def list_verdict(self, text: str) -> str:''', 1)

    old = '''        t = text or ""
        for w in EFF.get("blacklist", ()):
            if not w:
                continue
            if w[0] == "=":
                if t.strip() == w[1:].strip():
                    return "block"
            elif w in t:
                return "block"
        for w in EFF.get("whitelist", ()):
            if not w:
                continue
            if w[0] == "=":
                if t.strip() == w[1:].strip():
                    return "allow"
            elif w in t:
                return "allow"
        return ""'''
    new = '''        t = text or ""
        # 两种形态都拿来比:① 收到什么比什么;② 剥掉【角色名】/[标签] 之后的原文
        forms = {t, t.strip(), bare_for_list(t)}
        forms = {f for f in forms if f}

        def hit(w: str) -> bool:
            """这条名单规则命中了吗?"""
            if not w:
                return False
            exact = w[0] == "="
            body = w[1:].strip() if exact else w
            body_bare = bare_for_list(body)
            for f in forms:
                if exact:
                    if f.strip() == body:
                        return True
                else:
                    if body in f or (body_bare and body_bare in f):
                        return True
            return False

        for w in EFF.get("blacklist", ()):
            if hit(w):
                return "block"
        for w in EFF.get("whitelist", ()):
            if hit(w):
                return "allow"
        return ""'''
    assert old in t, "list_verdict 没匹配"
    t = t.replace(old, new, 1)
    io.open(SH, "w", encoding="utf-8", newline="\n").write(t)
    print("① storyhook.py 已加 bare_for_list 并用于名单比对")
else:
    print("① 已有 bare_for_list")

# ---------- ② server.py:存名单时统一存"原文"形态 ----------
s = io.open(SV, encoding="utf-8").read()
old2 = '''                if mode == "exact":
                    value = "=" + value'''
new2 = '''                # ★统一存"游戏原文"形态★:界面显示的 【角色名】/[标签] 前缀是我们自己拼的,
                #   原样存进去会导致比对永远对不上(玩家反馈"拉黑了还是读")。
                value = storyhook.bare_for_list(value) or value
                if mode == "exact":
                    value = "=" + value'''
if old2 in s and "bare_for_list(value)" not in s:
    s = s.replace(old2, new2, 1)
    io.open(SV, "w", encoding="utf-8", newline="\n").write(s)
    print("② server.py 存名单前会剥掉【角色名】/[标签] 前缀")
else:
    print("② 无需改或没匹配")

for f in (SH, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-16s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else r.stderr[:160]))
