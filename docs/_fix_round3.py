# -*- coding: utf-8 -*-
"""第三轮:①手动添加游戏 ②配音保存中不刷新 ③翻译箭头 ④安装器版面重排+信息重写
   ⑤卸载器"点了没反应"的真因(提前 return 跳过了自删机制)+ 任意盘安装的安全校验。"""
import io
import os

J = r"D:\Unity阅读器\webapp\static\js"
C = r"D:\Unity阅读器\webapp\static\css"
I = r"D:\Unity阅读器\installer"


def rw(p, pairs, count=1):
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, count)
            print("  OK   %s" % old.strip().split("\n")[0][:58])
        else:
            print("  !!   没找到 %s" % old.strip().split("\n")[0][:58])
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


# ① 手动添加游戏:pickedAdd 漏了声明
rw(os.path.join(J, "views", "library.js"), [(
    "let _gridSig = '';",
    "let _gridSig = '';\nlet pickedAdd = null;      /* 手动添加时选中的 exe 路径(拆模块时漏了声明) */"
)])

# ② 角色配音:保存过程中绝不重建 DOM
rw(os.path.join(J, "views", "cast.js"), [
    ("let _castBusySince = 0;",
     "let _castBusySince = 0;\nlet _castSaving = 0;      /* 正在提交的配音改动数:>0 时不重建 */"),
    ("function castBusy() {",
     "function castBusy() {\n  if (_castSaving > 0) return true;   /* 正在保存:等他写完再重建 */"),
])

# ③ 翻译流程图箭头垂直居中
css = os.path.join(C, "extra.css")
t = io.open(css, encoding="utf-8").read()
if ".tr-flow i" not in t:
    t += '''
/* ---------------- 翻译流程图:箭头要和药丸居中对齐 ---------------- */
.tr-flow { align-items: center; }
.tr-flow i {
  display: inline-flex; align-items: center; justify-content: center;
  align-self: center; line-height: 1; height: 22px; font-size: 15px;
  color: var(--muted-2);
}
.tr-step { display: inline-flex; align-items: center; height: 30px; }
'''
    io.open(css, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK   tr-flow 箭头对齐")

# ④ 安装器:信息重写(更全面、更简洁)+ 日志与说明共用同一区域 + 窗口放大
rw(os.path.join(I, "setup.c"), [
    # 信息文案:分「会给你装上 / 不会动你的东西」两组,短句
    ('        wchar_t info[512];\n'
     '        _snwprintf(info, 512,\n'
     '                   L"会给你装上:\\r\\n"\n'
     '                   L"    •  Lyra 主程序(界面 + 读音引擎),大约 %.0f MB\\r\\n"\n'
     '                   L"    •  一个自带男声语音包(超文);想换音色可以再下载别的男声包\\r\\n"\n'
     '                   L"    •  游戏插件(LDC):装好后在游戏卡片上点一下就能给那款游戏接上\\r\\n"\n'
     '                   L"不会做:\\r\\n"\n'
     '                   L"    •  不需要联网、不用注册;不改动你的游戏文件,卸载时也不碰游戏",\n'
     '                   payload_total_mb());',
     '        wchar_t info[900];\n'
     '        _snwprintf(info, 900,\n'
     '                   L"装好之后你会有:\\r\\n"\n'
     '                   L"    •  Lyra 主程序:游戏库、实时剧情、朗读、翻译都在里面(约 %.0f MB)\\r\\n"\n'
     '                   L"    •  一个自带男声语音包「超文」,开箱即用;还能再下别的男声\\r\\n"\n'
     '                   L"    •  游戏插件 LDC:在游戏卡片上点一下就能给那款游戏接上\\r\\n"\n'
     '                   L"    •  离线运行:文字、声音、AI 翻译都在你这台电脑上跑\\r\\n"\n'
     '                   L"\\r\\n"\n'
     '                   L"它不会动你的东西:\\r\\n"\n'
     '                   L"    •  不改游戏文件、不动存档;卸载时也一样\\r\\n"\n'
     '                   L"    •  不用注册、不装驱动、不需要管理员权限也能装到自己的目录\\r\\n"\n'
     '                   L"    •  装到哪个盘都行(C 盘 / D 盘 / U 盘皆可),卸载器跟着程序走",\n'
     '                   payload_total_mb());'),
    # 日志改用同一块区域并默认收起
    ('        g_hLog = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",\n'
     '                                 WS_CHILD | WS_VSCROLL | ES_MULTILINE |\n'
     '                                 ES_READONLY | ES_AUTOVSCROLL,\n'
     '                                 18, y + 42, 530, 150, h, (HMENU)IDC_LOG, g_hInst, NULL);',
     '        /* 日志与上面那块说明**共用同一区域**:默认只显示说明,点「显示详情」才盖上来,\n'
     '           这样窗口里不会多出一块空框(玩家反馈过) */\n'
     '        g_hLog = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",\n'
     '                                 WS_CHILD | WS_VSCROLL | ES_MULTILINE |\n'
     '                                 ES_READONLY | ES_AUTOVSCROLL,\n'
     '                                 18, y - 132, 530, 176, h, (HMENU)IDC_LOG, g_hInst, NULL);'),
    # 说明块加高(多了一行)
    ('                                18, y, 530, 118, h, NULL, g_hInst, NULL);',
     '                                18, y, 530, 176, h, NULL, g_hInst, NULL);'),
    ('        y += 126;', '        y += 184;'),
    # 「显示详情」按钮放到状态行右侧,不再压在日志上
    ('                                  18, y + 4, 116, 26, h, (HMENU)IDC_DETAIL, g_hInst, NULL);',
     '                                  432, y, 116, 24, h, (HMENU)IDC_DETAIL, g_hInst, NULL);'),
    # 详情切换时两块互换
    ('            g_detail = !g_detail;\n'
     '            ShowWindow(g_hLog, g_detail ? SW_SHOW : SW_HIDE);',
     '            g_detail = !g_detail;\n'
     '            ShowWindow(g_hLog, g_detail ? SW_SHOW : SW_HIDE);\n'
     '            ShowWindow(g_hInfo, g_detail ? SW_HIDE : SW_SHOW);'),
    # 窗口尺寸
    ('int w = 586, hgt = 520;', 'int w = 600, hgt = 596;'),
])

# ⑤ 卸载器:点了确认没生效 —— 把提前 return 去掉,让它继续走"复制到 TEMP 再自删"那条路
rw(os.path.join(I, "uninstall.c"), [
    ('        if (!quiet) {\n'
     '            CoInitialize(NULL);\n'
     '            int r = show_uninstall_window(dir);      /* 自绘窗口:确认 + 进度 + 结果 */\n'
     '            if (r == 1) return 0;                    /* 用户取消 */\n'
     '            if (g_rc == 0) {\n'
     '                wchar_t msg[600];\n'
     '                _snwprintf(msg, 600,\n'
     '                           L"%s 已卸载。\\n\\n你的游戏、存档、以及在游戏里的设置都没有被改动。\\n"\n'
     '                           L"(如果还在玩游戏,已经装进游戏里的 LDC 插件仍然有效;"\n'
     '                           L"想清掉请在 Lyra 里对每个游戏点「卸载 LDC」。)",\n'
     '                           APP_TITLE);\n'
     '                MessageBoxW(NULL, msg, APP_TITLE L" 卸载完成", MB_ICONINFORMATION | MB_OK);\n'
     '            }\n'
     '            return g_rc;\n'
     '        }',
     '        if (!quiet) {\n'
     '            CoInitialize(NULL);\n'
     '            int r = show_uninstall_window(dir);      /* 自绘窗口:确认 + 进度 + 结果 */\n'
     '            if (r == 1) return 0;                    /* 用户取消 */\n'
     '            /* ★关键★:不能在这里 return!\n'
     '               卸载器要删掉自己所在的目录,必须先复制到 %TEMP% 再重跑一次\n'
     '               (--run),否则正在运行的这个 exe 删不掉,玩家看着就是"点了确认没反应"。\n'
     '               已经确认过了,所以给临时实例加 --quiet,不再弹第二个窗。 */\n'
     '            quiet = TRUE;\n'
     '            if (g_rc == 0) {\n'
     '                wchar_t msg[600];\n'
     '                _snwprintf(msg, 600,\n'
     '                           L"%s 已卸载。\\n\\n你的游戏、存档、以及在游戏里的设置都没有被改动。\\n"\n'
     '                           L"(已经装进游戏里的 LDC 插件仍然有效;想清掉请在 Lyra 里"\n'
     '                           L"对每个游戏点「卸载 LDC」。)",\n'
     '                           APP_TITLE);\n'
     '                MessageBoxW(NULL, msg, APP_TITLE L" 卸载完成", MB_ICONINFORMATION | MB_OK);\n'
     '                return 0;\n'
     '            }\n'
     '        }'),
])

# ⑤b 安全校验:目录不像 Lyra 安装目录就拒绝(防止 --dir 写错把别的文件夹删了,装到 U 盘/别的盘也安全)
rw(os.path.join(I, "uninstall.c"), [(
    'static int do_uninstall(const wchar_t *dir, BOOL quiet)\n{\n    int killed, failed = 0;',
    'static int do_uninstall(const wchar_t *dir, BOOL quiet)\n{\n    int killed, failed = 0;\n'
    '    /* ★安全闸★:只肯删"看起来确实是 Lyra 安装目录"的文件夹 ——\n'
    '       玩家可能把程序装在 U 盘 / C 盘 / 别的盘的任意目录,也可能手滑传错 --dir。\n'
    '       判定:目录里同时有 app\\webapp\\server.py 或 runtime\\ 或 Lyra.exe 中的任意两个。 */\n'
    '    {\n'
    '        wchar_t probe[MAX_PATH];\n'
    '        int marks = 0;\n'
    '        join(probe, dir, L"app\\\\webapp\\\\server.py");\n'
    '        if (is_file(probe)) marks++;\n'
    '        join(probe, dir, L"runtime");\n'
    '        if (is_dir(probe)) marks++;\n'
    '        join(probe, dir, L"Lyra.exe");\n'
    '        if (is_file(probe)) marks++;\n'
    '        join(probe, dir, L"\u8046\u9605.exe");\n'
    '        if (is_file(probe)) marks++;\n'
    '        if (marks < 2) {\n'
    '            if (!quiet) MessageBoxW(NULL,\n'
    '                L"\u8fd9\u4e2a\u76ee\u5f55\u770b\u4e0d\u51fa\u662f Lyra \u7684\u5b89\u88c5\u76ee\u5f55,\u4e3a\u4e86\u5b89\u5168\u6ca1\u6709\u5220\u9664\u5b83\u3002\\n"\n'
    '                L"\u8bf7\u4ece\u5f00\u59cb\u83dc\u5355\u6216\u63a7\u5236\u9762\u677f\u91cc\u7684\u300c\u5378\u8f7d Lyra\u300d\u8fd0\u884c\u3002",\n'
    '                APP_TITLE L" \u5378\u8f7d", MB_ICONINFORMATION | MB_OK);\n'
    '            return 1;\n'
    '        }\n'
    '    }')
])
print("完成")
