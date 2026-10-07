# Lyra · Unity 游戏朗读器

<p align="center">
  <img src="docs/images/logo-256.png" width="112" alt="Lyra">
</p>

<p align="center">
  <b>把游戏里的文字念出来 —— 离线朗读 · 角色配音 · AI 实时汉化 · 不改游戏文件</b>
</p>

<p align="center">
  <a href="../../releases/latest"><img alt="下载" src="https://img.shields.io/badge/下载-Lyra%20安装程序-7C5CFF?style=for-the-badge"></a>
  <img alt="平台" src="https://img.shields.io/badge/平台-Windows%2010%2F11-0078D4?logo=windows">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="引擎" src="https://img.shields.io/badge/Unity-Mono%20%7C%20IL2CPP-000000?logo=unity">
  <img alt="许可" src="https://img.shields.io/badge/许可-MIT-3DA639">
  <img alt="离线" src="https://img.shields.io/badge/离线可用-是-2F9E63">
</p>

---

Lyra 是给 **Unity 视觉小说 / ADV 游戏**用的桌面朗读器:它从游戏内部**读出**正在显示的文字,用**本机语音**念出来,还能顺手用 AI 把外文**实时翻成简体中文**写回画面。全程不截图、不 OCR、不改动游戏文件。

> 名字取自天琴座(Lyra)。项目早期叫「聆阅」,现已改名 —— 数据目录做了兼容,老用户升级不会丢设置。

![游戏库](docs/images/01_游戏库.png)

![实时剧情朗读](docs/images/02_实时剧情.png)

## 下载安装

到 **[Releases](../../releases/latest)** 下载 `Lyra 安装程序.exe` 双击即可 —— 约 130 MB 的**离线安装包**,已内置便携 Python 运行环境与语音包,安装过程不需要联网。

装好后:打开 Lyra → 在游戏卡片上点 **「安装 LDC」** → 点「启动游戏」→ 进游戏看到对话,它就会开始念。

> 安装程序与卸载程序同样是网页界面(WebView2 渲染;机器上没有 WebView2 时自动回退系统界面):

![安装程序](docs/images/安装器_网页版.png)

**卸载**:运行安装目录里的 `卸载 Lyra.exe`。它只删自己,**不会动你的游戏与存档**;已经装进游戏里的 LDC 想清掉,在 Lyra 里对每个游戏点「卸载 LDC」。

## 功能

| | |
|---|---|
| **游戏库** | 自动列出 Steam / 桌面上的 Unity 游戏,识别 Mono / IL2CPP 与位数,一键启动、一键装挂钩 |
| **LDC 剧情挂钩** | 自研 BepInEx 插件(Mono 与 IL2CPP 双版本),代理 DLL 注入,不改游戏文件 |
| **实时剧情朗读** | 文字一出现就念;语速、音高、音量可调,界面文字自动跳过 |
| **角色配音** | 按说话人自动切换音色,每个角色单独指定声音 |
| **离线语音包** | 内置男声「超文」,可下载更多男声包(sherpa-onnx),全部本机推理 |
| **文本翻译** | 接入任意 OpenAI 兼容接口(如 DeepSeek),只替换外文;可选"译文也念出来" |
| **AI 用量统计** | 记录 token 与估算花费,单价可自己填 |
| **过滤规则** | 通用规则 + 每款游戏专用规则(内置 UTAGE、三相奇谈、Astatos 等档案) |
| **黑白名单** | 日志里点一句即可加白(一定念)或拉黑;AI 也能代你加过滤词 |
| **自动下一句** | 念完自动推进剧情:**静默方式**(不动鼠标)为主,失败自动退回点击兜底 |
| **悬浮窗** | 置顶小条:状态、当前台词、内存与读取速度;胶囊 / 卡片两种形态 |
| **主题** | 暗夜 / 明亮 / 护眼 / **Material 3**(按官方设计令牌实现),窗口与悬浮窗一起变色 |

更多界面截图见 **[截图集](docs/SCREENSHOTS.md)**。

## 工作原理

```
┌──────────────────────── 游戏进程 ────────────────────────┐
│  Unity 游戏  →  LDC 剧情挂钩(BepInEx 插件)               │
│                    │ 抓 TextMeshPro / UTAGE 的文本接口    │
└────────────────────┼─────────────────────────────────────┘
                     │ 插件日志(制表符分隔:type / method / text)
                     ▼
        ┌──────────  Lyra 主程序(Python + WebView2)  ──────────┐
        │  过滤判定  →  黑白名单  →  角色识别                    │
        │      ├─ 朗读:sherpa-onnx / Windows SAPI / Edge TTS   │
        │      └─ 翻译:AI 接口 → 写回游戏画面(XUnity 通道)      │
        │  悬浮窗 / 实时剧情 / 日志  ← 状态回传                  │
        └──────────────────────────────────────────────────────┘
                     │ 静默推进:写请求文件 + 读回执
                     ▼
              游戏内部 InputSendMessage(不动鼠标)
```

Unity 游戏显示文字时一定会调用引擎的文本接口,Lyra 就在这些接口上"蹲点":拿到文字 → 判断是不是剧情 → 念出来 / 翻译后再写回去。因为不碰游戏资源,所以卸载干净,也不需要管理员权限。

引擎适配的勘察记录(例如 UTAGE 的静默推进是怎么找到入口的)放在 [`docs/dev/`](docs/dev/)。

## 从源码构建

| 需要 | 说明 |
|---|---|
| Windows 10/11 x64 | |
| Python 3.11+ | 构建脚本用它打包与生成图标 |
| MinGW-w64 (gcc / g++) | 编译窗口宿主、安装器、卸载器 |
| .NET SDK 6+ | 编译两个游戏内插件 |
| WebView2 SDK | 首次构建自动下载到 `installer/build/webview2/` |

```powershell
git clone https://github.com/Halfworld-Prisoner/lyra.git
cd lyra

# 1) 准备两个大目录(不进 Git 仓库,说明见各自的 README):
#    voices/   内置离线语音包         voices/README.md
#    payload/  BepInEx 与翻译插件载荷  payload/README.md

# 2) 编译游戏内插件
powershell -File hooks/mono/build.ps1
powershell -File hooks/il2cpp_src/build.ps1

# 3) 打包安装程序(产物:Lyra 安装程序.exe)
powershell -File installer/build.ps1
```

静默安装:`"Lyra 安装程序.exe" --install D:\Lyra`

## 项目结构

```
lyra/
├── core/          朗读引擎核心(日志解析 / 过滤 / TTS / 翻译 / 游戏扫描 / 悬浮窗)
├── webapp/        主界面:Python 后端 + 原生 HTML/CSS/JS(6 份样式 + 10 个模块)
├── hooks/         游戏内插件(C#):mono/ 与 il2cpp_src/ 双版本
├── installer/     安装包构建:Win32 + WebView2 网页界面(player.cpp / setup.c / uninstall.c)
├── tools/         开发脚本:截图、悬浮窗渲染、过滤自检、热部署
├── docs/          文档、截图、开发记录、发布流程
└── config.example.json   配置示例(复制成 config.json 使用)
```

## 常见问题

**一定要联网吗?** 不用。朗读、语音包、界面都在本机;只有你主动打开「文本翻译」并填了 AI 接口时才联网。

**游戏不出声 / 认不出来?** 先看「日志」页有没有文字进来。没有的话:① 确认是 Unity 引擎;② 在游戏卡片上点过「安装 LDC」;③ 重启一次游戏(IL2CPP 首次注入会慢几秒)。

**静默推进没反应?** 各引擎的输入入口不同。内置了 UTAGE 的自适应,其它引擎会**自动退回**"移动鼠标点一下"的兜底方式(可在设置里关闭)。

**装到别的盘 / U 盘行吗?** 行,卸载器跟着程序走;它只删自己所在目录 + 快捷方式 + 注册表项,并且要目录里同时存在两个以上 Lyra 特征文件才肯删。

**设置在哪?** `<安装目录>\app\config.json`;下载的语音包在 `%LOCALAPPDATA%\Lyra\voices`(卸载不删)。

## 第三方组件

本仓库只包含 Lyra 自身源码。运行时依赖的第三方组件由安装包携带或构建脚本下载,遵循各自许可:

[BepInEx](https://github.com/BepInEx/BepInEx)(LGPL-2.1) ·
[XUnity.AutoTranslator](https://github.com/bbepis/XUnity.AutoTranslator)(MIT) ·
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)(Apache-2.0) ·
[WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)(微软可再发行条款) ·
[Pillow](https://python-pillow.org/)(MIT-CMU) · 语音包见 [`voices/README.md`](voices/README.md)

## 开发

- 开发日志与决策记录:[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- 发布流程(打包 → 打标签 → 上传 Release):[`docs/RELEASE.md`](docs/RELEASE.md)
- 更新日志:[`CHANGELOG.md`](CHANGELOG.md)
- 自检脚本:`python tools/reader_test.py`、`python tools/float_test.py`

## 免责声明

本项目仅供**个人学习与无障碍辅助**使用:帮助阅读困难或语言不通的玩家理解游戏内容。请在你拥有合法授权的游戏上使用,并遵守各游戏的用户协议。作者不对因使用本工具产生的任何后果负责。游戏名称、角色与相关素材版权归各自权利人所有。
