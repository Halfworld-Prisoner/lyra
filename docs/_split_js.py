# -*- coding: utf-8 -*-
"""把 webapp/static/app.js 拆成 ES 模块(内容按行区间搬运,再做跨模块改写)。

用法: python docs/_split_js.py
产出:
  js/core.js              基础工具 + 弹窗 + 主题
  js/state.js             全局状态 + 刷新循环 + 渲染器注册表
  js/boot.js              导航 / 顶栏 / 底栏 / 画图 / 启动
  js/views/library.js     游戏库 + 添加游戏
  js/views/cast.js        语音 + 角色配音
  js/views/rules.js       过滤规则
  js/views/logs.js        日志
  js/views/translate.js   文本翻译
  js/views/settings.js    设置
"""
import io
import os
import re

STATIC = r"D:\Unity阅读器\webapp\static"
SRC = os.path.join(STATIC, "app.js")

# (目标文件, 说明, [(起, 止)])  —— 行号 1 基,含两端
PLAN = [
    ("js/core.js", "基础工具:DOM 取值、请求封装、提示/弹窗、主题切换。",
     [(1, 67), (85, 114)]),
    ("js/state.js", "全局状态 + 轮询刷新 + 各页渲染器注册表。",
     [(131, 277)]),
    ("js/views/library.js", "游戏库:游戏卡片、启动/终止、LDA 安装、添加游戏弹窗。",
     [(278, 588)]),
    ("js/views/cast.js", "语音与角色配音:全局音色、语速声线、语音包、角色配音表。",
     [(589, 928)]),
    ("js/views/rules.js", "过滤规则:通用规则、游戏专用、AI 词、黑白名单。",
     [(929, 1221)]),
    ("js/views/logs.js", "日志页:运行状态、分类页签、点日志加黑白名单。",
     [(1222, 1381)]),
    ("js/views/translate.js", "文本翻译页:开关、设置、试翻、状态与用量。",
     [(1382, 1476)]),
    ("js/views/settings.js", "设置页:剧情过滤、自动下一句、窗口悬浮窗、LDC 进阶。",
     [(1477, 1558)]),
    ("js/boot.js", "导航与启动:切页、顶栏、底栏、曲线图、波浪动画、轮询。",
     [(68, 84), (115, 130), (1559, 1655)]),
]

HEADERS = {
    "js/core.js": """/* core.js —— 基础工具与主题
   这里只有"和具体页面无关"的东西:抓元素、发请求、弹提示、切主题。
   任何页面模块都可以 import 它。 */
""",
    "js/state.js": """/* state.js —— 全局状态与刷新循环
   S 里的东西来自 /api/state;各页面模块通过 registerRender() 注册自己的渲染函数,
   刷新时统一调用 —— 这样加一个页面不用改这里。 */
""",
    "js/boot.js": """/* boot.js —— 导航与启动
   左边栏切页、顶栏动作、底栏按钮、两个画布动画,最后启动 0.4 秒轮询。 */
""",
    "js/views/library.js": """/* 游戏库页 */""",
    "js/views/cast.js": """/* 角色配音页(含全局声音设置) */""",
    "js/views/rules.js": """/* 过滤规则页 */""",
    "js/views/logs.js": """/* 日志页 */""",
    "js/views/translate.js": """/* 文本翻译页 */""",
    "js/views/settings.js": """/* 设置页 */""",
}

# 每个模块要 import 什么(手写,避免自动推断出错)
IMPORTS = {
    "js/views/library.js": ("import { $, $$, esc, toast, get, post, choose, dialog } from '../core.js';\n"
                            "import { store, refresh, registerRender, scanData, setScanData } from '../state.js';\n"),
    "js/views/cast.js": ("import { $, $$, esc, toast, post, get, pitchText } from '../core.js';\n"
                         "import { store, refresh, registerRender } from '../state.js';\n"),
    "js/views/rules.js": ("import { $, $$, esc, toast, get, post, choose, dialog, closeModals } from '../core.js';\n"
                          "import { store, refresh, registerRender } from '../state.js';\n"),
    "js/views/logs.js": ("import { $, $$, esc, toast, get, post, dialog, closeModals, lsRow } from '../core.js';\n"
                         "import { store, refresh, registerRender } from '../state.js';\n"),
    "js/views/translate.js": ("import { $, $$, esc, toast, get, post, lsRow } from '../core.js';\n"
                              "import { store, refresh, registerRender } from '../state.js';\n"),
    "js/views/settings.js": ("import { $, $$, esc, toast, get, post, choose } from '../core.js';\n"
                             "import { store, refresh, registerRender } from '../state.js';\n"),
    "js/boot.js": ("import { $, $$, esc, toast, get, post, choose, applyTheme } from './core.js';\n"
                   "import { store, refresh, registerRender } from './state.js';\n"
                   "import './views/library.js';\n"
                   "import './views/cast.js';\n"
                   "import './views/rules.js';\n"
                   "import './views/logs.js';\n"
                   "import './views/translate.js';\n"
                   "import './views/settings.js';\n"),
}

# 全局级声明要挪到 state.js / core.js;原文件里这些行不搬
DECL = {
    "let S = { settings: {}, game_info: null, voices: [], games: [], metrics: {} };": "state.js",
    "let view = 'library';": "state.js",
    "let scanData = { steam: [], desktop: [] };": "state.js",
    "let pickedAdd = null;              // 手动添加时选中的路径": "library.js",
    "let sparkRate = [], sparkMem = [];  // 最近 60 秒": "boot.js",
}

# 需要导出给别的模块用的函数(目标文件 → 名字列表)
EXPORTS = {
    "js/core.js": ["get", "post", "esc", "toast", "choose", "dialog", "closeModals", "applyTheme"],
    "js/state.js": ["store", "refresh", "registerRender"],
    "js/views/rules.js": ["loadRules"],
    "js/views/cast.js": ["renderVoices", "renderCast", "renderVoiceNow"],
    "js/views/library.js": ["renderGames"],
    "js/views/logs.js": ["renderLogs"],
    "js/views/translate.js": ["renderTranslate"],
}

# 每个视图模块要在末尾注册的渲染器
REGISTER = {
    "js/views/library.js": ["renderGames", "syncInstallBtn", "syncLaunchBtn"],
    "js/views/cast.js": ["renderVoiceNow", "renderVoices", "renderCast"],
    "js/views/logs.js": ["renderLogs"],
    "js/views/translate.js": ["renderTranslate"],
}


def main():
    lines = io.open(SRC, encoding="utf-8").read().split("\n")
    os.makedirs(os.path.join(STATIC, "js", "views"), exist_ok=True)
    for rel, desc, ranges in PLAN:
        body = "\n".join("\n".join(lines[a - 1:b]) for a, b in ranges)
        # 跨模块改写
        body = re.sub(r"(?<![\w.$])S\.", "store.S.", body)
        body = re.sub(r"(?<![\w.$])view\b(?!\s*[:=])", "store.view", body)
        body = body.replace("let store.view = 'library';", "")
        # 去掉原文件里的全局声明(它们已经在 state.js/core.js 里统一声明)
        out_lines = []
        for ln in body.split("\n"):
            s = ln.strip()
            if s in DECL:
                continue
            out_lines.append(ln)
        body = "\n".join(out_lines)
        # 导出
        for name in EXPORTS.get(rel, []):
            if name in ("store", "refresh", "registerRender"):
                continue
            body = re.sub(r"(?m)^(async function %s\()" % re.escape(name), r"export \1", body)
            body = re.sub(r"(?m)^(function %s\()" % re.escape(name), r"export \1", body)
            body = re.sub(r"(?m)^(const %s = )" % re.escape(name), r"export \1", body)
        head = HEADERS[rel] + "\n" + IMPORTS.get(rel, "")
        tail = ""
        regs = REGISTER.get(rel)
        if regs:
            tail = ("\n/* 注册到刷新循环:数据一变就重画这一页 */\n"
                    + "".join("registerRender(%s);\n" % r for r in regs))
        text = head + "\n" + body.strip() + "\n" + tail
        io.open(os.path.join(STATIC, rel), "w", encoding="utf-8", newline="\n").write(text)
        print("  %-24s %5d 行" % (rel, text.count("\n")))

    # state.js 要补 store / registerRender 的定义
    p = os.path.join(STATIC, "js/state.js")
    t = io.open(p, encoding="utf-8").read()
    store_def = """
/* ---- 全局状态 ---- */
export const store = {
  S: { settings: {}, game_info: null, voices: [], games: [], metrics: {} },
  view: 'library',
  renderers: [],
};
export let scanData = { steam: [], desktop: [] };
export function setScanData(d) { scanData = d; }
/* 各页面模块在加载时注册自己的渲染函数;刷新时按注册顺序调用 */
export function registerRender(fn) {
  if (typeof fn === 'function' && store.renderers.indexOf(fn) < 0) store.renderers.push(fn);
}
export function setView(v) { store.view = v; }
"""
    t = t.replace("/* ---- 全局状态 ---- */", "")
    t = t.replace(HEADERS["js/state.js"] + "\n" + "\n", "")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        HEADERS["js/state.js"] + store_def + "\n" + t[t.index("/* ---------------- 状态刷新"):]
        if "/* ---------------- 状态刷新" in t else t)
    print("  state.js 已补上 store / registerRender 定义")


if __name__ == "__main__":
    main()
