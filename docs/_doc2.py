# -*- coding: utf-8 -*-
"""把这一轮(第二批需求)的改动追加到 docs/计划.md。"""
import io

P = r"D:\Unity阅读器\docs\计划.md"
TEXT = """

---

# 第二批:改名 Lyra / 代码拆分 / 界面瘦身 / AI 计费 / 窗口主题 / 右键菜单

玩家一次又提了 11 条,按条记录。

## 1) 产品改名 → **Lyra**(图标同时换成简洁风)

- 只改**玩家看得见的**:窗口标题、网页标题与侧栏品牌、安装程序/卸载程序里的名字、
  exe 名(`Lyra.exe` / `卸载 Lyra.exe` / `Lyra 安装程序.exe`)、关于页文字。
- **故意不改**的内部名(改了就破坏已经装好的东西):
  · 游戏目录里的 `_聆阅_已安装清单.json`、`_聆阅_注入代理.json`、`*.bak_聆阅`
    —— 换了名字,老安装会被当成"没装",玩家的 LDC 得重装一遍;
  · `%LOCALAPPDATA%\\LingYueReader\\voices` —— 玩家下载的语音包在这里;
  · 默认安装目录(`D:\\聆阅`):不动它,老配置/AI Key/角色配音/规则全都还在。
- 图标重做(`installer/make_icon.py`):去掉上一版的高光,改成**扁平渐变底 + 白色对话气泡
  (里面三道声波)** —— 缩到 16px 还能看出是"说话",并导出 `icon-preview-small.png`
  自检(16/32/48/64 放大对照)。

## 2) 前端拆成模块(以前 3 个文件各几十 KB,没法读)

```
index.html                骨架:侧栏 / 顶栏 / 各页容器 / 弹窗
css/tokens.css            设计令牌(颜色/圆角/阴影/动效)
css/themes.css            明亮 / 护眼 / MD3 三套主题
css/layout.css            外壳布局 + 自适应断点
css/components.css        按钮/开关/滑条/输入/芯片/面板/弹窗/提示/列表
css/views.css             各页专属
css/extra.css             右键菜单 / 隐藏外观的滑条 / 启动错误条
js/core.js                DOM 取值、请求、提示、弹窗、主题
js/state.js               全局状态 + 0.4 秒刷新循环 + 渲染器注册表
js/ui/charts.js           底栏曲线与声波
js/ui/contextmenu.js      右键菜单
js/boot.js                导航、顶栏、底栏、启动
js/views/{library,cast,rules,logs,translate,settings,settings_extra}.js
```
- 加一个页面只要新建 `views/xxx.js` 并 `registerRender()` —— 不用回头改 state.js。
- **顺手删掉 84 条死规则**(老版"截图识别"时代的样式:`.shot-wrap`/`.region-stage`/
  `.gc-pin`/`.hotkey-row`/`.voice-acts`… 56 个类已经没人引用)。
- 踩到的坑:模块加载失败时页面**白屏且没有任何提示**(ES 模块一个 import 路径写错,
  整个页面就静默不工作)。现在 index.html 里有一段内联自检脚本:任何脚本错误、
  未处理的 Promise 异常、或 3 秒后还没启动,都会在页面底部弹出红色说明条。

## 3) 「角色配音」页瘦身(玩家:只留下载语音包)

- 角色配音页现在只有:**下载语音包** + 每个角色的配音表 + 默认配音 + 出现过的角色。
- 全局声音(下拉选一个)、语速、声线、音量、自动朗读、念角色名 → 全部搬到**设置页的「朗读」面板**。
- 滑条按要求**去掉可视外观、保留拖动**:轨道和滑块全透明,只剩一条 26px 高的可拖区域
  (鼠标移上去变左右箭头,类名 `.bare`,CSS 在 `extra.css`)。

## 4) AI 配置统一收到「设置 → AI 助手」

以前过滤规则页和翻译页各有一份接口地址/模型/Key,改一处忘一处。现在只有设置页一份,
两处功能都读它。

## 5) AI 用量与花费

- `core/ai.py` 现在**累计**每次调用的 prompt/completion token(`total_usage()`),并给了
  `estimate_cost()`:照玩家填的"元 / 百万 token"单价换算。
- 设置页显示:累计调用次数、累计 token、输入/输出分开、**估算花费 ¥x.xxx**、最近一次用量,
  单价两个输入框可改(各家各时期价格不同,写死会过期;默认给的是 DeepSeek 常见档位)。
- 接口:`GET /api/ai/usage`、`POST /api/ai/reset-usage`。

## 6) 切主题时 Windows 窗口颜色也跟着变

以前网页换成明亮/护眼,原生窗口自己还是黑的(玩家反馈)。现在:
- 网页切主题时 `chrome.webview.postMessage({type:"theme",dark,bg})`;
- `player.cpp` 收到后:① `ICoreWebView2Controller2::put_DefaultBackgroundColor`(网页还没画出来时露的底色)
  ② 窗口类背景刷 ③ `DwmSetWindowAttribute`:标题栏明暗 + 标题/边框颜色;
- 启动时也先按暗色设一遍。

## 7) 右键菜单换成自己的

浏览器默认菜单(后退/刷新/检查元素)在桌面应用里很突兀。现在统一拦截,按点到的对象给菜单:
- 剧情句 / 日志条目:朗读这句、复制原文、**加入白名单/黑名单**、标成"不是剧情";
- 输入框:剪切/复制/粘贴/全选;
- 游戏卡片:启动、复制路径;
- 空白处:停止朗读、刷新界面、在浏览器里打开。

## 8) 顺手修掉的两个真 bug

- **`/api/voices/reload`(重载引擎)一直是个空操作**:它调的是 `voices.rescan()`,而这个函数
  根本不存在 → 改成 `clear_cache()`。
- **Edge 语音列表里凭印象加了两个不存在的音色**(Yunfeng/Yunze):用 `edge_tts.list_voices()`
  实测 zh-CN 男声只有 4 个,已删掉这两个假条目。

## 9) 男声包:实测结论与目录更新(第二批)

- 三个标着"男声"的 `vits-zh-hf-*`(禅雅塔/毁灭战士/阿比西尼亚)**默认音色实测是女声**
  (F0 296/267/330Hz),而且真实说话人数是 804 不是 1 —— 已从目录里删掉。
- 换上 4 个**实测 sid=0 就是男声**的 `fanchen-*`(沉稳男声·文 118Hz / UNITY 112Hz /
  智慧老者 117Hz / 老者新版 115Hz),外加一个「五音色·三男声」(5 个音色里 3 个男声,
  靠 `speaker_gender` 表只列男声)。
- **AISHELL3 的男声表修了三处错**:去掉 72/136/156(实测 172/207/169Hz,其实是女声)、
  去掉 98/102(151/163Hz 临界,换句长就飘到女声侧)、补上漏掉的 52/100。
  玩家当前用的 `aishell3#46`(146.8Hz)是真男声,不受影响。
"""
t = io.open(P, encoding="utf-8").read().rstrip("\n")
io.open(P, "w", encoding="utf-8", newline="\n").write(t + "\n" + TEXT)
print("已追加,现在", len((t + TEXT).split(chr(10))), "行")
