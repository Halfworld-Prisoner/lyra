# -*- coding: utf-8 -*-
"""把网页版界面接进安装器/卸载器:
   ① 两个 .rc 加资源:HTML(UTF-8 RCDATA)、WebView2Loader.dll、图标 PNG;
   ② webui.h 加 base64 + data URI 注入(把照片图标塞进网页);
   ③ setup.c / uninstall.c:先建原生控件(默认隐藏)→ 起 WebView2 → 就绪则只留网页,
      2.5 秒没就绪就回退原生界面;进度/状态/完成都推给网页。"""
import io
import os

I = r"D:\Unity阅读器\installer"


def rw(rel, pairs, must=True):
    p = os.path.join(I, rel)
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print("  OK   %-14s %s" % (rel, old.strip().split("\n")[0][:46]))
        elif must:
            print("  !!   %-14s 没找到:%s" % (rel, old.strip().split("\n")[0][:46]))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


# ---------- ① 资源 ----------
rw("app.rc", [
    ("#define IDI_APPICON 101",
     "#define IDI_APPICON 101\n"
     "#define IDR_WEBVIEW2  106\n"
     "#define IDR_UI_HTML   107\n"
     "#define IDR_LOGO_PNG  108"),
    ('IDI_APPICON ICON "icon.ico"',
     'IDI_APPICON ICON "icon.ico"\n'
     'IDR_UI_HTML   RCDATA "ui.html"\n'
     'IDR_LOGO_PNG  RCDATA "icon-preview-256.png"\n'
     'IDR_WEBVIEW2  RCDATA "WebView2Loader.dll"'),
])
rw("uninstall.rc", [
    ("#define IDI_APPICON 101",
     "#define IDI_APPICON 101\n"
     "#define IDR_WEBVIEW2  106\n"
     "#define IDR_UI_HTML   107\n"
     "#define IDR_LOGO_PNG  108"),
    ('IDI_APPICON ICON "icon.ico"',
     'IDI_APPICON ICON "icon.ico"\n'
     'IDR_UI_HTML   RCDATA "ui_uninstall.html"\n'
     'IDR_LOGO_PNG  RCDATA "icon-preview-256.png"\n'
     'IDR_WEBVIEW2  RCDATA "WebView2Loader.dll"'),
], must=False)

# ---------- ② webui.h:base64 + 图标注入 ----------
p = os.path.join(I, "webui.h")
t = io.open(p, encoding="utf-8").read()
if "WebUi_InjectLogo" not in t:
    t = t.replace("#endif /* LYRA_WEBUI_H */", '''
/* ---------------- 把照片图标当 data URI 塞进网页 ---------------- */
/* 网页是 NavigateToString 出来的(about:blank 源),file:// 一律读不到,
   所以图标只能转成 data URI 注入 —— 这样安装器窗口里那枚 logo 才是你要的那张图。 */
static void WebUi_Base64(const unsigned char *in, DWORD n, std::string &out) {
    static const char *T = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    out.clear();
    out.reserve((n + 2) / 3 * 4);
    for (DWORD i = 0; i < n; i += 3) {
        DWORD v = in[i] << 16;
        if (i + 1 < n) v |= in[i + 1] << 8;
        if (i + 2 < n) v |= in[i + 2];
        out += T[(v >> 18) & 63];
        out += T[(v >> 12) & 63];
        out += (i + 1 < n) ? T[(v >> 6) & 63] : '=';
        out += (i + 2 < n) ? T[v & 63] : '=';
    }
}

static void WebUi_InjectLogo(int png_res_id) {
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(png_res_id), RT_RCDATA);
    if (!hr) return;
    DWORD size = SizeofResource(NULL, hr);
    HGLOBAL hg = LoadResource(NULL, hr);
    if (!hg || !size) return;
    const unsigned char *src = (const unsigned char *)LockResource(hg);
    std::string b64;
    WebUi_Base64(src, size, b64);
    std::string js = "window.__lyra&&window.__lyra.src('data:image/png;base64," + b64 + "')";
    int n = MultiByteToWideChar(CP_UTF8, 0, js.c_str(), (int)js.size(), NULL, 0);
    std::wstring w(n, L'\\0');
    MultiByteToWideChar(CP_UTF8, 0, js.c_str(), (int)js.size(), &w[0], n);
    WebUi_Eval(w.c_str());
}

#endif /* LYRA_WEBUI_H */''')
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK   webui.h   已加 base64 / 图标注入")

# ---------- ③ 安装器 ----------
rw("setup.c", [
    (#define IDI_APPICON 101, #include "webui.h"          /* 网页界面宿主(失败自动回退) */
#define IDI_APPICON 101),
    ("static BOOL g_detail = FALSE;",
     "static BOOL g_detail = FALSE;\nstatic BOOL g_web = FALSE;           /* 网页界面是否接管 */"),
    # WM_CREATE 末尾:起网页 + 先藏原生控件 + 兜底定时器
    ("        SetWindowTextW(g_hPath, def);\n        ShowWindow(g_hLog, SW_HIDE);",
     "        SetWindowTextW(g_hPath, def);\n"
     "        ShowWindow(g_hLog, SW_HIDE);\n"
     "        /* ★网页版界面★:原生控件先建好(逻辑还要用),能起 WebView2 就把它们全藏起来 */\n"
     "        if (WebUi_Init(h, IDR_WEBVIEW2, IDR_UI_HTML, WebMsg)) {\n"
     "            g_web = TRUE;\n"
     "            HWND c = GetWindow(h, GW_CHILD);\n"
     "            while (c) { ShowWindow(c, SW_HIDE); c = GetWindow(c, GW_HWNDNEXT); }\n"
     "            SetTimer(h, 2, 2500, NULL);          /* 2.5 秒还没就绪 → 回退原生界面 */\n"
     "        }"),
    # 进度/状态:网页优先
    ("    case WM_APP_PROGRESS:\n        SendMessageW(g_hBar, PBM_SETPOS, wp, 0);\n        return 0;",
     "    case WM_APP_PROGRESS:\n"
     "        if (g_web) {\n"
     "            wchar_t js[48];\n"
     "            _snwprintf(js, 48, L\"window.__lyra&&window.__lyra.progress(%d)\", (int)wp);\n"
     "            WebUi_Eval(js);\n"
     "        } else {\n"
     "            SendMessageW(g_hBar, PBM_SETPOS, wp, 0);\n"
     "        }\n"
     "        return 0;"),
    ("    case WM_APP_LOG: {\n        wchar_t *text = (wchar_t *)lp;\n        if (text) {\n            if (wp == 1) SetWindowTextW(g_hStatus, text);\n            else append_log(text);\n            free(text);\n        }\n        return 0;\n    }",
     "    case WM_APP_LOG: {\n"
     "        wchar_t *text = (wchar_t *)lp;\n"
     "        if (text) {\n"
     "            if (g_web) {\n"
     "                wchar_t js[700];\n"
     "                if (wp == 1) _snwprintf(js, 700, L\"window.__lyra&&window.__lyra.status(%s)\", text);\n"
     "                else _snwprintf(js, 700, L\"window.__lyra&&window.__lyra.detail(%s)\", text);\n"
     "                WebUi_Eval(js);\n"
     "            } else if (wp == 1) {\n"
     "                SetWindowTextW(g_hStatus, text);\n"
     "            } else {\n"
     "                append_log(text);\n"
     "            }\n"
     "            free(text);\n"
     "        }\n"
     "        return 0;\n"
     "    }"),
    # 完成
    ("        if (wp == 1) {\n            SetWindowTextW(g_hInstall, L\"重新安装\");",
     "        if (g_web) {\n"
     "            WebUi_Eval(wp == 1 ? L\"window.__lyra&&window.__lyra.done(1)\"\n"
     "                               : L\"window.__lyra&&window.__lyra.done(0)\");\n"
     "            if (wp == 1 && SendMessageW(g_hRun, BM_GETCHECK, 0, 0) == BST_CHECKED) {\n"
     "                wchar_t dir[MAX_PATH];\n"
     "                GetWindowTextW(g_hPath, dir, MAX_PATH);\n"
     "                launch_app(dir);\n"
     "                PostMessageW(h, WM_CLOSE, 0, 0);\n"
     "            }\n"
     "            return 0;\n"
     "        }\n"
     "        if (wp == 1) {\n            SetWindowTextW(g_hInstall, L\"重新安装\");"),
    # 网页消息 + 定时器/尺寸
    ("    case WM_COMMAND:\n        switch (LOWORD(wp)) {",
     "    case WM_TIMER:\n"
     "        if (wp == 2) {\n"
     "            KillTimer(h, 2);\n"
     "            if (g_web && !WebUi_Ready()) {          /* 渲染层没起来 → 回退原生界面 */\n"
     "                WebUi_Show(FALSE);\n"
     "                HWND c = GetWindow(h, GW_CHILD);\n"
     "                while (c) { ShowWindow(c, SW_SHOW); c = GetWindow(c, GW_HWNDNEXT); }\n"
     "                ShowWindow(g_hLog, g_detail ? SW_SHOW : SW_HIDE);\n"
     "                g_web = FALSE;\n"
     "            }\n"
     "        }\n"
     "        return 0;\n"
     "    case WM_SIZE:\n"
     "        if (g_web) WebUi_Resize(h);\n"
     "        return 0;\n"
     "    case WM_COMMAND:\n        switch (LOWORD(wp)) {"),
])

# 网页消息回调(放在 WndProc 之前)
rw("setup.c", [
    ("static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {",
     '''/* 网页 → 原生:安装/换位置/关窗/改路径 */
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

static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {'''),
])
print("完成(安装器)")
