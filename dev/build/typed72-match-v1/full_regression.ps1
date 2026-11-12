param([string]$Tag)
# Full typed72 regression on the fixed 58-scenario list: simulation (batch_compare), native frames
# and room snapshots. Frozen V references are copied from frames-f7 / snap-s3 (never modified);
# every result goes to new directories tagged $Tag. Run serially (compiler/memory limits).
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$res="$root\test_results\typed72-20261108"
$py='C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe'
$names=(Get-ChildItem "$res\frames-f7" -Filter '*.cmp.json' | ForEach-Object { $_.Name -replace '\.cmp\.json$','' } | Sort-Object)
"scenarios=$($names.Count)"
# 1. simulation (tick-for-tick against the V journal)
Set-Location -LiteralPath $root; $env:PYTHONIOENCODING='utf-8'
"== sim $Tag"
& $py build/typed72-match-v1/batch_compare.py "sim-$Tag" 3 ($names -join ',') | Select-Object -Last 3
& $py build/typed72-match-v1/show_batch.py "sim-$Tag" 80
# 2. native frames
"== frames $Tag"
$fo="$res\frames-$Tag"; New-Item -ItemType Directory -Force $fo | Out-Null
foreach($n in $names){ Copy-Item "$res\frames-f7\$n.frames.jsonl" $fo }
& "$PSScriptRoot\frames_batch.ps1" $Tag ($names -join ',')
# 3. room snapshots
"== snapshots $Tag"
$so="$res\snap-$Tag"; New-Item -ItemType Directory -Force $so | Out-Null
foreach($n in $names){ if(Test-Path "$res\snap-s3\$n.snap.jsonl"){Copy-Item "$res\snap-s3\$n.snap.jsonl" $so} }
& "$PSScriptRoot\snap_batch.ps1" $Tag ($names -join ',')
"== done $Tag"
