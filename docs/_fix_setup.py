# -*- coding: utf-8 -*-
"""补齐 setup.c 新界面需要的宏/全局/字体与辅助函数,并修正一处括号笔误。"""
import io

p = r"D:\Unity阅读器\installer\setup.c"
t = io.open(p, encoding="utf-8").read()

# ① 修掉我写歪的那段按钮创建(保留 BS_OWNERDRAW 的单个创建)
bad = '''        g_hInstall = CreateWindowW(L"BUTTON", L"开始安装",
                                   WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON | BS_OWNERDRAW,
                                   318, y - 4, 112, 34, h, (HMENU)IDC_INSTALL), g_hInst, NULL);
        if (!g_hInstall) g_hInstall = CreateWindowW(L"BUTTON", L"开始安装",
                                   WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON | BS_OWNERDRAW,
                                   318, y - 4, 112, 34, h, (HMENU)IDC_INSTALL, g_hInst, NULL);
        SendMessageW(g_hInstall, WM_SETFONT, (WPARAM)g_fBody, TRUE);'''
good = '''        g_hInstall = CreateWindowW(L"BUTTON", L"开始安装",
                                   WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON | BS_OWNERDRAW,
                                   318, y - 4, 112, 34, h, (HMENU)IDC_INSTALL, g_hInst, NULL);
        SendMessageW(g_hInstall, WM_SETFONT, (WPARAM)g_fBody, TRUE);'''
assert bad in t, "按钮那段没找到"
t = t.replace(bad, good, 1)

# ② 宏:版本号 + 详情按钮 id
t = t.replace('#define IDC_RUN       1007',
              '#define IDC_RUN       1007\n#define IDC_DETAIL    1008', 1)
t = t.replace('#define SETUP_EXE     L"Lyra 安装程序.exe"',
              '#define SETUP_EXE     L"Lyra 安装程序.exe"\n'
              '#define APP_VERSION   L"1.0"          /* 界面右上角显示的版本 */', 1)

# ③ 全局:字体 / 颜色 / 新控件
t = t.replace('static HWND g_hStatus;',
              'static HWND g_hStatus;\n'
              'static HWND g_hInfo, g_hDetail;\n'
              'static BOOL g_detail = FALSE;          /* 「显示详情」是否展开 */\n'
              'static HFONT g_fTitle, g_fBody, g_fSmall, g_fBold;\n'
              'static HBRUSH g_brBg;\n'
              '#define CLR_BG     RGB(246, 247, 251)\n'
              '#define CLR_TEXT   RGB(26, 31, 43)\n'
              '#define CLR_MUTED  RGB(104, 112, 132)', 1)

# ④ 辅助函数:字体、负载总大小
HELPERS = '''
/* ---------------------------------------------------------------- 界面辅助 */
/* 字体:标题用 17pt 粗、正文 10pt、小字 9pt(微软雅黑,中文才好看)。
   全部一次性建好,窗口销毁时不必回收(进程随即退出)。 */
static void make_fonts(void) {
    if (g_fBody) return;
    g_fTitle = CreateFontW(-23, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_fBody  = CreateFontW(-14, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_fBold  = CreateFontW(-14, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_fSmall = CreateFontW(-13, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_brBg = CreateSolidBrush(CLR_BG);
}

/* 安装包里的负载总字节数(给玩家看的"大约占多少空间") */
static double payload_total_mb(void) {
    double total = 0;
    int ids[4] = { IDR_PAYLOAD, IDR_RUNTIME, IDR_PLAYER, IDR_UNINSTALL };
    for (int i = 0; i < 4; i++) {
        HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(ids[i]), RT_RCDATA);
        if (hr) total += (double)SizeofResource(NULL, hr);
    }
    return total / 1048576.0;
}

'''
anchor = '/* ---------------------------------------------------------------- 入口 */'
assert anchor in t
t = t.replace(anchor, HELPERS + anchor, 1)

# ⑤ 窗口放大一点(内容变多了)
t = t.replace('int w = 566, hgt = 470;', 'int w = 586, hgt = 520;', 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("setup.c 已补:宏/全局/字体/负载大小/窗口尺寸")
