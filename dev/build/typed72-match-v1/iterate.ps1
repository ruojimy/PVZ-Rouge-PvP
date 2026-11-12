param([string]$Scenario,[string]$Tag)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
& "$PSScriptRoot\build_match.ps1" | ForEach-Object { if($_.Length -gt 230){$_.Substring(0,230)}else{$_} }
Set-Location -LiteralPath 'C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe' build/typed72-match-v1/compare_match.py $Scenario "test_results/typed72-20261106/match-$Scenario-$Tag" | ForEach-Object { if($_.Length -gt 3000){$_.Substring(0,3000)}else{$_} }
