"""Deterministically merge the frozen typed72 stage sources into one fresh tree.

Base is the newest combat stage (content-controller-v8).  Every other stage
contributes either whole new modules or explicitly listed additive field
edits; any unexpected difference stops the merge instead of being guessed.
The result records the origin and SHA256 of every file.  Frozen stages are
only read, so their build evidence stays intact.

    python integrate_stage.py --stage build/typed72-integrated-v1
"""
import argparse,hashlib,json,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TYPED='source/src/sim/typed'
def stage(name):return ROOT/'build'/name/TYPED
BASE=stage('typed72-content-controller-v8')
EXPANSION=stage('typed72-expansion-combat-v2')
ROOM=stage('typed72-room-stage')
COLD=stage('typed72-cold-runtime-v2')
DRAFT=ROOT/'tools/typed72/drafts'

# Whole modules that only exist in one later stage.
FROM_EXPANSION=['expansion_clock_state.h','expansion_combat.cpp','expansion_combat.h','expansion_combat_state.h','expansion_garden.cpp','expansion_garden.h']
# attack_identity gains the closed Kind schema used by public snapshots; its
# existing tokens are unchanged (see the stage diff), so it replaces v8's.
REPLACE_FROM_ROOM=['attack_identity.cpp','attack_identity.h']
# Drafts newer than every stage that compiled them, or never in a stage.
REPLACE_FROM_DRAFT=['native_art.cpp','native_art.h','expansion_art.cpp','expansion_art.h','content_art.cpp','content_art.h','content_raster.h',
    'cold_admission.cpp','cold_admission.h','cold_catalog.h','cold_card_fields.h','cold_factory_state.h','cold_hero_scope.cpp','cold_hero_scope.h',
    'cold_native_factory.cpp','cold_native_factory.h','cold_registration_state.h','cold_zombie_secrets.cpp','cold_zombie_secrets.h',
    'native_tick.h','native_tick.cpp','cold_registration.cpp','cold_deployment.cpp','cold_deployment.h','cold_deployment_state.h','ai_plant_placement.cpp','ai_plant_placement.h','ai_observation_builder.h',
    'room_native_pose.cpp','room_native_pose.h','room_native_pose_codec.cpp','room_native_pose_codec.h','room_public.cpp','room_public.h','room_public_codec.h']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def is_source(path):
    return path.suffix in('.cpp','.h','.inc') and not path.name.endswith('_probe.cpp') and not path.name.startswith('v_')

def insert(text,anchor,line):
    if line in text:return text
    newline='\r\n' if '\r\n' in text else '\n'
    probe=anchor+newline
    if text.count(probe)!=1:raise ValueError('ambiguous anchor: '+anchor)
    return text.replace(probe,probe+line+newline,1)

def edit(path,operations):
    raw=path.read_bytes().decode('utf8');text=raw
    for anchor,line in operations:text=insert(text,anchor,line)
    path.write_bytes(text.encode('utf8'))

def merge(stage_dir):
    source=stage_dir/TYPED
    if stage_dir.exists():raise SystemExit('stage exists, use a new directory: '+str(stage_dir))
    source.mkdir(parents=True)
    origin={}
    for path in sorted(BASE.iterdir()):
        if path.is_file() and is_source(path):
            shutil.copyfile(path,source/path.name);origin[path.name]=('v8',sha(path))
    def take(name,folder,label):
        path=folder/name;shutil.copyfile(path,source/name);origin[name]=(label,sha(path))
    for name in FROM_EXPANSION:take(name,EXPANSION,'expansion-combat-v2')
    for name in REPLACE_FROM_ROOM:take(name,ROOM,'room-stage')
    for name in REPLACE_FROM_DRAFT:take(name,DRAFT,'draft')
    # Later-stage modules that the base never saw.
    for label,folder in (('room-stage',ROOM),('cold-runtime-v2',COLD),('draft',DRAFT)):
        for path in sorted(folder.iterdir()):
            if path.is_file() and is_source(path) and path.name not in origin:
                shutil.copyfile(path,source/path.name);origin[path.name]=(label,sha(path))
    # Fixes to the exact file version used here; see _integration_overrides/OVERRIDES.json.
    overrides=DRAFT/'_integration_overrides'
    if overrides.exists():
        for path in sorted(overrides.iterdir()):
            if path.is_file() and is_source(path):shutil.copyfile(path,source/path.name);origin[path.name]=('integration-override',sha(path))
    # Additive authoritative fields from sibling stages.
    edit(source/'plant.h',[('#pragma once','#include "sim/typed/expansion_clock_state.h"'),('#pragma once','#include "sim/typed/cold_registration_state.h"'),
        ('struct CombatPlant {','    ExpansionClockState expansion_clock;'),('struct CombatPlant {','    ColdPlantRegistrationState registration;'),
        ('#pragma once','#include "sim/typed/pve_director_state.h"'),('struct CombatPlant {','    PvePlantState pve;')])
    edit(source/'targets.h',[('#pragma once','#include "sim/typed/expansion_combat_state.h"'),('#pragma once','#include "sim/typed/cold_registration_state.h"'),
        ('#pragma once','#include "sim/typed/cold_factory_state.h"'),('struct CombatZombie {','    ExpansionCombatState expansion;'),
        ('struct CombatZombie {','    ColdZombieRegistrationState registration;'),('struct CombatZombie {','    ColdFactoryZombieState factory;'),
        ('#pragma once','#include "sim/typed/zombie_secret_state.h"'),('struct CombatZombie {','    ZombieSecretUnitState secret;'),
        ('#pragma once','#include "sim/typed/pve_director_state.h"'),('struct CombatZombie {','    PveZombieState pve;')])
    edit(source/'hero.h',[('#pragma once','#include "sim/typed/expansion_combat_state.h"'),('struct HeroProxyState : ZombieRecordFields {','    ExpansionCombatState expansion;'),
        ('#pragma once','#include "sim/typed/zombie_secret_state.h"'),('struct HeroState {','    ZombieSecretHeroState secret;')])
    for name in('plant.h','targets.h','hero.h'):origin[name]=('v8+additive-overlay',sha(source/name))
    manifest={'base':'typed72-content-controller-v8','files':{k:{'origin':v[0],'sha256':sha(source/k),'origin_sha256':v[1]} for k,v in sorted(origin.items())}}
    (stage_dir/'integration-manifest.json').write_text(json.dumps(manifest,indent=1,ensure_ascii=False),encoding='utf8')
    return source,manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True);args=parser.parse_args()
    source,manifest=merge((ROOT/args.stage).resolve())
    counts={}
    for row in manifest['files'].values():counts[row['origin']]=counts.get(row['origin'],0)+1
    print(json.dumps(counts,ensure_ascii=False),len(manifest['files']))
