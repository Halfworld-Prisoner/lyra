# -*- coding: utf-8 -*-
"""收尾两处小修:①安装器详情默认收起;②player.cpp 里两处旧产品名。"""
import io

p = r"D:\Unity阅读器\installer\setup.c"
t = io.open(p, encoding="utf-8").read()
old = "        SetWindowTextW(g_hPath, def);"
new = ("        SetWindowTextW(g_hPath, def);\n"
       "        ShowWindow(g_hLog, SW_HIDE);                     /* 技术细节默认收起 */\n"
       "        SetWindowTextW(g_hDetail, L\"显示详情\";")
if "ShowWindow(g_hLog, SW_HIDE)" not in t:
    t = t.replace(old, new.replace('L"显示详情";', 'L"\\u663e\\u793a\\u8be6\\u60c5 \\u25be");'), 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("setup.c:详情默认收起 + 按钮文案已写死")
else:
    print("setup.c:已经有了")

p2 = r"D:\Unity阅读器\installer\player.cpp"
s = io.open(p2, encoding="utf-8").read()
n = s.count('L"\u8046\u9605"')
s = s.replace('L"\u8046\u9605"', 'L"Lyra"')
io.open(p2, "w", encoding="utf-8", newline="\n").write(s)
print("player.cpp:替换旧名字", n, "处")
