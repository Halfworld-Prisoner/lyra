# -*- coding: utf-8 -*-
"""给卸载器换上自绘窗口界面(替代原来的系统 MessageBox):
   浅色底 + 微软雅黑 + 顶部图标 + "会删什么/不会删什么"两栏 + 紫色确认按钮 + 状态行。
   quiet 模式(--quiet,给安装程序/脚本调用)仍然不弹窗。"""
import io

p = r"D:\Unity阅读器\installer\uninstall.c"
t = io.open(p, encoding="utf-8").read()

# ---------- 1) 头部:需要的头文件 / 宏 / 全局 ----------
t = t.replace('#define REG_OURS       L"Software\\\\" APP_TITLE',
              '#define REG_OURS       L"Software\\\\" APP_TITLE\n'
              '#define IDI_APPICON    101\n'
              '#define IDC_GO         2001\n'
              '#define IDC_QUIT       2002\n'
              '#define CLR_BG         RGB(246, 247, 251)\n'
              '#define CLR_TEXT       RGB(26, 31, 43)\n'
              '#define CLR_MUTED      RGB(104, 112, 132)\n'
              '\n'
              'static HWND g_hWin, g_hStatus, g_hGo, g_hQuit;\n'
              'static HFONT g_fTitle, g_fBody, g_fSmall;\n'
              'static HBRUSH g_brBg;\n'
              'static wchar_t g_dir[MAX_PATH];\n'
              'static int g_rc = 0;\n'
              'static int g_stage = 0;      /* 0=确认页 1=卸载中 2=完成 */\n'
              'static void make_fonts(void);\n'
              'static void run_uninstall_ui(void);', 1)

# ---------- 2) 窗口实现 ----------
UI = r'''
/* ================================================================ 界面 */
/* 原来的卸载器全是系统 MessageBox(灰底、宋体、一堆技术细节)。这里换成一个
   自己的小窗口:浅色背景 + 微软雅黑 + 图标 + "会删什么 / 不会删什么" 两栏,
   确认按钮自绘成主题紫。quiet 模式(脚本调用)完全不弹窗。 */
static void make_fonts(void) {
    if (g_fBody) return;
    g_fTitle = CreateFontW(-23, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_fBody  = CreateFontW(-14, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_fSmall = CreateFontW(-13, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                           0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
    g_brBg = CreateSolidBrush(CLR_BG);
}

static void ui_status(const wchar_t *s) {
    if (g_hStatus) SetWindowTextW(g_hStatus, s);
}

static void run_uninstall_ui(void) {
    g_stage = 1;
    ui_status(L"正在卸载…");
    EnableWindow(g_hGo, FALSE);
    EnableWindow(g_hQuit, FALSE);
    UpdateWindow(g_hWin);
    g_rc = do_uninstall(g_dir, TRUE);
    g_stage = 2;
    if (g_rc == 0) {
        ui_status(L"卸载完成。你的游戏、存档、以及在游戏里的设置都没有被改动。");
        SetWindowTextW(g_hGo, L"关闭");
    } else {
        ui_status(L"卸载完成,但目录里有文件正被占用 —— 重启电脑后再运行一次本卸载器即可清干净。");
        SetWindowTextW(g_hGo, L"关闭");
    }
    EnableWindow(g_hGo, TRUE);
    EnableWindow(g_hQuit, TRUE);
    InvalidateRect(g_hGo, NULL, TRUE);
}

static LRESULT CALLBACK UnWndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        make_fonts();
        int y = 18;
        HWND ico = CreateWindowW(L"STATIC", NULL, WS_CHILD | WS_VISIBLE | SS_ICON,
                                 18, y, 48, 48, h, NULL, GetModuleHandleW(NULL), NULL);
        SendMessageW(ico, STM_SETICON,
                     (WPARAM)LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(IDI_APPICON)), 0);
        HWND t1 = CreateWindowW(L"STATIC", L"卸载 " APP_TITLE, WS_CHILD | WS_VISIBLE,
                                78, y - 2, 320, 30, h, NULL, GetModuleHandleW(NULL), NULL);
        SendMessageW(t1, WM_SETFONT, (WPARAM)g_fTitle, TRUE);
        HWND t2 = CreateWindowW(L"STATIC", L"只会删掉这个程序本身,不会动你的游戏和数据", WS_CHILD | WS_VISIBLE,
                                80, y + 28, 420, 20, h, NULL, GetModuleHandleW(NULL), NULL);
        SendMessageW(t2, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        y += 68;
        CreateWindowW(L"STATIC", NULL, WS_CHILD | WS_VISIBLE | SS_ETCHEDHORZ,
                      18, y, 500, 1, h, NULL, GetModuleHandleW(NULL), NULL);
        y += 12;

        wchar_t info[900];
        _snwprintf(info, 900,
                   L"会删除:\r\n"
                   L"    •  程序本体:%s\r\n"
                   L"    •  桌面和开始菜单里的快捷方式\r\n"
                   L"    •  这里的设置(声音、角色配音、过滤规则等)\r\n"
                   L"\r\n"
                   L"不会删除:\r\n"
                   L"    •  你的游戏、存档、以及游戏目录里的任何文件\r\n"
                   L"    •  已经装进游戏里的 LDC 插件 —— 想一起清掉的话,\r\n"
                   L"       请在 Lyra 里对每个游戏点一次「卸载 LDC」(游戏要关着)",
                   g_dir);
        HWND box = CreateWindowW(L"STATIC", info, WS_CHILD | WS_VISIBLE | SS_LEFT,
                                 18, y, 500, 150, h, NULL, GetModuleHandleW(NULL), NULL);
        SendMessageW(box, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        y += 158;

        g_hStatus = CreateWindowW(L"STATIC", L"", WS_CHILD | WS_VISIBLE,
                                  18, y, 500, 24, h, NULL, GetModuleHandleW(NULL), NULL);
        SendMessageW(g_hStatus, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        y += 34;

        g_hGo = CreateWindowW(L"BUTTON", L"确认卸载",
                              WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON | BS_OWNERDRAW,
                              300, y, 112, 34, h, (HMENU)IDC_GO, GetModuleHandleW(NULL), NULL);
        SendMessageW(g_hGo, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        g_hQuit = CreateWindowW(L"BUTTON", L"取消", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                420, y, 98, 34, h, (HMENU)IDC_QUIT, GetModuleHandleW(NULL), NULL);
        SendMessageW(g_hQuit, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        return 0;
    }
    case WM_CTLCOLORSTATIC: {
        HDC dc = (HDC)wp;
        SetTextColor(dc, (HWND)lp == g_hStatus ? CLR_MUTED : CLR_TEXT);
        SetBkColor(dc, CLR_BG);
        return (LRESULT)g_brBg;
    }
    case WM_ERASEBKGND: {
        RECT r;
        GetClientRect(h, &r);
        FillRect((HDC)wp, &r, g_brBg);
        return 1;
    }
    case WM_DRAWITEM: {
        DRAWITEMSTRUCT *di = (DRAWITEMSTRUCT *)lp;
        if (di && di->CtlID == IDC_GO) {
            wchar_t text[64];
            GetWindowTextW(di->hwndItem, text, 64);
            BOOL on = IsWindowEnabled(di->hwndItem);
            COLORREF base = g_stage == 0 ? RGB(214, 72, 92) : RGB(124, 92, 255);
            HBRUSH br = CreateSolidBrush(on ? ((di->itemState & ODS_SELECTED)
                       ? RGB(base > 0 ? GetRValue(base) * 8 / 10 : 0,
                             GetGValue(base) * 8 / 10, GetBValue(base) * 8 / 10) : base)
                       : RGB(200, 202, 214));
            HPEN pen = CreatePen(PS_SOLID, 1, on ? base : RGB(200, 202, 214));
            HGDIOBJ ob = SelectObject(di->hDC, br), op = SelectObject(di->hDC, pen);
            RoundRect(di->hDC, di->rcItem.left, di->rcItem.top, di->rcItem.right, di->rcItem.bottom, 18, 18);
            SelectObject(di->hDC, ob); SelectObject(di->hDC, op);
            DeleteObject(br); DeleteObject(pen);
            SetBkMode(di->hDC, TRANSPARENT);
            SetTextColor(di->hDC, RGB(255, 255, 255));
            HGDIOBJ of = SelectObject(di->hDC, g_fBody);
            DrawTextW(di->hDC, text, -1, &di->rcItem, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            SelectObject(di->hDC, of);
            return TRUE;
        }
        break;
    }
    case WM_COMMAND:
        if (LOWORD(wp) == IDC_GO) {
            if (g_stage == 0) run_uninstall_ui();
            else DestroyWindow(h);
            return 0;
        }
        if (LOWORD(wp) == IDC_QUIT) { DestroyWindow(h); return 0; }
        return 0;
    case WM_CLOSE:
        if (g_stage == 1) return 0;                /* 卸载中不让关 */
        DestroyWindow(h);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, msg, wp, lp);
}

/* 返回 0=用户点了确认并已执行,1=用户取消 */
static int show_uninstall_window(const wchar_t *dir) {
    wcsncpy(g_dir, dir, MAX_PATH);
    g_dir[MAX_PATH - 1] = 0;
    WNDCLASSEXW wc;
    ZeroMemory(&wc, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = UnWndProc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.hIcon = LoadIconW(wc.hInstance, MAKEINTRESOURCEW(IDI_APPICON));
    wc.hIconSm = wc.hIcon;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = NULL;
    wc.lpszClassName = L"LyraUninstaller";
    if (!RegisterClassExW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) return 1;
    int w = 556, hgt = 452;
    int x = (GetSystemMetrics(SM_CXSCREEN) - w) / 2;
    int y = (GetSystemMetrics(SM_CYSCREEN) - hgt) / 2;
    g_hWin = CreateWindowExW(0, wc.lpszClassName, L"卸载 " APP_TITLE,
                             WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
                             x, y, w, hgt, NULL, NULL, wc.hInstance, NULL);
    if (!g_hWin) return 1;
    SendMessageW(g_hWin, WM_SETICON, ICON_BIG, (LPARAM)wc.hIcon);
    SendMessageW(g_hWin, WM_SETICON, ICON_SMALL, (LPARAM)wc.hIconSm);
    ShowWindow(g_hWin, SW_SHOW);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return g_stage == 0 ? 1 : 0;                   /* 没进入卸载阶段就是取消 */
}

'''
anchor = 'static int do_uninstall(const wchar_t *dir, BOOL quiet)'
assert anchor in t
t = t.replace(anchor, UI + anchor, 1)

# ---------- 3) 入口:用新窗口替代两个 MessageBox ----------
old_confirm = '''    if (!fromTemp) {
        if (!quiet) {
            wchar_t msg[1024];
            _snwprintf(msg, 1024,
                       L"确定要卸载 %s 吗?\\n\\n"
                       L"会删除:\\n"
                       L"· 程序目录(含配置、便携运行环境):\\n   %s\\n"
                       L"· 桌面与开始菜单快捷方式\\n"
                       L"· 注册表里的卸载项\\n\\n"
                       L"游戏本体和存档不会被删除。",
                       APP_TITLE, dir);
            if (MessageBoxW(NULL, msg, APP_TITLE L" 卸载",
                            MB_ICONQUESTION | MB_YESNO | MB_DEFBUTTON2) != IDYES)
                return 0;
        }'''
new_confirm = '''    if (!fromTemp) {
        if (!quiet) {
            CoInitialize(NULL);
            int r = show_uninstall_window(dir);      /* 自绘窗口:确认 + 进度 + 结果 */
            if (r == 1) return 0;                    /* 用户取消 */
            if (g_rc == 0) {
                wchar_t msg[600];
                _snwprintf(msg, 600,
                           L"%s 已卸载。\\n\\n你的游戏、存档、以及在游戏里的设置都没有被改动。\\n"
                           L"(如果还在玩游戏,已经装进游戏里的 LDC 插件仍然有效;"
                           L"想清掉请在 Lyra 里对每个游戏点「卸载 LDC」。)",
                           APP_TITLE);
                MessageBoxW(NULL, msg, APP_TITLE L" 卸载完成", MB_ICONINFORMATION | MB_OK);
            }
            return g_rc;
        }'''
assert old_confirm in t, "确认框那段没找到"
t = t.replace(old_confirm, new_confirm, 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("uninstall.c 已换上新界面")
