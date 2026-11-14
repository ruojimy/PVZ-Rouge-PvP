param(
    [ValidateSet('Play','Evaluate','Train')][string]$Mode = 'Play',
    [string]$Id = '005',
    [ValidateSet('plant','zombie','both')][string]$Seat = 'both',
    [double]$LimitSeconds = 600,
    [string]$Model = '',
    [string]$Output = '',
    [switch]$Baseline
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$evidenceRoot = Join-Path $taskRoot 'test_results/ai-nn-local-20261114'
if (-not $Model) { $Model = Join-Path $evidenceRoot 'training-v1/model.json' }
if (-not $Output) { $Output = Join-Path $evidenceRoot ('manual-' + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
$Model = [System.IO.Path]::GetFullPath($Model)
$Output = [System.IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "Output exists: $Output" }
$binary = Join-Path $PSScriptRoot 'windows-local/Release/headless_neural.exe'
$corpus = Join-Path $PSScriptRoot 'corpus-pvp743-r2-plain'
Push-Location -LiteralPath $taskRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $corpus 'index.json'))) {
        & python -X utf8 (Join-Path $PSScriptRoot 'bootstrap.py')
        if ($LASTEXITCODE -ne 0) { throw 'Input preparation failed' }
    }
    if ($Mode -eq 'Train') {
        if (-not (Test-Path -LiteralPath (Join-Path $evidenceRoot 'dataset.jsonl'))) {
            & python -X utf8 (Join-Path $PSScriptRoot 'bootstrap.py') --training
            if ($LASTEXITCODE -ne 0) { throw 'Training input preparation failed' }
        }
        & python -X utf8 (Join-Path $PSScriptRoot 'train.py') --data (Join-Path $evidenceRoot 'dataset.jsonl') --out $Output
    } elseif ($Mode -eq 'Evaluate') {
        $split = Get-Content -LiteralPath (Join-Path (Split-Path $Model) 'split.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $index = Get-Content -LiteralPath (Join-Path $corpus 'index.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $testIds = @($index.entries | Where-Object { $split.test.maps -contains $_.map } | ForEach-Object { $_.id })
        $taskArgs = @('-X','utf8',(Join-Path $PSScriptRoot 'eval.py'),'--bin',$binary,'--corpus',$corpus,'--out-dir',$Output,
                      '--ids',($testIds -join ','),'--jobs','4','--limit-seconds',"$LimitSeconds")
        if ($Baseline) { $taskArgs += @('--','--no-records') }
        else { $taskArgs += @('--planner','nn','--','--model',$Model,'--nn-seat',$Seat,'--no-records') }
        & python @taskArgs
    } else {
        New-Item -ItemType Directory -Path $Output | Out-Null
        $taskArgs = @('--corpus',$corpus,'--id',$Id,'--out',(Join-Path $Output 'match.jsonl'),'--limit-seconds',"$LimitSeconds")
        if (-not $Baseline) { $taskArgs += @('--planner','nn','--model',$Model,'--nn-seat',$Seat) }
        & $binary @taskArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "Research command failed: $LASTEXITCODE" }
} finally { Pop-Location }
