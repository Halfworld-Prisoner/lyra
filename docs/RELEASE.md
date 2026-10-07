# 发布流程(GitHub Release)

面向维护者。玩家视角的安装说明在 [README](../README.md)。

## 一、准备版本号

1. 改 `installer/setup.c` 里的 `APP_VERSION`(界面右上角显示的版本);
2. 在 `CHANGELOG.md` 顶部加一节;
3. 提交:`git commit -am "chore: bump version to x.y.z"`。

## 二、构建安装包

```powershell
# 1) 编译两个游戏内插件(需要 .NET SDK)
powershell -File hooks/mono/build.ps1
powershell -File hooks/il2cpp_src/build.ps1

# 2) 确认 voices/ 有内置语音包、payload/ 有第三方载荷(见各自 README)

# 3) 打包(首次会自动下载 WebView2 SDK 并构建便携运行环境,耗时较久)
powershell -File installer/build.ps1
```

产物:`Lyra 安装程序.exe`(单文件,约 130 MB;既是安装程序,装好后也是启动器)。

自检建议:

```powershell
# 装到临时目录跑一遍
.\"Lyra 安装程序.exe" --install "$env:TEMP\lyra_test"
# 再卸一遍,确认目录被清干净
& "$env:TEMP\lyra_test\卸载 Lyra.exe" --quiet
```

## 三、打标签并上传

```powershell
git tag -a v1.0.0 -m "Lyra 1.0.0"
git push origin main --tags
```

在 GitHub 上:**Releases → Draft a new release**

| 字段 | 填什么 |
|---|---|
| Tag | 选刚推上去的 `v1.0.0` |
| Title | `Lyra 1.0.0` |
| Describe | 把 CHANGELOG 里这一节贴过来(玩家看得懂的话) |
| Attach binaries | 上传 `Lyra 安装程序.exe`(GitHub 单文件上限 2 GB,没问题) |

**不要**把 exe 提交进仓库 —— 它已在 `.gitignore` 里,体积会让 clone 变得很痛苦。

## 四、发布检查清单

- [ ] 全新机器上装一遍:能启动、能出声、游戏卡片能装 LDC
- [ ] 卸载一遍:目录清干净,游戏与存档未受影响
- [ ] README 的截图与文字和实际界面一致
- [ ] `CHANGELOG.md`、`APP_VERSION`、Release 标题三处版本号一致
- [ ] 仓库里没有任何 API Key(`grep -r "sk-" .` 应为空)
