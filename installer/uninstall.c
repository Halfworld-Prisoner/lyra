/* Lyra 卸载器
 *
 * 双击运行 → 确认 → 结束进程 → 删快捷方式 → 删注册表 → 删全部文件 → 自删。
 *
 * 关键点:卸载器自己就在要被删掉的目录里,Windows 不允许删除正在运行的程序,
 * 所以第一件事是把自己复制到 %TEMP% 再从那里重新启动去做清理,
 * 原来那份随即退出(退出后就能被删掉了)。
 *
 * 编译:gcc uninstall.c res.o -o uninstall.exe -O2 -municode -mwindows -static-libgcc
 *       -lcomctl32 -lole32 -loleaut32 -luuid -lshell32 -lshlwapi -ladvapi32
 */
#define _WIN32_WINNT 0x0601          /* 需要 QueryFullProcessImageNameW / RegDeleteTreeW */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <shlobj.h>
#include <tlhelp32.h>
#include <stdio.h>

#define APP_TITLE      L"Lyra"
#define UNINSTALL_NAME L"卸载 Lyra.exe"
#define REG_UNINSTALL  L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" APP_TITLE
#define REG_OURS       L"Software\\" APP_TITLE
#include "webui.h"        /* 网页界面宿主(失败自动回退到原生界面) */
#define IDI_APPICON    101
#define IDR_WEBVIEW2   106
#define IDR_UI_HTML    107
#define IDR_LOGO_PNG   108
#define IDC_GO         2001
#define IDC_QUIT       2002
#define CLR_BG         RGB(246, 247, 251)
#define CLR_TEXT       RGB(26, 31, 43)
#define CLR_MUTED      RGB(104, 112, 132)

static HWND g_hWin, g_hStatus, g_hGo, g_hQuit;
static HFONT g_fTitle, g_fBody, g_fSmall;
static HBRUSH g_brBg;
static wchar_t g_dir[MAX_PATH];
static int g_rc = 0;
static int g_stage = 0;
static BOOL g_web = FALSE;      /* 网页界面是否接管 */      /* 0=确认页 1=卸载中 2=完成 */
static void make_fonts(void);
static void run_uninstall_ui(void);
static int do_uninstall(const wchar_t *dir, BOOL quiet);   /* 界面里要调它 */

static void join(wchar_t *out, const wchar_t *a, const wchar_t *b)
{
    _snwprintf(out, MAX_PATH, L"%s\\%s", a, b);
}

static BOOL is_dir(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static BOOL is_file(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static long long dir_size(const wchar_t *dir)
{
    long long total = 0;
    wchar_t pat[MAX_PATH];
    WIN32_FIND_DATAW fd;
    join(pat, dir, L"*");
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    do {
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        wchar_t full[MAX_PATH];
        join(full, dir, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) total += dir_size(full);
        else total += ((long long)fd.nFileSizeHigh << 32) | fd.nFileSizeLow;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return total;
}

/* 只结束"从这个安装目录启动的"进程,不动别的程序 */
static int kill_ours(const wchar_t *dir)
{
    int killed = 0;
    size_t n = wcslen(dir);
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;
    PROCESSENTRY32W pe;
    pe.dwSize = sizeof(pe);
    if (Process32FirstW(snap, &pe)) {
        do {
            HANDLE hp = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE,
                                    FALSE, pe.th32ProcessID);
            if (!hp) continue;
            wchar_t path[1024];
            DWORD cap = 1024;
            if (QueryFullProcessImageNameW(hp, 0, path, &cap)) {
                if (_wcsnicmp(path, dir, n) == 0) {
                    if (TerminateProcess(hp, 0)) killed++;
                }
            }
            CloseHandle(hp);
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return killed;
}

static BOOL delete_tree(const wchar_t *dir)
{
    wchar_t pat[MAX_PATH];
    WIN32_FIND_DATAW fd;
    join(pat, dir, L"*");
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
            wchar_t full[MAX_PATH];
            join(full, dir, fd.cFileName);
            SetFileAttributesW(full, FILE_ATTRIBUTE_NORMAL);
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                delete_tree(full);
                RemoveDirectoryW(full);
            } else {
                if (!DeleteFileW(full)) {
                    Sleep(120);                       /* 刚退出的进程可能还没释放文件 */
                    SetFileAttributesW(full, FILE_ATTRIBUTE_NORMAL);
                    DeleteFileW(full);
                }
            }
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    return RemoveDirectoryW(dir);
}

static void delete_shortcut(int csidl, const wchar_t *folder)
{
    wchar_t dir[MAX_PATH], lnk[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, csidl, NULL, 0, dir))) {
        _snwprintf(lnk, MAX_PATH, L"%s\\%s.lnk", dir, APP_TITLE);
        DeleteFileW(lnk);
    }
    if (folder) {
        _snwprintf(lnk, MAX_PATH, L"%s\\%s.lnk", folder, APP_TITLE);
        DeleteFileW(lnk);
    }
}

static void delete_start_menu(void)
{
    wchar_t dir[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PROGRAMS, NULL, 0, dir))) {
        wchar_t lnk[MAX_PATH];
        _snwprintf(lnk, MAX_PATH, L"%s\\%s.lnk", dir, APP_TITLE);
        DeleteFileW(lnk);
        _snwprintf(lnk, MAX_PATH, L"%s\\%s", dir, APP_TITLE);
        RemoveDirectoryW(lnk);
    }
}

static void delete_registry(void)
{
    RegDeleteTreeW(HKEY_CURRENT_USER, REG_UNINSTALL);
    RegDeleteTreeW(HKEY_CURRENT_USER, REG_OURS);
    /* 保险:万一曾经被加进开机启动 */
    HKEY k;
    if (RegOpenKeyExW(HKEY_CURRENT_USER,
                      L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                      0, KEY_SET_VALUE, &k) == ERROR_SUCCESS) {
        RegDeleteValueW(k, APP_TITLE);
        RegDeleteValueW(k, L"LingYueReader");
        RegCloseKey(k);
    }
}

/* ---------------- 主流程 ---------------- */


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
    /* ★这里不能就地删★:卸载器要删掉它自己所在的目录,必须先复制到 %TEMP% 再重跑一份。
       所以窗口只负责"确认",确认完就关掉,真正干活的是外层那条 --run 路径。 */
    g_stage = 1;
    if (g_web) {
        WebUi_Eval(L"window.__lyra&&window.__lyra.status('正在卸载…')");
        WebUi_Eval(L"window.__lyra&&window.__lyra.progress(40)");
    } else {
        ui_status(L"正在卸载…");
    }
    UpdateWindow(g_hWin);
    DestroyWindow(g_hWin);
}

/* 网页 -> 原生:确认卸载 / 取消 */
static void UnWebMsg(const wchar_t *json) {
    if (!json) return;
    if (wcsstr(json, L"\"ready\"")) {
        WebUi_InjectLogo(IDR_LOGO_PNG);
        WebUi_EvalStr(L"dir", g_dir);
        return;
    }
    if (wcsstr(json, L"\"uninstall\"")) { PostMessageW(g_hWin, WM_COMMAND, IDC_GO, 0); return; }
    if (wcsstr(json, L"\"close\"")) { PostMessageW(g_hWin, WM_CLOSE, 0, 0); }
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
        /* ★网页界面★:原生控件先建好(逻辑还要用),能起 WebView2 就全藏起来 */
        if (WebUi_Init(h, IDR_WEBVIEW2, IDR_UI_HTML, UnWebMsg)) {
            g_web = TRUE;
            HWND c = GetWindow(h, GW_CHILD);
            while (c) { ShowWindow(c, SW_HIDE); c = GetWindow(c, GW_HWNDNEXT); }
            SetTimer(h, 2, 2500, NULL);          /* 2.5 秒没就绪 -> 回退原生界面 */
        }
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
    case WM_TIMER:
        if (wp == 2) {
            KillTimer(h, 2);
            if (g_web && !WebUi_Ready()) {
                WebUi_Show(FALSE);
                HWND c = GetWindow(h, GW_CHILD);
                while (c) { ShowWindow(c, SW_SHOW); c = GetWindow(c, GW_HWNDNEXT); }
                g_web = FALSE;
            }
        }
        return 0;
    case WM_SIZE:
        if (g_web) WebUi_Resize(h);
        return 0;
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
    int w = 680, hgt = 560;   /* 要装得下网页 */
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

static int do_uninstall(const wchar_t *dir, BOOL quiet)
{
    int killed, failed = 0;
    /* ★安全闸★:只肯删"看起来确实是 Lyra 安装目录"的文件夹 ——
       玩家可能把程序装在 U 盘 / C 盘 / 别的盘的任意目录,也可能手滑传错 --dir。
       判定:目录里同时有 app\webapp\server.py 或 runtime\ 或 Lyra.exe 中的任意两个。 */
    {
        wchar_t probe[MAX_PATH];
        int marks = 0;
        join(probe, dir, L"app\\webapp\\server.py");
        if (is_file(probe)) marks++;
        join(probe, dir, L"runtime");
        if (is_dir(probe)) marks++;
        join(probe, dir, L"Lyra.exe");
        if (is_file(probe)) marks++;
        join(probe, dir, L"聆阅.exe");
        if (is_file(probe)) marks++;
        if (marks < 2) {
            if (!quiet) MessageBoxW(NULL,
                L"这个目录看不出是 Lyra 的安装目录,为了安全没有删除它。\n"
                L"请从开始菜单或控制面板里的「卸载 Lyra」运行。",
                APP_TITLE L" 卸载", MB_ICONINFORMATION | MB_OK);
            return 1;
        }
    }
    long long bytes = dir_size(dir);

    killed = kill_ours(dir);
    Sleep(killed ? 900 : 100);            /* 给进程一点退出时间,释放文件句柄 */

    delete_shortcut(CSIDL_DESKTOPDIRECTORY, NULL);
    delete_shortcut(CSIDL_COMMON_DESKTOPDIRECTORY, NULL);
    delete_start_menu();
    delete_registry();

    for (int i = 0; i < 4; i++) {         /* 文件被占用时多试几次 */
        if (!is_dir(dir)) break;
        if (delete_tree(dir)) break;
        failed = 1;
        Sleep(400);
    }
    failed = is_dir(dir);

    if (!quiet) {
        wchar_t msg[1024];
        if (failed) {
            _snwprintf(msg, 1024,
                       L"%s 已卸载,但目录里还有文件没删掉(可能被占用):\n%s\n\n"
                       L"注销或重启后再运行一次本卸载器即可清干净。",
                       APP_TITLE, dir);
            MessageBoxW(NULL, msg, APP_TITLE L" 卸载", MB_ICONWARNING | MB_OK);
        } else {
            _snwprintf(msg, 1024,
                       L"%s 已完全卸载。\n\n"
                       L"· 结束了 %d 个正在运行的进程\n"
                       L"· 删除了安装目录(约 %.1f MB)\n"
                       L"· 删除了桌面/开始菜单快捷方式\n"
                       L"· 删除了注册表项\n\n"
                       L"配置文件 config.json 也已一并删除。",
                       APP_TITLE, killed, (double)bytes / 1048576.0);
            MessageBoxW(NULL, msg, APP_TITLE L" 卸载", MB_ICONINFORMATION | MB_OK);
        }
    }
    return failed ? 1 : 0;
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int nCmdShow)
{
    (void)hInst; (void)hPrev; (void)nCmdShow;
    wchar_t self[MAX_PATH], dir[MAX_PATH] = {0}, tempDir[MAX_PATH], tempExe[MAX_PATH];
    BOOL quiet = FALSE, fromTemp = FALSE, confirmed = FALSE;

    GetModuleFileNameW(NULL, self, MAX_PATH);
    if (cmdLine) {
        if (wcsstr(cmdLine, L"--quiet")) quiet = TRUE;
        if (wcsstr(cmdLine, L"--run")) fromTemp = TRUE;
        wchar_t *p = wcsstr(cmdLine, L"--dir ");
        if (p) {
            p += 6;
            while (*p == L'"' || *p == L' ') p++;
            int i = 0;
            while (*p && *p != L'"' && i < MAX_PATH - 1) dir[i++] = *p++;
            dir[i] = 0;
        }
    }

    if (!dir[0]) {
        /* 默认:安装目录 = 本程序所在目录(卸载器就装在安装根目录) */
        wcsncpy(dir, self, MAX_PATH);
        wchar_t *slash = wcsrchr(dir, L'\\');
        if (slash) *slash = 0;
    }

    if (!fromTemp) {
        if (!quiet) {
            CoInitialize(NULL);
            int r = show_uninstall_window(dir);      /* 自绘窗口:确认 + 进度 + 结果 */
            if (r == 1) return 0;                    /* 用户取消 */
            /* ★关键★:不能在这里 return!
               卸载器要删掉自己所在的目录,必须先复制到 %TEMP% 再重跑一次
               (--run),否则正在运行的这个 exe 删不掉,玩家看着就是"点了确认没反应"。
               已经确认过了,所以给临时实例加 --quiet,不再弹第二个窗。 */
            quiet = TRUE;          /* 已确认:临时那份不要再问一遍 */
            confirmed = TRUE;
        }
        /* 复制自己到 %TEMP% 再从那里清理,这样才能删掉本文件所在的目录 */
        if (!GetTempPathW(MAX_PATH, tempDir)) return 1;
        _snwprintf(tempExe, MAX_PATH, L"%sgtreader_uninstall_tmp.exe", tempDir);
        DeleteFileW(tempExe);
        if (!CopyFileW(self, tempExe, FALSE)) {
            /* 复制失败就原地清理(自己这份删不掉,提示重启后重试) */
            return do_uninstall(dir, quiet);
        }
        wchar_t args[2048];
        _snwprintf(args, 2048, L"\"%s\" --run %s--dir \"%s\"",
                   tempExe, quiet ? L"--quiet " : L"", dir);
        STARTUPINFOW si;
        PROCESS_INFORMATION pi;
        ZeroMemory(&si, sizeof(si));
        si.cb = sizeof(si);
        ZeroMemory(&pi, sizeof(pi));
        if (CreateProcessW(NULL, args, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            /* 等临时那份干完,再按"目录还在不在"给玩家一句人话 */
            WaitForSingleObject(pi.hProcess, 60000);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            /* ★不再另开结果弹窗★(玩家反馈"卸载完又弹一个新窗口")。
               卸载成不成功,玩家自己看目录在不在就知道;真要留痕就写进日志。 */
            if (confirmed && is_dir(dir)) {
                wchar_t note[MAX_PATH + 200];
                _snwprintf(note, MAX_PATH + 200,
                           L"卸载未完全成功(有文件被占用):%s\r\n"
                           L"关掉 Lyra 窗口或重启电脑后再运行一次本卸载器即可清干净。\r\n",
                           dir);
                wchar_t logp[MAX_PATH];
                _snwprintf(logp, MAX_PATH, L"%s\\lyra_uninstall.log", tempDir);
                FILE *f = _wfopen(logp, L"a, ccs=UTF-8");
                if (f) { fwprintf(f, L"%s", note); fclose(f); }
            }
            return 0;                       /* 退出后临时那份才能删掉整个目录 */
        }
        return do_uninstall(dir, quiet);
    }

    /* 从 %TEMP% 运行的这一份:真正干活 */
    int rc = do_uninstall(dir, quiet);
    /* 自删:先直接删(运行中会失败)→ 起一个隐藏的 cmd 等本进程退出后删除
       → 再兜底登记到"重启后删除" */
    if (!DeleteFileW(self)) {
        wchar_t cmd[2048];
        _snwprintf(cmd, 2048,
                   L"/c ping -n 3 127.0.0.1 >nul & del /f /q \"%s\"", self);
        STARTUPINFOW si;
        PROCESS_INFORMATION pi;
        ZeroMemory(&si, sizeof(si));
        si.cb = sizeof(si);
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
        ZeroMemory(&pi, sizeof(pi));
        wchar_t full[2200];
        _snwprintf(full, 2200, L"cmd.exe %s", cmd);
        if (CreateProcessW(NULL, full, NULL, NULL, FALSE, CREATE_NO_WINDOW,
                           NULL, NULL, &si, &pi)) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
        } else {
            MoveFileExW(self, NULL, MOVEFILE_DELAY_UNTIL_REBOOT);
        }
    }
    return rc;
}
