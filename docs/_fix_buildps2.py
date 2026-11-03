# -*- coding: utf-8 -*-
"""把 build.ps1 里安装器/卸载器的编译命令整段换成稳妥写法(显式 -I "路径")。"""
import io
import re

p = r"D:\Unity阅读器\installer\build.ps1"
t = io.open(p, encoding="utf-8").read()
lines = t.split("\n")
out = []
i = 0
changed = 0
while i < len(lines):
    ln = lines[i]
    if re.match(r"\s*&\s*g\+\+\s+\(Join-Path \$inst \"uninstall\.c\"\)", ln):
        out.append('& g++ (Join-Path $inst "uninstall.c") $unRes -o (Join-Path $inst "uninstall.exe") `')
        out.append('    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `')
        out.append('    -I "$inst\\compat" -I "$wvInc" `')
        out.append('    -lcomctl32 -lole32 -loleaut32 -luuid -lshell32 -lshlwapi -ladvapi32')
        while i < len(lines) and not re.search(r"-ladvapi32|-lurlmon", lines[i]):
            i += 1
        i += 1
        changed += 1
        continue
    if re.match(r"\s*&\s*g\+\+\s+\(Join-Path \$inst \"setup\.c\"\)", ln):
        out.append('& g++ (Join-Path $inst "setup.c") $res -o $tmpExe `')
        out.append('    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `')
        out.append('    -I "$inst\\compat" -I "$wvInc" `')
        out.append('    -lcomctl32 -lole32 -loleaut32 -luuid -lshell32 -lshlwapi -lurlmon -ladvapi32')
        while i < len(lines) and not re.search(r"-ladvapi32|-lurlmon", lines[i]):
            i += 1
        i += 1
        changed += 1
        continue
    out.append(ln)
    i += 1
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("替换了", changed, "处编译命令")
for n, l in enumerate(io.open(p, encoding="utf-8").read().split("\n"), 1):
    if "g++" in l or "-I \"$inst" in l:
        print("  %4d %s" % (n, l.strip()[:100]))
