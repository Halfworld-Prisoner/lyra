# -*- coding: utf-8 -*-
"""修卸载器"点了确认没反应"的最后一环:
   ① 窗口只负责**确认**,真正的删除交给 %TEMP% 里的那份(它才能删掉自己所在的目录);
   ② 父进程等子进程干完,再按"目录还在不在"给结果提示。"""
import io

p = r"D:\Unity阅读器\installer\uninstall.c"
t = io.open(p, encoding="utf-8").read()

# ① 窗口里的 run_uninstall_ui:不再就地删除,直接关窗交给外层
old = '''static void run_uninstall_ui(void) {
    g_stage = 1;
    ui_status(L"正在卸载…");
    EnableWindow(g_hGo, FALSE);
    EnableWindow(g_hQuit, FALSE);
    UpdateWindow(g_hWin);
    g_rc = do_uninstall(g_dir, TRUE);
    g_stage = 2;
    if (g_rc == 0) {
        ui_status(L"卸载完成。你的游戏、存档、以及在游戏里的设置都没有被改动。");
        SetWindowTextW(g_hGo, L"关闭");
    } else {
        ui_status(L"卸载完成,但目录里有文件正被占用 —— 重启电脑后再运行一次本卸载器即可清干净。");
        SetWindowTextW(g_hGo, L"关闭");
    }
    EnableWindow(g_hGo, TRUE);
    EnableWindow(g_hQuit, TRUE);
    InvalidateRect(g_hGo, NULL, TRUE);
}'''
new = '''static void run_uninstall_ui(void) {
    /* ★这里不能就地删★:卸载器要删掉它自己所在的目录,必须先复制到 %TEMP% 再重跑一份。
       所以窗口只负责"确认",确认完就关掉,真正干活的是外层那条 --run 路径。 */
    g_stage = 1;
    ui_status(L"正在卸载…");
    UpdateWindow(g_hWin);
    DestroyWindow(g_hWin);
}'''
assert old in t, "run_uninstall_ui 没找到"
t = t.replace(old, new, 1)

# ② 入口:确认后继续走复制+重跑,并等子进程结束再报结果
old2 = '''            quiet = TRUE;
            if (g_rc == 0) {
                wchar_t msg[600];
                _snwprintf(msg, 600,
                           L"%s 已卸载。\\n\\n你的游戏、存档、以及在游戏里的设置都没有被改动。\\n"
                           L"(已经装进游戏里的 LDC 插件仍然有效;想清掉请在 Lyra 里"
                           L"对每个游戏点「卸载 LDC」。)",
                           APP_TITLE);
                MessageBoxW(NULL, msg, APP_TITLE L" 卸载完成", MB_ICONINFORMATION | MB_OK);
                return 0;
            }
        }'''
new2 = '''            quiet = TRUE;          /* 已确认:临时那份不要再问一遍 */
            confirmed = TRUE;
        }'''
assert old2 in t, "入口那段没找到"
t = t.replace(old2, new2, 1)

# ③ 声明 confirmed,并在子进程结束后报结果
t = t.replace('    BOOL quiet = FALSE, fromTemp = FALSE;',
              '    BOOL quiet = FALSE, fromTemp = FALSE, confirmed = FALSE;', 1)
old3 = '''        if (CreateProcessW(NULL, args, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            return 0;                       /* 退出后临时那份才能删掉整个目录 */
        }'''
new3 = '''        if (CreateProcessW(NULL, args, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            /* 等临时那份干完,再按"目录还在不在"给玩家一句人话 */
            WaitForSingleObject(pi.hProcess, 60000);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            if (confirmed) {
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
            return 0;                       /* 退出后临时那份才能删掉整个目录 */
        }'''
assert old3 in t, "CreateProcess 那段没找到"
t = t.replace(old3, new3, 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("uninstall.c 已修:窗口只确认、父进程等子进程、结果按实际目录判断")
