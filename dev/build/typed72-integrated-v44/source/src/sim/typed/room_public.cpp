#include "sim/typed/room_public.h"
#include "core/pymath.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
template<class T>bool flag(const Field<T>& value){return value.present()&&!value.is_null()&&bool(value.get());}
const void* address(const NativeObject& o){return std::visit([](const auto& p)->const void*{return p.get();},o);}
AttackSource& source(const NativeObject& o){return std::visit([](const auto& p)->AttackSource&{return p->source;},o);}
const UnitProtectionState& protection(const NativeObject& o){return std::visit([](const auto& p)->const UnitProtectionState&{return p->protection;},o);}
int poison(const PoisonSlot& slot){return slot.present()&&!slot.is_null()&&slot.get()?slot.get()->level.or_missing(0):0;}
Seat original_owner(const NativeObject& o){const auto& s=source(o);const auto owner=s.owner.get();if(owner=="plant")return Seat::plant;if(owner=="zombie")return Seat::zombie;throw std::logic_error("registered native unit has invalid owner");}
}
const RoomPublishedUnit* RoomPublicSync::find(const std::string& id)const{const auto it=lookup_.find(id);return it==lookup_.end()?nullptr:&published_.units.at(it->second);}
void RoomPublicSync::sync(std::span<const Seat> avatar_order,bool publish_terrain){
    struct ScratchRelease {std::vector<NativeObject>& births;std::vector<NativeObjectRegistry::Entry>& entries;~ScratchRelease(){births.clear();entries.clear();}} release{births_,registered_};
    for(const auto& plant:*world_.plant_roster)services_.harden(plant);
    for(const auto seat:avatar_order){const auto i=seat_index(seat);auto& hero=*world_.heroes.heroes[i];auto& player=*world_.heroes.players[i];const auto& m=*hero.frame.position.get();const double ice=hero.ice.or_missing(0.);
        player.position={m.x,m.y};player.hp=hero.frame.hp.get();if(!published_.heroes[i])published_.heroes[i].emplace();auto& view=published_.heroes[i]->visible;
        view.position=player.position;view.velocity={m.vx*250.,m.vy*250.};view.hp=player.hp;view.max_hp=player.max_hp;view.h=player.height;view.poison=poison(hero.poison);
        view.frozen=ice>1000.;view.slowed=(ice>0.&&ice<=1000.)||hero.cold_until.or_missing(0.)>world_.heroes.tick;view.buttered=hero.butter.or_missing(0.)>0.;view.grounded=hero.landing_result.or_missing(0)!=0;
        view.facing=int64_t(hero.frame.facing.get());view.jumps=int64_t(hero.frame.jump.get());const int cap=services_.jump_cap(seat);view.jump_cap=cap?cap:2;
        const auto facts=services_.hero_facts(seat);view.resource=facts.resource;view.teleport_ready=facts.teleport_ready;view.cannon_aimed=facts.cannon_aimed;view.absent=facts.absent;
        published_.heroes[i]->native_pose.capture(hero);
    }
    // Python concatenates these two lists before registration. Take the same
    // ordered shallow handle snapshot, so a registered birth cannot extend
    // the loop that is already in progress.
    births_.clear();births_.reserve(world_.plant_roster->size()+world_.targets->size());for(const auto& p:*world_.plant_roster)births_.emplace_back(p);for(const auto& t:*world_.targets)if(t.unit)births_.emplace_back(t.unit);
    for(const auto& object:births_){const auto& s=source(object);if((s.id.present()&&!s.id.is_null()&&world_.native_objects.get(s.id.get()))||protection(object).hero)continue;
        const bool plant=s.plant.present();const Seat side=plant?Seat::plant:Seat::zombie;const auto name=plant?s.plant.get():std::string(s.zombie_name());services_.auto_register(object,side,std::string(seat_name(side))+":"+name,true);
    }
    births_.clear();
    live_.clear();live_.reserve(world_.plant_roster->size()+world_.targets->size()+world_.suspended_graves.size());for(const auto& p:*world_.plant_roster)live_.push_back(p.get());for(const auto& t:*world_.targets)if(t.unit)live_.push_back(t.unit.get());for(const auto& z:world_.suspended_graves)live_.push_back(z.get());std::sort(live_.begin(),live_.end(),std::less<const void*>{});
    registered_.assign(world_.native_objects.entries().begin(),world_.native_objects.entries().end());
    published_.units.clear();lookup_.clear();published_.units.reserve(registered_.size());lookup_.reserve(registered_.size());
    const bool blue=std::find(native_secrets_->begin(),native_secrets_->end(),"蓝火")!=native_secrets_->end();
    for(const auto& entry:registered_){const auto& object=entry.object;const auto owner=original_owner(object);const auto& src=source(object);const auto& protected_state=protection(object);const auto& key=protected_state.card.get();
        if(!std::binary_search(live_.begin(),live_.end(),address(object),std::less<const void*>{})){
            services_.death({entry.key,key,owner});if(world_.protection.secrets.enabled)services_.unit_gone(object);
            const auto* plant=std::get_if<PlantRef>(&object);const bool consumed=plant&&src.content.present()&&!src.content.is_null()&&src.content.get()=="黄金蓓蕾"&&flag((*plant)->effect_done);
            if(services_.base_producer(key)&&!consumed)++room_.players[seat_index(src.seat.value_or(owner))].producer_lost;world_.native_objects.erase(entry.key);continue;
        }
        RoomPublishedUnit unit;unit.id=entry.key;unit.original_owner=owner;unit.side=src.charmed.present()?Seat::plant:owner;unit.seat=src.seat;unit.card=services_.unit_card(owner,key);if(!unit.card)throw std::logic_error("missing resolved public unit card");const auto facts=services_.registration(object);
        unit.w=world_.runtime.tile*.6;unit.h=world_.runtime.tile;unit.floating=facts.floating;unit.secret_speed.assign(facts.secret_speed.begin(),facts.secret_speed.end());
        if(const auto* plant=std::get_if<PlantRef>(&object)){const auto& p=**plant;unit.position={(p.cell.x+.5)*world_.runtime.tile,(p.cell.y+1.)*world_.runtime.tile};unit.hp=p.hp.or_missing(0.);unit.max_hp=facts.registered_plant_max_hp;unit.facing=p.facing;unit.armor_max=facts.plant_armor_max;unit.temporary=flag(p.temporary);unit.awake=!p.sleep.present();unit.copy_card=p.copy_card.present()&&!p.copy_card.is_null()&&!p.copy_card.get().empty()?std::optional<std::string>(p.copy_card.get()):std::nullopt;unit.drowsy=facts.coop_dormant;unit.drowsy_level=facts.coop_dormant?1.:0.;
        }else{const auto& z=*std::get<ZombieRef>(object);const auto& m=z.body.motion.get();unit.position={m.x,m.y};unit.velocity={m.vx*250.,m.vy*250.};unit.hp=z.body.hp;unit.max_hp=z.max_hp.get();unit.facing=z.body.facing;unit.armor_hp=z.body.armor_hp;unit.armor_max=z.armor_max.get();unit.mobile=!z.protection.grave&&!z.orphan_barrel;unit.h=world_.runtime.tile*(!z.protection.grave&&unit.card->behavior!="tentacle"?1.5:1.);unit.burrowed=z.native.emerged.present();unit.temporary=facts.zombie_temporary;
            const double ice=z.body.ice.or_missing(0.);unit.frozen=ice>1000.;unit.slowed=ice>0.&&ice<=1000.;unit.buttered=z.body.butter.or_missing(0.)>0.;unit.stunned=z.body.stun.or_missing(0.)>0.;unit.production_rate=z.production_rate.or_missing(1.);unit.mature=flag(z.mature);unit.poison_level=poison(z.poison.poison);
            const bool asleep=world_.heroes.tick<z.patch.torch_sleep_until.or_missing(0.);unit.drowsy=graves_.drowsy(z)||asleep||facts.coop_dormant;unit.drowsy_level=asleep||facts.coop_dormant?1.:py::roundn(graves_.level(z),3);
            if(z.protection.grave)unit.first_soldier_ready=services_.first_soldier()&&!facts.first_soldier_used;
            if(z.orphan_barrel){unit.orphan_barrel=true;unit.w=unit.h=world_.runtime.tile*1.2;unit.armor_hp=unit.armor_max=0.;}
        }
        unit.torch_blue=key=="zombie:石化火炬"&&(services_.rage()||blue);lookup_[entry.key]=published_.units.size();published_.units.push_back(std::move(unit));
    }
    registered_.clear();
    if(publish_terrain){published_.terrain.sync(world_.terrain,services_.head_only_cells(),sight_);services_.set_belts(published_.terrain.belts);}
}
} // namespace pvz::typed72
