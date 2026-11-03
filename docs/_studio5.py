# -*- coding: utf-8 -*-
"""给宿主加 --designer(全屏设计窗口)——**只用简单字符串替换,不动任何括号结构**:

  ① 解析 --designer
  ② 设计窗口用**不同的窗口类名** LyraDesignerWindow
     → 那段"单实例判断"用的是 FindWindowW(L"LingYueReaderWindow"),
       换个类名它就找不到"已有窗口",于是不会把新窗口挡回去(不用改那段代码)
  ③ 设计窗口 = 全屏
  ④ 标题 = Lyra · UI 创作
  ⑤ 打开 /designer 而不是 /
"""
import io
import os
import subprocess

SRC = r"D:\Unity阅读器"
PC = os.path.join(SRC, "installer", "player.cpp")
t = io.open(PC, encoding="utf-8").read()

edits = []

def rep(old, new, why):
    global t
    if old in t:
        t = t.replace(old, new)          # 全部替换(类名等出现多次也要一起改)
        edits.append("OK   " + why)
    else:
        edits.append("!!   没找到:" + why)

# ① 解析参数
rep("int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR cmdLine, int) {",
    "static bool g_designer = false;          /* --designer:另开一个全屏设计窗口 */\n\n"
    "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR cmdLine, int) {",
    "声明 g_designer")
rep("    g_hInst = hInst;",
    "    g_hInst = hInst;\n"
    "    if (cmdLine && wcsstr(cmdLine, L\"--designer\")) g_designer = true;",
    "解析 --designer")

# ② 类名:设计窗口用另一个(单实例判断就找不到它了)
rep('wc.lpszClassName = L"LingYueReaderWindow";',
    'wc.lpszClassName = g_designer ? L"LyraDesignerWindow" : L"LingYueReaderWindow";',
    "设计窗口类名分开")

# ③ 全屏
rep("int w = 1180, hgt = 820;",
    "int w = g_designer ? GetSystemMetrics(SM_CXSCREEN) : 1180;\n"
    "    int hgt = g_designer ? GetSystemMetrics(SM_CYSCREEN) : 820;",
    "设计窗口全屏")

# ④ 标题
rep('CreateWindowExW(0, wc.lpszClassName, L"Lyra",',
    'CreateWindowExW(0, wc.lpszClassName, g_designer ? L"Lyra \u00b7 UI \u521b\u4f5c" : L"Lyra",',
    "设计窗口标题")

# ⑤ 地址:设计窗口看 /designer
rep('g_url = L"http://127.0.0.1:" + std::to_wstring(g_port) + L"/";',
    'g_url = L"http://127.0.0.1:" + std::to_wstring(g_port) + (g_designer ? L"/designer" : L"/");',
    "设计窗口地址 /designer")

io.open(PC, "w", encoding="utf-8", newline="\n").write(t)
print("\n".join(edits))

print("\n编译:")
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", os.path.join(SRC, "installer", "build_player.ps1")],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
out = (r.stdout or "") + (r.stderr or "")
tail = [x for x in out.splitlines() if x.strip()][-3:]
print("  " + "\n  ".join(tail))
print("  编译成功:", "窗口宿主" in out and "失败" not in out)
