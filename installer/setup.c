/* ============================================================================
 * Lyra —— 安装程序 / 启动器(纯 C,Win32 API)
 *
 * 一个 exe 干两件事:
 *   1) 还没安装(同目录没有 runtime/.deps-ok)→ 显示安装界面,可自定义安装目录(默认优先 D 盘),
 *      自动准备**私有** Python 3.13 运行环境(优先复用系统已装的 3.13 建 venv;
 *      没有就下载官方嵌入式包解压到安装目录),再装依赖、释放内嵌的应用负载(我们的 Python 后端 + 网页前端),
 *      建桌面快捷方式,勾选后直接启动。
 *   2) 已经安装(同目录有 .deps-ok)→ 直接启动应用(网页后端 + 自动开窗口)。
 *
 * 运行环境完全位于安装目录内(runtime\),不写 PATH、不改注册表、不影响系统与其他 Python。
 *
 * 构建见 build.ps1(gcc + windres)。
 * ==========================================================================*/
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define _WIN32_WINNT 0x0601

#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <urlmon.h>
#include <stdio.h>
#include <stdarg.h>
#include <wchar.h>

#include "webui.h"        /* 网页界面宿主(失败自动回退到原生界面) */
#define IDI_APPICON   101
#define IDR_PAYLOAD   102
#define IDR_RUNTIME   103
#define IDR_PLAYER    104
#define IDR_UNINSTALL 105
#define IDR_WEBVIEW2  106
#define IDR_UI_HTML   107
#define IDR_LOGO_PNG  108

#define APP_TITLE     L"Lyra"
#define APP_EXE_NAME  L"Lyra.exe"
#define UNINSTALL_NAME L"卸载 Lyra.exe"
#define SETUP_EXE     L"Lyra 安装程序.exe"
#define APP_VERSION   L"1.0"          /* 界面右上角显示的版本 */
#define REG_UNINSTALL L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" APP_TITLE
#define SERVER_REL    L"app\\webapp\\server.py"
#define DEPS_MARKER   L"runtime\\.deps-ok"
#define REQUIREMENTS  L"app\\requirements.txt"

/* 控件 */
#define IDC_PATH      1001
#define IDC_BROWSE    1002
#define IDC_INSTALL   1003
#define IDC_CLOSE     1004
#define IDC_PROGRESS  1005
#define IDC_LOG       1006
#define IDC_RUN       1007
#define IDC_DETAIL    1008

#define WM_APP_LOG      (WM_APP + 1)
#define WM_APP_PROGRESS (WM_APP + 2)
#define WM_APP_DONE     (WM_APP + 3)

static HINSTANCE g_hInst;
static HWND g_hWnd, g_hPath, g_hBrowse, g_hInstall, g_hClose, g_hBar, g_hLog, g_hRun;
static HWND g_hStatus;
static HWND g_hInfo, g_hDetail;
static BOOL g_detail = FALSE;

static BOOL g_web = FALSE;           /* 网页界面是否接管 */          /* 「显示详情」是否展开 */
static HFONT g_fTitle, g_fBody, g_fSmall, g_fBold;
static HBRUSH g_brBg;
#define CLR_BG     RGB(246, 247, 251)
#define CLR_TEXT   RGB(26, 31, 43)
#define CLR_MUTED  RGB(104, 112, 132)
static void make_fonts(void);          /* 前置声明:窗口过程里要用 */
static double payload_total_mb(void);
static volatile LONG g_running = 0;
static wchar_t g_logFile[MAX_PATH];

/* ---------------------------------------------------------------- 小工具 */
static void path_join(wchar_t *out, const wchar_t *a, const wchar_t *b) {
    wcsncpy(out, a, MAX_PATH - 1);
    out[MAX_PATH - 1] = 0;
    size_t n = wcslen(out);
    if (n && out[n - 1] != L'\\' && n < MAX_PATH - 2) { out[n] = L'\\'; out[n + 1] = 0; }
    wcsncat(out, b, MAX_PATH - wcslen(out) - 1);
}

static BOOL exists(const wchar_t *p) { return GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES; }
static BOOL is_dir(const wchar_t *p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

/* 注意:MinGW 的 msvcrt 不支持 "ccs=UTF-8",日志自己转 UTF-8 写二进制 */
static void append_utf8_file(const wchar_t *path, const wchar_t *text) {
    int need = WideCharToMultiByte(CP_UTF8, 0, text, -1, NULL, 0, NULL, NULL);
    if (need <= 1) return;
    char *buf = (char *)malloc(need);
    if (!buf) return;
    WideCharToMultiByte(CP_UTF8, 0, text, -1, buf, need, NULL, NULL);
    FILE *f = _wfopen(path, L"ab");
    if (f) { fwrite(buf, 1, need - 1, f); fclose(f); }
    free(buf);
}

static void log_write(const wchar_t *msg) {
    if (!g_logFile[0]) return;
    SYSTEMTIME st; GetLocalTime(&st);
    wchar_t line[2200];
    _snwprintf(line, 2199, L"[%02d:%02d:%02d] %s\n", st.wHour, st.wMinute, st.wSecond, msg);
    line[2199] = 0;
    append_utf8_file(g_logFile, line);
}

static void log_msg(const wchar_t *fmt, ...) {
    wchar_t buf[2048];
    va_list ap; va_start(ap, fmt);
    _vsnwprintf(buf, 2047, fmt, ap);
    va_end(ap);
    buf[2047] = 0;
    log_write(buf);
    if (g_hWnd && g_hLog) {
        wchar_t *copy = _wcsdup(buf);
        PostMessageW(g_hWnd, WM_APP_LOG, 0, (LPARAM)copy);
    }
}

static void set_progress(int percent) {
    if (g_hWnd) PostMessageW(g_hWnd, WM_APP_PROGRESS, (WPARAM)percent, 0);
}

static void set_status(const wchar_t *text) {
    if (g_hWnd && g_hStatus) {
        wchar_t *copy = _wcsdup(text);
        PostMessageW(g_hWnd, WM_APP_LOG, 1, (LPARAM)copy);   /* wParam=1 表示状态文字 */
    }
}

/* 执行命令并等待结束(hidden=不弹窗) */
static BOOL run_cmd(const wchar_t *cmdline, const wchar_t *workdir, BOOL hidden, DWORD *code) {
    wchar_t *buf = _wcsdup(cmdline);
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    DWORD flags = CREATE_UNICODE_ENVIRONMENT | (hidden ? CREATE_NO_WINDOW : 0);
    BOOL ok = CreateProcessW(NULL, buf, NULL, NULL, FALSE, flags, NULL,
                             (workdir && workdir[0]) ? workdir : NULL, &si, &pi);
    free(buf);
    if (!ok) { log_msg(L"  × 无法启动命令(错误码 %lu)", GetLastError()); return FALSE; }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD ec = 1;
    GetExitCodeProcess(pi.hProcess, &ec);
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    if (code) *code = ec;
    return ec == 0;
}

/* 读取文本文件(先按 UTF-8,失败再按本地代码页) */
static void read_text_file(const wchar_t *path, wchar_t *out, size_t out_chars) {
    out[0] = 0;
    FILE *f = _wfopen(path, L"rb");
    if (!f) return;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size <= 0 || size > 65536) { fclose(f); return; }
    char *buf = (char *)malloc((size_t)size + 1);
    if (!buf) { fclose(f); return; }
    size_t n = fread(buf, 1, (size_t)size, f);
    buf[n] = 0;
    fclose(f);
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, buf, -1, out, (int)out_chars) == 0) {
        if (MultiByteToWideChar(CP_ACP, 0, buf, -1, out, (int)out_chars) == 0) out[0] = 0;
    }
    free(buf);
    /* 去掉首尾空白 */
    wchar_t *s = out;
    while (*s == L' ' || *s == L'\r' || *s == L'\n' || *s == L'\t') s++;
    if (s != out) memmove(out, s, (wcslen(s) + 1) * sizeof(wchar_t));
    size_t L = wcslen(out);
    while (L && (out[L - 1] == L'\r' || out[L - 1] == L'\n' || out[L - 1] == L' ' || out[L - 1] == L'\t'))
        out[--L] = 0;
}

/* 执行命令,把 stdout/stderr 重定向到一个文件并等待结束。
 *
 * 注意:**不能走 cmd.exe + 批处理** —— cmd 按 ANSI(GBK)解析 .bat,
 * 中文安装路径(如 D:\聆阅)会被解码坏,命令直接跑不起来。
 * 这里直接 CreateProcess + 文件句柄重定向,路径以 UTF-16 传递,任何中文路径都没问题。
 */
static BOOL run_to_file(const wchar_t *cmdline, const wchar_t *workdir,
                        const wchar_t *outFile, DWORD *code) {
    SECURITY_ATTRIBUTES sa;
    sa.nLength = sizeof(sa);
    sa.lpSecurityDescriptor = NULL;
    sa.bInheritHandle = TRUE;

    HANDLE hOut = CreateFileW(outFile, GENERIC_WRITE, FILE_SHARE_READ, &sa,
                              CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hOut == INVALID_HANDLE_VALUE) return FALSE;
    HANDLE hNul = CreateFileW(L"NUL", GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);

    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = hOut;
    si.hStdError = hOut;
    si.hStdInput = hNul;

    wchar_t *buf = _wcsdup(cmdline);
    BOOL ok = CreateProcessW(NULL, buf, NULL, NULL, TRUE,
                             CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                             NULL, (workdir && workdir[0]) ? workdir : NULL, &si, &pi);
    free(buf);

    DWORD ec = (DWORD)-1;
    if (ok) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &ec);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    CloseHandle(hOut);
    if (hNul != INVALID_HANDLE_VALUE) CloseHandle(hNul);
    if (code) *code = ec;
    return ok && ec == 0;
}

/* 执行命令并捕获输出到内存(先按 UTF-8 解析,失败再按本地代码页) */
static BOOL run_capture(const wchar_t *cmdline, wchar_t *out, size_t out_chars) {
    wchar_t tmpDir[MAX_PATH], txt[MAX_PATH];
    GetTempPathW(MAX_PATH, tmpDir);
    _snwprintf(txt, MAX_PATH, L"%sgtreader_cap_%lu.txt", tmpDir, GetCurrentProcessId());
    BOOL ok = run_to_file(cmdline, NULL, txt, NULL);
    if (out && out_chars) read_text_file(txt, out, out_chars);
    DeleteFileW(txt);
    return ok;
}

static BOOL download(const wchar_t *url, const wchar_t *dest) {
    log_msg(L"  下载 %s", url);
    HRESULT hr = URLDownloadToFileW(NULL, url, dest, 0, NULL);
    if (FAILED(hr) || !exists(dest)) {
        log_msg(L"  × 下载失败(HRESULT 0x%08lX)", (unsigned long)hr);
        return FALSE;
    }
    return TRUE;
}

/* 递归创建目录 */
static BOOL make_dirs(const wchar_t *path) {
    wchar_t tmp[MAX_PATH];
    wcsncpy(tmp, path, MAX_PATH - 1); tmp[MAX_PATH - 1] = 0;
    for (wchar_t *p = tmp; *p; p++) {
        if ((*p == L'\\' || *p == L'/') && p != tmp && !(p == tmp + 2 && tmp[1] == L':')) {
            wchar_t c = *p; *p = 0;
            if (!is_dir(tmp)) CreateDirectoryW(tmp, NULL);
            *p = c;
        }
    }
    if (!is_dir(tmp)) CreateDirectoryW(tmp, NULL);
    return is_dir(path);
}

/* ---------------------------------------------------------------- 负载释放 */
static BOOL extract_payload(const wchar_t *dir) {
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(IDR_PAYLOAD), RT_RCDATA);
    if (!hr) { log_msg(L"× 安装包内未找到应用负载"); return FALSE; }
    DWORD size = SizeofResource(NULL, hr);
    HGLOBAL hg = LoadResource(NULL, hr);
    void *data = LockResource(hg);
    if (!data || !size) { log_msg(L"× 应用负载为空"); return FALSE; }

    wchar_t zip[MAX_PATH], appDir[MAX_PATH];
    path_join(zip, dir, L"payload.zip");
    path_join(appDir, dir, L"app");
    make_dirs(appDir);

    FILE *f = _wfopen(zip, L"wb");
    if (!f) { log_msg(L"× 无法写入 %s", zip); return FALSE; }
    fwrite(data, 1, size, f);
    fclose(f);

    log_msg(L"释放应用文件(%.1f MB)…", size / 1048576.0);
    wchar_t cmd[MAX_PATH * 3];
    _snwprintf(cmd, MAX_PATH * 3, L"tar.exe -xf \"%s\" -C \"%s\"", zip, appDir);
    if (!run_cmd(cmd, NULL, TRUE, NULL)) { log_msg(L"× 解压失败"); return FALSE; }
    DeleteFileW(zip);

    wchar_t srv[MAX_PATH];
    path_join(srv, dir, SERVER_REL);
    if (!exists(srv)) { log_msg(L"× 解压后缺少 %s", srv); return FALSE; }
    return TRUE;
}

/* ---------------------------------------------------------------- Python 环境 */
typedef struct { wchar_t exe[MAX_PATH]; BOOL is_venv; } PyInfo;

static BOOL try_system_python(wchar_t *out, size_t n) {
    /* 1) py 启动器里注册的 3.13 */
    wchar_t cap[1024];
    if (run_capture(L"py -3.13 -c \"import sys;print(sys.executable)\"", cap, 1024) && cap[0]) {
        if (exists(cap)) { wcsncpy(out, cap, n - 1); out[n - 1] = 0; return TRUE; }
    }
    /* 2) 常见安装位置 */
    wchar_t cand[MAX_PATH];
    const wchar_t *locals[] = {
        L"\\Programs\\Python\\Python313\\python.exe",
        L"\\Programs\\Python\\Python312\\python.exe",
    };
    wchar_t local[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_LOCAL_APPDATA, NULL, 0, local))) {
        for (int i = 0; i < 2; i++) { path_join(cand, local, locals[i]); if (exists(cand)) { wcsncpy(out, cand, n - 1); return TRUE; } }
    }
    const wchar_t *fixed[] = {
        L"D:\\Python\\Python313\\python.exe", L"C:\\Python313\\python.exe",
        L"D:\\Python313\\python.exe", L"D:\\Python\\Python312\\python.exe",
    };
    for (int i = 0; i < 4; i++) if (exists(fixed[i])) { wcsncpy(out, fixed[i], n - 1); return TRUE; }
    return FALSE;
}

/* ------------------------------ 内嵌便携运行时(离线安装) ------------------------------
 * 构建时把「嵌入式 Python 3.13 + 全部依赖」打成 runtime.zip 内嵌进 exe,
 * 安装时只需解压:不再执行 pip、不再联网。
 * ---------------------------------------------------------------------------------- */
static BOOL extract_zip_resource(int res_id, const wchar_t *dir, const wchar_t *zip_name,
                                 const wchar_t *sub_dir, const wchar_t *label) {
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(res_id), RT_RCDATA);
    if (!hr) { log_msg(L"× 安装包内缺少%s", label); return FALSE; }
    DWORD size = SizeofResource(NULL, hr);
    HGLOBAL hg = LoadResource(NULL, hr);
    const unsigned char *data = (const unsigned char *)LockResource(hg);
    if (!data || !size) { log_msg(L"× %s为空", label); return FALSE; }

    wchar_t zip[MAX_PATH], target[MAX_PATH];
    path_join(zip, dir, zip_name);
    path_join(target, dir, sub_dir);
    make_dirs(target);

    log_msg(L"释放%s(%.1f MB,无需联网)…", label, size / 1048576.0);
    FILE *f = _wfopen(zip, L"wb");
    if (!f) { log_msg(L"× 无法写入 %s(磁盘空间或权限不足)", zip); return FALSE; }
    const DWORD CHUNK = 4 * 1024 * 1024;
    DWORD written = 0;
    while (written < size) {
        DWORD n = (size - written > CHUNK) ? CHUNK : (size - written);
        if (fwrite(data + written, 1, n, f) != n) {
            fclose(f);
            log_msg(L"× 写入失败:磁盘空间可能不足(需要约 500 MB 空闲)");
            return FALSE;
        }
        written += n;
        set_progress(12 + (int)(40.0 * written / size));
    }
    fclose(f);

    wchar_t cmd[MAX_PATH * 3];
    _snwprintf(cmd, MAX_PATH * 3, L"tar.exe -xf \"%s\" -C \"%s\"", zip, target);
    BOOL ok = run_cmd(cmd, NULL, TRUE, NULL);
    DeleteFileW(zip);
    if (!ok) { log_msg(L"× %s解压失败", label); return FALSE; }
    return TRUE;
}

static BOOL ensure_runtime(const wchar_t *dir, PyInfo *info) {
    wchar_t rt[MAX_PATH], py[MAX_PATH], venvPy[MAX_PATH];
    path_join(rt, dir, L"runtime");
    path_join(py, rt, L"python\\python.exe");
    path_join(venvPy, rt, L"venv\\Scripts\\python.exe");

    if (!exists(py)) {
        if (!extract_zip_resource(IDR_RUNTIME, dir, L"runtime.zip", L"runtime", L"便携运行环境"))
            return FALSE;
    }
    if (exists(py)) {
        wcsncpy(info->exe, py, MAX_PATH - 1); info->is_venv = FALSE;
    } else if (exists(venvPy)) {              /* 兼容早期用 venv 安装的目录 */
        wcsncpy(info->exe, venvPy, MAX_PATH - 1); info->is_venv = TRUE;
    } else {
        log_msg(L"× 未找到运行时 python.exe");
        return FALSE;
    }
    log_msg(L"运行环境(便携版,不依赖系统):%s", info->exe);

    /* 自检:核心依赖能否导入;不通过则由上层用 pip 兜底修复。
       -X utf8 保证输出是 UTF-8(便于日志阅读) */
    wchar_t cap[4096], cmd[MAX_PATH * 4];
    _snwprintf(cmd, MAX_PATH * 4,
               L"\"%s\" -X utf8 -c \"import numpy,PIL,winrt.windows.media.speechsynthesis;"
               L"print('SELFCHECK_OK')\"", info->exe);
    BOOL ok = run_capture(cmd, cap, 4096);
    if (ok && wcsstr(cap, L"SELFCHECK_OK")) { log_msg(L"运行时自检通过(依赖齐全)"); return TRUE; }
    if (cap[0]) log_msg(L"! 运行时自检未通过:%.200s", cap);
    else log_msg(L"! 运行时自检未通过(命令无输出,退出异常)");
    return FALSE;
}

/* 执行命令,并把输出尾部追加到日志(用于 pip:失败时必须能看到原因) */
static BOOL run_cmd_logged(const wchar_t *cmdline, const wchar_t *workdir, int tail_lines) {
    wchar_t tmpDir[MAX_PATH], txt[MAX_PATH];
    GetTempPathW(MAX_PATH, tmpDir);
    _snwprintf(txt, MAX_PATH, L"%sgtreader_run_%lu.txt", tmpDir, GetCurrentProcessId());
    DeleteFileW(txt);

    BOOL ok = run_to_file(cmdline, workdir, txt, NULL);

    /* 把输出写进日志(只保留尾部若干行,避免刷屏) */
    if (exists(txt)) {
        const int MAXL = 512;
        wchar_t *lines = (wchar_t *)malloc(sizeof(wchar_t) * MAXL * MAXL);
        if (lines) {
            read_text_file(txt, lines, MAXL * MAXL - 1);
            int count = 0;
            for (wchar_t *p = lines; *p; p++) if (*p == L'\n') count++;
            int skip = (count > tail_lines) ? (count - tail_lines) : 0;
            wchar_t *start = lines;
            for (int i = 0; i < skip && *start; i++) {
                while (*start && *start != L'\n') start++;
                if (*start == L'\n') start++;
            }
            if (*start) {
                log_write(L"----- 命令输出 -----");
                log_write(start);
                log_write(L"--------------------");
                if (g_hWnd && g_hLog) {   /* 界面上也显示尾部 */
                    wchar_t *copy = _wcsdup(start);
                    if (copy) PostMessageW(g_hWnd, WM_APP_LOG, 0, (LPARAM)copy);
                }
            }
            free(lines);
        }
    }
    DeleteFileW(txt);
    return ok;
}

static BOOL ensure_deps(const wchar_t *dir, const PyInfo *py) {
    wchar_t marker[MAX_PATH], req[MAX_PATH];
    path_join(marker, dir, DEPS_MARKER);
    path_join(req, dir, REQUIREMENTS);

    BOOL need = TRUE;
    if (exists(marker) && exists(req)) {
        HANDLE hm = CreateFileW(marker, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        HANDLE hr = CreateFileW(req, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        if (hm != INVALID_HANDLE_VALUE && hr != INVALID_HANDLE_VALUE) {
            FILETIME fm, fr;
            if (GetFileTime(hm, NULL, NULL, &fm) && GetFileTime(hr, NULL, NULL, &fr)) {
                need = (CompareFileTime(&fr, &fm) > 0);   /* 依赖清单更新过才重装 */
            }
        }
        if (hm != INVALID_HANDLE_VALUE) CloseHandle(hm);
        if (hr != INVALID_HANDLE_VALUE) CloseHandle(hr);
    }
    if (!need) { log_msg(L"依赖已是最新,跳过下载"); return TRUE; }

    wchar_t cmd[MAX_PATH * 5];
    log_msg(L"安装依赖(首次约 3~6 分钟,请耐心等待)…");
    set_status(L"升级 pip…");
    _snwprintf(cmd, MAX_PATH * 5, L"\"%s\" -m pip install --upgrade pip --disable-pip-version-check", py->exe);
    run_cmd_logged(cmd, NULL, 5);

    /* 失败多为写入 .pyd 被临时占用/杀毒扫描(WinError 5)、或网络抖动:
       自动重试,并在两次失败后换用国内镜像源。 */
    const wchar_t *mirror = L"";
    for (int attempt = 1; attempt <= 4; attempt++) {
        if (attempt == 3) mirror = L"-i https://pypi.tuna.tsinghua.edu.cn/simple";
        _snwprintf(cmd, MAX_PATH * 5,
                   L"\"%s\" -X utf8 -m pip install -r \"%s\" --disable-pip-version-check "
                   L"--no-warn-script-location --retries 5 --timeout 60 %s",
                   py->exe, req, mirror);
        set_status(attempt == 1 ? L"安装依赖库…" :
                   (mirror[0] ? L"重试(国内镜像)…" : L"重试…"));
        log_msg(L"pip 安装开始(第 %d 次尝试%s)…", attempt, mirror[0] ? L",国内镜像" : L"");
        if (attempt == 3) log_msg(L"  改用清华镜像源:%s", mirror + 3);
        if (run_cmd_logged(cmd, NULL, 25)) {
            HANDLE h = CreateFileW(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
            if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
            return TRUE;
        }
        log_msg(L"  第 %d 次失败,3 秒后重试…", attempt);
        Sleep(3000);
    }
    log_msg(L"× 依赖安装失败。可尝试:①关闭杀毒软件后重试 ②检查网络 ③手动执行下面的命令:");
    log_msg(L"  \"%s\" -m pip install -r \"%s\"", py->exe, req);
    return FALSE;
}

/* 关键修复:winrt 包自带一份较老的 msvcp140.dll(14.29),与 sherpa-onnx 需要的
 * 系统版本(14.5x)在同一进程里并存会引发访问违例,表现为程序启动后立刻消失。
 * 把自带的那份改名禁用,让它改用系统版本即可(改名不删除,可回滚)。 */
static void fix_bundled_crt(const wchar_t *dir) {
    const wchar_t *rels[] = {
        L"runtime\\venv\\Lib\\site-packages\\winrt\\msvcp140.dll",
        L"runtime\\python\\Lib\\site-packages\\winrt\\msvcp140.dll",
    };
    for (int i = 0; i < 2; i++) {
        wchar_t src[MAX_PATH], dst[MAX_PATH];
        path_join(src, dir, rels[i]);
        if (!exists(src)) continue;
        _snwprintf(dst, MAX_PATH, L"%s.disabled", src);
        DeleteFileW(dst);
        if (MoveFileW(src, dst)) log_msg(L"已禁用 winrt 自带 CRT(改用系统版本)");
        else log_msg(L"  ! 禁用 winrt 自带 CRT 失败(错误码 %lu)", GetLastError());
    }
}

static BOOL create_shortcut(const wchar_t *dir) {
    wchar_t target[MAX_PATH], desktop[MAX_PATH], lnk[MAX_PATH];
    path_join(target, dir, APP_EXE_NAME);
    if (FAILED(SHGetFolderPathW(NULL, CSIDL_DESKTOPDIRECTORY, NULL, 0, desktop))) return FALSE;
    _snwprintf(lnk, MAX_PATH, L"%s\\%s.lnk", desktop, APP_TITLE);

    IShellLinkW *sl = NULL;
    if (FAILED(CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, IID_IShellLinkW, (void **)&sl))) return FALSE;
    sl->SetPath(target);
    sl->SetWorkingDirectory(dir);
    sl->SetDescription(L"截屏识别游戏字幕并朗读");
    sl->SetIconLocation(target, 0);

    IPersistFile *pf = NULL;
    BOOL ok = FALSE;
    if (SUCCEEDED(sl->QueryInterface(IID_IPersistFile, (void **)&pf))) {
        ok = SUCCEEDED(pf->Save(lnk, TRUE));
        pf->Release();
    }
    sl->Release();
    if (ok) log_msg(L"已创建桌面快捷方式:%s", lnk);
    return ok;
}

static BOOL launch_app(const wchar_t *dir) {
    wchar_t rt[MAX_PATH], pyw[MAX_PATH], venvPyw[MAX_PATH], srv[MAX_PATH], appDir[MAX_PATH];
    wchar_t cmd[MAX_PATH * 3];

    /* 优先启动"窗口程序":它自带原生窗口,并且会以 --no-browser 起后端,
       不会再多弹一个浏览器窗口出来。 */
    wchar_t player[MAX_PATH];
    path_join(player, dir, APP_EXE_NAME);
    if (exists(player)) {
        _snwprintf(cmd, MAX_PATH * 3, L"\"%s\"", player);
        STARTUPINFOW si0; PROCESS_INFORMATION pi0;
        ZeroMemory(&si0, sizeof(si0)); si0.cb = sizeof(si0);
        ZeroMemory(&pi0, sizeof(pi0));
        if (CreateProcessW(NULL, cmd, NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT,
                           NULL, dir, &si0, &pi0)) {
            CloseHandle(pi0.hProcess); CloseHandle(pi0.hThread);
            return TRUE;
        }
        log_msg(L"窗口程序启动失败,改用后端 + 浏览器");
    }

    path_join(rt, dir, L"runtime");
    path_join(pyw, rt, L"python\\pythonw.exe");
    path_join(venvPyw, rt, L"venv\\Scripts\\pythonw.exe");
    if (!exists(pyw)) {
        if (exists(venvPyw)) wcsncpy(pyw, venvPyw, MAX_PATH - 1);
    }
    path_join(srv, dir, SERVER_REL);
    path_join(appDir, dir, L"app");
    if (!exists(pyw) || !exists(srv)) {
        log_msg(L"× 启动失败:运行环境或程序文件不完整");
        return FALSE;
    }
    _snwprintf(cmd, MAX_PATH * 3, L"\"%s\" \"%s\"", pyw, srv);
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                        NULL, appDir, &si, &pi)) {
        log_msg(L"× 启动进程失败(错误码 %lu)", GetLastError());
        return FALSE;
    }
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    return TRUE;
}

/* 写“依赖就绪”标记(离线路径用) */
static void touch_marker(const wchar_t *dir) {
    wchar_t marker[MAX_PATH];
    path_join(marker, dir, DEPS_MARKER);
    HANDLE h = CreateFileW(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
}

/* 把内嵌资源写成文件 */
static BOOL write_resource_to_file(int res_id, const wchar_t *path) {
    HRSRC hr = FindResourceW(NULL, MAKEINTRESOURCEW(res_id), RT_RCDATA);
    if (!hr) return FALSE;
    DWORD size = SizeofResource(NULL, hr);
    const unsigned char *data = (const unsigned char *)LockResource(LoadResource(NULL, hr));
    if (!data || !size) return FALSE;
    FILE *f = _wfopen(path, L"wb");
    if (!f) return FALSE;
    BOOL ok = (fwrite(data, 1, size, f) == size);
    fclose(f);
    return ok;
}

/* 安装窗口宿主:写进安装目录,并在桌面创建快捷方式 */
static BOOL install_player(const wchar_t *dir) {
    wchar_t exePath[MAX_PATH];
    path_join(exePath, dir, APP_EXE_NAME);
    if (!write_resource_to_file(IDR_PLAYER, exePath)) {
        log_msg(L"× 释放窗口程序失败");
        return FALSE;
    }
    log_msg(L"窗口程序已就位:%s", exePath);
    create_shortcut(dir);          /* 桌面快捷方式指向安装目录里的这个 exe */
    return TRUE;
}

/* 安装卸载器,并写注册表卸载项(控制面板/设置→应用 里能看到并卸载) */
static BOOL install_uninstaller(const wchar_t *dir) {
    wchar_t exePath[MAX_PATH];
    path_join(exePath, dir, UNINSTALL_NAME);
    if (!write_resource_to_file(IDR_UNINSTALL, exePath)) {
        log_msg(L"× 释放卸载器失败");
        return FALSE;
    }
    log_msg(L"卸载器已就位:%s", exePath);

    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, REG_UNINSTALL, 0, NULL, 0,
                        KEY_SET_VALUE | KEY_WOW64_64KEY, NULL, &k, NULL) != ERROR_SUCCESS)
        return TRUE;                       /* 注册表写不进去不影响使用 */
    wchar_t quoted[MAX_PATH + 8];
    _snwprintf(quoted, MAX_PATH + 8, L"\"%s\"", exePath);
    RegSetValueExW(k, L"DisplayName", 0, REG_SZ, (const BYTE *)APP_TITLE,
                   (DWORD)((wcslen(APP_TITLE) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"UninstallString", 0, REG_SZ, (const BYTE *)quoted,
                   (DWORD)((wcslen(quoted) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"QuietUninstallString", 0, REG_SZ, (const BYTE *)quoted,
                   (DWORD)((wcslen(quoted) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"DisplayIcon", 0, REG_SZ, (const BYTE *)quoted,
                   (DWORD)((wcslen(quoted) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"InstallLocation", 0, REG_SZ, (const BYTE *)dir,
                   (DWORD)((wcslen(dir) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"Publisher", 0, REG_SZ, (const BYTE *)APP_TITLE,
                   (DWORD)((wcslen(APP_TITLE) + 1) * sizeof(wchar_t)));
    RegSetValueExW(k, L"DisplayVersion", 0, REG_SZ, (const BYTE *)L"2.0.0",
                   (DWORD)(6 * sizeof(wchar_t)));
    RegSetValueExW(k, L"EstimatedSize", 0, REG_DWORD, (const BYTE *)&(DWORD){140000}, 4);
    DWORD one = 1;
    RegSetValueExW(k, L"NoModify", 0, REG_DWORD, (const BYTE *)&one, 4);
    RegSetValueExW(k, L"NoRepair", 0, REG_DWORD, (const BYTE *)&one, 4);
    RegCloseKey(k);
    log_msg(L"已写入卸载注册表项");
    return TRUE;
}

/* 判断“安装到 dir”是否已完成 */
static BOOL already_installed(const wchar_t *dir) {
    wchar_t marker[MAX_PATH], srv[MAX_PATH];
    path_join(marker, dir, DEPS_MARKER);
    path_join(srv, dir, SERVER_REL);
    return exists(marker) && exists(srv);
}

/* ---------------------------------------------------------------- 安装流程 */
static void do_install(const wchar_t *dir) {
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(NULL, self, MAX_PATH);
    wchar_t *slash = wcsrchr(self, L'\\');
    if (slash) *(slash + 1) = 0;
    _snwprintf(g_logFile, MAX_PATH, L"%sinstall.log", self);

    log_msg(L"===== 开始安装 =====");
    log_msg(L"安装目录:%s", dir);
    set_status(L"准备安装目录…");
    set_progress(5);
    if (!make_dirs(dir)) { log_msg(L"× 无法创建目录(权限不足?)"); goto done; }

    set_status(L"准备运行环境(内嵌便携版,无需联网)…");
    set_progress(12);
    PyInfo py; ZeroMemory(&py, sizeof(py));
    BOOL runtime_ok = ensure_runtime(dir, &py);
    if (!runtime_ok) {
        log_msg(L"运行时自检未通过,尝试用 pip 兜底修复(此步需要网络)…");
        if (!ensure_deps(dir, &py)) { log_msg(L"× 运行环境准备失败"); goto done; }
    } else {
        touch_marker(dir);          /* 离线路径:直接写依赖就绪标记 */
    }

    set_status(L"释放程序文件…");
    set_progress(58);
    if (!extract_payload(dir)) goto done;

    set_status(L"收尾…");
    set_progress(90);
    fix_bundled_crt(dir);
    install_player(dir);
    install_uninstaller(dir);

    set_progress(100);
    set_status(L"安装完成");
    log_msg(L"===== 安装完成 =====");
    if (g_hWnd) PostMessageW(g_hWnd, WM_APP_DONE, 1, 0);
    return;

done:
    set_status(L"安装失败,请看下方日志");
    log_msg(L"===== 安装中断 =====");
    if (g_hWnd) PostMessageW(g_hWnd, WM_APP_DONE, 0, 0);
}

static DWORD WINAPI install_thread(LPVOID param) {
    wchar_t *dir = (wchar_t *)param;
    do_install(dir);
    free(dir);
    InterlockedExchange(&g_running, 0);
    return 0;
}

/* ---------------------------------------------------------------- 界面 */
static void append_log(const wchar_t *text) {
    int len = GetWindowTextLengthW(g_hLog);
    SendMessageW(g_hLog, EM_SETSEL, (WPARAM)len, (LPARAM)len);
    SendMessageW(g_hLog, EM_REPLACESEL, FALSE, (LPARAM)text);
    SendMessageW(g_hLog, EM_REPLACESEL, FALSE, (LPARAM)L"\r\n");
}

static void pick_folder(void) {
    BROWSEINFOW bi; ZeroMemory(&bi, sizeof(bi));
    wchar_t cur[MAX_PATH], display[MAX_PATH];
    GetWindowTextW(g_hPath, cur, MAX_PATH);
    bi.hwndOwner = g_hWnd;
    bi.lpszTitle = L"选择安装位置(建议装在 D 盘)";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_USENEWUI;
    bi.pszDisplayName = display;
    LPITEMIDLIST pidl = SHBrowseForFolderW(&bi);
    if (pidl) {
        wchar_t sel[MAX_PATH];
        if (SHGetPathFromIDListW(pidl, sel)) {
            /* 如果选的是盘根目录,自动追加一层文件夹名 */
            size_t n = wcslen(sel);
            if (n == 3 && sel[1] == L':' && sel[2] == L'\\')
                wcsncat(sel, APP_TITLE, MAX_PATH - n - 1);
            SetWindowTextW(g_hPath, sel);
        }
        CoTaskMemFree(pidl);
    }
}

static void start_install(void) {
    if (InterlockedCompareExchange(&g_running, 1, 0) != 0) return;
    wchar_t dir[MAX_PATH];
    GetWindowTextW(g_hPath, dir, MAX_PATH);
    size_t n = wcslen(dir);
    while (n && (dir[n - 1] == L'\\' || dir[n - 1] == L' ')) dir[--n] = 0;
    if (n < 4) { MessageBoxW(g_hWnd, L"请填写有效的安装目录。", APP_TITLE, MB_ICONWARNING); InterlockedExchange(&g_running, 0); return; }

    SetWindowTextW(g_hInstall, L"安装中…");
    EnableWindow(g_hInstall, FALSE);
    EnableWindow(g_hBrowse, FALSE);
    EnableWindow(g_hPath, FALSE);
    SetWindowTextW(g_hLog, L"");
    wchar_t *copy = _wcsdup(dir);
    HANDLE t = CreateThread(NULL, 0, install_thread, copy, 0, NULL);
    if (t) CloseHandle(t); else { free(copy); InterlockedExchange(&g_running, 0); }
}

/* 网页 -> 原生:安装 / 换位置 / 关窗 / 改路径 */
static void WebMsg(const wchar_t *json) {
    if (!json) return;
    if (wcsstr(json, L"\"ready\"")) {
        WebUi_InjectLogo(IDR_LOGO_PNG);
        wchar_t dir[MAX_PATH];
        GetWindowTextW(g_hPath, dir, MAX_PATH);
        WebUi_EvalStr(L"dir", dir);
        if (already_installed(dir))
            WebUi_Eval(L"window.__lyra&&window.__lyra.status('这台电脑上已经装过 Lyra,再点一次就是重新安装(设置不会丢)')");
        return;
    }
    if (wcsstr(json, L"\"browse\"")) { PostMessageW(g_hWnd, WM_COMMAND, IDC_BROWSE, 0); return; }
    if (wcsstr(json, L"\"install\"")) {
        wchar_t dir[MAX_PATH];
        if (WebUi_Field(json, L"dir", dir, MAX_PATH)) SetWindowTextW(g_hPath, dir);
        PostMessageW(g_hWnd, WM_COMMAND, IDC_INSTALL, 0);
        return;
    }
    if (wcsstr(json, L"\"close\"")) { PostMessageW(g_hWnd, WM_CLOSE, 0, 0); return; }
    if (wcsstr(json, L"\"path\"")) {
        wchar_t dir[MAX_PATH];
        if (WebUi_Field(json, L"dir", dir, MAX_PATH)) SetWindowTextW(g_hPath, dir);
    }
}

static LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        make_fonts();
        int y = 18;
        /* ── 顶部:图标 + 标题 + 一句话说明(只给玩家看"表面信息") ── */
        HWND ico = CreateWindowW(L"STATIC", NULL, WS_CHILD | WS_VISIBLE | SS_ICON,
                                 18, y, 48, 48, h, NULL, g_hInst, NULL);
        SendMessageW(ico, STM_SETICON, (WPARAM)LoadIconW(g_hInst, MAKEINTRESOURCEW(IDI_APPICON)), 0);
        HWND t1 = CreateWindowW(L"STATIC", APP_TITLE, WS_CHILD | WS_VISIBLE,
                                78, y - 2, 260, 30, h, NULL, g_hInst, NULL);
        SendMessageW(t1, WM_SETFONT, (WPARAM)g_fTitle, TRUE);
        HWND t2 = CreateWindowW(L"STATIC", L"Unity 游戏朗读器 · 把游戏里的文字念出来", WS_CHILD | WS_VISIBLE,
                                80, y + 26, 440, 20, h, NULL, g_hInst, NULL);
        SendMessageW(t2, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        HWND t3 = CreateWindowW(L"STATIC", L"版本 " APP_VERSION L" · 完全离线 · 不改动游戏文件", WS_CHILD | WS_VISIBLE,
                                80, y + 44, 440, 20, h, NULL, g_hInst, NULL);
        SendMessageW(t3, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        y += 66;

        HWND line = CreateWindowW(L"STATIC", NULL, WS_CHILD | WS_VISIBLE | SS_ETCHEDHORZ,
                                  18, y, 530, 1, h, NULL, g_hInst, NULL);
        (void)line;
        y += 14;

        /* ── 安装位置 ── */
        HWND lab = CreateWindowW(L"STATIC", L"安装到哪里(可以直接改,建议装在空间大的盘):",
                                 WS_CHILD | WS_VISIBLE, 18, y, 420, 20, h, NULL, g_hInst, NULL);
        SendMessageW(lab, WM_SETFONT, (WPARAM)g_fBold, TRUE);
        g_hPath = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
                                  WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
                                  18, y + 24, 430, 28, h, (HMENU)IDC_PATH, g_hInst, NULL);
        SendMessageW(g_hPath, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        g_hBrowse = CreateWindowW(L"BUTTON", L"换个位置…", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
                                  458, y + 24, 90, 28, h, (HMENU)IDC_BROWSE, g_hInst, NULL);
        SendMessageW(g_hBrowse, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        y += 64;

        /* ── 说明:装出来有什么、会占多少空间(算的是真实字节数) ── */
        wchar_t info[900];
        _snwprintf(info, 900,
                   L"装好之后你会有:\r\n"
                   L"    •  Lyra 主程序:游戏库、实时剧情、朗读、翻译都在里面(约 %.0f MB)\r\n"
                   L"    •  一个自带男声语音包「超文」,开箱即用;还能再下别的男声\r\n"
                   L"    •  游戏插件 LDC:在游戏卡片上点一下就能给那款游戏接上\r\n"
                   L"    •  离线运行:文字、声音、AI 翻译都在你这台电脑上跑\r\n"
                   L"\r\n"
                   L"它不会动你的东西:\r\n"
                   L"    •  不改游戏文件、不动存档;卸载时也一样\r\n"
                   L"    •  不用注册、不装驱动、不需要管理员权限也能装到自己的目录\r\n"
                   L"    •  装到哪个盘都行(C 盘 / D 盘 / U 盘皆可),卸载器跟着程序走",
                   payload_total_mb());
        g_hInfo = CreateWindowW(L"STATIC", info, WS_CHILD | WS_VISIBLE | SS_LEFT,
                                18, y, 530, 200, h, NULL, g_hInst, NULL);
        SendMessageW(g_hInfo, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        y += 208;

        /* ── 进度与状态(技术细节默认**收起来**,点「显示详情」才看) ── */
        g_hStatus = CreateWindowW(L"STATIC", L"准备就绪", WS_CHILD | WS_VISIBLE,
                                  18, y, 530, 22, h, NULL, g_hInst, NULL);
        SendMessageW(g_hStatus, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        g_hBar = CreateWindowExW(0, PROGRESS_CLASSW, NULL,
                                 WS_CHILD | WS_VISIBLE | PBS_SMOOTH, 18, y + 26, 530, 10,
                                 h, (HMENU)IDC_PROGRESS, g_hInst, NULL);
        SendMessageW(g_hBar, PBM_SETRANGE, 0, MAKELPARAM(0, 100));
        SendMessageW(g_hBar, PBM_SETBARCOLOR, 0, (LPARAM)RGB(124, 92, 255));
        SendMessageW(g_hBar, PBM_SETBKCOLOR, 0, (LPARAM)RGB(226, 229, 238));

        /* 日志与上面那块说明**共用同一区域**:默认只显示说明,点「显示详情」才盖上来,
           这样窗口里不会多出一块空框(玩家反馈过) */
        g_hLog = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
                                 WS_CHILD | WS_VSCROLL | ES_MULTILINE |
                                 ES_READONLY | ES_AUTOVSCROLL,
                                 18, y - 208, 530, 200, h, (HMENU)IDC_LOG, g_hInst, NULL);
        SendMessageW(g_hLog, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        g_hDetail = CreateWindowW(L"BUTTON", L"显示详情 ▾", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
                                  432, y - 2, 116, 24, h, (HMENU)IDC_DETAIL, g_hInst, NULL);
        SendMessageW(g_hDetail, WM_SETFONT, (WPARAM)g_fSmall, TRUE);
        y += 84;

        g_hRun = CreateWindowW(L"BUTTON", L"装完立刻打开 Lyra",
                               WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_AUTOCHECKBOX,
                               18, y, 240, 26, h, (HMENU)IDC_RUN, g_hInst, NULL);
        SendMessageW(g_hRun, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        SendMessageW(g_hRun, BM_SETCHECK, BST_CHECKED, 0);

        g_hInstall = CreateWindowW(L"BUTTON", L"开始安装",
                                   WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON | BS_OWNERDRAW,
                                   318, y - 4, 112, 34, h, (HMENU)IDC_INSTALL, g_hInst, NULL);
        SendMessageW(g_hInstall, WM_SETFONT, (WPARAM)g_fBody, TRUE);
        g_hClose = CreateWindowW(L"BUTTON", L"关闭",
                                 WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                 438, y - 4, 110, 34, h, (HMENU)IDC_CLOSE, g_hInst, NULL);
        SendMessageW(g_hClose, WM_SETFONT, (WPARAM)g_fBody, TRUE);

        /* 默认安装目录:优先 D 盘 */
        wchar_t def[MAX_PATH];
        if (GetDriveTypeW(L"D:\\") != DRIVE_NO_ROOT_DIR)
            _snwprintf(def, MAX_PATH, L"D:\\%s", APP_TITLE);
        else
            _snwprintf(def, MAX_PATH, L"C:\\%s", APP_TITLE);
        SetWindowTextW(g_hPath, def);
        ShowWindow(g_hLog, SW_HIDE);                     /* 技术细节默认收起 */
        /* ★网页界面★:原生控件先建好(安装逻辑还在用它们),能起 WebView2 就全部藏起来 */
        if (WebUi_Init(h, IDR_WEBVIEW2, IDR_UI_HTML, WebMsg)) {
            g_web = TRUE;
            HWND c = GetWindow(h, GW_CHILD);
            while (c) { ShowWindow(c, SW_HIDE); c = GetWindow(c, GW_HWNDNEXT); }
            SetTimer(h, 2, 2500, NULL);                  /* 2.5 秒没就绪 -> 回退原生界面 */
        }                     /* 技术细节默认收起 */
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
        /* 主按钮自绘:紫色圆角(原生按钮太"系统脸",这里是整窗唯一的重点) */
        DRAWITEMSTRUCT *di = (DRAWITEMSTRUCT *)lp;
        if (di && di->CtlID == IDC_INSTALL) {
            wchar_t text[64];
            GetWindowTextW(di->hwndItem, text, 64);
            BOOL on = IsWindowEnabled(di->hwndItem);
            HBRUSH br = CreateSolidBrush(on
                       ? ((di->itemState & ODS_SELECTED) ? RGB(96, 70, 210) : RGB(124, 92, 255))
                       : RGB(198, 200, 212));
            HPEN pen = CreatePen(PS_SOLID, 1, on ? RGB(124, 92, 255) : RGB(198, 200, 212));
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
    case WM_APP_LOG: {
        wchar_t *text = (wchar_t *)lp;
        if (text) {
            if (g_web) {
                wchar_t js[700];
                WebUi_EvalStr(wp == 1 ? L"status" : L"detail", text);
                (void)js;
            } else if (wp == 1) {
                SetWindowTextW(g_hStatus, text);
            } else {
                append_log(text);
            }
            free(text);
        }
        return 0;
    }
    case WM_APP_PROGRESS:
        if (g_web) {
            wchar_t js[56];
            _snwprintf(js, 56, L"window.__lyra&&window.__lyra.progress(%d)", (int)wp);
            WebUi_Eval(js);
        } else {
            SendMessageW(g_hBar, PBM_SETPOS, wp, 0);
        }
        return 0;
    case WM_APP_DONE: {
        EnableWindow(g_hInstall, TRUE);
        EnableWindow(g_hBrowse, TRUE);
        EnableWindow(g_hPath, TRUE);
        if (g_web) {
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
        if (g_web) {
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
            SetWindowTextW(g_hInstall, L"重新安装");
            SetWindowTextW(g_hStatus, L"装好了 —— 可以直接打开 Lyra,然后在游戏卡片上点「安装 LDC」");
            InvalidateRect(g_hInstall, NULL, TRUE);
            if (SendMessageW(g_hRun, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                wchar_t dir[MAX_PATH];
                GetWindowTextW(g_hPath, dir, MAX_PATH);
                launch_app(dir);
                PostMessageW(h, WM_CLOSE, 0, 0);
            }
        } else {
            SetWindowTextW(g_hInstall, L"重试");
            SetWindowTextW(g_hStatus, L"没装上 —— 换一个目录再试一次,或者把 Lyra 的窗口关掉后重来");
            InvalidateRect(g_hInstall, NULL, TRUE);
        }
        return 0;
    }
    case WM_TIMER:
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
        switch (LOWORD(wp)) {
        case IDC_BROWSE: pick_folder(); return 0;
        case IDC_INSTALL: start_install(); return 0;
        case IDC_CLOSE: PostMessageW(h, WM_CLOSE, 0, 0); return 0;
        case IDC_DETAIL: {
            /* 技术细节默认收起:玩家要看才展开(展开后窗口不动,只是把日志盖在说明上) */
            g_detail = !g_detail;
            ShowWindow(g_hLog, g_detail ? SW_SHOW : SW_HIDE);
            ShowWindow(g_hInfo, g_detail ? SW_HIDE : SW_SHOW);
            SetWindowTextW(g_hDetail, g_detail ? L"收起详情 ▴" : L"显示详情 ▾");
            return 0;
        }
        }
        return 0;
    case WM_CLOSE:
        if (InterlockedCompareExchange(&g_running, 0, 0) != 0) {
            if (MessageBoxW(h, L"正在安装,确定要退出吗?", APP_TITLE,
                            MB_ICONQUESTION | MB_YESNO) != IDYES) return 0;
        }
        DestroyWindow(h);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, msg, wp, lp);
}


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

/* ---------------------------------------------------------------- 入口 */
static void attach_console(void) {
    if (AttachConsole(ATTACH_PARENT_PROCESS)) {
        freopen("CONOUT$", "w", stdout);
        freopen("CONOUT$", "w", stderr);
    }
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, LPWSTR cmdLine, int show) {
    (void)hPrev; (void)show;
    g_hInst = hInst;
    CoInitialize(NULL);

    wchar_t selfDir[MAX_PATH];
    GetModuleFileNameW(NULL, selfDir, MAX_PATH);
    wchar_t *slash = wcsrchr(selfDir, L'\\');
    if (slash) *slash = 0;

    /* ---- 命令行:静默安装 / 直接启动 ---- */
    if (cmdLine && cmdLine[0]) {
        if (wcsstr(cmdLine, L"--help")) {
            attach_console();
            wprintf(L"Lyra 安装程序\n"
                    L"  安装程序.exe                 打开安装界面(已安装则直接启动)\n"
                    L"  安装程序.exe --install <目录>  静默安装到指定目录\n"
                    L"  安装程序.exe --run            直接启动已安装的程序\n");
            return 0;
        }
        wchar_t *p = wcsstr(cmdLine, L"--install");
        if (p) {
            attach_console();
            wchar_t dir[MAX_PATH] = { 0 };
            wchar_t *q = p + 9;
            while (*q == L' ') q++;
            if (*q == L'"') { q++; int i = 0; while (*q && *q != L'"' && i < MAX_PATH - 1) dir[i++] = *q++; }
            else { int i = 0; while (*q && *q != L' ' && i < MAX_PATH - 1) dir[i++] = *q++; }
            if (!dir[0]) { _snwprintf(dir, MAX_PATH, L"D:\\%s", APP_TITLE); }
            _snwprintf(g_logFile, MAX_PATH, L"%sinstall.log", selfDir);
            do_install(dir);
            wprintf(L"安装结束,详情见 %sinstall.log\n", selfDir);
            CoUninitialize();
            return 0;
        }
        if (wcsstr(cmdLine, L"--run")) {
            if (already_installed(selfDir)) { launch_app(selfDir); CoUninitialize(); return 0; }
            attach_console();
            wprintf(L"当前目录尚未安装,请直接双击打开安装界面。\n");
            CoUninitialize();
            return 1;
        }
    }

    /* ---- 已安装:本 exe 就是应用入口,直接启动 ---- */
    if (already_installed(selfDir)) {
        launch_app(selfDir);
        CoUninitialize();
        return 0;
    }

    /* ---- 未安装:显示安装界面 ---- */
    INITCOMMONCONTROLSEX icc = { sizeof(icc), ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&icc);

    WNDCLASSEXW wc; ZeroMemory(&wc, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APPICON));
    wc.hIconSm = wc.hIcon;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = L"LingYueReaderSetup";
    RegisterClassExW(&wc);

    int w = 600, hgt = 620;
    int x = (GetSystemMetrics(SM_CXSCREEN) - w) / 2;
    int y = (GetSystemMetrics(SM_CYSCREEN) - hgt) / 2;
    g_hWnd = CreateWindowExW(0, wc.lpszClassName, APP_TITLE L" 安装程序",
                             WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                             x, y, w, hgt, NULL, NULL, hInst, NULL);
    if (!g_hWnd) return 1;
    SendMessageW(g_hWnd, WM_SETICON, ICON_BIG, (LPARAM)wc.hIcon);
    SendMessageW(g_hWnd, WM_SETICON, ICON_SMALL, (LPARAM)wc.hIconSm);
    ShowWindow(g_hWnd, SW_SHOW);
    UpdateWindow(g_hWnd);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    CoUninitialize();
    return 0;
}
