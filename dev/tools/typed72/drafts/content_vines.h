#pragma once
#include "sim/typed/economy.h"
namespace pvz::typed72 {
class ContentVines {
public:
    ContentVines(TypedBattleState& world,Resources& resources,const ProductionRules& rules,const bool& hardening)
        :world_(world),resources_(resources),rules_(rules),hardening_(hardening){}
    bool configure(const PlantRef&,std::string_view);
    void wake_cell(const PlantRef&);
    std::optional<size_t> coffee_target(Cell);
    void tick();
private:
    TypedBattleState& world_;Resources& resources_;const ProductionRules& rules_;const bool& hardening_;
    double rest_factor(const PlantRef&);
};
} // namespace pvz::typed72
