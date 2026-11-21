#pragma once
// PvP75 content: 巴豆 (bite-triggered poison gas), 激光豆 (player-aimed continuous beam),
// 盾卫僵尸 (damage-raised guard) and the Boss control conversion. One world, one owner
// for the rules; the native regions only hand over bites through TypedBattleState::pvp75.
#include "sim/typed/content_queries.h"
#include "sim/typed/native_status.h"
#include "sim/typed/native_canvas.h"
#include <functional>
#include <span>
namespace pvz::typed72 {
namespace pvp75 {
constexpr double kLaserMinCells=8.,kLaserMaxCells=20.,kLaserHalfAngle=80.;
constexpr double kLaserPulseTicks=100.,kLaserDamage=30.;
constexpr double kCrotonDamage=150.,kCrotonStunTicks=1500.,kCrotonPoisonSeconds=6.;
constexpr double kGasCells=6.,kGasStunTicks=750.,kGasPoisonSeconds=3.,kGasTicks=500.,kGasSpreadTicks=190.;
constexpr double kGuardRaiseTicks=150.,kGuardTicks=1500.,kGuardCooldownTicks=1500.;
constexpr double kGuardDefense=60.,kGuardBaseDefense=6.,kGuardSpeed=.25;
constexpr int kStarPierce=3;
// Eye of the 48x48 runtime art (right-facing), relative to the cell's top-left.
Point laser_eye(const CombatPlant&,double tile);
// "" when the point is a legal target for this bean; the rejection text otherwise.
std::string laser_target_error(const CombatPlant&,Point,double tile,double width);
bool shield_guard(const CombatZombie&);
bool guard_active(const CombatZombie&);
// Freeze, butter and stun on a Boss become a slow of the same total length.
void convert_boss_control(CombatZombie&);
}
class Pvp75Content {
public:
    Pvp75Content(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,NativeStatus& status,
                 const std::vector<std::string>& bosses)
        :world_(world),queries_(queries),targets_(targets),status_(status),bosses_(bosses){}
    bool configure(const PlantRef&,std::string_view content);
    bool configure(const ZombieRef&,std::string_view content);
    bool is_boss(const CombatZombie&)const;
    // Before each zombie's native step: Boss conversion and the guard art alias.
    void zombie_gate(const ZombieRef&,const std::function<void(const std::string&,const std::string&)>& alias);
    void before_tick();
    void after_plants();
    void draw(NativeCanvas&);
    uint64_t beam_pulses=0,gas_hits=0,croton_triggers=0,guards=0;
private:
    TypedBattleState& world_;ContentQueries& queries_;ContentTargets& targets_;NativeStatus& status_;
    const std::vector<std::string>& bosses_;
    void croton(const ZombieRef& biter,const PlantRef& plant);
    void gases();
    void lasers();
    void guard(const ZombieRef&);
};
} // namespace pvz::typed72
