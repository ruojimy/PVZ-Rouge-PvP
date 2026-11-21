param([string[]]$Targets=@('PvZPvPNative'),[string]$Log='test_results/pvp75/build.log',[int]$Jobs=6)
# PvP75 local build helper: VS2022 CMake on build/app-typed72-v2 (same tree as 74.4 r4).
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
foreach($k in @('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')){Remove-Item "Env:$k" -ErrorAction SilentlyContinue}
$env:VSLANG='1033'
$env:_CL_='/FS'
New-Item -ItemType Directory -Force (Split-Path $Log -Parent) | Out-Null
$args2=@('--build','build/app-typed72-v2','--config','Release')
foreach($t in ($Targets -join ',').Split(',')){if($t){$args2+=@('--target',$t)}}
$args2+=@('--',"/m:$Jobs",'/nologo')
& $cmake @args2 2>&1 | Out-File -FilePath $Log -Encoding utf8
$code=$LASTEXITCODE
Get-Content $Log | Select-String -Pattern ' error |error C|error LNK|FAILED|warning C4715' | Select-Object -First 40 | ForEach-Object { $_.Line }
"exit=$code"
exit $code
