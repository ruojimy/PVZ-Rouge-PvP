#!/bin/bash
# Regenerate src/sim/gen/{regions,physics,original_funcs}.cpp from extract/ (after dump_live_regions + fix_live).
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
P=/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe
$P tools/fix_live.py
L=extract/live; args=""
for r in zombies zombies_scripted plants entities plant_maintenance particles placement coffee shovel sun_motion water_animation important_blocks water_ice_clock umbrella_player_trigger umbrella_player_bounce cannon_select cannon_fire plant_draw unit_target_index zombie_coordinates zombie_body_index; do args="$args $L/$r.py:region:region_$r"; done
$P tools/py2cpp.py src/sim/gen/regions.cpp regions $args
args=""
for r in $(ls $L | grep '^physics_.*\.py$' | sed 's/\.py$//') dave_draw dave_state; do args="$args $L/$r.py:region:region_$r"; done
$P tools/py2cpp.py src/sim/gen/physics.cpp physics $args
$P tools/py2cpp.py src/sim/gen/original_funcs.cpp original_funcs extract/original/functions.py:funcs:x
