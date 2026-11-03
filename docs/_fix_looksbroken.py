# -*- coding: utf-8 -*-
"""只做一件事:删掉 _looks_broken 里那条会误判的"连续符号"启发式。

   原文「原來如此……」他說道——是這樣嗎? 里 …… 和 —— 是**合法**的连续符号,
   却被这条规则当成"乱码"→ 整句退回原文(表现:这句永远是繁体)。
   删掉它,只保留"文字太少""符号比原文多"这两条真正靠谱的判据。"""
import io

TR = r"D:\Unity阅读器\core\translate.py"
t = io.open(TR, encoding="utf-8").read()
old = '''    if re.search(r"[^\\w\\s][^\\w\\s]{4,}", out):
        return True
'''
if old in t:
    t = t.replace(old, '''    # (这里曾经有一条"连续 5 个以上符号就算乱码"的规则 —— 实测会把
    #  「原來如此……」他說道——是這樣嗎? 这种**合法**写法误判成乱码,
    #  导致整句退回原文。已删除。)
''', 1)
    io.open(TR, "w", encoding="utf-8", newline="\n").write(t)
    print("已删除误判规则")
else:
    print("没找到那条规则(可能写法不同),当前 _looks_broken 内容:")
    i = t.find("def _looks_broken")
    print(t[i:i+520])
