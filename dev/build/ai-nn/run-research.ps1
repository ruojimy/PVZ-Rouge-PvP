param(
    [ValidateSet('Play','Evaluate','Train')][string]$Mode = 'Play',
    [ValidateSet('pvp744','r4','legacy')][string]$Build = 'pvp744',
    [string]$Id = '005',
    [string]$Ids = '',
    [ValidateSet('plant','zombie','both')][string]$Seat = 'plant',
    [double]$LimitSeconds = 600,
    [string]$Model = '',
    [string]$Data = '',
    [string]$ValidationData = '',
    [string]$Output = '',
    [switch]$Baseline
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ($Build -eq 'pvp744') {
    $evidenceRoot = Join-Path $taskRoot 'test_results/ai-nn-dagger-20261117'
    if (-not $Model) {
        if ($Mode -eq 'Train') { $Model = Join-Path $evidenceRoot 'training-1/selected/model.json' }
        else { $Model = Join-Path $evidenceRoot 'warm/old.json' }
    }
    if (-not $Data) { $Data = Join-Path $evidenceRoot 'train-1.jsonl' }
    if (-not $ValidationData) { $ValidationData = Join-Path $evidenceRoot 'validation-data.jsonl' }
    $binary = Join-Path $PSScriptRoot 'windows-pvp744-20261117/Release/headless_match.exe'
    $corpus = Join-Path $evidenceRoot 'corpus-plain'
} elseif ($Build -eq 'r4') {
    $evidenceRoot = Join-Path $taskRoot 'test_results/ai-nn-r4-tempo-20261116'
    if (-not $Model) { $Model = Join-Path $evidenceRoot 'models/old.json' }
    if (-not $Data) { $Data = Join-Path $evidenceRoot 'features-r4.jsonl' }
    $binary = Join-Path $PSScriptRoot 'windows-r4-20261116/Release/headless_match.exe'
    $corpus = Join-Path $taskRoot 'test_results/ai-nn-strength-20261116/corpus-plain'
} else {
    $evidenceRoot = Join-Path $taskRoot 'test_results/ai-nn-followup-20261115'
    if (-not $Model) { $Model = Join-Path $evidenceRoot 'training-v1-revalidated/model.json' }
    if (-not $Data) { $Data = Join-Path $evidenceRoot 'dataset.jsonl' }
    $binary = Join-Path $PSScriptRoot 'windows-local/Release/headless_neural.exe'
    $corpus = Join-Path $PSScriptRoot 'corpus-pvp743-r2-plain'
}
if (-not $Output) { $Output = Join-Path $evidenceRoot ('manual-' + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
$Model = [System.IO.Path]::GetFullPath($Model)
$Output = [System.IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw "Output exists: $Output" }
Push-Location -LiteralPath $taskRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $corpus 'index.json'))) {
        if ($Build -ne 'legacy') { throw "Frozen $Build corpus missing: $corpus. Do not substitute an older corpus." }
        & python -X utf8 (Join-Path $PSScriptRoot 'bootstrap.py')
        if ($LASTEXITCODE -ne 0) { throw 'Input preparation failed' }
    }
    if ($Mode -eq 'Train') {
        if (-not (Test-Path -LiteralPath $Data)) {
            throw "Training dataset missing: $Data. Generate it with prepare_training.py for the current encoder, or specify -Data."
        }
        if ($Build -eq 'pvp744') {
            & python -X utf8 (Join-Path $PSScriptRoot 'fit_imitation.py') --data $Data --validation $ValidationData --initial $Model --out $Output
        } else {
            & python -X utf8 (Join-Path $PSScriptRoot 'train.py') --data $Data --out $Output
        }
    } elseif ($Mode -eq 'Evaluate') {
        if ($Ids) { $evaluationIds = $Ids }
        elseif ($Build -eq 'pvp744') {
            # After this study, these are observed regression openings, not a new test set.
            $plan = Get-Content -LiteralPath (Join-Path $evidenceRoot 'plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $evaluationIds = (@($plan.entries | Where-Object { $_.part -eq 'test' } | ForEach-Object { $_.id }) -join ',')
        } elseif ($Build -eq 'r4') {
            # Already observed reference openings; this is a regression evaluation.
            $evaluationIds = '@' + (Join-Path $taskRoot 'test_results/ai-nn-strength-20261116/test-ids.txt')
        } else {
            $split = Get-Content -LiteralPath (Join-Path (Split-Path $Model) 'split.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $index = Get-Content -LiteralPath (Join-Path $corpus 'index.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $evaluationIds = (@($index.entries | Where-Object { $split.test.maps -contains $_.map } | ForEach-Object { $_.id }) -join ',')
        }
        $taskArgs = @('-X','utf8',(Join-Path $PSScriptRoot 'eval.py'),'--bin',$binary,'--corpus',$corpus,'--out-dir',$Output,
                      '--ids',$evaluationIds,'--jobs','4','--limit-seconds',"$LimitSeconds")
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
