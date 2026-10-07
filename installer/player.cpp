/* ============================================================================
 * Lyra —— 窗口宿主(原生窗口内嵌网页,基于 WebView2)
 *
 * 行为:
 *   1) 启动本目录下的 Python 后端(runtime\python\pythonw.exe app\webapp\server.py)
 *      若后端已在运行则直接复用(例如你先用浏览器打开着)
 *   2) 在原生窗口里显示 http://127.0.0.1:<port>/(不是浏览器窗口)
 *   3) 关闭窗口 → 同步关掉后端(已启动的进程会被结束,端口释放)
 *   4) 窗口开着时,浏览器仍可访问同一地址
 *
 * 编译: 见 installer\build.ps1(g++ + windres);需要 WebView2Loader.dll 与 exe 同目录。
 * ==========================================================================*/
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define _WIN32_WINNT 0x0601

#include <windows.h>
#include <winhttp.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <string>
#include <cstdio>

#include "WebView2.h"

#define IDI_APPICON 101
#define IDR_WVLOADER 110

static HINSTANCE g_hInst = nullptr;
static HWND      g_hWnd = nullptr;
static ICoreWebView2Controller* g_controller = nullptr;
static ICoreWebView2*           g_webview = nullptr;
static std::wstring g_url;
static int      g_port = 0;
static HANDLE   g_backendProc = nullptr;   /* 由本程序启动的后端进程 */
static bool     g_backendOwned = false;    /* true = 我们启动的,退出时要结束它 */
static bool     g_browserFallback = false;
static HANDLE   g_browserProc = nullptr;

/* ---------------------------------------------------------------- 小工具 */
static std::wstring ExeDir() {
    wchar_t buf[MAX_PATH] = {0};
    GetModuleFileNameW(nullptr, buf, MAX_PATH);
    wchar_t* p = wcsrchr(buf, L'\\');
    if (p) *p = 0;
    return std::wstring(buf);
}

static std::wstring Join(const std::wstring& a, const wchar_t* b) {
    std::wstring r = a;
    if (!r.empty() && r[r.size() - 1] != L'\\') r += L'\\';
    r += b;
    return r;
}

static bool FileExists(const std::wstring& p) {
    return GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES;
}

/* 找到安装目录:
 *   1) exe 同目录(安装在安装目录里的那份)
 *   2) 注册表 HKCU\Software\LingYueReader\InstallDir(安装器写入;桌面上的那份靠它定位)
 */
static std::wstring FindInstallDir() {
    std::wstring here = ExeDir();
    if (FileExists(Join(Join(here, L"runtime"), L"python\\pythonw.exe"))) return here;

    wchar_t buf[MAX_PATH] = {0};
    DWORD size = sizeof(buf) - sizeof(wchar_t);
    if (RegGetValueW(HKEY_CURRENT_USER, L"Software\\LingYueReader", L"InstallDir",
                     RRF_RT_REG_SZ, nullptr, buf, &size) == ERROR_SUCCESS) {
        std::wstring dir = buf;
        while (!dir.empty() && dir[dir.size() - 1] == L'\\') dir.erase(dir.size() - 1);
        if (FileExists(Join(Join(dir, L"runtime"), L"python\\pythonw.exe"))) return dir;
    }
    return L"";
}

/* ---------------------------------------------------------------- HTTP(WinHTTP) */
static bool HttpRequest(const wchar_t* verb, int port, const wchar_t* path,
                        int timeoutMs, std::wstring* outBody) {
    bool ok = false;
    HINTERNET hS = WinHttpOpen(L"LingYueReader/2.0", WINHTTP_ACCESS_TYPE_NO_PROXY,
                               WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hS) return false;
    WinHttpSetTimeouts(hS, timeoutMs, timeoutMs, timeoutMs, timeoutMs);
    HINTERNET hC = WinHttpConnect(hS, L"127.0.0.1", (INTERNET_PORT)port, 0);
    if (hC) {
        HINTERNET hR = WinHttpOpenRequest(hC, verb, path, nullptr, WINHTTP_NO_REFERER,
                                          WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
        if (hR) {
            if (WinHttpSendRequest(hR, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                                   WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
                WinHttpReceiveResponse(hR, nullptr)) {
                DWORD status = 0, len = sizeof(status);
                WinHttpQueryHeaders(hR, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                    WINHTTP_HEADER_NAME_BY_INDEX, &status, &len,
                                    WINHTTP_NO_HEADER_INDEX);
                ok = (status == 200);
                if (outBody && ok) {
                    DWORD avail = 0;
                    std::string data;
                    do {
                        avail = 0;
                        if (!WinHttpQueryDataAvailable(hR, &avail) || !avail) break;
                        char buf[4096];
                        DWORD read = 0;
                        DWORD want = avail > sizeof(buf) ? (DWORD)sizeof(buf) : avail;
                        if (!WinHttpReadData(hR, buf, want, &read) || !read) break;
                        data.append(buf, read);
                    } while (avail > 0);
                    int n = MultiByteToWideChar(CP_UTF8, 0, data.c_str(), (int)data.size(), nullptr, 0);
                    if (n > 0) {
                        outBody->resize(n);
                        MultiByteToWideChar(CP_UTF8, 0, data.c_str(), (int)data.size(), &(*outBody)[0], n);
                    }
                }
            }
            WinHttpCloseHandle(hR);
        }
        WinHttpCloseHandle(hC);
    }
    WinHttpCloseHandle(hS);
    return ok;
}

static bool PortAlive(int port) {
    return HttpRequest(L"GET", port, L"/api/state", 800, nullptr);
}

/* ---------------------------------------------------------------- 后端管理 */
static int ReadPortFile(const std::wstring& dir) {
    std::wstring f = Join(Join(dir, L"app"), L"server.port");
    FILE* fp = _wfopen(f.c_str(), L"rb");
    if (!fp) return 0;
    char buf[64] = {0};
    size_t n = fread(buf, 1, sizeof(buf) - 1, fp);
    fclose(fp);
    buf[n] = 0;
    int port = atoi(buf);
    return (port > 0 && port < 65536) ? port : 0;
}

static bool StartBackend(const std::wstring& dir) {
    std::wstring pyw = Join(Join(dir, L"runtime"), L"python\\pythonw.exe");
    std::wstring script = Join(Join(dir, L"app"), L"webapp\\server.py");
    if (!FileExists(pyw) || !FileExists(script)) return false;

    /* --no-browser:窗口由本程序提供,后端不要再自己开浏览器/应用窗口 */
    std::wstring cmd = L"\"" + pyw + L"\" \"" + script + L"\" --no-browser";
    std::wstring cwd = Join(dir, L"app");
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    std::wstring mut = cmd;
    if (!CreateProcessW(nullptr, &mut[0], nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                        nullptr, cwd.c_str(), &si, &pi))
        return false;
    g_backendProc = pi.hProcess;
    CloseHandle(pi.hThread);

    /* 等后端就绪(最多 40 秒:首次启动较慢) */
    for (int i = 0; i < 200; i++) {
        Sleep(200);
        int port = ReadPortFile(dir);
        if (port && PortAlive(port)) return true;
        DWORD code = 0;
        if (GetExitCodeProcess(g_backendProc, &code) && code != STILL_ACTIVE) return false;
    }
    return false;
}

static void StopBackend() {
    if (g_port > 0) {
        HttpRequest(L"POST", g_port, L"/api/quit", 1500, nullptr);   /* 优雅退出 */
        for (int i = 0; i < 15 && PortAlive(g_port); i++) Sleep(100);
    }
    if (g_backendOwned && g_backendProc) {
        DWORD code = 0;
        if (GetExitCodeProcess(g_backendProc, &code) && code == STILL_ACTIVE) {
            TerminateProcess(g_backendProc, 0);                      /* 兜底强杀 */
        }
        CloseHandle(g_backendProc);
        g_backendProc = nullptr;
    }
    if (g_browserProc) { TerminateProcess(g_browserProc, 0); CloseHandle(g_browserProc); g_browserProc = nullptr; }
}

/* 标题栏也做成深色/浅色,和界面统一(旧系统不支持就忽略,不影响功能) */
static void ApplyDarkTitleBar(HWND hwnd, bool darkMode, COLORREF captionColor) {
    typedef HRESULT(WINAPI * PFN_DWM)(HWND, DWORD, LPCVOID, DWORD);
    HMODULE dwm = LoadLibraryW(L"dwmapi.dll");
    if (!dwm) return;
    PFN_DWM set = (PFN_DWM)GetProcAddress(dwm, "DwmSetWindowAttribute");
    if (set) {
        BOOL dark = darkMode ? TRUE : FALSE;
        if (FAILED(set(hwnd, 20, &dark, sizeof(dark))))        /* DWMWA_USE_IMMERSIVE_DARK_MODE */
            set(hwnd, 19, &dark, sizeof(dark));                /* 旧版编号 */
        COLORREF caption = captionColor;                       /* 与网页底色同色 */
        COLORREF text = darkMode ? RGB(233, 237, 245) : RGB(26, 31, 43);
        COLORREF border = darkMode ? RGB(30, 34, 44) : RGB(214, 219, 229);
        set(hwnd, 35, &caption, sizeof(caption));              /* DWMWA_CAPTION_COLOR(Win11) */
        set(hwnd, 36, &text, sizeof(text));                    /* DWMWA_TEXT_COLOR */
        set(hwnd, 34, &border, sizeof(border));                /* DWMWA_BORDER_COLOR */
    }
    FreeLibrary(dwm);
}

/* 网页那边切主题时会 postMessage({type:"theme",dark,bg}),
   这里把**原生窗口自己的底色**也跟着换 —— 不换的话,切到明亮/护眼主题时
   窗口边缘与加载瞬间还是黑的(玩家反馈过这个问题)。 */
static void ApplyWindowTheme(HWND hwnd, bool darkMode, COLORREF bg) {
    if (hwnd) {
        /* 类背景刷:窗口重绘时的兜底底色 */
        static HBRUSH s_brush = nullptr;
        HBRUSH nb = CreateSolidBrush(bg);
        if (nb) {
            HBRUSH old = (HBRUSH)SetClassLongPtrW(hwnd, GCLP_HBRBACKGROUND, (LONG_PTR)nb);
            if (old) DeleteObject(old);
            if (s_brush) DeleteObject(s_brush);
            s_brush = nb;
            InvalidateRect(hwnd, nullptr, TRUE);
        }
        ApplyDarkTitleBar(hwnd, darkMode, bg);
    }
    /* WebView2 自己的默认底色(网页还没画出来时露的就是它) */
    if (g_controller) {
        ICoreWebView2Controller2* c2 = nullptr;
        if (SUCCEEDED(g_controller->QueryInterface(IID_ICoreWebView2Controller2, (void**)&c2)) && c2) {
            COREWEBVIEW2_COLOR col;
            col.A = 255;
            col.R = GetRValue(bg);
            col.G = GetGValue(bg);
            col.B = GetBValue(bg);
            c2->put_DefaultBackgroundColor(col);
            c2->Release();
        }
    }
}

/* ---- 网页 → 宿主 的消息(目前只有主题切换) ---- */
class WebMessageHandler : public ICoreWebView2WebMessageReceivedEventHandler {
public:
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2WebMessageReceivedEventHandler) {
            *ppv = static_cast<ICoreWebView2WebMessageReceivedEventHandler*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_ref); }
    STDMETHODIMP_(ULONG) Release() override {
        ULONG n = InterlockedDecrement(&m_ref);
        if (n == 0) delete this;
        return n;
    }
    STDMETHODIMP Invoke(ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs* args) override {
        LPWSTR json = nullptr;
        if (!args || FAILED(args->TryGetWebMessageAsString(&json)) || !json) return S_OK;
        std::wstring s(json);
        CoTaskMemFree(json);
        if (s.find(L"\"theme\"") == std::wstring::npos) return S_OK;
        bool dark = s.find(L"\"dark\":0") == std::wstring::npos;      /* 没写或为 1 都当暗色 */
        COLORREF bg = dark ? RGB(13, 15, 20) : RGB(243, 234, 216);
        size_t p = s.find(L"\"bg\":\"#");
        if (p != std::wstring::npos && s.size() >= p + 11) {          /* "#rrggbb" */
            auto hex = [&](size_t i) -> int {
                wchar_t c = s[p + 7 + i];
                if (c >= L'0' && c <= L'9') return c - L'0';
                if (c >= L'a' && c <= L'f') return c - L'a' + 10;
                if (c >= L'A' && c <= L'F') return c - L'A' + 10;
                return -1;
            };
            int r1 = hex(0), r0 = hex(1), g1 = hex(2), g0 = hex(3), b1 = hex(4), b0 = hex(5);
            if (r1 >= 0 && r0 >= 0 && g1 >= 0 && g0 >= 0 && b1 >= 0 && b0 >= 0)
                bg = RGB(r1 * 16 + r0, g1 * 16 + g0, b1 * 16 + b0);
        }
        ApplyWindowTheme(g_hWnd, dark, bg);
        return S_OK;
    }
private:
    LONG m_ref = 1;
};

/* ---------------------------------------------------------------- WebView2 回调 */
class EnvHandler : public ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler {
public:
    ULONG ref = 1;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown ||
            riid == IID_ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&ref); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG r = InterlockedDecrement(&ref);
        if (r == 0) delete this;
        return r;
    }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Environment* env) override;
};

class ControllerHandler : public ICoreWebView2CreateCoreWebView2ControllerCompletedHandler {
public:
    ULONG ref = 1;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown ||
            riid == IID_ICoreWebView2CreateCoreWebView2ControllerCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&ref); }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG r = InterlockedDecrement(&ref);
        if (r == 0) delete this;
        return r;
    }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Controller* controller) override;
};

static void ResizeWebView() {
    if (!g_controller) return;
    RECT rc;
    GetClientRect(g_hWnd, &rc);
    g_controller->put_Bounds(rc);
}

HRESULT EnvHandler::Invoke(HRESULT errorCode, ICoreWebView2Environment* env) {
    if (FAILED(errorCode) || !env) return S_OK;
    return env->CreateCoreWebView2Controller(g_hWnd, new ControllerHandler());
}

HRESULT ControllerHandler::Invoke(HRESULT errorCode, ICoreWebView2Controller* controller) {
    if (FAILED(errorCode) || !controller) return S_OK;
    g_controller = controller;
    g_controller->AddRef();
    if (FAILED(g_controller->get_CoreWebView2(&g_webview)) || !g_webview) return S_OK;
    g_webview->AddRef();
    /* 网页切主题时会 postMessage,宿主据此换窗口底色/标题栏明暗 */
    EventRegistrationToken tok;
    g_webview->add_WebMessageReceived(new WebMessageHandler(), &tok);
    ApplyWindowTheme(g_hWnd, true, RGB(13, 15, 20));      /* 默认暗色,和网页初始主题一致 */
    ResizeWebView();
    g_webview->Navigate(g_url.c_str());
    return S_OK;
}

/* ---------------------------------------------------------------- 窗口 */
#define TIMER_BACKEND 1

static std::wstring g_appDir;          /* 安装目录(看门狗重启后端要用) */

static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_SIZE:
        ResizeWebView();
        return 0;
    case WM_TIMER:
        if (wp == TIMER_BACKEND) {
            /* 看门狗:后端万一崩了/被外部关掉,自动把它拉起来,免得界面变成"连不上服务" */
            if (!PortAlive(g_port) && !g_appDir.empty()) {
                StartBackend(g_appDir);
                int p = ReadPortFile(g_appDir);
                if (p && p != g_port) {
                    g_port = p;
                    g_url = L"http://127.0.0.1:" + std::to_wstring(g_port) + L"/";
                    if (g_webview) g_webview->Navigate(g_url.c_str());
                }
            }
            return 0;
        }
        break;
    case WM_DESTROY:
        StopBackend();
        PostQuitMessage(0);
        return 0;
    case WM_CLOSE:
        DestroyWindow(h);
        return 0;
    }
    return DefWindowProcW(h, msg, wp, lp);
}

/* 把内嵌的 WebView2Loader.dll 释放到临时目录,返回其完整路径。
   这样桌面只放一个 exe 也能运行,不需要额外的 DLL 文件。 */
static std::wstring ExtractLoader() {
    HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(IDR_WVLOADER), RT_RCDATA);
    if (!hr) return L"";
    DWORD size = SizeofResource(nullptr, hr);
    HGLOBAL hg = LoadResource(nullptr, hr);
    void* data = LockResource(hg);
    if (!data || !size) return L"";

    wchar_t tmp[MAX_PATH] = {0};
    GetTempPathW(MAX_PATH, tmp);
    std::wstring dirRaw = std::wstring(tmp) + L"LingYueReaderWebView";
    CreateDirectoryW(dirRaw.c_str(), nullptr);
    std::wstring file = dirRaw + L"\\WebView2Loader.dll";

    /* 已存在且大小一致就复用 */
    WIN32_FILE_ATTRIBUTE_DATA fad;
    if (GetFileAttributesExW(file.c_str(), GetFileExInfoStandard, &fad) &&
        fad.nFileSizeLow == size) {
        return file;
    }
    HANDLE h = CreateFileW(file.c_str(), GENERIC_WRITE, 0, nullptr,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return L"";
    DWORD written = 0;
    BOOL ok = WriteFile(h, data, size, &written, nullptr);
    CloseHandle(h);
    return (ok && written == size) ? file : L"";
}

static bool InitWebView2() {
    typedef HRESULT (STDAPICALLTYPE *PFN)(PCWSTR, PCWSTR, ICoreWebView2EnvironmentOptions*,
                                          ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*);
    PFN create = nullptr;

    /* 1) 先用内嵌的加载器(释放到临时目录) */
    std::wstring embedded = ExtractLoader();
    if (!embedded.empty()) {
        HMODULE h = LoadLibraryW(embedded.c_str());
        if (h) create = (PFN)GetProcAddress(h, "CreateCoreWebView2EnvironmentWithOptions");
    }
    /* 2) 再试 exe 同目录 / 系统搜索路径 */
    if (!create) {
        wchar_t dll[MAX_PATH] = {0};
        GetModuleFileNameW(nullptr, dll, MAX_PATH);
        wchar_t* p = wcsrchr(dll, L'\\');
        if (p) *(p + 1) = 0;
        wcscat(dll, L"WebView2Loader.dll");
        HMODULE h = LoadLibraryW(dll);
        if (!h) h = LoadLibraryW(L"WebView2Loader.dll");
        if (h) create = (PFN)GetProcAddress(h, "CreateCoreWebView2EnvironmentWithOptions");
    }
    if (!create) return false;

    /* 用户数据目录放在 %LOCALAPPDATA%,避免写入安装目录 */
    wchar_t dataDir[MAX_PATH] = {0};
    if (SUCCEEDED(SHGetFolderPathW(nullptr, CSIDL_LOCAL_APPDATA, nullptr, 0, dataDir))) {
        wcscat(dataDir, L"\\LingYueReaderWebView");
        CreateDirectoryW(dataDir, nullptr);
    }
    HRESULT hr = create(nullptr, dataDir[0] ? dataDir : nullptr, nullptr, new EnvHandler());
    return SUCCEEDED(hr);
}

static void OpenInBrowserFallback() {
    std::wstring cmd = L"msedge.exe --app=" + g_url;
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    std::wstring m = cmd;
    if (CreateProcessW(nullptr, &m[0], nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, &pi)) {
        g_browserProc = pi.hProcess;
        CloseHandle(pi.hThread);
        WaitForSingleObject(g_browserProc, INFINITE);
    }
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR cmdLine, int) {
    g_hInst = hInst;
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    std::wstring dir = FindInstallDir();
    if (dir.empty()) {
        MessageBoxW(nullptr,
                    L"没有找到程序安装目录。\n\n"
                    L"如果你是第一次使用,请先运行「Lyra 安装程序.exe」完成安装;\n"
                    L"如果已经装过,请重新运行安装程序修复(它会重新登记安装位置)。",
                    L"Lyra", MB_ICONERROR);
        CoUninitialize();
        return 1;
    }
    bool silent = (cmdLine && wcsstr(cmdLine, L"--no-window"));   /* 只起后端(调试用) */

    /* 0) 已经开着窗口就把它调到前面,不重复开第二个(双击两次只应有一个窗口)。
       只认自己注册的窗口类:浏览器里那个网页版窗口标题也一样,不能按标题找,
       否则会把浏览器窗口当成"已经开着"而直接退出、什么都打不开。 */
    if (!silent) {
        HWND other = FindWindowW(L"LingYueReaderWindow", nullptr);
        if (other) {
            if (IsIconic(other)) ShowWindow(other, SW_RESTORE);
            ShowWindow(other, SW_SHOW);
            SetForegroundWindow(other);
            CoUninitialize();
            return 0;
        }
    }

    /* 1) 后端:已在运行就直接复用,否则启动 */
    int port = ReadPortFile(dir);
    if (port && PortAlive(port)) {
        g_port = port;
        g_backendOwned = false;
    } else {
        if (!StartBackend(dir)) {
            MessageBoxW(nullptr,
                        L"启动后端失败。\n\n请确认安装目录完整(runtime\\python 与 app\\webapp 都在),\n"
                        L"或重新运行安装程序。",
                        L"Lyra", MB_ICONERROR);
            CoUninitialize();
            return 1;
        }
        g_port = ReadPortFile(dir);
        g_backendOwned = true;
    }
    if (!g_port) g_port = 8765;
    g_url = L"http://127.0.0.1:" + std::to_wstring(g_port) + L"/";
    g_appDir = dir;                    /* 看门狗要用 */
    if (silent) { CoUninitialize(); return 0; }

    /* 2) 窗口 */
    WNDCLASSEXW wc; ZeroMemory(&wc, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APPICON));
    wc.hIconSm = wc.hIcon;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)CreateSolidBrush(RGB(13, 15, 20));   /* 深色底,避免启动瞬间白闪 */
    wc.lpszClassName = L"LingYueReaderWindow";
    RegisterClassExW(&wc);

    int w = 1180, hgt = 820;
    int x = (GetSystemMetrics(SM_CXSCREEN) - w) / 2;
    int y = (GetSystemMetrics(SM_CYSCREEN) - hgt) / 2;
    g_hWnd = CreateWindowExW(0, wc.lpszClassName, L"Lyra",
                             WS_OVERLAPPEDWINDOW, x, y, w, hgt,
                             nullptr, nullptr, hInst, nullptr);
    if (!g_hWnd) { StopBackend(); CoUninitialize(); return 1; }
    SendMessageW(g_hWnd, WM_SETICON, ICON_BIG, (LPARAM)wc.hIcon);
    SendMessageW(g_hWnd, WM_SETICON, ICON_SMALL, (LPARAM)wc.hIconSm);
    ApplyWindowTheme(g_hWnd, true, RGB(13, 15, 20));   /* 标题栏 + 窗口底色都跟界面走 */
    ShowWindow(g_hWnd, SW_SHOW);
    UpdateWindow(g_hWnd);

    /* 3) 内嵌网页;失败则退回浏览器 app 窗口 */
    if (!InitWebView2()) {
        g_browserFallback = true;
        OpenInBrowserFallback();
        DestroyWindow(g_hWnd);
    }

    MSG msg;
    SetTimer(g_hWnd, TIMER_BACKEND, 4000, nullptr);      /* 后端看门狗:每 4 秒查一次 */
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    if (g_controller) { g_controller->Close(); g_controller->Release(); g_controller = nullptr; }
    if (g_webview) { g_webview->Release(); g_webview = nullptr; }
    CoUninitialize();
    return 0;
}
