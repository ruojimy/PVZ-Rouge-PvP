param([string]$Tag)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$built=@(& "$PSScriptRoot\build_match.ps1"); $built | ForEach-Object { if($_.Length -gt 200){$_.Substring(0,200)}else{$_} }
# A failed build leaves the previous match72.exe in place; never compare that under a new tag.
if(-not ($built -contains 'build=0')){ 'ABORT: match72 build failed; no comparison run'; exit 1 }
Set-Location -LiteralPath 'C:\Users\xiech\Downloads\PVZ_rougePvP_native'; $env:PYTHONIOENCODING='utf-8'; $py='C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe'
& $py build/typed72-match-v1/batch_compare.py $Tag 3 "empty,basic,zombie_swarm,projectile_storm,mixed_late_game,hero_inputs,grave_economy,duo_basic,coop_waves,duel_settle_1,cards_p0,cards_p1,cards_p2,cards_p3,cards_p4,cards_p5,cards_p6,cards_t0,cards_t1,cards_t2,cards_t3,cards_z0,cards_z1,cards_z2,cards_z3,cards_z4,cards_z5,cards_z6,secrets_0,secrets_1,secrets_2,secrets_3,secrets_4,secrets_5,secrets_6" | Select-Object -Last 1 | ForEach-Object { if($_.Length -gt 300){$_.Substring(0,300)}else{$_} }
& $py build/typed72-match-v1/show_batch.py $Tag 30 | ForEach-Object { if($_.Length -gt 230){$_.Substring(0,230)}else{$_} } | Where-Object { $_ -notmatch ' ID 0 ' }
