param([string]$Name,[string]$Out='C:\Users\xiech\AppData\Local\Temp\claude\6239892f822f7614\6da366be-0fc4-4fdb-a433-a072a3fe27a0\scratchpad\frames',[switch]$Reference)
# Native frame identity for one scenario: V frames (ref72_record v3 REF_FRAMES) against typed frames
# (match72 MATCH_FRAMES) on the same cold export. -Reference re-records the V side.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
Set-Location -LiteralPath $root
$env:SDL_VIDEODRIVER='dummy';$env:SDL_AUDIODRIVER='dummy';$env:PYTHONIOENCODING='utf-8'
New-Item -ItemType Directory -Force $Out | Out-Null
$src="tools\scenarios\_expanded_$Name.json";if(-not(Test-Path $src)){$src="tools\scenarios\$Name.json"};if(Test-Path "build\typed72-match-v1\scenarios\$Name.json"){$src="build\typed72-match-v1\scenarios\$Name.json"}
if($Reference -or -not (Test-Path "$Out\$Name.frames.jsonl")){
    $env:PVP_USERDATA="$Out\ud_ref_$Name";$env:REF_FRAMES="$Out\$Name.frames.jsonl"
    & build\typed72-ref-recorder-v3\build\Release\ref72_record.exe $src "$Out\$Name.jsonl" *> "$Out\$Name.ref.log"
    Remove-Item Env:REF_FRAMES
}
$env:PVP_USERDATA="$Out\ud_cold_$Name"
& build\typed72-match-v1\build\Release\cold72_export.exe $src "$Out\$Name.cold.json" "$Out\$Name.atlas.bin" *> "$Out\$Name.cold.log"
$env:MATCH_FRAMES="$Out\$Name.typed.frames.jsonl";$env:MATCH_NO_TRACE='1'
& build\typed72-match-v1\build\Release\match72.exe "$Out\$Name.cold.json" "$Out\$Name.atlas.bin" $src "$Out\$Name.typed.jsonl" "$Out\$Name.report.json" *> "$Out\$Name.match.log"
"match exit=$LASTEXITCODE failure=" + (Get-Content "$Out\$Name.report.json" -Raw -Encoding utf8 | ConvertFrom-Json).failure + " unsupported=" + ((Get-Content "$Out\$Name.report.json" -Raw -Encoding utf8 | ConvertFrom-Json).unsupported_draws | ConvertTo-Json -Compress)
Remove-Item Env:MATCH_FRAMES;Remove-Item Env:MATCH_NO_TRACE
python build\typed72-match-v1\compare_frames.py "$Out\$Name.frames.jsonl" "$Out\$Name.typed.frames.jsonl" "$Out\$Name.cmp.json"
