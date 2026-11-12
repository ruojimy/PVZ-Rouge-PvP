param([string]$Name,[string]$Out='C:\Users\xiech\Downloads\PVZ_rougePvP_native\test_results\typed72-20261108\snap-s1')
# Room snapshot identity for one scenario: V battle.snapshot() (recorder v4 REF_SNAPSHOTS) vs typed MATCH_SNAPSHOTS.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
Set-Location -LiteralPath $root
$env:SDL_VIDEODRIVER='dummy';$env:SDL_AUDIODRIVER='dummy';$env:PYTHONIOENCODING='utf-8'
New-Item -ItemType Directory -Force $Out | Out-Null
$src="tools\scenarios\_expanded_$Name.json";if(-not(Test-Path $src)){$src="tools\scenarios\$Name.json"};if(Test-Path "build\typed72-match-v1\scenarios\$Name.json"){$src="build\typed72-match-v1\scenarios\$Name.json"}
if(-not (Test-Path "$Out\$Name.snap.jsonl")){
    $env:PVP_USERDATA="$Out\ud_snap_$Name";$env:REF_SNAPSHOTS="$Out\$Name.snap.jsonl"
    & build\typed72-ref-recorder-v4\build\Release\ref72_record.exe $src "$Out\$Name.snapref.jsonl" *> "$Out\$Name.snapref.log"
    Remove-Item Env:REF_SNAPSHOTS
}
$env:PVP_USERDATA="$Out\ud_cold_$Name"
& build\typed72-match-v1\build\Release\cold72_export.exe $src "$Out\$Name.cold.json" "$Out\$Name.atlas.bin" *> "$Out\$Name.cold.log"
$env:MATCH_SNAPSHOTS="$Out\$Name.typed.snap.jsonl";$env:MATCH_NO_TRACE='1'
& build\typed72-match-v1\build\Release\match72.exe "$Out\$Name.cold.json" "$Out\$Name.atlas.bin" $src "$Out\$Name.typed.jsonl" "$Out\$Name.report.json" *> "$Out\$Name.match.log"
"match exit=$LASTEXITCODE"
Remove-Item Env:MATCH_SNAPSHOTS;Remove-Item Env:MATCH_NO_TRACE
python build\typed72-match-v1\compare_snapshots.py "$Out\$Name.snap.jsonl" "$Out\$Name.typed.snap.jsonl" "$Out\$Name.snapcmp.json"
