# tools/ —— 开发脚本

这些脚本是开发时用来**验证功能**的,不参与运行,也不需要打包进安装包。都假设你在仓库根目录执行。

| 脚本 | 作用 |
|---|---|
| `reader_test.py` | 过滤与日志解析自检:喂入各种"游戏日志行",检查是否被判成剧情、黑名单是否生效 |
| `float_test.py` | 把悬浮窗的 8 种状态 × 2 种形态 × 4 套主题渲染成总览图,肉眼检查配色 |
| `shot.py` | 按窗口标题/进程名截某个窗口(`PrintWindow`,不需要窗口在最前) |
| `shot_pid.py` | 同上,但按 **PID** 找窗口 —— 装机器这类自绘窗口用这个更稳 |
| `vtest.py` | 打开内置的界面探针页(`tools/probe.html`),按视图/主题/宽度批量截图 |
| `deploy.py` | 把源码热同步到已安装目录并重启应用(开发时改一行就能看效果) |
| `probe.html` | 界面探针:在一个 iframe 里按 `?v=视图&t=主题&w=宽度` 加载主界面,便于截图对比 |

## 例子

```powershell
python tools/reader_test.py
python tools/float_test.py
python tools/shot_pid.py 12345 docs/images/window.png
python tools/vtest.py            # 需要先启动应用(默认 127.0.0.1:8890)
python tools/deploy.py          # 默认同步到 D:\Lyra\app
```

> `deploy.py` / `probe.html` 里的路径默认按本机开发环境写(`D:\Unity阅读器`、`D:\Lyra`),
> 换机器请先改文件开头的常量。
