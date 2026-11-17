#pragma once
#include <array>
#include <map>
#include <memory>
#include <string>
namespace pvz::typed72 {
struct CombatZombie;
struct TerrariaNpcState {
    int type=0,frame=0,frame_ticks=0,despawn=750;
    std::array<double,4> ai{};
    double vx=0.,vy=0.,rotation=0.,damage=0.,width=0.,height=0.;
    double alpha=0.;
    bool initialized=false,burrowing=false,removed=false;
    std::weak_ptr<CombatZombie> ahead,behind,parent;
    std::string target_id;
    std::map<std::string,int64_t> contact_ready;
};
}
