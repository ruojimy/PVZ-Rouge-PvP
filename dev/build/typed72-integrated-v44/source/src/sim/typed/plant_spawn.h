#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
class PlantLifecycle {
public:
    virtual ~PlantLifecycle()=default;
    virtual bool clear(Cell)=0;
    virtual void plant(Cell,std::string,double facing)=0;
    virtual void important(Cell,std::string)=0;
};
// Literal raw constructors/lifecycle. PvP admission, placement rules and the
// patch constructor layers are additional callers, not approximated here.
PlantRef plant_original(TypedBattleState&,Cell,std::string kind,double facing);
std::optional<size_t> find_plant(const PlantRoster&,Cell,bool exclude_pumpkin=false);
bool clear_original_plant(TypedBattleState&,Cell);
void destroy_original_block(TypedBattleState&,PlantLifecycle&,Cell,bool solid_only=false);
void destroy_pvp_block(TypedBattleState&,PlantLifecycle&,Cell);
} // namespace pvz::typed72
