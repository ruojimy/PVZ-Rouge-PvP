param(
    [Parameter(Mandatory=$true)][string]$Game,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$tool = Join-Path (Split-Path -Parent $PSScriptRoot) 'launch.cmd'
& $tool --game $Game --work $Output capabilities
exit $LASTEXITCODE
