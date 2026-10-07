# ============================================================================
# 编译「窗口宿主」installer\player.exe(原生窗口内嵌网页,WebView2)
#
#  - 若缺 WebView2 SDK,会自动从 NuGet 下载一次(构建阶段联网,产物缓存复用)
#  - WebView2Loader.dll 会被内嵌进 player.exe(桌面只放一个 exe 即可运行)
#
# 用法: powershell -ExecutionPolicy Bypass -File installer\build_player.ps1 [-Force]
# ============================================================================
param([switch]$Force)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$inst = Join-Path $root "installer"
$build = Join-Path $inst "build"
$sdk = Join-Path $build "webview2"
$inc = Join-Path $sdk "build\native\include"
$out = Join-Path $inst "player.exe"
New-Item -ItemType Directory -Force -Path $build | Out-Null

# 1) 确保 WebView2 SDK 存在
if ($Force -or -not (Test-Path (Join-Path $inc "WebView2.h"))) {
    Write-Host "  下载 WebView2 SDK …"
    $idx = & curl.exe -s --max-time 60 "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/index.json"
    $ver = ($idx | ConvertFrom-Json).versions | Where-Object { $_ -notmatch '-' } | Select-Object -Last 1
    if (-not $ver) { throw "无法获取 WebView2 SDK 版本(检查网络)" }
    $zip = Join-Path $build "webview2.nupkg"
    & curl.exe -sL --max-time 300 -o $zip "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$ver/microsoft.web.webview2.$ver.nupkg"
    if (-not (Test-Path $zip)) { throw "WebView2 SDK 下载失败" }
    Remove-Item -Recurse -Force $sdk -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $sdk | Out-Null
    & tar.exe -xf $zip -C $sdk
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Write-Host "  SDK $ver 就绪"
} else {
    Write-Host "  SDK 已就绪(复用)"
}
if (-not (Test-Path (Join-Path $inst "WebView2Loader.dll"))) {
    Copy-Item (Join-Path $sdk "build\native\x64\WebView2Loader.dll") $inst -Force
}

# 2) 编译
Write-Host "  编译窗口宿主 …"
Push-Location $inst
try {
    & windres "player.rc" -O coff -o (Join-Path $build "player.res")
    if ($LASTEXITCODE -ne 0) { throw "windres 编译 player.rc 失败" }
    & g++ "player.cpp" (Join-Path $build "player.res") -o $out `
        -O2 -municode -mwindows -static-libgcc -static-libstdc++ `
        -I "compat" -I $inc `
        -lole32 -loleaut32 -luuid -lshlwapi -lwinhttp -lshell32 -ladvapi32
    if ($LASTEXITCODE -ne 0) { throw "g++ 编译 player.cpp 失败" }
} finally { Pop-Location }

Write-Host ("  窗口宿主: {0}  ({1} KB)" -f $out, [math]::Round((Get-Item $out).Length / 1KB))
