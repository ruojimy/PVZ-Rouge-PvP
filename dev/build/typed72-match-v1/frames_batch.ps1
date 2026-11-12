param([string]$Tag,[string]$Names)
# Native frame identity over many scenarios; one summary line each, reports in test_results.
$out="C:\Users\xiech\Downloads\PVZ_rougePvP_native\test_results\typed72-20261108\frames-$Tag"
New-Item -ItemType Directory -Force $out | Out-Null
foreach($n in $Names.Split(',')){
    $lines=@(& "$PSScriptRoot\frames_run.ps1" $n $out 2>&1 | ForEach-Object { "$_" })
    $sum=($lines | Where-Object { $_ -match '^frames identical|^missing|^match exit' }) -join ' | '
    "$n :: $sum"
}
