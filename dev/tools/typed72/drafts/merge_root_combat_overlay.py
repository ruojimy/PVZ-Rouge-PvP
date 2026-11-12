"""Idempotent root combat additions; retain other agents' fields and ABI fixes.

Apply only to a fresh, non-running isolated build source tree. This is not a
production promotion or proof that the combined runtime is complete.
"""
import argparse
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
STABLE=ROOT/'build/typed72-expansion-combat-v2/source/src/sim/typed'
FILES=('bonus_state.h','bonus_projectiles.h','bonus_projectiles.cpp','bonus_plants.h','bonus_plants.cpp','bonus_scan.h','bonus_scan.cpp',
       'expansion_clock_state.h','expansion_garden.h','expansion_garden.cpp','expansion_combat_state.h','expansion_combat.h','expansion_combat.cpp')

def merge(destination,copy_modules=True):
    destination=Path(destination).resolve()
    if (ROOT/'build').resolve() not in destination.parents:raise ValueError('overlay requires a fresh isolated build source directory')
    if copy_modules:
        for name in FILES:
            path=destination/name
            if path.exists() and path.read_bytes()!= (STABLE/name).read_bytes():
                raise ValueError('module already changed; resolve newer implementation explicitly: '+str(path))
            if not path.exists():shutil.copy2(STABLE/name,path)
    def change(name,operation):
        path=destination/name;text=path.read_text(encoding='utf8');changed=operation(text)
        if text!=changed:path.write_text(changed,encoding='utf8')
    def insert(text,anchor,line):
        if line in text:return text
        if text.count(anchor)!=1:raise ValueError('ambiguous overlay anchor '+anchor)
        return text.replace(anchor,anchor+'\n'+line,1)
    def state(text):
        text=insert(text,'#pragma once','#include "sim/typed/bonus_state.h"')
        text=insert(text,'struct Entity {','    BonusEntityState bonus;')
        if 'EntityExpiry expires;' not in text:
            anchor='    Field<double> gravity, expires, through_wall, rotation;'
            if text.count(anchor)!=1:raise ValueError('EntityExpiry ownership requires manual merge')
            text=text.replace(anchor,'    Field<double> gravity, through_wall, rotation;\n    EntityExpiry expires;')
        return text
    change('state.h',state)
    change('plant.h',lambda s:insert(insert(insert(s,'#pragma once','#include "sim/typed/expansion_clock_state.h"'),'struct CombatPlant {','    BonusPlantState bonus;'),'struct CombatPlant {','    ExpansionClockState expansion_clock;'))
    change('targets.h',lambda s:insert(insert(s,'#pragma once','#include "sim/typed/expansion_combat_state.h"'),'struct CombatZombie {','    ExpansionCombatState expansion;'))
    change('hero.h',lambda s:insert(insert(s,'#pragma once','#include "sim/typed/expansion_combat_state.h"'),'struct HeroProxyState : ZombieRecordFields {','    ExpansionCombatState expansion;'))
    def events(text):
        start=text.index('enum class HeroHit {');end=text.index('};',start)
        body=text[start:end]
        for value in ('chili','tentacle','black_armor'):
            if value not in body:body=body.rstrip()+', '+value
        return text[:start]+body.rstrip()+' '+text[end:]
    change('combat_events.h',events)
    def names(text):
        for name in ('chili','tentacle','black_armor'):
            if 'case HeroHit::'+name+':' not in text:
                anchor='case HeroHit::anchor:return "anchor";'
                if text.count(anchor)!=1:raise ValueError('HeroHit name switch needs explicit merge')
                text=text.replace(anchor,anchor+'case HeroHit::'+name+':return "'+name+'";',1)
        return text
    change('hero.cpp',names)
    def cmake(text):
        for name in FILES:
            if name.endswith('.cpp') and name not in text:text+='\ntarget_sources(pvztyped72 PRIVATE '+name+')\n'
        return text
    change('CMakeLists.txt',cmake)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');parser.add_argument('--fields-only',action='store_true');args=parser.parse_args()
    merge(args.destination,not args.fields_only)
    print('Merged root typed combat fields and modules; full ABI rebuild is required.')
