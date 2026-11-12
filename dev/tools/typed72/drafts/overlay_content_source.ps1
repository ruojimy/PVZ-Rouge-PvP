param([Parameter(Mandatory=$true)][string]$TypedDirectory)
$ErrorActionPreference='Stop'
$typedRoot=(Resolve-Path -LiteralPath $TypedDirectory).Path
$draftRoot=$PSScriptRoot
foreach($name in @('attack_source.h','borrowed_zombie_kind.h','entity_source_link.h','zombie_source_link.h','content_target_state.h',
    'content_entity_state.h','content_zombie_state.h','content_zombie56_state.h','content_zombie70_state.h',
    'content_plant_state.h','content_plant70_state.h','particle_dispatch.h')){
    Copy-Item -LiteralPath (Join-Path $draftRoot $name) -Destination (Join-Path $typedRoot $name)
}
$statePath=Join-Path $typedRoot 'state.h'
$state=[IO.File]::ReadAllText($statePath)
if(-not $state.Contains('#include "sim/typed/particle_dispatch.h"')){
    $state=$state.Replace('#include "sim/typed/attack_source.h"',"#include `"sim/typed/attack_source.h`"`n#include `"sim/typed/particle_dispatch.h`"")
}
if(-not $state.Contains('NativeParticleDispatch* particle_dispatch=nullptr;')){
    $state=$state.Replace('    void emit_particles(const std::string& name, Point position, int count,std::optional<int> direction={});',
        "    NativeParticleDispatch* particle_dispatch=nullptr;`n    bool particle_dispatch_required=false;`n    void bind_particles(NativeParticleDispatch& dispatch){if(particle_dispatch&&particle_dispatch!=&dispatch)throw std::logic_error(`"particle dispatch already bound`");particle_dispatch=&dispatch;}`n    void require_particles(bool required=true){particle_dispatch_required=required;}`n    void emit_particles_native(const std::string& name, Point position, int count,std::optional<int> direction={});`n    void emit_particles(const std::string& name, Point position, int count,std::optional<int> direction={});")
}
if(-not $state.Contains('#include "sim/typed/content_entity_state.h"')){
    $state=$state.Replace('#include "sim/typed/attack_source.h"',"#include `"sim/typed/attack_source.h`"`n#include `"sim/typed/content_entity_state.h`"")
}
if(-not $state.Contains('ContentEntityState content_state;')){
    $state=$state.Replace('struct Entity {',"struct Entity {`n    ContentEntityState content_state;")
}
if(-not $state.Contains('#include "sim/typed/content_target_state.h"')){
    $state=$state.Replace('#include "sim/typed/attack_source.h"',"#include `"sim/typed/attack_source.h`"`n#include `"sim/typed/content_target_state.h`"")
}
if(-not $state.Contains('ContentTargetState content_target;')){
    $state=$state.Replace('struct ZombieRecordFields {',"struct ZombieRecordFields {`n    ContentTargetState content_target;")
}
$old='inline std::shared_ptr<AttackSource> source_ref(const EntityRef& entity){return {entity,&entity->source};}'
$new='inline std::shared_ptr<AttackSource> source_ref(const EntityRef& entity){entity->source.entity.bind(entity);return {entity,&entity->source};}'
if(-not $state.Contains($new)){
    if(-not $state.Contains($old)){throw 'Entity source_ref contract changed; inspect before overlay.'}
    $state=$state.Replace($old,$new)
}
[IO.File]::WriteAllText($statePath,$state,[Text.UTF8Encoding]::new($false))
$targetPath=Join-Path $typedRoot 'targets.h'
$target=[IO.File]::ReadAllText($targetPath)
foreach($name in @('content_zombie_state.h','content_zombie56_state.h','content_zombie70_state.h')){
    if(-not $target.Contains('#include "sim/typed/'+$name+'"')){
        $target=$target.Replace('#include "sim/typed/content_zombie64_state.h"',"#include `"sim/typed/content_zombie64_state.h`"`n#include `"sim/typed/$name`"")
    }
}
foreach($field in @('ContentZombieState content;','ContentZombie56State content56;','ContentZombie70State content70;')){
    if(-not $target.Contains($field)){$target=$target.Replace('    ContentZombie64State content64;',"    ContentZombie64State content64;`n    $field")}
}
$oldZombie='inline std::shared_ptr<AttackSource> source_ref(const ZombieRef& unit){return {unit,&unit->source};}'
$newZombie='inline std::shared_ptr<AttackSource> source_ref(const ZombieRef& unit){unit->source.unit.bind(unit);return {unit,&unit->source};}'
if(-not $target.Contains($newZombie)){
    if(-not $target.Contains($oldZombie)){throw 'Zombie source_ref contract changed; inspect before overlay.'}
    $target=$target.Replace($oldZombie,$newZombie)
}
[IO.File]::WriteAllText($targetPath,$target,[Text.UTF8Encoding]::new($false))
$plantPath=Join-Path $typedRoot 'plant.h'
$plant=[IO.File]::ReadAllText($plantPath)
if(-not $plant.Contains('#include "sim/typed/content_plant70_state.h"')){
    $plant=$plant.Replace('#include "sim/typed/flying_state.h"',"#include `"sim/typed/flying_state.h`"`n#include `"sim/typed/content_plant70_state.h`"")
}
if(-not $plant.Contains('ContentPlant70State content70;')){
    $plant=$plant.Replace('    FlyingPlantState flying;',"    FlyingPlantState flying;`n    ContentPlant70State content70;`n    Field<double> ash,ice,butter,stun;")
}
if(-not $plant.Contains('#include "sim/typed/content_plant_state.h"')){
    $plant=$plant.Replace('#include "sim/typed/flying_state.h"',"#include `"sim/typed/flying_state.h`"`n#include `"sim/typed/content_plant_state.h`"")
}
if(-not $plant.Contains('ContentPlantState content_state;')){
    $plant=$plant.Replace('    FlyingPlantState flying;',"    FlyingPlantState flying;`n    ContentPlantState content_state;")
}
[IO.File]::WriteAllText($plantPath,$plant,[Text.UTF8Encoding]::new($false))
$terrainPath=Join-Path $typedRoot 'terrain.h'
$terrain=[IO.File]::ReadAllText($terrainPath)
if(-not $terrain.Contains('Field<std::string> basin;')){
    $terrain=$terrain.Replace('struct TerrainCell {',"struct TerrainCell {`n    Field<std::string> basin;")
}
[IO.File]::WriteAllText($terrainPath,$terrain,[Text.UTF8Encoding]::new($false))
