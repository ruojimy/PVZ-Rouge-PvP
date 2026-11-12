#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
enum class NativeSpawnMode { normal,extreme,doomsday,endless,test,lottery,other };
struct ZombieSpawnInput {
    NativeSpawnMode mode=NativeSpawnMode::normal;
    Point player;
    int map_rows=0,map_cols=0;
    double screen_height=0;
    std::vector<std::string> bosses;
};
// The original constructor (all original zombie kinds). The reference input
// position is intentionally mutable for balloon/miner/red-eye spawn branches.
// PvP admission/card registration and the 1.5.0.1 constructor wrappers are
// additional required callers, not silently approximated here.
void populate_original_zombie(CombatRuntime&,CombatZombie&,std::string name,Motion& input_position,double facing,const ZombieSpawnInput&);
ZombieRef spawn_original_zombie(TypedBattleState&,std::string name,Motion& input_position,double facing,const ZombieSpawnInput&);
} // namespace pvz::typed72
