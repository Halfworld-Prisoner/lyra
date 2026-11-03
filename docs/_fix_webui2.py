# -*- coding: utf-8 -*-
"""修网页版的两个小 bug:
   ① ui.html / ui_uninstall.html 里补 window.__lyra.src(u)(照片图标注入用);
   ② 原生推字符串给网页时必须做 **JS 字符串转义**(路径里的反斜杠/引号),
      否则 __lyra.dir(D:\\Lyra) 这种会直接语法报错 —— 路径框是空的真因。"""
import io
import os

I = r"D:\Unity阅读器\installer"


# ---------- ① 页面补 src() ----------
def add_src(fn, marker):
    p = os.path.join(I, fn)
    t = io.open(p, encoding="utf-8").read()
    if "src(u)" in t:
        print("  --  %s 已有 src()" % fn)
        return
    t = t.replace(marker,
                  "    src(u) { const i = document.getElementById('logo'); if (i && u) i.src = u; },\n" + marker, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  %s 已补 src()" % fn)


add_src("ui.html", "    status(t) {")
add_src("ui_uninstall.html", "    dir(p) {")

# ---------- ② webui.h:JS 字符串转义 ----------
p = os.path.join(I, "webui.h")
t = io.open(p, encoding="utf-8").read()
if "WebUi_JsStr" not in t:
    t = t.replace("#endif /* LYRA_WEBUI_H */", r'''
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

#endif /* LYRA_WEBUI_H */''', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  webui.h 已加 WebUi_JsStr / WebUi_EvalStr")

# ---------- ③ 两个 C 文件改用 EvalStr ----------
p = os.path.join(I, "setup.c")
t = io.open(p, encoding="utf-8").read()
old = '''        wchar_t js[MAX_PATH + 60];
        _snwprintf(js, MAX_PATH + 60, L"window.__lyra&&window.__lyra.dir(%s)", dir);
        WebUi_Eval(js);'''
if old in t:
    t = t.replace(old, '        WebUi_EvalStr(L"dir", dir);', 1)
    print("  OK  setup.c ready 里的 dir 改成转义版")
else:
    print("  --   setup.c 的 dir 那两行没匹配")
old2 = '''                if (wp == 1) _snwprintf(js, 700, L"window.__lyra&&window.__lyra.status(%s)", text);
                else _snwprintf(js, 700, L"window.__lyra&&window.__lyra.detail(%s)", text);
                WebUi_Eval(js);'''
if old2 in t:
    t = t.replace(old2,
                  '                WebUi_EvalStr(wp == 1 ? L"status" : L"detail", text);\n'
                  '                (void)js;', 1)
    print("  OK  setup.c 状态/详情改成转义版")
else:
    print("  --   setup.c 状态那几行没匹配")
io.open(p, "w", encoding="utf-8", newline="\n").write(t)

p = os.path.join(I, "uninstall.c")
t = io.open(p, encoding="utf-8").read()
old3 = '''        wchar_t js[MAX_PATH + 60];
        _snwprintf(js, MAX_PATH + 60, L"window.__lyra&&window.__lyra.dir(%s)", g_dir);
        WebUi_Eval(js);'''
if old3 in t:
    t = t.replace(old3, '        WebUi_EvalStr(L"dir", g_dir);', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  uninstall.c dir 改成转义版")
else:
    print("  --   uninstall.c 的 dir 没匹配")
print("完成")
