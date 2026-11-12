#pragma once
#include "sim/typed/command_input.h"
#include "sim/typed/grave_clock.h"
#include "sim/typed/plant_region.h"
#include "sim/typed/plant_lookup.h"

namespace pvz::typed72 {
// The public unit observation is a read-only room boundary. Body ownership
// remains in native_objects; no input command writes a projected HP field.
struct CommandTargetView {
    Point position;
    double hp=0.;
    Seat side=Seat::plant,card_side=Seat::plant;
    bool grave=false,tentacle=false,airborne=false;
};
class NativeCommandServices : public RoomEventSink {
public:
    virtual const CommandTargetView* published_target(const std::string&)const=0;
    virtual void sync_public()=0;
    virtual void zombie_teleport(Seat)=0;
    virtual bool has_self_destruct(Seat)const=0;
    virtual std::string self_destruct(Seat,const std::string&)=0;
    virtual void remove_basin(const PlantRef&)=0;
    virtual std::string basin_to_pot(const PlantRef&,Cell,double facing)=0;
    virtual std::string deploy(Seat,const NativeCommand&)=0;
};
class NativeRoomCommands {
public:
    NativeRoomCommands(TypedBattleState& w,RoomState& s,const RoomRules& r,
        const RallyPoints& rally,PlantRegionState& plants,GraveClock& grave,
        const TargetSight& map,const std::shared_ptr<std::vector<std::string>>& native_secrets,
        NativeCommandServices& services):world_(w),state_(s),rules_(r),rally_(rally),plants_(plants),
        graves_(grave),map_(map),native_secrets_(native_secrets),services_(services){}
    std::string apply(Seat,const NativeCommand&);
private:
    TypedBattleState& world_;RoomState& state_;const RoomRules& rules_;const RallyPoints& rally_;
    PlantRegionState& plants_;GraveClock& graves_;const TargetSight& map_;
    const std::shared_ptr<std::vector<std::string>>& native_secrets_;NativeCommandServices& services_;
    bool secret(Seat,std::string_view)const;
    bool coordinates(const NativeCommand&)const;
    std::string turn(Seat,const NativeCommand&);
    std::string teleport(Seat,const NativeCommand&);
    std::string cannon(Seat,const NativeCommand&);
    std::string shovel(Seat,const NativeCommand&);
    std::string detonate(Seat,const NativeCommand&);
    std::string select_grave(Seat,const NativeCommand&);
};
} // namespace pvz::typed72
