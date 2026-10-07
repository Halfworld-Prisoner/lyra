# ============================================================================
# 构建「便携运行时」installer\runtime.zip
#
# 内容 = 官方嵌入式 Python 3.13(可重定位,不含绝对路径)
#        + requirements.txt 里的全部依赖(直接装进嵌入式 Python)
#
# 这样安装程序只需解压,不跑 pip、不连网。
# 只需在构建阶段联网一次;产物缓存到 installer\build\runtime,重复构建会复用。
#
# 用法: powershell -ExecutionPolicy Bypass -File installer\build_runtime.ps1 [-Force]
# ============================================================================
param([switch]$Force)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$inst = Join-Path $root "installer"
$stage = Join-Path $inst "build\runtime"
$pyDir = Join-Path $stage "python"
$pyExe = Join-Path $pyDir "python.exe"
$zipOut = Join-Path $inst "runtime.zip"
$req = Join-Path $root "requirements.txt"

$needBuild = $Force -or -not (Test-Path $pyExe) -or -not (Test-Path $zipOut)
if (-not $needBuild) {
    # requirements.txt 更新过就重建
    if ((Get-Item $req).LastWriteTime -gt (Get-Item $zipOut).LastWriteTime) { $needBuild = $true }
}
if (-not $needBuild) {
    Write-Host "运行时已就绪(复用):$zipOut  ($([math]::Round((Get-Item $zipOut).Length/1MB,1)) MB)"
    return
}

Write-Host "=== 构建便携运行时(构建阶段联网一次)==="
if ($Force) { Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null

# 1) 嵌入式 Python
if (-not (Test-Path $pyExe)) {
    $ver = $null
    foreach ($v in @("3.13.15","3.13.14","3.13.13","3.13.12","3.13.11","3.13.10","3.13.9","3.13.8","3.13.7")) {
        $url = "https://www.python.org/ftp/python/$v/python-$v-embed-amd64.zip"
        $tmp = Join-Path $inst "build\py-embed.zip"
        Write-Host "  下载 $v …"
        try {
            Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 120
            if ((Get-Item $tmp).Length -gt 5MB) { $ver = $v; break }
        } catch { }
    }
    if (-not $ver) { throw "嵌入式 Python 下载失败" }
    Write-Host "  解压 Python $ver"
    & tar.exe -xf (Join-Path $inst "build\py-embed.zip") -C $pyDir
    Remove-Item (Join-Path $inst "build\py-embed.zip") -Force -ErrorAction SilentlyContinue

    # 2) 启用 site-packages
    Set-Content -Path (Join-Path $pyDir "python313._pth") -Value @(
        "python313.zip", ".", "Lib\site-packages", "import site"
    ) -Encoding ASCII
}

# 3) pip
if (-not (Test-Path (Join-Path $pyDir "Lib\site-packages\pip"))) {
    Write-Host "  安装 pip …"
    $getpip = Join-Path $pyDir "get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip -UseBasicParsing -TimeoutSec 120
    & $pyExe $getpip --no-warn-script-location --disable-pip-version-check
    Remove-Item $getpip -Force -ErrorAction SilentlyContinue
}

# 4) 全部依赖
Write-Host "  安装依赖(约 3~6 分钟)…"
& $pyExe -m pip install -r $req --disable-pip-version-check --no-warn-script-location --retries 5 --timeout 60
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

$code = @'
import sys
try:
except Exception as e:
    print("models skip:", e)
'@
$tmpPy = Join-Path $inst "build\_predl.py"
Set-Content -Path $tmpPy -Value $code -Encoding UTF8
& $pyExe $tmpPy
Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue

# 6) 清理缓存/多余文件后打包
Write-Host "  清理并打包 …"
foreach ($p in @("Lib\site-packages\pip\_internal\network\auth.py")) { }
Get-ChildItem $pyDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $pyDir "get-pip.py") -Force -ErrorAction SilentlyContinue

Remove-Item $zipOut -Force -ErrorAction SilentlyContinue
& tar.exe -a -c -f $zipOut -C $stage "python"
if (-not (Test-Path $zipOut)) { throw "运行时打包失败" }

$mb = [math]::Round((Get-Item $zipOut).Length / 1MB, 1)
$rawMB = [math]::Round((Get-ChildItem $pyDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "运行时打包完成:$zipOut"
Write-Host "  压缩前 $rawMB MB → 压缩后 $mb MB"
