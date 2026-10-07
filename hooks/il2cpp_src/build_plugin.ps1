# build_plugin.ps1 -- build the IL2CPP story-hook plugin (StoryHookIl2Cpp.dll)
#
# The machine has the .NET *runtime* but no SDK, so `dotnet build` is unavailable.
# We use the in-box C# compiler (csc v4.0, C# 5) and compile straight against the
# .NET 6 assemblies that BepInEx ships inside the game's `dotnet` folder.
# Keep this file ASCII-only (PowerShell 5.1 + no-BOM = mojibake).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build_plugin.ps1 -GameDir "D:\Program Files\AnaDos"
param(
    [string]$GameDir = 'D:\Program Files\AnaDos',
    [string]$Src     = "$PSScriptRoot\StoryHookIl2Cpp.cs",
    [string]$Out     = "$PSScriptRoot\StoryHookIl2Cpp.dll"
)

$ErrorActionPreference = 'Stop'
$csc   = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$vm    = Join-Path $GameDir 'dotnet'
$core  = Join-Path $GameDir 'BepInEx\core'

if (-not (Test-Path $csc))  { throw "csc.exe not found: $csc" }
if (-not (Test-Path $Src)) { throw "source not found: $Src" }
if (-not (Test-Path $vm))   { throw "dotnet runtime folder not found: $vm (is the hook installed?)" }
if (-not (Test-Path $core)) { throw "BepInEx core not found: $core" }

$refs = @(
    (Join-Path $vm 'System.Private.CoreLib.dll'),
    (Join-Path $vm 'System.Runtime.dll'),
    (Join-Path $vm 'netstandard.dll'),
    (Join-Path $vm 'System.Collections.dll'),
    (Join-Path $vm 'System.Collections.Concurrent.dll'),
    (Join-Path $vm 'System.Threading.dll'),
    (Join-Path $vm 'System.Threading.Thread.dll'),
    (Join-Path $vm 'System.Runtime.Extensions.dll'),
    (Join-Path $vm 'System.Linq.dll'),
    (Join-Path $vm 'System.IO.FileSystem.dll'),
    (Join-Path $vm 'System.Text.Encoding.Extensions.dll'),
    (Join-Path $vm 'System.Reflection.dll'),
    (Join-Path $core 'BepInEx.Core.dll'),
    (Join-Path $core 'BepInEx.Unity.IL2CPP.dll'),
    (Join-Path $core 'BepInEx.Unity.Common.dll'),
    (Join-Path $core '0Harmony.dll'),
    (Join-Path $core 'Il2CppInterop.Runtime.dll'),
    (Join-Path $core 'Il2CppInterop.Common.dll')
)

foreach ($r in $refs) {
    if (-not (Test-Path $r)) { throw "missing reference: $r" }
}

$args = @('/nologo', '/target:library', '/nostdlib+', '/noconfig', '/langversion:5',
          '/optimize+', '/warn:0', "/out:$Out")
foreach ($r in $refs) { $args += "/r:$r" }
$args += $Src

Write-Host "== compiling $Src"
& $csc @args
if ($LASTEXITCODE -ne 0) { throw "csc failed with exit code $LASTEXITCODE" }

$f = Get-Item $Out
Write-Host ("== OK  {0}  {1} bytes" -f $f.FullName, $f.Length)

# Sanity: confirm the assembly really targets the .NET 6 System.Runtime
$bytes = [System.IO.File]::ReadAllBytes($Out)
$text  = [System.Text.Encoding]::UTF8.GetString($bytes)
foreach ($need in 'System.Runtime', '0Harmony', 'BepInEx.Unity.IL2CPP') {
    if ($text -notmatch [regex]::Escape($need)) { throw "assembly does not reference $need" }
}
Write-Host "== references look right (System.Runtime / 0Harmony / BepInEx.Unity.IL2CPP)"
