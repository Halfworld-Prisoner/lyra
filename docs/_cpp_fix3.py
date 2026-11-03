# -*- coding: utf-8 -*-
"""① 修 &IID_…(C++ 不需要取地址);② 把 base64 + 图标注入补进 webui.h。"""
import io
import os
import re

I = r"D:\Unity阅读器\installer"

# ---------- ① 看看并修掉 CoCreateInstance 那行 ----------
p = os.path.join(I, "setup.c")
t = io.open(p, encoding="utf-8").read()
print("  当前那行:")
for i, ln in enumerate(t.split("\n"), 1):
    if "CoCreateInstance" in ln:
        print("   %d: %s" % (i, ln.strip()))
t2 = re.sub(r"CoCreateInstance\(&(\w+),\s*NULL,\s*(\w+),\s*&(\w+),",
            r"CoCreateInstance(\1, NULL, \2, \3,", t)
if t2 != t:
    io.open(p, "w", encoding="utf-8", newline="\n").write(t2)
    print("  OK  已去掉 &CLSID/&IID")
else:
    print("  --  CoCreateInstance 那行没匹配到,手工看")

# ---------- ② webui.h 补 base64 / 图标注入 ----------
p = os.path.join(I, "webui.h")
w = io.open(p, encoding="utf-8").read()
if "WebUi_InjectLogo" in w:
    print("  --  webui.h 已有 InjectLogo")
else:
    BLOCK = r'''
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

#endif /* LYRA_WEBUI_H */'''
    w = w.replace("#endif /* LYRA_WEBUI_H */", BLOCK.lstrip("\n"), 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(w)
    print("  OK  webui.h 已加 base64 / 图标注入")
print("完成")
