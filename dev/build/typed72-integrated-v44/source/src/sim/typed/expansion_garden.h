#pragma once
#include "sim/typed/expansion_clock_state.h"
#include "sim/typed/scarecrow.h"
#include <map>

namespace pvz::typed72 {
// Lock-time secret selection and tick-local pressure positions belong to this
// state. Public player positions are deliberately not used for native pressure.
class ExpansionGarden {
public:
    ExpansionGarden(TypedBattleState& world, Scarecrows& scarecrows)
        : world_(world), scarecrows_(scarecrows) {}
    bool cactus_spikes = false;
    std::vector<Seat> pressure_holders;
    std::optional<int64_t> pressure_tick;
    std::vector<Point> pressure_positions;
    std::vector<Cell> aura_centers;
    std::map<std::pair<int, int64_t>, int> aura_cells;
    ScarecrowCells slow_cells;
    std::unordered_map<uint64_t, ExpansionClockValues> timer_before;
    void configure_locked_secrets();
    double pressure(const PlantRef&);
    double aura(const PlantRef&);
    void absorb_clock_cap();
    void before_plants(std::span<const std::string> producers);
    void after_plants();
    static Field<double>& timer(CombatPlant&, ExpansionTimer);
private:
    TypedBattleState& world_;
    Scarecrows& scarecrows_;
};
} // namespace pvz::typed72
