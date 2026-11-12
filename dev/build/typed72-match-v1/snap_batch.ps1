param([string]$Tag,[string]$Names)
$out="C:\Users\xiech\Downloads\PVZ_rougePvP_native\test_results\typed72-20261108\snap-$Tag"
New-Item -ItemType Directory -Force $out | Out-Null
foreach($n in $Names.Split(',')){
    $lines=@(& "$PSScriptRoot\snap_run.ps1" $n $out 2>&1 | ForEach-Object { "$_" })
    $sum=($lines | Select-Object -First 5) -join ' | '
    if($sum.Length -gt 400){$sum=$sum.Substring(0,400)}
    "$n :: $sum"
}
