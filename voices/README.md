# voices/ —— 内置离线语音包(不进 Git 仓库)

安装包需要一个**开箱即用**的离线音色。这里放的就是它。语音模型体积在几十 MB 级别,不适合进 Git 仓库,所以只保留这份说明。

## 结构

```
voices/
└── chaowen/                 内置男声「超文」(sherpa-onnx VITS)
    ├── model.onnx           模型权重
    ├── tokens.txt           词表
    └── (可选的 lexicon.txt / dict/ 等)
```

## 怎么准备

1. 到 [sherpa-onnx 的预训练模型库](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models)挑一个**中文单说话人**模型
   (例如 `vits-zh-hf-fanchen-*` 系列),解压后把 `*.onnx` 与 `tokens.txt` 放进 `voices/chaowen/`;
2. 打包脚本会把这个目录压进安装包的负载;程序首次启动时复制到
   `%LOCALAPPDATA%\Lyra\voices\`,玩家之后下载的语音包也放在那里(卸载不删)。

## 音色挑选建议

- 只内置**男声**是刻意的取舍:项目定位是"读给你听",统一音色更好听也更省事;女声可由玩家在「角色配音」页自行下载。
- 判断某个模型是不是男声,可以看模型卡里的 `speaker` 列表与试听,或者跑一遍基频统计(本项目开发时就是这么筛的:同一条文本合成后统计 F0,110–130 Hz 判为男声)。

## 许可提醒

各语音包许可证不同(常见 Apache-2.0 / CC-BY / 非商用),**分发安装包前请确认所选模型的许可允许再分发**,并把许可证文件一并带上。
