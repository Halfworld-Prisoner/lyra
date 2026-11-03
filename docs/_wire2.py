# -*- coding: utf-8 -*-
"""网页版界面接线(干净版,不经 shell 引号)。

 ① app.rc / uninstall.rc:加 HTML、照片图标 PNG、WebView2Loader 三个资源;
 ② setup.c:include webui.h;WM_CREATE 末尾起 WebView2(原生控件先建好但藏起来);
    WM_TIMER 兜底回退;WM_SIZE 适配;进度/状态/完成推给网页;WebMsg 处理网页命令。
 ③ uninstall.c:同样接上(确认后走"复制到 %TEMP% 再重跑"那条老路)。
"""
import io
import os

I = r"D:\Unity阅读器\installer"


def patch(rel, pairs):
    p = os.path.join(I, rel)
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        tag = old.strip().split("\n")[0][:44]
        if old in t:
            t = t.replace(old, new, 1)
            print("  OK   %-13s %s" % (rel, tag))
        else:
            print("  --   %-13s 未匹配:%s" % (rel, tag))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


RES_DEFS = """#define IDI_APPICON 101
#define IDR_WEBVIEW2  106
#define IDR_UI_HTML   107
#define IDR_LOGO_PNG  108"""

RES_LINES = """IDI_APPICON ICON "icon.ico"
IDR_UI_HTML   RCDATA "ui.html"
IDR_LOGO_PNG  RCDATA "icon-preview-256.png"
IDR_WEBVIEW2  RCDATA "WebView2Loader.dll\""""

RES_LINES_UN = """IDI_APPICON ICON "icon.ico"
IDR_UI_HTML   RCDATA "ui_uninstall.html"
IDR_LOGO_PNG  RCDATA "icon-preview-256.png"
IDR_WEBVIEW2  RCDATA "WebView2Loader.dll\""""

# ---------------- ① 资源 ----------------
patch("app.rc", [("#define IDI_APPICON 101", RES_DEFS),
                 ('IDI_APPICON ICON "icon.ico"', RES_LINES)])
patch("uninstall.rc", [("#define IDI_APPICON 101", RES_DEFS),
                       ('IDI_APPICON ICON "icon.ico"', RES_LINES_UN)])

# ---------------- ② 安装器 ----------------
patch("setup.c", [
    ("#define IDI_APPICON   101",
     '#include "webui.h"        /* 网页界面宿主(失败自动回退到原生界面) */\n#define IDI_APPICON   101'),
    ("static BOOL g_detail = FALSE;",
     "static BOOL g_detail = FALSE;\nstatic BOOL g_web = FALSE;           /* 网页界面是否接管 */"),
    # 网页消息回调(放在 WndProc 之前)
    ("static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {",
     """/* 网页 -> 原生:安装 / 换位置 / 关窗 / 改路径 */
static void WebMsg(const wchar_t *json) {
    if (!json) return;
    if (wcsstr(json, L"\\"ready\\"")) {
        WebUi_InjectLogo(IDR_LOGO_PNG);
        wchar_t dir[MAX_PATH];
        GetWindowTextW(g_hPath, dir, MAX_PATH);
        wchar_t js[MAX_PATH + 60];
        _snwprintf(js, MAX_PATH + 60, L"window.__lyra&&window.__lyra.dir(%s)", dir);
        WebUi_Eval(js);
        if (already_installed(dir))
            WebUi_Eval(L"window.__lyra&&window.__lyra.status('这台电脑上已经装过 Lyra,再点一次就是重新安装(设置不会丢)')");
        return;
    }
    if (wcsstr(json, L"\\"browse\\"")) { PostMessageW(g_hWnd, WM_COMMAND, IDC_BROWSE, 0); return; }
    if (wcsstr(json, L"\\"install\\"")) {
        wchar_t dir[MAX_PATH];
        if (WebUi_Field(json, L"dir", dir, MAX_PATH)) SetWindowTextW(g_hPath, dir);
        PostMessageW(g_hWnd, WM_COMMAND, IDC_INSTALL, 0);
        return;
    }
    if (wcsstr(json, L"\\"close\\"")) { PostMessageW(g_hWnd, WM_CLOSE, 0, 0); return; }
    if (wcsstr(json, L"\\"path\\"")) {
        wchar_t dir[MAX_PATH];
        if (WebUi_Field(json, L"dir", dir, MAX_PATH)) SetWindowTextW(g_hPath, dir);
    }
}

static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {"""),
    # 起 WebView2
    ("        SetWindowTextW(g_hPath, def);\n        ShowWindow(g_hLog, SW_HIDE);",
     """        SetWindowTextW(g_hPath, def);
        ShowWindow(g_hLog, SW_HIDE);                     /* 技术细节默认收起 */
        /* ★网页界面★:原生控件先建好(安装逻辑还在用它们),能起 WebView2 就全部藏起来 */
        if (WebUi_Init(h, IDR_WEBVIEW2, IDR_UI_HTML, WebMsg)) {
            g_web = TRUE;
            HWND c = GetWindow(h, GW_CHILD);
            while (c) { ShowWindow(c, SW_HIDE); c = GetWindow(c, GW_HWNDNEXT); }
            SetTimer(h, 2, 2500, NULL);                  /* 2.5 秒没就绪 -> 回退原生界面 */
        }"""),
    # 进度
    ("    case WM_APP_PROGRESS:\n        SendMessageW(g_hBar, PBM_SETPOS, wp, 0);\n        return 0;",
     """    case WM_APP_PROGRESS:
        if (g_web) {
            wchar_t js[56];
            _snwprintf(js, 56, L"window.__lyra&&window.__lyra.progress(%d)", (int)wp);
            WebUi_Eval(js);
        } else {
            SendMessageW(g_hBar, PBM_SETPOS, wp, 0);
        }
        return 0;"""),
    # 状态/详情
    ("            if (wp == 1) SetWindowTextW(g_hStatus, text);\n            else append_log(text);\n            free(text);",
     """            if (g_web) {
                wchar_t js[700];
                if (wp == 1) _snwprintf(js, 700, L"window.__lyra&&window.__lyra.status(%s)", text);
                else _snwprintf(js, 700, L"window.__lyra&&window.__lyra.detail(%s)", text);
                WebUi_Eval(js);
            } else if (wp == 1) {
                SetWindowTextW(g_hStatus, text);
            } else {
                append_log(text);
            }
            free(text);"""),
    # 完成
    ("        if (wp == 1) {\n            SetWindowTextW(g_hInstall, L\"重新安装\");",
     """        if (g_web) {
            WebUi_Eval(wp == 1 ? L"window.__lyra&&window.__lyra.done(1)"
                               : L"window.__lyra&&window.__lyra.done(0)");
            if (wp == 1 && SendMessageW(g_hRun, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                wchar_t dir[MAX_PATH];
                GetWindowTextW(g_hPath, dir, MAX_PATH);
                launch_app(dir);
                PostMessageW(h, WM_CLOSE, 0, 0);
            }
            return 0;
        }
        if (wp == 1) {
            SetWindowTextW(g_hInstall, L"重新安装");"""),
    # 定时器回退 + 尺寸
    ("    case WM_COMMAND:\n        switch (LOWORD(wp)) {",
     """    case WM_TIMER:
        if (wp == 2) {
            KillTimer(h, 2);
            if (g_web && !WebUi_Ready()) {               /* 渲染层起不来 -> 回退原生界面 */
                WebUi_Show(FALSE);
                HWND c = GetWindow(h, GW_CHILD);
                while (c) { ShowWindow(c, SW_SHOW); c = GetWindow(c, GW_HWNDNEXT); }
                ShowWindow(g_hLog, g_detail ? SW_SHOW : SW_HIDE);
                g_web = FALSE;
            }
        }
        return 0;
    case WM_SIZE:
        if (g_web) WebUi_Resize(h);
        return 0;
    case WM_COMMAND:
        switch (LOWORD(wp)) {"""),
])
print("安装器接线完成")
