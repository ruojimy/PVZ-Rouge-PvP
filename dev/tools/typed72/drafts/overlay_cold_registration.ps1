param([Parameter(Mandatory=$true)][string]$TypedDirectory)
$ErrorActionPreference='Stop'
$coldRoot=(Resolve-Path -LiteralPath $TypedDirectory).Path
$workspaceRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$approvedBuild=(Join-Path $workspaceRoot 'build')+[IO.Path]::DirectorySeparatorChar
if(-not $coldRoot.StartsWith($approvedBuild,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Cold registration overlay is restricted to an isolated build tree.'
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'cold_registration_state.h') -Destination (Join-Path $coldRoot 'cold_registration_state.h')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'content_plant_state.h') -Destination (Join-Path $coldRoot 'content_plant_state.h')
$plantPath=Join-Path $coldRoot 'plant.h'
$plant=[IO.File]::ReadAllText($plantPath)
if(-not $plant.Contains('#include "sim/typed/cold_registration_state.h"')){
    $plant=$plant.Replace('#include "sim/typed/flying_state.h"',"#include `"sim/typed/flying_state.h`"`n#include `"sim/typed/cold_registration_state.h`"")
}
if(-not $plant.Contains('#include "sim/typed/content_plant_state.h"')){
    $plant=$plant.Replace('#include "sim/typed/flying_state.h"',"#include `"sim/typed/flying_state.h`"`n#include `"sim/typed/content_plant_state.h`"")
}
if(-not $plant.Contains('ContentPlantState content_state;')){
    $plant=$plant.Replace('    FlyingPlantState flying;',"    FlyingPlantState flying;`n    ContentPlantState content_state;")
}
if(-not $plant.Contains('ColdPlantRegistrationState registration;')){
    $plant=$plant.Replace('    UnitProtectionState protection;',"    ColdPlantRegistrationState registration;`n    UnitProtectionState protection;")
}
if(-not $plant.Contains('ColdPlantRegistrationState registration;')){throw 'Plant schema changed before cold overlay.'}
[IO.File]::WriteAllText($plantPath,$plant,[Text.UTF8Encoding]::new($false))
$zombiePath=Join-Path $coldRoot 'targets.h'
$zombie=[IO.File]::ReadAllText($zombiePath)
if(-not $zombie.Contains('#include "sim/typed/cold_registration_state.h"')){
    $zombie=$zombie.Replace('#include "sim/typed/plant.h"',"#include `"sim/typed/plant.h`"`n#include `"sim/typed/cold_registration_state.h`"")
}
if(-not $zombie.Contains('ColdZombieRegistrationState registration;')){
    $zombie=$zombie.Replace('struct CombatZombie {',"struct CombatZombie {`n    ColdZombieRegistrationState registration;")
}
if(-not $zombie.Contains('ColdZombieRegistrationState registration;')){throw 'Zombie schema changed before cold overlay.'}
[IO.File]::WriteAllText($zombiePath,$zombie,[Text.UTF8Encoding]::new($false))
