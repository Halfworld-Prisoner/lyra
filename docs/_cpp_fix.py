# -*- coding: utf-8 -*-
"""把 setup.c / uninstall.c 改成能用 g++ 编译(C++):
   ① 去掉重复声明;
   ② C 风格 COM 调用 sl->lpVtbl->X(sl, ...) 改成 C++ 的 sl->X(...);
   ③ 资源里重复的 ID 去重(windres 会报 duplicate value)。"""
import io
import os
import re

I = r"D:\Unity阅读器\installer"


def read(p):
    return io.open(os.path.join(I, p), encoding="utf-8").read()


def write(p, t):
    io.open(os.path.join(I, p), "w", encoding="utf-8", newline="\n").write(t)


# ---------- ① setup.c:重复声明 ----------
t = read("setup.c")
dup = "static BOOL g_web = FALSE;           /* 网页界面是否接管 */"
if t.count(dup) > 1:
    t = t.replace(dup, "", t.count(dup) - 1)
    print("  OK   setup.c 去掉重复的 g_web 声明(%d 处)" % (t.count(dup) - 1 if False else 1))

# ---------- ② C 风格 COM → C++ ----------
com = [
    ("sl->lpVtbl->SetPath(sl, target);", "sl->SetPath(target);"),
    ("sl->lpVtbl->SetWorkingDirectory(sl, dir);", "sl->SetWorkingDirectory(dir);"),
    ('sl->lpVtbl->SetDescription(sl, L"截屏识别游戏字幕并朗读");',
     'sl->SetDescription(L"截屏识别游戏字幕并朗读");'),
    ("sl->lpVtbl->SetIconLocation(sl, target, 0);", "sl->SetIconLocation(target, 0);"),
    ("sl->lpVtbl->QueryInterface(sl, &IID_IPersistFile, (void **)&pf)",
     "sl->QueryInterface(IID_IPersistFile, (void **)&pf)"),
    ("pf->lpVtbl->Save(pf, lnk, TRUE)", "pf->Save(lnk, TRUE)"),
    ("pf->lpVtbl->Release(pf);", "pf->Release();"),
    ("sl->lpVtbl->Release(sl);", "sl->Release();"),
]
for a, b in com:
    if a in t:
        t = t.replace(a, b)
        print("  OK   COM: %s" % a[:44])
    else:
        print("  --   没找到: %s" % a[:44])
write("setup.c", t)

# ---------- ③ 资源去重 ----------
for f in ("app.rc", "uninstall.rc"):
    lines = read(f).split("\n")
    seen = set()
    out = []
    for ln in lines:
        m = re.match(r"\s*(IDR_[A-Z0-9_]+|IDI_APPICON)\s+(RCDATA|ICON)\s", ln)
        if m:
            key = (m.group(1), m.group(2))
            if key in seen:
                print("  OK   %s 去掉重复资源行: %s" % (f, ln.strip()[:42]))
                continue
            seen.add(key)
        out.append(ln)
    write(f, "\n".join(out))
print("完成")
