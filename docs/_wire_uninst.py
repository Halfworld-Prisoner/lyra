# -*- coding: utf-8 -*-
"""给卸载器接上网页界面,并把 build.ps1 里两个 C 文件的编译改成 g++(C++)。"""
import io
import os

I = r"D:\Unity阅读器\installer"


def patch(f, pairs):
    p = os.path.join(I, f)
    t = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        if a in t:
            t = t.replace(a, b, 1)
            print("  OK   %-12s %s" % (f, a.strip().split("\n")[0][:50]))
        else:
            print("  --   %-12s 未匹配 %s" % (f, a.strip().split("\n")[0][:50]))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


# ---------------- 卸载器 ----------------
patch("uninstall.c", [
    ("#define IDI_APPICON    101",
     '#include "webui.h"        /* 网页界面宿主(失败自动回退到原生界面) */\n'
     '#define IDI_APPICON    101\n'
     '#define IDR_WEBVIEW2   106\n'
     '#define IDR_UI_HTML    107\n'
     '#define IDR_LOGO_PNG   108'),
    ("static int g_stage = 0;",
     "static int g_stage = 0;\nstatic BOOL g_web = FALSE;      /* 网页界面是否接管 */"),
    # 网页消息回调
    ("static LRESULT CALLBACK UnWndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {",
     '''/* 网页 -> 原生:确认卸载 / 取消 */
static void UnWebMsg(const wchar_t *json) {
    if (!json) return;
    if (wcsstr(json, L"\\"ready\\"")) {
        WebUi_InjectLogo(IDR_LOGO_PNG);
        wchar_t js[MAX_PATH + 60];
        _snwprintf(js, MAX_PATH + 60, L"window.__lyra&&window.__lyra.dir(%s)", g_dir);
        WebUi_Eval(js);
        return;
    }
    if (wcsstr(json, L"\\"uninstall\\"")) { PostMessageW(g_hWin, WM_COMMAND, IDC_GO, 0); return; }
    if (wcsstr(json, L"\\"close\\"")) { PostMessageW(g_hWin, WM_CLOSE, 0, 0); }
}

static LRESULT CALLBACK UnWndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {'''),
    # WM_CREATE 末尾:起网页
    ("        SendMessageW(g_hQuit, WM_SETFONT, (WPARAM)g_fBody, TRUE);\n        return 0;",
     """        SendMessageW(g_hQuit, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        /* ★网页界面★:原生控件先建好(逻辑还要用),能起 WebView2 就全藏起来 */
        if (WebUi_Init(h, IDR_WEBVIEW2, IDR_UI_HTML, UnWebMsg)) {
            g_web = TRUE;
            HWND c = GetWindow(h, GW_CHILD);
            while (c) { ShowWindow(c, SW_HIDE); c = GetWindow(c, GW_HWNDNEXT); }
            SetTimer(h, 2, 2500, NULL);          /* 2.5 秒没就绪 -> 回退原生界面 */
        }
        return 0;"""),
    # 定时器回退 + 尺寸 + 网页按钮文案
    ("    case WM_COMMAND:\n        if (LOWORD(wp) == IDC_GO) {",
     """    case WM_TIMER:
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
        if (LOWORD(wp) == IDC_GO) {"""),
    # 确认后:网页里显示"正在卸载",然后关窗交给外层
    ("    g_stage = 1;\n    ui_status(L\"正在卸载…\");\n    UpdateWindow(g_hWin);\n    DestroyWindow(g_hWin);",
     """    g_stage = 1;
    if (g_web) {
        WebUi_Eval(L"window.__lyra&&window.__lyra.status('正在卸载…')");
        WebUi_Eval(L"window.__lyra&&window.__lyra.progress(40)");
    } else {
        ui_status(L"正在卸载…");
    }
    UpdateWindow(g_hWin);
    DestroyWindow(g_hWin);"""),
])

# ---------------- build.ps1:两个 C 文件改 g++ ----------------
p = os.path.join(I, "build.ps1")
t = io.open(p, encoding="utf-8").read()
old_un = '& gcc (Join-Path $inst "uninstall.c") $unRes -o (Join-Path $inst "uninstall.exe") `\n    -O2 -municode -mwindows -static-libgcc -s `'
new_un = ('& g++ (Join-Path $inst "uninstall.c") $unRes -o (Join-Path $inst "uninstall.exe") `\n'
          '    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `\n'
          '    -I (Join-Path $inst "compat") -I $wvInc `')
if old_un in t:
    t = t.replace(old_un, new_un, 1)
    print("  OK   build.ps1 卸载器 -> g++")
else:
    print("  --   build.ps1 卸载器那行没匹配")
old_se = '& gcc (Join-Path $inst "setup.c") $res -o $tmpExe `\n    -O2 -municode -mwindows -static-libgcc `'
new_se = ('& g++ (Join-Path $inst "setup.c") $res -o $tmpExe `\n'
          '    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `\n'
          '    -I (Join-Path $inst "compat") -I $wvInc `')
if old_se in t:
    t = t.replace(old_se, new_se, 1)
    print("  OK   build.ps1 安装器 -> g++")
else:
    print("  --   build.ps1 安装器那行没匹配")
# 补一个 $wvInc 变量(WebView2 SDK 头文件目录),没有就插在 $inst 定义之后
if "$wvInc" in t and "wvInc =" not in t:
    t = t.replace('$inst = ', '$wvInc = Join-Path $inst "build\\webview2\\build\\native\\include"\n$inst = ', 1)
    print("  OK   build.ps1 已加 $wvInc")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("完成")
