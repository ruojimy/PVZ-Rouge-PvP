param([string]$Tag)
# App interaction audits on the production typed build (all four input paths) and, as the
# environment control, the frozen V-backend battle_interaction_audit on the same paths.
# SDL dummy video: no real window, so desktop mouse/focus cannot inject events.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
Set-Location -LiteralPath $root
$out="$root\test_results\typed72-20261108\app-audits-$Tag"
New-Item -ItemType Directory -Force $out | Out-Null
$env:SDL_VIDEODRIVER='dummy';$env:SDL_AUDIODRIVER='dummy'
$rows=@()
foreach($case in @(
    @('typed','build\app-typed72-v2\Release\typed72_battle_audit.exe'),
    @('v-baseline','build\Release\battle_interaction_audit.exe'))){
  foreach($variant in 'mouse','touch','sdl-mouse','sdl-touch'){
    $o="$out\$($case[0])-$variant";New-Item -ItemType Directory -Force $o | Out-Null
    $t0=Get-Date
    cmd /c "$($case[1]) $o $variant 1> $o\stdout.txt 2> $o\stderr.txt"
    $code=$LASTEXITCODE
    $r=Get-Content "$o\report.json" -Raw -Encoding utf8 | ConvertFrom-Json
    $fails=@($r.checks | Where-Object { -not $_.passed } | ForEach-Object { $_.id })
    $session=(Select-String -Path "$o\stderr.txt" -Pattern 'battle session started' -SimpleMatch | Select-Object -First 1).Line
    $rows+=[pscustomobject]@{backend=$case[0];variant=$variant;exit=$code;planned=$r.planned_checks.Count;completed=$r.completed_checks;passed=$r.pass_count;failed=$r.fail_count;unrun=$r.unrun_count;fatal=$r.fatal_error;fails=($fails -join ',');typed_session=[bool]$session;seconds=[int]((Get-Date)-$t0).TotalSeconds}
  }
}
Remove-Item Env:SDL_VIDEODRIVER;Remove-Item Env:SDL_AUDIODRIVER
$rows | ConvertTo-Json | Set-Content "$out\summary.json" -Encoding utf8
$rows | Format-Table -AutoSize | Out-String -Width 250
