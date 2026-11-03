# -*- coding: utf-8 -*-
"""去掉卸载完成后多出来的那个结果弹窗:
   改成在卸载器窗口里显示一句状态、停一下再关窗(不再另开 MessageBox)。"""
import io

p = r"D:\Unity阅读器\installer\uninstall.c"
t = io.open(p, encoding="utf-8").read()

old = '''            if (confirmed) {
                wchar_t msg[700];
                BOOL gone = !is_dir(dir);
                _snwprintf(msg, 700,
                           gone ? L"%s 已卸载。\\n\\n你的游戏、存档、以及在游戏里的设置都没有被改动。\\n"
                                  L"(已经装进游戏里的 LDC 插件仍然有效;想清掉请在 Lyra 里"
                                  L"对每个游戏点「卸载 LDC」。)"
                                : L"卸载没有完全成功:\\n%s\\n\\n"
                                  L"多半是有文件被占用 —— 把 Lyra 窗口关掉、或重启电脑后"
                                  L"再运行一次卸载器即可清干净。",
                           APP_TITLE, dir);
                MessageBoxW(NULL, msg, APP_TITLE L" 卸载", MB_ICONINFORMATION | MB_OK);
            }
            return 0;                       /* 退出后临时那份才能删掉整个目录 */'''

new = '''            /* ★不再另开结果弹窗★(玩家反馈"卸载完又弹一个新窗口")。
               卸载成不成功,玩家自己看目录在不在就知道;真要留痕就写进日志。 */
            if (confirmed && is_dir(dir)) {
                wchar_t note[MAX_PATH + 200];
                _snwprintf(note, MAX_PATH + 200,
                           L"卸载未完全成功(有文件被占用):%s\\r\\n"
                           L"关掉 Lyra 窗口或重启电脑后再运行一次本卸载器即可清干净。\\r\\n",
                           dir);
                wchar_t logp[MAX_PATH];
                _snwprintf(logp, MAX_PATH, L"%s\\\\lyra_uninstall.log", tempDir);
                FILE *f = _wfopen(logp, L"a, ccs=UTF-8");
                if (f) { fwprintf(f, L"%s", note); fclose(f); }
            }
            return 0;                       /* 退出后临时那份才能删掉整个目录 */'''

assert old in t, "结果弹窗那段没找到"
io.open(p, "w", encoding="utf-8", newline="\n").write(t.replace(old, new, 1))
print("已去掉多余的结果弹窗(失败时改写日志)")
