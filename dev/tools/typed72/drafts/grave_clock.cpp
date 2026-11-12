#include "sim/typed/grave_clock.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& field){return field.present() && !field.is_null() && field.get();}
}
double GraveClock::level(const CombatZombie& grave)const {
    if(!yes(grave.producer))return 0.;
    return std::clamp((grave.idle.or_missing(0.)+1e-9-rules_.idle_seconds)/rules_.doze_seconds,0.,1.);
}
bool GraveClock::drowsy(const CombatZombie& grave)const {
    return yes(grave.producer) && grave.idle.or_missing(0.)+1e-9>=rules_.idle_seconds;
}
void GraveClock::wake(const ZombieRef& grave,std::string cause){
    const bool was=drowsy(*grave);grave->idle.set(0.);
    if(was){
        const auto& id=grave->source.id;
        world_.runtime.events.push_back(GraveWokenEvent{id.present()&&!id.is_null()?std::optional<std::string>(id.get()):std::nullopt,std::move(cause)});
    }
}
bool GraveClock::guarded(const CombatZombie& grave)const {
    const auto& point=grave.body.motion.get();
    const auto owner=grave.source.owner.present()?
        (grave.source.owner.is_null()?std::nullopt:known_seat(grave.source.owner.get())):std::optional<Seat>(Seat::zombie);
    for(const auto& target:*world_.targets){
        if(target.is_hero())continue;
        const auto& unit=*target.unit;
        const auto& name=unit.source.content;
        if(!name.present() || name.is_null() || name.get()!=rules_.scarecrow || unit.body.hp<=0. || unit.body.ash.present())continue;
        if(world_.heroes.owner(source_ref(target.unit))!=owner)continue;
        const auto& position=unit.body.motion.get();
        if(std::hypot(wrap_delta(point.x,position.x,world_.world_width.get()),position.y-point.y)<=rules_.scarecrow_radius*world_.runtime.tile)return true;
    }
    return false;
}
bool GraveClock::touched(const CombatZombie& grave,std::span<const Seat> present)const {
    const auto& point=grave.body.motion.get();const auto tile=world_.runtime.tile;
    for(const auto seat:present){
        if(team_of(seat)!=Seat::zombie)continue;
        const auto& avatar=world_.heroes.heroes.at(seat_index(seat)).value().frame;
        if(avatar.hp.or_missing(0.)<=0.)continue;
        const auto& position=*avatar.position.get();
        const auto dx=std::abs(wrap_delta(point.x,position.x,world_.world_width.get()));
        if(dx<=tile*.9 && point.y-tile<position.y && position.y-2*tile<point.y)return true;
    }
    return false;
}
double GraveClock::idle(const ZombieRef& grave,double factor,std::span<const Seat> present){
    if(!yes(grave->producer))return factor;
    if(world_.protection.deathmatch || yes(grave->permanently_awake) || !world_.heroes.last_stand_order.empty()){
        grave->idle.set(0.);return factor;
    }
    if(guarded(*grave)){wake(grave,"scarecrow");return factor;}
    grave->idle.set(grave->idle.or_missing(0.)+1./250.);
    if(touched(*grave,present))wake(grave,"hero");
    return factor*(1.-(1.-rules_.sleep_rate)*level(*grave));
}
void GraveClock::advance(std::span<const ZombieRef> graves,std::span<const Seat> present,double production_multiplier){
    for(const auto& grave:graves){
        auto& body=grave->body;
        const auto ice=body.ice.or_missing(0.),butter=body.butter.or_missing(0.);
        const auto factor=butter>0. || ice>1000. || body.stun.or_missing(0.)>0.?0.:ice>0.?.5:1.;
        const auto rate=idle(grave,factor,present);grave->production_rate.set(rate);
        for(auto* status:{&body.ice,&body.butter,&body.stun})
            if(status->or_missing(0.)>0.)status->set(std::max(0.,status->get()-1.));
        if(!yes(grave->producer))continue;
        const auto multiplier=world_.protection.deathmatch || !world_.heroes.last_stand_order.empty()?production_multiplier:1.;
        economy_.grave_progress[grave->source.id.get()]+=rate/250.*multiplier;
    }
}
GraveWakeResult GraveClock::wake_input(Seat seat,std::optional<std::string> id){
    if(team_of(seat)!=Seat::zombie)return GraveWakeResult::wrong_team;
    if(!id)return GraveWakeResult::invalid_id;
    const auto record=world_.native_objects.get(*id);
    if(!record)return GraveWakeResult::missing;
    const auto* stored=std::get_if<ZombieRef>(&*record);
    if(!stored)return GraveWakeResult::missing;
    const auto& grave=*stored;
    const auto& owner=grave->source.owner;
    if(!grave->protection.grave || grave->body.hp<=0. || !owner.present() || owner.is_null() || owner.get()!="zombie")return GraveWakeResult::missing;
    if(!yes(grave->producer))return GraveWakeResult::nonproducer;
    wake(grave,"sweep");return GraveWakeResult::success;
}
} // namespace pvz::typed72
