/* webui.h —— 安装器/卸载器共用的"网页界面"宿主(和主程序 player.exe 同一套做法)
 *
 *   · 主程序窗口就是 WebView2 + HTML/CSS,安装器/卸载器也用它,三处观感才一致;
 *   · **必须能回退**:WebUi_Init 返回 FALSE(没有 WebView2 运行时 / 初始化失败)时,
 *     调用方继续用原来那套 Win32 自绘界面,功能完全不受影响 ——
 *     装东西的工具不能因为渲染层罢工就装不上;
 *   · 原生 → 网页:WebUi_Eval(L"__lyra.progress(45)");
 *     网页 → 原生:window.chrome.webview.postMessage({cmd:"install"}),经 on_msg 回调;
 *   · HTML 与 WebView2Loader.dll 都从**资源**里取(安装器还没装好,不能指望系统里有)。
 *
 * 用法:
 *     if (WebUi_Init(hwnd, IDR_WEBVIEW2, IDR_UI_HTML, OnWebMsg)) { ...只跑网页... }
 *     else { ...原来的 CreateWindow 那一套... }
 *
 * header-only:直接 #include,不要单独编译。
 */
#ifndef LYRA_WEBUI_H
#define LYRA_WEBUI_H

#include <windows.h>
#include <objbase.h>
#include <string>
#include "WebView2.h"

static ICoreWebView2Controller *g_wu_ctl = NULL;
static ICoreWebView2 *g_wu_view = NULL;
static void (*g_wu_msg)(const wchar_t *) = NULL;
static volatile LONG g_wu_ready = 0;
static std::wstring g_wu_html;
static HWND g_wu_hwnd = NULL;

/* ---------------- 网页 → 原生 ---------------- */
class LyraWebMsgHandler : public ICoreWebView2WebMessageReceivedEventHandler {
public:
    STDMETHODIMP QueryInterface(REFIID riid, void **ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2WebMessageReceivedEventHandler) {
            *ppv = static_cast<ICoreWebView2WebMessageReceivedEventHandler *>(this);
            AddRef();
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_ref); }
    STDMETHODIMP_(ULONG) Release() override {
        ULONG n = InterlockedDecrement(&m_ref);
        if (n == 0) delete this;
        return n;
    }
    STDMETHODIMP Invoke(ICoreWebView2 *, ICoreWebView2WebMessageReceivedEventArgs *args) override {
        LPWSTR json = NULL;
        if (!args || FAILED(args->TryGetWebMessageAsString(&json)) || !json) return S_OK;
        if (g_wu_msg) g_wu_msg(json);
        CoTaskMemFree(json);
        return S_OK;
    }
private:
    LONG m_ref = 1;
};

/* ---------------- 控制器就绪:设置尺寸 + 收消息 + 灌 HTML ---------------- */
class LyraWebCtlHandler : public ICoreWebView2CreateCoreWebView2ControllerCompletedHandler {
public:
    STDMETHODIMP QueryInterface(REFIID riid, void **ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2CreateCoreWebView2ControllerCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler *>(this);
            AddRef();
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_ref); }
    STDMETHODIMP_(ULONG) Release() override {
        ULONG n = InterlockedDecrement(&m_ref);
        if (n == 0) delete this;
        return n;
    }
    STDMETHODIMP Invoke(HRESULT err, ICoreWebView2Controller *ctl) override {
        if (FAILED(err) || !ctl) return S_OK;
        g_wu_ctl = ctl;
        g_wu_ctl->AddRef();
        if (FAILED(ctl->get_CoreWebView2(&g_wu_view)) || !g_wu_view) return S_OK;
        g_wu_view->AddRef();
        RECT rc;
        GetClientRect(g_wu_hwnd, &rc);
        g_wu_ctl->put_Bounds(rc);
        EventRegistrationToken tok;
        g_wu_view->add_WebMessageReceived(new LyraWebMsgHandler(), &tok);
        g_wu_view->NavigateToString(g_wu_html.c_str());
        InterlockedExchange(&g_wu_ready, 1);
        if (g_wu_msg) g_wu_msg(L"{\"cmd\":\"ready\"}");
        return S_OK;
    }
private:
    LONG m_ref = 1;
};

class LyraWebEnvHandler : public ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler {
public:
    STDMETHODIMP QueryInterface(REFIID riid, void **ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler *>(this);
            AddRef();
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_ref); }
    STDMETHODIMP_(ULONG) Release() override {
        ULONG n = InterlockedDecrement(&m_ref);
        if (n == 0) delete this;
        return n;
    }
    STDMETHODIMP Invoke(HRESULT err, ICoreWebView2Environment *env) override {
        if (FAILED(err) || !env) return S_OK;
        return env->CreateCoreWebView2Controller(g_wu_hwnd, new LyraWebCtlHandler());
    }
private:
    LONG m_ref = 1;
};

/* ---------------- 资源 → 字符串 ---------------- */
/* HTML 以 **UTF-8 RCDATA** 存,这里转成宽字符(页面自己是 UTF-8 的,别按 ANSI 读) */
static BOOL WebUi_LoadHtml(int res_id) {
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(res_id), RT_RCDATA);
    if (!hr) return FALSE;
    DWORD size = SizeofResource(NULL, hr);
    HGLOBAL hg = LoadResource(NULL, hr);
    if (!hg || !size) return FALSE;
    const char *src = (const char *)LockResource(hg);
    int n = MultiByteToWideChar(CP_UTF8, 0, src, (int)size, NULL, 0);
    if (n <= 0) return FALSE;
    g_wu_html.resize(n);
    MultiByteToWideChar(CP_UTF8, 0, src, (int)size, &g_wu_html[0], n);
    return TRUE;
}

/* WebView2Loader.dll 从资源释放到 %TEMP%(安装器自己都还没装好,不能指望系统里有) */
static BOOL WebUi_ExtractLoader(int res_id, wchar_t *out_dir, size_t n) {
    wchar_t tmp[MAX_PATH];
    if (!GetTempPathW(MAX_PATH, tmp)) return FALSE;
    _snwprintf(out_dir, n, L"%sLyraWebView2", tmp);
    CreateDirectoryW(out_dir, NULL);
    wchar_t dll[MAX_PATH];
    _snwprintf(dll, MAX_PATH, L"%s\\WebView2Loader.dll", out_dir);
    if (GetFileAttributesW(dll) != INVALID_FILE_ATTRIBUTES) return TRUE;
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(res_id), RT_RCDATA);
    if (!hr) return FALSE;
    DWORD size = SizeofResource(NULL, hr);
    HGLOBAL hg = LoadResource(NULL, hr);
    if (!hg || !size) return FALSE;
    void *src = LockResource(hg);
    HANDLE f = CreateFileW(dll, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) return FALSE;
    DWORD wrote = 0;
    BOOL ok = WriteFile(f, src, size, &wrote, NULL) && wrote == size;
    CloseHandle(f);
    return ok;
}

/* 初始化网页界面:成功返回 TRUE(此后不要再建原生控件);失败返回 FALSE(调用方回退) */
static BOOL WebUi_Init(HWND hwnd, int loader_res_id, int html_res_id,
                       void (*on_msg)(const wchar_t *)) {
    typedef HRESULT(STDAPICALLTYPE *PFN_CREATE)(PCWSTR, PCWSTR,
        ICoreWebView2EnvironmentOptions *, ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler *);
    if (!WebUi_LoadHtml(html_res_id)) return FALSE;
    wchar_t dir[MAX_PATH];
    if (!WebUi_ExtractLoader(loader_res_id, dir, MAX_PATH)) return FALSE;
    wchar_t dll[MAX_PATH];
    _snwprintf(dll, MAX_PATH, L"%s\\WebView2Loader.dll", dir);
    HMODULE h = LoadLibraryW(dll);
    if (!h) h = LoadLibraryW(L"WebView2Loader.dll");
    if (!h) return FALSE;
    PFN_CREATE create = (PFN_CREATE)GetProcAddress(h, "CreateCoreWebView2EnvironmentWithOptions");
    if (!create) { FreeLibrary(h); return FALSE; }
    g_wu_hwnd = hwnd;
    g_wu_msg = on_msg;
    if (FAILED(create(NULL, dir, NULL, new LyraWebEnvHandler()))) {
        FreeLibrary(h);
        return FALSE;
    }
    return TRUE;
}

static void WebUi_Resize(HWND hwnd) {
    if (g_wu_ctl) {
        RECT rc;
        GetClientRect(hwnd, &rc);
        g_wu_ctl->put_Bounds(rc);
    }
}
static void WebUi_Show(BOOL show) { if (g_wu_ctl) g_wu_ctl->put_IsVisible(show ? TRUE : FALSE); }
static void WebUi_Eval(const wchar_t *js) { if (g_wu_view && js) g_wu_view->ExecuteScript(js, NULL); }
static BOOL WebUi_Ready(void) { return InterlockedCompareExchange(&g_wu_ready, 0, 0) != 0; }

/* 小工具:JSON 里取一个字符串字段的值(安装器只收几个固定命令,不值得引 JSON 库) */
static BOOL WebUi_Field(const wchar_t *json, const wchar_t *key, wchar_t *out, size_t n) {
    if (!json || !key) return FALSE;
    std::wstring pat = L"\"";
    pat += key;
    pat += L"\"";
    const wchar_t *p = wcsstr(json, pat.c_str());
    if (!p) return FALSE;
    p += pat.size();
    while (*p && (*p == L' ' || *p == L':')) p++;
    if (*p == L'"') p++;
    size_t i = 0;
    while (*p && *p != L'"' && i + 1 < n) out[i++] = *p++;
    out[i] = 0;
    return i > 0;
}

/* ---------------- 把照片图标当 data URI 塞进网页 ---------------- */
/* 网页是 NavigateToString 出来的(about:blank 源),file:// 一律读不到,
   所以图标只能转成 data URI 注入 —— 安装器窗口里那枚 logo 才是你要的那张图。 */
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
    std::wstring wide(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, js.c_str(), (int)js.size(), &wide[0], n);
    WebUi_Eval(wide.c_str());
}


/* 把一段文字转成 JS 字符串字面量(含引号)。**必须转义反斜杠** ——
   路径里的 \ 在 JS 里是转义符,不处理的话 __lyra.dir(D:\Lyra) 会语法报错,
   表现就是"网页里的路径框是空的"。 */
static void WebUi_JsStr(const wchar_t *s, std::wstring &out) {
    out = L"'";
    for (const wchar_t *p = s; p && *p; p++) {
        if (*p == L'\\')      out += L"\\\\";
        else if (*p == L'\'') out += L"\\'";
        else if (*p == L'\n') out += L"\\n";
        else if (*p == L'\r') out += L"\\r";
        else                  out += *p;
    }
    out += L"'";
}

/* 组合成 window.__lyra&&window.__lyra.<fn>(<字符串>) */
static void WebUi_EvalStr(const wchar_t *fn, const wchar_t *val) {
    std::wstring q;
    WebUi_JsStr(val, q);
    std::wstring js = L"window.__lyra&&window.__lyra.";
    js += fn;
    js += L"(";
    js += q;
    js += L")";
    WebUi_Eval(js.c_str());
}

#endif /* LYRA_WEBUI_H */
