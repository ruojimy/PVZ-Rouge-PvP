$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$taskOutput=Join-Path $taskRoot 'test_results/typed72-20261105/room-work'
$reference=Join-Path $taskOutput 'reference'
New-Item -ItemType Directory -Path $reference -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $taskRoot 'tools/typed72') -File -Filter '*.py' | Copy-Item -Destination $reference -Force
foreach($name in @('verify_native_tick.py','verify_room.py')){
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $reference -Force
}
foreach($file in Get-ChildItem -LiteralPath $reference -File -Filter '*.py'){
    $body=[IO.File]::ReadAllText($file.FullName)
    $body=[regex]::Replace($body,'(?m)^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parents\[2\]\s*$',('ROOT = Path(r"'+$taskRoot+'")'))
    [IO.File]::WriteAllText($file.FullName,$body,[Text.UTF8Encoding]::new($false))
}
$pins=[ordered]@{}
Get-ChildItem -LiteralPath $reference -File | Sort-Object FullName | ForEach-Object{$pins[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pins|ConvertTo-Json -Depth 3|Set-Content -LiteralPath (Join-Path $taskOutput 'reference-pins.json') -Encoding utf8
Write-Output $reference
