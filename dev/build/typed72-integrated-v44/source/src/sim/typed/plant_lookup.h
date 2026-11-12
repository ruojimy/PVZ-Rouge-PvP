#pragma once
#include "sim/typed/targets.h"

namespace pvz::typed72 {
bool pvp_shell(const CombatPlant&);
bool september_targetable(const CombatPlant&);
std::optional<size_t> lookup_pvp_plant(const TypedBattleState&,Cell,bool skip_shell);
bool clear_pvp_plant(TypedBattleState&,Cell);
std::optional<Point> patch_plant_point(const TypedBattleState&,const CombatPlant&);

// Vines._shell_first_peas captures the shell cells outside the sourced hit
// wrapper, and restores the preceding capture even when a nested hit throws.
class PeaShellScope {
public:
    explicit PeaShellScope(TypedBattleState&);
    ~PeaShellScope();
    PeaShellScope(const PeaShellScope&)=delete;
    PeaShellScope& operator=(const PeaShellScope&)=delete;
private:
    TypedBattleState& world_;
    std::vector<Cell> cells_;
    const std::vector<Cell>* previous_;
    bool installed_;
};
} // namespace pvz::typed72
