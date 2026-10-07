# ============================================================================
# 编译 StoryHook(Mono 版 BepInEx 插件)并把产物同步到 hooks/ 与 payload/
#   用法: powershell -ExecutionPolicy Bypass -File hooks\mono\build_plugin.ps1
# ============================================================================
$ErrorActionPreference = 'Stop'
# 用 $PSScriptRoot 定位项目根(比 $MyInvocation 可靠,尤其在 -File 调用时)
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
$root = Split-Path -Parent (Split-Path -Parent $here)      # ...\Unity阅读器
if (-not (Test-Path (Join-Path $root 'hooks\mono\StoryHook.cs'))) {
    throw "定位项目根失败:$root"
}
$src  = Join-Path $root 'hooks\mono\StoryHook.cs'
$out  = Join-Path $root 'hooks\mono\StoryHook.dll'
$t    = Join-Path $env:TEMP 'lingyue_plugin'
$csc  = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'

New-Item -ItemType Directory -Force -Path $t | Out-Null
Copy-Item $src (Join-Path $t 'StoryHook.cs') -Force

# 引用:BepInEx 用 payload 里的(游戏不一定还装着),Unity 的用任意一个 Mono Unity 游戏里的
$payload = Join-Path $root 'payload\mono_x64'
$refs = @(
    (Join-Path $payload 'BepInEx\core\BepInEx.dll'),
    (Join-Path $payload 'BepInEx\core\0Harmony.dll')
)
$cands = @(
    'd:\steam\steamapps\common\KnightsCollege\KnightsCollege_Data\Managed',
    'D:\Steam\steamapps\common\Threefold Recital 三相奇谈\ThreefoldRecital_Data\Managed'
)
$managed = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($managed) {
    foreach ($f in @('UnityEngine.dll','UnityEngine.CoreModule.dll','UnityEngine.UI.dll','netstandard.dll')) {
        $p = Join-Path $managed $f
        if (Test-Path $p) { $refs += $p }
    }
    Write-Host "  Unity 引用源: $managed"
} else {
    Write-Host "  !! 没找到 Managed 目录"
}
foreach ($r in $refs) { if (-not (Test-Path $r)) { Write-Host "  !! 缺引用: $r" } }

$dll = Join-Path $t 'StoryHook.dll'
$a = @('/target:library','/nologo',"/out:$dll",(Join-Path $t 'StoryHook.cs'))
foreach ($r in $refs) { if (Test-Path $r) { $a += "/r:$r" } }
& $csc @a
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dll)) { throw "编译失败" }
Copy-Item $dll $out -Force
Write-Host ("  插件: {0}  ({1} KB)" -f $out, [math]::Round((Get-Item $out).Length / 1KB, 1))

foreach ($pk in @('mono_x64','mono_x86')) {
    $dst = Join-Path $root "payload\$pk\BepInEx\plugins\StoryHook.dll"
    if (Test-Path (Split-Path $dst -Parent)) {
        Copy-Item $dll $dst -Force
        Write-Host "  已同步 -> payload\$pk\BepInEx\plugins\StoryHook.dll"
    }
}
Write-Host "完成(装到游戏里要重启游戏才生效)"
