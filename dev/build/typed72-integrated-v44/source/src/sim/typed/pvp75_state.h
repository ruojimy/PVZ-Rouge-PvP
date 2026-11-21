#pragma once
// PvP75 per-unit and world state: 激光豆 beams, 巴豆 bites and gas, 盾卫僵尸 guard,
// Boss control conversion. Plain data only; the rules live in pvp75_content.cpp.
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>
namespace pvz::typed72 {
struct CombatPlant;
struct CombatZombie;
struct AttackSource;
struct Pvp75PlantState {
    bool firing=false;           // 激光豆: beam active until the bean is clicked again
    bool aimed=false;            // a plant player selected this bean and is choosing a point
    Point target{};              // world point chosen in the firing state
    double clock=0.;             // native ticks since the last beam pulse
    int64_t started=0;           // tick the beam started (texture phase)
};
enum class GuardPhase {ready,raising,guarding,cooldown};
struct Pvp75ZombieState {
    GuardPhase guard=GuardPhase::ready;
    double guard_clock=0.;       // native ticks spent in the current guard phase
    double seen_hp=-1.,seen_armor=-1.,seen_hand=-1.;
    std::optional<double> walk_speed; // speed saved while guarding (multiplicative 0.25)
    double boss_slow=0.;         // Boss control converted to slow beyond the 1000-tick ice slow
};
struct CrotonBite {std::weak_ptr<CombatZombie> biter;std::shared_ptr<CombatPlant> plant;};
struct CrotonGas {
    int64_t tick=0;Point origin{};double direction=1.;
    std::shared_ptr<AttackSource> source;   // the eaten bean (allegiance + attribution)
    std::vector<uint64_t> touched;          // identities already poisoned by this cloud
};
struct Pvp75World {
    std::vector<CrotonBite> bites;
    std::vector<CrotonGas> gases;
};
} // namespace pvz::typed72
