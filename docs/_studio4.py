# -*- coding: utf-8 -*-
"""三处简单替换(不用正则,改完全部打印核对)+ 编译 + 部署 + 启动设计窗口验证。"""
import io
import os
import re
import subprocess

SRC = r"D:\Unity阅读器"
PC = os.path.join(SRC, "installer", "player.cpp")
t = io.open(PC, encoding="utf-8").read()

# 看 g_url 是怎么拼的
for m in re.finditer(r"[^\n]*g_url[^\n]*", t):
    print("   g_url:", m.group(0).strip()[:120])

# ① 声明 + 解析参数
if "g_designer" not in t:
    t = t.replace("int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR cmdLine, int) {",
                  "static bool g_designer = false;          /* --designer:全屏设计窗口 */\n\n"
                  "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR cmdLine, int) {", 1)
    t = t.replace("    g_hInst = hInst;",
                  "    g_hInst = hInst;\n"
                  "    if (cmdLine && wcsstr(cmdLine, L\"--designer\")) g_designer = true;", 1)

# ② 全屏
t = t.replace("int w = 1180, hgt = 820;",
              "int w = g_designer ? GetSystemMetrics(SM_CXSCREEN) : 1180;\n"
              "    int hgt = g_designer ? GetSystemMetrics(SM_CYSCREEN) : 820;", 1)

# ③ 标题
t = t.replace('CreateWindowExW(0, wc.lpszClassName, L"Lyra",',
              'CreateWindowExW(0, wc.lpszClassName, g_designer ? L"Lyra \u00b7 UI \u521b\u4f5c" : L"Lyra",', 1)

# ④ 导航到 /designer
if "g_url" in t:
    # 找到给 g_url 赋值的那一行,在赋值后按需改成 /designer
    m = re.search(r"(\s*)(g_url\s*=\s*[^;]+;)", t)
    if m:
        indent, stmt = m.group(1), m.group(2)
        if "g_designer" not in stmt:
            t = t[:m.end()] + indent + 'if (g_designer) g_url += L"designer";' + t[m.end():]
            print("④ 已插入 g_url 改写")

io.open(PC, "w", encoding="utf-8", newline="\n").write(t)

print("\n改动核对:")
for pat in (r"static bool g_designer[^\n]*", r"if \(cmdLine && wcsstr[^\n]*",
            r"int w = g_designer[^\n]*", r"int hgt = g_designer[^\n]*",
            r"CreateWindowExW\(0, wc\.lpszClassName[^\n]*", r"if \(g_designer\) g_url[^\n]*"):
    for m in re.finditer(pat, t):
        print("   ", m.group(0).strip()[:120])

print("\n编译:")
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", os.path.join(SRC, "installer", "build_player.ps1")],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("  ", (r.stdout or "").strip().splitlines()[-1] if r.stdout else r.stderr[:200])
print("   player.exe 存在:", os.path.isfile(os.path.join(SRC, "installer", "player.exe")))
