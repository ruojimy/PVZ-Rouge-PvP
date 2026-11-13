#include "sim/typed/september_zombies.h"
#include "sim/typed/content_zombie_state.h"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/projectile_rules.h"

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present() && !value.is_null() && value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present() && !value.is_null() && value.get()==name;}
bool garbage(const CombatZombie& unit) {
    const auto& kind=unit.content64.hand_kind;
    if(kind.present() && !kind.is_null() && !kind.get().empty())return kind.get()=="垃圾桶";
    return named(unit.source.content,"垃圾桶僵尸") || (!named(unit.source.content,"传送带僵尸") && unit.body.hand=="垃圾桶");
}
}
bool SeptemberZombies::ordered(const ZombieRef& unit)const {
    return commands_.for_owner(world_.mode,unit->source.seat)==PathMode::follow_hero ||
        rallies_.for_owner(world_.mode,unit->source.seat).has_value();
}
void SeptemberZombies::chase(const ZombieRef& unit,const std::shared_ptr<Motion>& goal,SeptemberPathKey key,
                            const std::shared_ptr<Motion>& tracking_goal) {
    auto saved=std::make_shared<PathSnapshot>(snapshots_.capture());
    unit->content.yeti_tracking.set(saved);unit->content.player_position=world_.heroes.globals.position;
    auto& entry=banks_[key];
    if(!entry) {
        entry=std::make_shared<SeptemberPathBank>();entry->snapshot=snapshots_.independent(*saved);
        entry->snapshot.flood[0].queue=std::make_shared<std::vector<Cell>>();entry->snapshot.flood[0].cooldown=0;
        if(banks_.size()>64) {auto retained=entry;banks_.clear();banks_.emplace(key,std::move(retained));}
    }
    // Cache eviction above invalidates map references but not the retained bank.
    const auto state=banks_.at(key);snapshots_.restore(state->snapshot);
    if(state->tick!=world_.heroes.tick) {
        const auto target=tracking_goal?tracking_goal:goal;const double tile=world_.runtime.tile;
        navigation_.target_position={int(std::floor((target->y-.5*tile)/tile)),int64_t(std::floor(target->x/tile))};
        tracking_.advance({target->x,target->y},PathMode::follow_hero);
        state->snapshot=snapshots_.capture();state->tick=world_.heroes.tick;
    }
    world_.heroes.globals.position.set(goal);
}
void SeptemberZombies::gate(const ZombieRef& unit) {
    const bool yeti=named(unit->source.content,"雪人僵尸");
    if(yeti)for(const auto part:{"-身","-首"})services_.alias_art(unit->body.kind+part,std::string("雪人僵尸")+part);
    if(garbage(*unit) && unit->body.hand=="钢门" && unit->body.hand_hp>0.)services_.alias_art("钢门","垃圾桶-手持");
    if(!yeti || unit->source.charmed.present() || unit->body.hp<=0.)return;
    if(yes(unit->content.headhunt)){
        // Head-hunting borrows the selected Dave field, never the ordinary
        // yeti's nearest-plant field. Share it by goal cell and map revision.
        const auto hero=world_.heroes.globals.position.get();const double tile=world_.runtime.tile;
        chase(unit,hero,{true,int64_t(std::floor(hero->x/tile)),int64_t(std::floor(hero->y/tile)),revision_},hero);
        const auto& p=unit->body.motion.get();const auto row=int(std::floor(p.y/tile));const auto col=int64_t(std::floor(p.x/tile));
        for(int y=row-3;y<row+2;++y)if(world_.terrain.valid_row(y))for(auto x=col-2;x<col+3;++x){
            const auto cell=world_.terrain.at(y,world_.terrain.wrap(x));if(cell&&cell->plant.present()){
                hidden_plants_.emplace_back(cell,cell->plant);cell->plant.erase();
            }
        }
        services_.hide_headhunt_plants(unit);return;
    }
    if(ordered(unit))return;
    const auto origin=targets_.point(CombatTarget::zombie(unit));PlantRef chosen;double closest=0.;
    for(const auto& plant:*world_.plant_roster)if(september_targetable(*plant)) {
        const auto point=targets_.point(plant);const double dx=wrap_delta(origin.x,point.x,world_.world_width.get()),dy=point.y-origin.y;
        const double distance=dx*dx+dy*dy;if(!chosen || distance<closest){chosen=plant;closest=distance;}
    }
    const auto target=chosen?targets_.point(chosen):origin;
    auto goal=std::make_shared<Motion>(Motion{target.x,target.y+world_.runtime.tile*.55,0.,0.});
    if(chosen && chosen->source.id.present())unit->content.target=chosen->source.id;else unit->content.target.set_null();
    chase(unit,goal,{false,int64_t(std::floor(target.x/world_.runtime.tile)),int64_t(std::floor(goal->y/world_.runtime.tile)),revision_});
}
bool SeptemberZombies::wave_chase(const ZombieRef& unit) {
    if(world_.mode==MatchMode::pve || world_.mode==MatchMode::coop)return false;
    if(!scripted_ || unit->source.charmed.present() || unit->protection.grave || unit->orphan_barrel)return false;
    if(yes(unit->content.headhunt) || ordered(unit) || unit->body.hp<=0. || named(unit->source.content,"雪人僵尸"))return false;
    const auto origin=targets_.point(CombatTarget::zombie(unit));std::shared_ptr<Motion> chosen;double closest=0.;
    for(const auto seat:present_) {
        if(team_of(seat)!=Seat::plant)continue;
        const auto& hero=world_.heroes.heroes.at(seat_index(seat)).value();if(hero.frame.hp.get()<=0.)continue;
        const auto position=hero.frame.position.get();
        const double dx=wrap_delta(origin.x,position->x,world_.world_width.get()),dy=position->y-origin.y,distance=dx*dx+dy*dy;
        if(!chosen || distance<closest){chosen=position;closest=distance;}
    }
    if(!chosen)return false;
    auto goal=std::make_shared<Motion>(Motion{chosen->x,chosen->y+world_.runtime.tile*.55,0.,0.});
    chase(unit,goal,{true,int64_t(std::floor(chosen->x/world_.runtime.tile)),int64_t(std::floor(chosen->y/world_.runtime.tile)),revision_},chosen);
    return true;
}
void SeptemberZombies::finish(const ZombieRef& unit) {
    restore_hidden_plants();
    auto& value=unit->content.yeti_tracking;if(!value.present())return;
    const auto saved=value;value.erase();if(!saved.is_null())snapshots_.restore(*saved.get());
}
void SeptemberZombies::restore_hidden_plants(){
    for(auto at=hidden_plants_.rbegin();at!=hidden_plants_.rend();++at)at->first->plant=at->second;
    hidden_plants_.clear();
}
} // namespace pvz::typed72
