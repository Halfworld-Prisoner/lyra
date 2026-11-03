# -*- coding: utf-8 -*-
r"""修「正常台词里带 商店/记忆/设置 这类词就被整句过滤掉」。

根因:is_story_text() 里**先**跑界面词匹配(EFF_WORDS 子串命中就 return False),
      而"是不是带引号的台词"这个判断在**后面**(第 473 行)→ 于是
      「就是有很多商店聚集的地方！」这种台词被当成界面文字丢掉(日志有记录)。

修法:把"台词优先"提到界面词匹配**之前** ——
      · 带 「」『』"" 引号的行 = 台词 → 直接放行,不受界面词影响;
      · 面板/菜单那种**没有引号**的整句,照旧按界面词丢掉(过滤能力不变);
      · 另外给界面词判断加一条保险:命中的词只是"台词的一部分"且该行带句末标点时,
        也不算界面文字。
"""
import io
import subprocess

P = r"D:\Unity阅读器\core\storyhook.py"
t = io.open(P, encoding="utf-8").read()

OLD = '''    for kw in EFF_WORDS:
        if kw and kw in s:
            return False, f"界面词({kw})"
    if (s[0] in "「『“" or s[-1] in "」』”") and cjk >= 1:
        return True, ""
'''

NEW = '''    # ★台词优先★:带引号的行就是台词,不能被界面词误杀★
    #   玩家反馈:正常剧情里只要出现「商店」「记忆」「设置」这类词,整句就被丢掉。
    #   所以先认台词(引号),再按界面词过滤 —— 面板文字没有引号,照旧拦得住。
    if (s[0] in "「『“" or s[-1] in "」』”") and cjk >= 1:
        return True, ""
    for kw in EFF_WORDS:
        if not kw or kw not in s:
            continue
        # 保险:这一句又长又带句末标点 / 引号 → 更像台词,放行
        looks_like_speech = (len(s) >= 14 and any(ch in s for ch in "。！？…!?")
                             and any(ch in s for ch in "「」『』“”"))
        if looks_like_speech:
            continue
        return False, f"界面词({kw})"
'''

assert OLD in t, "没找到那段过滤代码"
t = t.replace(OLD, NEW, 1)
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("已修:台词优先于界面词过滤")

r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:250])
