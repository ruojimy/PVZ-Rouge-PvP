#include "sim/typed/native_barrels.h"
#include "sim/typed/content_zombie_state.h"
#include "sim/typed/projectile_rules.h"
#include "sim/typed/flood.h"
#include "core/pymath.h"
#include <array>
#include <unordered_set>
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& field){return field.present() && !field.is_null() && field.get();}
bool named(const Field<std::string>& field,std::string_view name){return field.present() && !field.is_null() && field.get()==name;}
bool closed(const CombatZombie& unit){return yes(unit.content.barrel_broken) || yes(unit.content.barrel_discarded) || yes(unit.content.barrel_detached);}
}
bool NativeBarrels::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));
    if(row<0)return false;if(uint64_t(row)>=published_.solid.size())return true;
    const auto& line=published_.solid.at(size_t(row));
    return line.at(size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile))%line.size())!=0;
}
bool NativeBarrels::active(const CombatZombie& unit){return named(unit.source.content,"滚桶僵尸") && unit.body.hand_hp>0. && !unit.source.charmed.present();}
void NativeBarrels::track(const ZombieRef& unit){carriers_.push_back(unit);unit->content.barrel_remaining.set(unit->body.hand_hp);}
ZombieRef NativeBarrels::orphan_copy(const ZombieRef& unit,double hp) {
    // deepcopy(native record), then remove only _pvp_* fields and the four
    // explicit raw status keys. The surviving original patch fields are typed.
    auto orphan=std::make_shared<CombatZombie>();orphan->body=unit->body;orphan->native=unit->native;orphan->patch=unit->patch;
    auto& patch=orphan->patch;
    patch.umbrella_secret.erase();patch.umbrella_initialized.erase();patch.no_attack.erase();patch.bite_plant.erase();
    patch.miner_rally.erase();patch.speed_factors.clear();patch.shotgun_volley.erase();patch.torch_sleep_until.erase();patch.torch_brain.erase();
    orphan->source.content=unit->source.content;orphan->content.barrel_direction=unit->content.barrel_direction;
    auto position=*unit->barrel_position.get();position.vx=0.;orphan->body.motion.replace(position);
    orphan->barrel_position.set(orphan->body.motion.retain());orphan->body.ash.erase();orphan->body.blown.erase();
    orphan->body.hp=hp;orphan->body.hand.clear();orphan->body.hand_hp=hp;orphan->body.armor.clear();orphan->body.armor_hp=0.;
    orphan->native.entry.set(500.);orphan->body.size.set(3.);orphan->body.ice.set(0.);orphan->body.butter.set(0.);orphan->body.stun.set(0.);
    orphan->body.hurt=0.;orphan->orphan_barrel=true;orphan->body.facing=unit->content.barrel_direction.get();
    orphan->protection.basketball=unit->protection.basketball;
    return orphan;
}
ZombieRef NativeBarrels::detach(const ZombieRef& unit,std::optional<double> hp) {
    if(!named(unit->source.content,"滚桶僵尸") || unit->orphan_barrel || closed(*unit))return {};
    const double remaining=hp.value_or(unit->body.hand_hp);if(remaining<=0.)return {};
    auto orphan=orphan_copy(unit,remaining);
    unit->body.hand.clear();unit->body.hand_hp=0.;unit->content.barrel_detached.set(true);
    world_.add_zombie(orphan);services_.register_barrel(orphan,unit->source.id);
    ScriptedSpawnBudget::inherit(orphan->source,&unit->source);orphan->max_hp.set(400.);
    const auto position=*orphan->barrel_position.get();
    services_.barrel_event({BarrelEvent::Kind::detached,orphan->source.id,unit->source.id,remaining,{position.x,position.y}});
    return orphan;
}
void NativeBarrels::reconcile() {
    std::unordered_set<const CombatZombie*> live;for(const auto& target:*world_.targets)if(target.unit)live.insert(target.unit.get());
    std::vector<ZombieRef> kept;
    // A callback can track another carrier while this list is being traversed.
    for(size_t i=0;i<carriers_.size();++i) {
        const auto unit=carriers_[i];if(closed(*unit))continue;
        if(!live.contains(unit.get()) || unit->body.hp<=0. || unit->body.ash.present())
            detach(unit,unit->body.hand_hp!=0.?unit->body.hand_hp:unit->content.barrel_remaining.or_missing(0.));
        else {unit->content.barrel_remaining.set(unit->body.hand_hp);kept.push_back(unit);}
    }
    carriers_=std::move(kept);
}
void NativeBarrels::contact(const ZombieRef& unit,double factor) {
    const auto before=*unit->barrel_position.get();const double tile=world_.runtime.tile;
    const auto roster=world_.plant_roster;
    for(size_t i=0;i<roster->size();++i) {
        if(unit->body.hand_hp<=0.)break;
        const auto plant=roster->at(i);const auto point=targets_.point(plant);
        if(plant->hp.or_missing(0.)<=0. || plant->dead.present() ||
           std::abs(wrap_delta(before.x,point.x,world_.world_width.get()))>tile*.7 || std::abs(before.y-tile*.5-point.y)>tile)continue;
        if(plant->kind=="地刺" || plant->kind=="地刺王") {
            unit->body.hand_hp=0.;if(plant->kind=="地刺")plant->dead.set(DeathMarker(0.));
        }else if(factor!=0.) {
            services_.crush_barrel_plant(unit,plant);if(!unit->orphan_barrel)unit->native.biting.set(0.);
        }
    }
    if(unit->body.hand_hp<=0.)break_barrel(unit);
}
void NativeBarrels::float_on_water(Motion& position) {
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    int64_t row=int64_t(std::floor((position.y-tile*.3)/tile));
    if(!published_.water_at({position.x,(row+.5)*tile},tile,width))return;
    while(row>0 && published_.water_at({position.x,(row-.5)*tile},tile,width))--row;
    const double surface=row*tile+tile*.6;
    if(position.y>=surface) {
        if(position.y<=surface+1.){position.y=surface;position.vy=std::min(0.,position.vy);}
        else position.vy=std::min(position.vy,-std::min(world_.runtime.plk*180.,(position.y-surface)*.08));
    }
}
void NativeBarrels::correct_pair(const ZombieRef& unit) {
    auto& position=*unit->barrel_position.get();const auto body=unit->body.motion.get();
    const double tile=world_.runtime.tile,width=world_.world_width.get(),direction=unit->content.barrel_direction.get();
    const double gap=wrap_delta(body.x,position.x,width)*direction;if(gap>=-.1*tile && gap<=1.8*tile)return;
    const double x=py::mod(body.x+direction*tile*.9,width);
    for(const auto rise:{0.,.5,1.,1.5}) {
        const double y=body.y-rise*tile;bool clear=true;
        for(const auto dx:{-.6,0.,.6})for(const auto dy:{.01,.6,1.2})if(solid({x+dx*tile,y-dy*tile}))clear=false;
        if(clear){position={x,y,0.,std::min(0.,position.vy)};services_.barrel_event({BarrelEvent::Kind::corrected,unit->source.id,{},0.,{x,y}});return;}
    }
}
int NativeBarrels::displace(Motion& position) {
    const double tile=world_.runtime.tile,plk=world_.runtime.plk;const auto& map=world_.terrain;
    const double x=position.x,y=position.y;
    const std::array<Point,9> samples{{{x-tile*.6,y-tile*1.2},{x-tile*.6,y-tile*.01},
        {x+tile*.6,y-tile*1.2},{x+tile*.6,y-tile*.01},{x-tile*.6,y-tile*.6},{x+tile*.6,y-tile*.6},
        {x,y-tile*1.2},{x,y-tile*.6},{x,y-tile*.01}}};
    if(position.vx<0.){position.vx+=plk*2.;if(position.vx>0.)position.vx=0.;}
    else if(position.vx>0.){position.vx-=plk*2.;if(position.vx<0.)position.vx=0.;}
    position.vy+=plk*4.;bool horizontal=true,vertical=true;
    const auto outside=[&](Cell point,bool open_top){return (!open_top && point.y<0)||point.y>=map.rows();};
    for(const auto point:samples) {
        const auto v=terrain_cell({point.x,point.y+position.vy},tile),h=terrain_cell({point.x+position.vx,point.y},tile);
        if(outside(v,true)||(v.y>=0&&!map.empty(v.y,v.x)))vertical=false;
        if(outside(h,true)||(h.y>=0&&!map.empty(h.y,h.x)))horizontal=false;
    }
    if(!(horizontal||vertical)){position.y-=plk*20.;position.x-=position.vx;}
    int collision=0;
    if(vertical)position.y+=position.vy;
    else {collision=2;if(position.vy>0.){collision=1;position.vy=std::max(-std::abs(position.vx),-plk*200.);}else position.vy=0.;}
    if(horizontal)position.x+=position.vx;
    else {if(!(vertical||horizontal))position.x-=position.vx;position.vx=0.;}
    if(outside(terrain_cell({position.x-tile*.6,position.y},tile),false))position.x+=plk*10.;
    if(outside(terrain_cell({position.x+tile*.6,position.y},tile),false))position.x-=plk*10.;
    return collision;
}
void NativeBarrels::break_barrel(const ZombieRef& unit) {
    if(closed(*unit) || yes(unit->poison.killed))return;
    unit->content.barrel_broken.set(true);unit->body.hand.clear();unit->body.hand_hp=0.;if(unit->orphan_barrel)unit->body.hp=0.;
    const auto position=*unit->barrel_position.get();world_.runtime.emit_particles("滚桶",{position.x,position.y},12.);
    for(int index=0;index<2;++index)summons_.summon(unit,"小鬼僵尸",true,index*.2);
}
void NativeBarrels::move(const ZombieRef& unit,double factor) {
    auto& position=*unit->barrel_position.get();auto& body=unit->body.motion.get();
    const double tile=world_.runtime.tile,width=world_.world_width.get(),direction=unit->content.barrel_direction.get();
    double distance=wrap_delta(body.x,position.x,width)*direction;
    const double pushed=std::max(0.,wrap_delta(unit->grenadier.before.get().x,body.x,width)*direction);
    position.vx=factor!=0. && distance<=1.8*tile?direction*pushed:0.;
    const int landed=displace(position);float_on_water(position);position.x=py::mod(position.x,width);
    const bool obstacle=solid({position.x+direction*tile*.65,position.y-tile*.3});
    const bool grounded=landed==1 || solid({position.x,position.y+tile*.1});
    if(factor!=0. && grounded && obstacle)position.vy=-world_.runtime.plk*400.;
    distance=wrap_delta(body.x,position.x,width)*direction;
    if(distance<tile*.6) {const double candidate=py::mod(position.x-direction*tile*.6,width);if(!solid({candidate,body.y-tile*.5}))body.x=candidate;}
    position.vx=0.;
}
void NativeBarrels::tick() {
    reconcile();const auto snapshot=*world_.targets;
    for(const auto& target:snapshot) {
        const auto unit=target.unit;if(!unit || !unit->orphan_barrel || yes(unit->content.barrel_broken))continue;
        auto& position=unit->body.motion.get();position.vx=0.;displace(position);float_on_water(position);
        position.x=py::mod(position.x,world_.world_width.get());position.vx=0.;
        const bool held=unit->body.ice.or_missing(0.)>1000. || unit->body.butter.or_missing(0.)>0. || unit->body.stun.or_missing(0.)>0.;
        contact(unit,held?0.:1.);
        for(auto* field:{&unit->body.ice,&unit->body.butter,&unit->body.stun})if(field->or_missing(0.)>0.)field->get()-=1.;
        unit->body.hand_hp=std::max(0.,unit->body.hp);if(unit->body.hand_hp<=0.)break_barrel(unit);
    }
    auto kept=std::make_shared<TargetRoster>();for(const auto& target:*world_.targets)
        if(!target.unit || !target.unit->orphan_barrel || !yes(target.unit->content.barrel_broken))kept->push_back(target);
    world_.targets=std::move(kept);
}
bool NativeBarrels::overlap(const ZombieRef& unit,Point point)const {
    const auto barrel=*unit->barrel_position.get();const double radius=world_.runtime.tile*.65;
    const double dx=wrap_delta(barrel.x,point.x,world_.world_width.get())/radius,dy=(point.y-(barrel.y-world_.runtime.tile*.6))/radius;
    return dx*dx+dy*dy<=1.;
}
void NativeBarrels::draw(const ZombieRef& unit,bool drawing) {
    if(!drawing || !active(*unit))return;const auto position=*unit->barrel_position.get();
    services_.draw_barrel_sprite({position.x,position.y},-position.x/world_.runtime.tile*90.);
}
} // namespace pvz::typed72
