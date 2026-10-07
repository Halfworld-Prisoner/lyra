# ============================================================================
# 构建「Lyra 安装程序.exe」——单文件、带图标、**离线安装**
#   0) 准备便携运行环境(嵌入式 Python 3.13 + 依赖)→ runtime.zip
#   1) 生成图标(installer/icon.ico)
#   2) 打包应用负载(core/ webapp/ config.py requirements.txt)→ installer/payload.zip
#   3) 编译资源(图标 + 清单 + 负载 + 运行环境)→ build/app.res
#   4) gcc 编译 setup.c → 单文件 exe(改名成中文名)
#
# 用法: powershell -ExecutionPolicy Bypass -File installer\build.ps1
#       (步骤 0 只在首次构建/依赖更新时需要联网,之后会复用缓存)
# ============================================================================
param(
    [string]$OutName = "Lyra 安装程序.exe",
    [string]$Python = "",
    [switch]$ForceRuntime
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # D:\读器工具
$inst = Join-Path $root "installer"
$wvInc = Join-Path $inst "build\webview2\build\native\include"   # WebView2 SDK 头文件(安装器/卸载器要用)
$build = Join-Path $inst "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null

Write-Host "=== 0/5 准备便携运行环境(内嵌,安装时无需联网)==="
$rtArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $inst "build_runtime.ps1"))
if ($ForceRuntime) { $rtArgs += "-Force" }
# 注意:build_runtime 里会跑 pip / python,它们往 stderr 写 INFO 日志;
# PowerShell 5.1 在 $ErrorActionPreference="Stop" 下会把原生命令的 stderr 当成错误直接终止构建,
# 所以这里先降到 Continue,并且只按"退出码 + runtime.zip 是否存在"判断成败。
$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell.exe @rtArgs 2>&1 | ForEach-Object { if ("$_" -match '^\s*(===|完成|已|安装|下载|准备|打包|使用)') { Write-Host "  $_" } }
$rtCode = $LASTEXITCODE
$ErrorActionPreference = $old
if ($rtCode -ne 0) { throw "便携运行环境构建失败(退出码 $rtCode)" }
if (-not (Test-Path (Join-Path $inst "runtime.zip"))) { throw "runtime.zip 未生成" }

Write-Host "=== 1/5 生成图标 + 编译窗口宿主 ==="
$py = $Python
if (-not $py) {
    foreach ($c in @((Join-Path $root ".venv\Scripts\python.exe"),
                     (Join-Path $root "runtime\venv\Scripts\python.exe"),
                     (Join-Path $root "runtime\python\python.exe"))) {
        if (Test-Path $c) { $py = $c; break }
    }
}
if (-not $py) { $py = "python" }
& $py (Join-Path $inst "make_icon.py")
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $inst "build_player.ps1")
if (-not (Test-Path (Join-Path $inst "player.exe"))) { throw "player.exe 未生成" }

# 卸载器(独立 exe,安装时释放到安装目录)
Write-Host "  编译卸载器 …"
$unRes = Join-Path $build "uninstall.res"
Push-Location $inst
try {
    & windres "uninstall.rc" -O coff -o $unRes
    if ($LASTEXITCODE -ne 0) { throw "windres 编译卸载器资源失败" }
} finally { Pop-Location }
& g++ (Join-Path $inst "uninstall.c") $unRes -o (Join-Path $inst "uninstall.exe") `
    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `
    -I "$inst\compat" -I "$wvInc" `
    -lcomctl32 -lole32 -loleaut32 -luuid -lshell32 -lshlwapi -ladvapi32
if ($LASTEXITCODE -ne 0) { throw "gcc 编译卸载器失败" }
if (-not (Test-Path (Join-Path $inst "uninstall.exe"))) { throw "uninstall.exe 未生成" }
Write-Host ("  卸载器: {0} KB" -f [math]::Round((Get-Item (Join-Path $inst "uninstall.exe")).Length / 1KB))

Write-Host "=== 2/5 打包应用负载 ==="
$payload = Join-Path $inst "payload.zip"
Remove-Item $payload -Force -ErrorAction SilentlyContinue
$items = @("core", "webapp", "hooks", "payload", "voices", "config.py", "requirements.txt", "README.md")
$existing = $items | Where-Object { Test-Path (Join-Path $root $_) }
& tar.exe -a -c -f $payload -C $root @existing
if (-not (Test-Path $payload)) { throw "负载打包失败" }
$mb = [math]::Round((Get-Item $payload).Length / 1MB, 2)
Write-Host ("  负载大小: {0} MB  (内容: {1})" -f $mb, ($existing -join ", "))

Write-Host "=== 3/5 编译资源(图标/清单/负载) ==="
$res = Join-Path $build "app.res"
Push-Location $inst
try {
    & windres "app.rc" -O coff -o $res
    if ($LASTEXITCODE -ne 0) { throw "windres 编译资源失败" }
} finally { Pop-Location }

Write-Host "=== 4/5 编译 exe ==="
$tmpExe = Join-Path $build "setup.exe"
& g++ (Join-Path $inst "setup.c") $res -o $tmpExe `
    -x c++ -O2 -municode -mwindows -static-libgcc -static-libstdc++ -fpermissive -w `
    -I "$inst\compat" -I "$wvInc" `
    -lcomctl32 -lole32 -loleaut32 -luuid -lshell32 -lshlwapi -lurlmon -ladvapi32
if ($LASTEXITCODE -ne 0) { throw "gcc 编译失败" }

$final = Join-Path $root $OutName
# 若安装器窗口正开着,它会锁住 exe(改名会失败)——先关掉
$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
           Where-Object { $_.ExecutablePath -eq $final }
if ($running) {
    Write-Host "  检测到安装程序窗口正在运行,先关闭以免文件被占用…"
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}
Remove-Item $final -Force -ErrorAction SilentlyContinue
# 刚生成的 100+MB exe 常被杀毒软件短暂占用,改名失败就重试
for ($i = 1; $i -le 10; $i++) {
    try { Move-Item -Force $tmpExe $final -ErrorAction Stop; break }
    catch {
        if ($i -eq 10) { throw "无法写入 $final(文件被占用,请关闭正在运行的安装程序后重试)" }
        Write-Host ("  文件正被占用(杀毒扫描或安装程序未关),1 秒后重试 ({0}/10)…" -f $i)
        Start-Sleep -Seconds 1
    }
}
$exeMB = [math]::Round((Get-Item $final).Length / 1MB, 2)
Write-Host "=== 5/5 完成 ==="
Write-Host ""
Write-Host "构建完成: $final  ($exeMB MB)"
Write-Host "  · 双击 = 打开安装界面(可选安装目录,默认 D 盘);装好后同一个 exe 就是启动器"
Write-Host "  · 静默安装: `"$OutName`" --install D:\Lyra"
