# -*- coding: utf-8 -*-
"""再补两处:① setup.c 里要有 IDR_WEBVIEW2/IDR_UI_HTML/IDR_LOGO_PNG 宏;
   ② C++ 下 CoCreateInstance 的 &CLSID/&IID 要去掉取地址符。"""
import io
import os
import re

I = r"D:\Unity阅读器\installer"


def patch(f, pairs):
    p = os.path.join(I, f)
    t = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        if a in t:
            t = t.replace(a, b)
            print("  OK   %-12s %s" % (f, a.strip().split("\n")[0][:48]))
        else:
            print("  --   %-12s 未匹配 %s" % (f, a.strip().split("\n")[0][:48]))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


patch("setup.c", [
    ("#define IDR_UNINSTALL 105",
     "#define IDR_UNINSTALL 105\n"
     "#define IDR_WEBVIEW2  106\n"
     "#define IDR_UI_HTML   107\n"
     "#define IDR_LOGO_PNG  108"),
    ("CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW,",
     "CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, IID_IShellLinkW,"),
])
print("完成")
