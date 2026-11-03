# -*- coding: utf-8 -*-
"""产品改名:聆阅 → Lyra(只改"玩家看得见的名字"与 exe 名)。

**故意不改**的(一改就会破坏玩家已经装好的东西):
  · 游戏目录里的 _聆阅_已安装清单.json / _聆阅_注入代理.json / *.bak_聆阅
  · %LOCALAPPDATA%\\LingYueReader\\voices(已下载的语音包在这)
  · 默认安装目录 D:\\聆阅
用法: python docs/_rename_to_lyra.py
"""
import io
import os

ROOT = r"D:\Unity阅读器"

# 文件 → [(旧, 新), ...]  只替换明确的那几处
EDITS = {
    "webapp/server.py": [
        ('"""聆阅 · 本地服务(全新实现)', '"""Lyra · 本地服务(全新实现)'),
        ('APP_TITLE = "聆阅 · Unity 游戏朗读器"', 'APP_TITLE = "Lyra · Unity 游戏朗读器"'),
        ('"安装包里缺少翻译插件文件(重新安装聆阅可修复)"', '"安装包里缺少翻译插件文件(重新安装 Lyra 可修复)"'),
    ],
    "core/__init__.py": [('"""聆阅核心模块。"""', '"""Lyra 核心模块。"""')],
    "config.py": [('"""聆阅 · 配置(全新实现,纯挂钩方案)', '"""Lyra · 配置(全新实现,纯挂钩方案)')],
    "core/games.py": [('_SELF_NAMES = ("聆阅", "gametextreader", "安装程序", "installer")',
                       '_SELF_NAMES = ("lyra", "聆阅", "gametextreader", "安装程序", "installer")')],
    "core/floatwin.py": [('cls, "聆阅 悬浮窗", WS_POPUP,', 'cls, "Lyra 悬浮窗", WS_POPUP,')],
    "webapp/static/index.html": [
        ('<span class="muted sm">让聆阅的窗口始终压在游戏上面</span>',
         '<span class="muted sm">让 Lyra 的窗口始终压在游戏上面</span>'),
        ('聆阅 · Unity 游戏朗读器 —— 只做 Unity 的 LDC', 'Lyra · Unity 游戏朗读器 —— 只做 Unity 的 LDC'),
    ],
    "installer/app.rc": [
        ('VALUE "CompanyName",      "聆阅"', 'VALUE "CompanyName",      "Lyra"'),
        ('VALUE "FileDescription",  "聆阅 安装程序"', 'VALUE "FileDescription",  "Lyra 安装程序"'),
        ('VALUE "OriginalFilename", "聆阅 安装程序.exe"', 'VALUE "OriginalFilename", "Lyra 安装程序.exe"'),
        ('VALUE "ProductName",      "聆阅"', 'VALUE "ProductName",      "Lyra"'),
    ],
    "installer/player.rc": [
        ('VALUE "CompanyName",      "聆阅"', 'VALUE "CompanyName",      "Lyra"'),
        ('VALUE "FileDescription",  "聆阅"', 'VALUE "FileDescription",  "Lyra"'),
        ('VALUE "OriginalFilename", "聆阅.exe"', 'VALUE "OriginalFilename", "Lyra.exe"'),
        ('VALUE "ProductName",      "聆阅"', 'VALUE "ProductName",      "Lyra"'),
    ],
    "installer/uninstall.rc": [
        ('VALUE "CompanyName",      "聆阅"', 'VALUE "CompanyName",      "Lyra"'),
        ('VALUE "FileDescription",  "聆阅 卸载程序"', 'VALUE "FileDescription",  "Lyra 卸载程序"'),
        ('VALUE "OriginalFilename", "卸载 聆阅.exe"', 'VALUE "OriginalFilename", "卸载 Lyra.exe"'),
        ('VALUE "ProductName",      "聆阅"', 'VALUE "ProductName",      "Lyra"'),
    ],
    "installer/setup.c": [
        ('#define APP_TITLE     L"聆阅"', '#define APP_TITLE     L"Lyra"'),
        ('#define APP_EXE_NAME  L"聆阅.exe"', '#define APP_EXE_NAME  L"Lyra.exe"'),
        ('#define UNINSTALL_NAME L"卸载 聆阅.exe"', '#define UNINSTALL_NAME L"卸载 Lyra.exe"'),
        ('#define SETUP_EXE     L"聆阅 安装程序.exe"', '#define SETUP_EXE     L"Lyra 安装程序.exe"'),
        ('wprintf(L"聆阅 安装程序\\n"', 'wprintf(L"Lyra 安装程序\\n"'),
        ('* 聆阅 —— 安装程序 / 启动器(纯 C,Win32 API)', '* Lyra —— 安装程序 / 启动器(纯 C,Win32 API)'),
    ],
    "installer/uninstall.c": [
        ('#define APP_TITLE      L"聆阅"', '#define APP_TITLE      L"Lyra"'),
        ('#define UNINSTALL_NAME L"卸载 聆阅.exe"', '#define UNINSTALL_NAME L"卸载 Lyra.exe"'),
        ('/* 聆阅 卸载器', '/* Lyra 卸载器'),
    ],
    "installer/player.cpp": [
        ('L"如果你是第一次使用,请先运行「聆阅 安装程序.exe」完成安装;\\n"',
         'L"如果你是第一次使用,请先运行「Lyra 安装程序.exe」完成安装;\\n"'),
        ('g_hWnd = CreateWindowExW(0, wc.lpszClassName, L"聆阅",',
         'g_hWnd = CreateWindowExW(0, wc.lpszClassName, L"Lyra",'),
        ('* 聆阅 —— 窗口宿主(原生窗口内嵌网页,基于 WebView2)', '* Lyra —— 窗口宿主(原生窗口内嵌网页,基于 WebView2)'),
    ],
    "installer/build.ps1": [
        ('# 构建「聆阅 安装程序.exe」——单文件、带图标、**离线安装**',
         '# 构建「Lyra 安装程序.exe」——单文件、带图标、**离线安装**'),
        ('[string]$OutName = "聆阅 安装程序.exe",', '[string]$OutName = "Lyra 安装程序.exe",'),
        ('Write-Host "  · 静默安装: `"$OutName`" --install D:\\聆阅"',
         'Write-Host "  · 静默安装: `"$OutName`" --install D:\\Lyra"'),
    ],
}


def main():
    for rel, pairs in EDITS.items():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            print("  缺文件", rel)
            continue
        t = io.open(p, encoding="utf-8").read()
        n = 0
        for old, new in pairs:
            if old in t:
                t = t.replace(old, new)
                n += 1
            else:
                print("    !! %s 里没找到:%s" % (rel, old[:60]))
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        print("  %-28s 替换 %d 处" % (rel, n))


if __name__ == "__main__":
    main()
