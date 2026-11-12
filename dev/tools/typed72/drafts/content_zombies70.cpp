#include "sim/typed/content_zombies70.h"
#include "sim/typed/content_zombie70_state.h"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <tuple>
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& value){return value.present() && !value.is_null() && value.get();}
bool named(const Field<std::string>& value,std::string_view name){return value.present() && !value.is_null() && value.get()==name;}
bool defused(const ContentProjectile& value){return yes(value.defused);}
bool defused(const Grenade& value){return value.defused;}
void defuse(ContentProjectile& value){value.defused.set(true);}
void defuse(Grenade& value){value.defused=true;}
Seat shot_owner(const ContentProjectile& value){return value.owner.get();}
Seat shot_owner(const Grenade& value){return value.owner;}
std::string shot_kind(const ContentProjectile& value){return value.kind.or_missing("grenade");}
std::string shot_kind(const Grenade&){return "grenade";}
void shot_direction(ContentProjectile& value,double direction){value.direction=direction;}
void shot_direction(Grenade& value,double direction){value.direction.set(direction);}
std::optional<Seat> target_owner(TypedBattleState& world,const ContentTarget& target) {
    if(const auto* plant=std::get_if<PlantRef>(&target))return world.heroes.owner(source_ref(*plant));
    const auto& body=std::get<CombatTarget>(target);
    return body.is_hero()?std::optional<Seat>(team_of(body.hero)):world.heroes.owner(source_ref(body.unit));
}
struct Exemption {int& count;explicit Exemption(int& value):count(value){++count;}~Exemption(){--count;}};
}
bool ContentZombies70::head(const PlantRef& plant){return named(plant->source.content,"抓人草触手");}
bool ContentZombies70::alive(const ContentTarget& value)const {
    if(const auto* plant=std::get_if<PlantRef>(&value))return (*plant)->hp.or_missing(0.)>0. && !(*plant)->dead.present();
    const auto body=std::get<CombatTarget>(value);
    const auto& state=body.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(body.hero)):
        static_cast<const ZombieRecordFields&>(body.unit->body);
    return state.hp>0. && !state.ash.present() && !state.dead.present();
}
double ContentZombies70::factor(const CombatZombie& unit) {
    return unit.body.ice.or_missing(0.)>1000. || unit.body.butter.or_missing(0.)>0. || unit.body.stun.or_missing(0.)>0.?
        0.:unit.body.ice.or_missing(0.)>0.?.5:1.;
}
bool ContentZombies70::seat_has(const ZombieRef& unit,std::string_view secret)const {
    const auto seat=unit->source.seat?*unit->source.seat:unit->source.owner.present()?parse_seat(unit->source.owner.get()):Seat::zombie;
    const auto& values=world_.heroes.players.at(seat_index(seat)).value().secrets;
    return std::find(values.begin(),values.end(),secret)!=values.end();
}
bool ContentZombies70::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));
    if(row<0)return false;if(uint64_t(row)>=published_.solid.size())return true;
    const auto& line=published_.solid.at(size_t(row));
    return line.at(size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile))%line.size())!=0;
}
std::shared_ptr<AttackSource> ContentZombies70::snapshot(const ZombieRef& unit)const {
    const auto owner=world_.heroes.owner(source_ref(unit)).value();auto seat=unit->source.seat.value_or(owner);
    if(team_of(seat)!=owner)seat=owner;
    auto source=std::make_shared<AttackSource>();source->owner.set(std::string(seat_name(owner)));source->seat=seat;source->id=unit->source.id;
    return source;
}
std::optional<ContentTarget> ContentZombies70::target(const std::optional<NativeObject>& object) {
    if(!object)return {};
    return std::visit([](const auto& unit)->ContentTarget {
        if constexpr(std::is_same_v<std::decay_t<decltype(unit)>,PlantRef>)return unit;
        else return CombatTarget::zombie(unit);
    },*object);
}
bool ContentZombies70::configure(const ZombieRef& unit,std::string_view name) {
    if(name!="钩索僵尸" && name!="死神僵尸")return false;
    unit->source.content.set(std::string(name));unit->content70.clock.set(0.);unit->body.hp=120.;unit->max_hp.set(120.);
    if(name=="死神僵尸")unit->protection.reaper_hurt.set(double(world_.heroes.tick));return true;
}
void ContentZombies70::gate(const ZombieRef& unit) {
    if(unit->body.kind=="飞贼僵尸")airdrop(unit);
    const bool is_hook=named(unit->source.content,"钩索僵尸"),is_reaper=named(unit->source.content,"死神僵尸");
    if(!is_hook && !is_reaper)return;
    for(const auto part:{"-身","-首"})services_.alias_art(unit->body.kind+part,unit->source.content.get()+part);
    if(!alive(CombatTarget::zombie(unit)) || unit->native.entry.or_missing(500.)<400.)return;
    auto& state=unit->content70;
    if(is_reaper) {
        const bool idle=double(world_.heroes.tick)-unit->protection.reaper_hurt.get()>=5000.;
        if(idle!=yes(state.reaper_idle)) {
            state.reaper_idle.set(idle);services_.zombie70_event({idle?Zombie70Event::Kind::reaper_idle:Zombie70Event::Kind::reaper_resumed,unit->source.id});
        }
        if(idle)return;
    }
    state.clock.get()+=factor(*unit);
    if(state.clock.get()>=1500.) {const bool fired=is_hook?hook(unit):throw_bone(unit);state.clock.set(fired?state.clock.get()-1500.:1450.);}
}
void ContentZombies70::airdrop(const ZombieRef& unit) {
    if(!alive(CombatTarget::zombie(unit)) || unit->native.entry.or_missing(0.)<500. || unit->native.leaving.present() ||
       yes(unit->content70.airdrop_used) || !seat_has(unit,"zsecret:空输"))return;
    unit->content70.airdrop_used.set(true);const auto source=scripted_spawn_origin(unit);
    if(!budget_.can_spawn(1,source.source)){budget_.defer(source.source,"airdrop",0.,[this,source]{return airdrop_child(source);});return;}
    airdrop_child(source);
}
bool ContentZombies70::airdrop_child(const ScriptedSpawnOrigin& source) {
    const auto point=source.position.get();const auto owner=world_.heroes.owner(source.source).value();if(world_.native_objects.size()>=700)return false;
    ZombieRef child;
    {HeroContext context(world_.heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::summon,source.source,{}});
     Exemption exemption(world_.spawn_ban_exempt);child=services_.spawn_airdrop({point.x,point.y},source.facing.or_missing(-1.),source);}
    if(!child)return false;child->native.entry.set(500.);if(owner==Seat::plant)child->source.charmed.set(200.);
    Zombie70Event event{Zombie70Event::Kind::airdrop,source.source->id,child->source.id};event.owner.set(owner);services_.zombie70_event(event);return true;
}
std::optional<ContentTarget> ContentZombies70::hook_target(const ZombieRef& unit) {
    const bool charmed=world_.heroes.owner(source_ref(unit))==Seat::plant;const auto start=targets_.point(CombatTarget::zombie(unit));
    std::optional<ContentTarget> chosen;std::pair<double,std::string> best;
    for(const auto& candidate:queries_.enemies(source_ref(unit))) {
        const auto* body=std::get_if<CombatTarget>(&candidate);const auto* plant=std::get_if<PlantRef>(&candidate);
        if((body && body->is_hero()) || !alive(candidate))continue;
        if(charmed && (!body || body->unit->protection.grave))continue;
        if(!charmed && (!plant || head(*plant)))continue;
        const auto point=targets_.point(candidate);const double distance=std::hypot(wrap_delta(start.x,point.x,world_.world_width.get()),point.y-start.y);
        if(distance>12.*world_.runtime.tile)continue;
        const auto key=std::pair{-distance,world_.heroes.source_id(queries_.source(candidate))};
        if(!chosen || key<best){chosen=candidate;best=key;}
    }
    return !chosen || charmed?chosen:taunts_.taunt_target(CombatTarget::zombie(unit),chosen);
}
bool ContentZombies70::hook(const ZombieRef& unit) {
    const auto selected=hook_target(unit);if(!selected)return false;
    const auto start=targets_.point(CombatTarget::zombie(unit)),end=targets_.point(*selected);const auto source=snapshot(unit);
    const bool anchor=seat_has(unit,"zsecret:船锚");const double firing_direction=unit->body.facing;
    if(anchor)for(const auto& candidate:queries_.enemies(source)) {
        if(!alive(candidate) || (candidate!=*selected && !targets_.contact(candidate,start,{wrap_delta(start.x,end.x,world_.world_width.get()),end.y-start.y})))continue;
        const auto* body=std::get_if<CombatTarget>(&candidate);
        targets_.damage(source,candidate,body && !body->is_hero()?30.:3.,firing_direction,false,HeroHit::anchor);
    }
    auto shot=std::make_shared<ContentProjectile>();shot->kind.set("hook");shot->motion={start.x,start.y,0.,0.};
    shot->owner.set(world_.heroes.owner(source).value());shot->source=unit->source.id;shot->seat.set(source->seat.value());
    shot->direction=unit->body.facing;shot->target.set(world_.heroes.source_id(queries_.source(*selected)));shot->anchor.set(anchor);shot->defused.set(false);
    world_.content_projectiles.shots.push_back(shot);
    services_.zombie70_event({Zombie70Event::Kind::hook_fired,unit->source.id,{},shot->target});return true;
}
ContentZombies70::Graves ContentZombies70::graves()const {
    Graves result;const double tile=world_.runtime.tile;
    for(const auto& entry:world_.native_objects.entries())if(const auto* unit=std::get_if<ZombieRef>(&entry.object))
        if((*unit)->protection.grave && alive(CombatTarget::zombie(*unit))) {
            const auto position=(*unit)->body.motion.get();
            result[{int(py::round0(position.y/tile))-1,world_.terrain.wrap(int64_t(std::floor(position.x/tile)))}]=*unit;
        }
    return result;
}
bool ContentZombies70::grave_cell(Cell cell,const Graves& index)const {
    cell.x=world_.terrain.wrap(cell.x);if(cell.y<0 || cell.y>=world_.terrain.rows()-1)return false;
    const auto& tile=world_.terrain.native_at(cell.y,cell.x);
    if(!world_.terrain.empty(cell.y,cell.x) || named(tile.block,"水") || tile.plant.present() || index.contains({cell.y,cell.x}))return false;
    for(const auto& plant:*world_.plant_roster)if(alive(plant) && !head(plant) && plant->cell==cell)return false;
    return !world_.terrain.empty(cell.y+1,cell.x);
}
std::optional<Cell> ContentZombies70::bone_cell(const ZombieRef& unit) {
    const auto start=targets_.point(CombatTarget::zombie(unit));const double tile=world_.runtime.tile,width=world_.world_width.get();
    const auto owner=world_.heroes.owner(source_ref(unit));std::vector<Point> plants;
    for(const auto& plant:*world_.plant_roster)if(alive(plant) && !head(plant) && september_targetable(*plant))plants.push_back(targets_.point(plant));
    const auto index=graves();std::optional<Cell> chosen;std::tuple<double,double,int,int64_t> best;
    for(int row=0;row<world_.terrain.rows();++row)for(int64_t col=0;col<int64_t(world_.terrain.grid.at(size_t(row)).size());++col) {
        const Point point{(col+.5)*tile,(row+.5)*tile};const double distance=std::hypot(wrap_delta(start.x,point.x,width),point.y-start.y);
        if(distance>12.*tile || (owner==Seat::zombie && !grave_cell({row,col},index)))continue;
        const auto grave=index.find({row,col});double score=0.;
        if(owner==Seat::plant)score=grave!=index.end() && world_.heroes.owner(source_ref(grave->second))==Seat::zombie?1000.:0.;
        else for(const auto plant:plants)score+=std::max(0.,4.-std::hypot(wrap_delta(point.x,plant.x,width),plant.y-point.y)/tile);
        const auto key=std::tuple{-score,distance,row,col};if(!chosen || key<best){chosen=Cell{row,col};best=key;}
    }
    return chosen;
}
bool ContentZombies70::throw_bone(const ZombieRef& unit) {
    const auto cell=bone_cell(unit);if(!cell)return false;
    const double tile=world_.runtime.tile;const auto start=targets_.point(CombatTarget::zombie(unit));const Point end{(cell->x+.5)*tile,(cell->y+.8)*tile};
    const double dx=wrap_delta(start.x,end.x,world_.world_width.get()),dy=end.y-start.y;
    const double flight=std::clamp(std::hypot(dx,dy)/(tile*.035),100.,300.),gravity=4.*world_.runtime.plk;
    const auto source=snapshot(unit);auto shot=std::make_shared<ContentProjectile>();shot->kind.set("bone");
    shot->motion={start.x,start.y,dx/flight,(dy-.5*gravity*flight*(flight+1.))/flight};shot->owner.set(world_.heroes.owner(source).value());
    shot->source=unit->source.id;shot->seat.set(source->seat.value());shot->direction=unit->body.facing;shot->cell.set(*cell);shot->defused.set(false);
    world_.content_projectiles.shots.push_back(shot);Zombie70Event event{Zombie70Event::Kind::bone_thrown,unit->source.id};event.cell=*cell;services_.zombie70_event(event);return true;
}
template<class Shot> bool ContentZombies70::reflect_shot(const std::shared_ptr<Shot>& shot) {
    if(defused(*shot))return false;const double tile=world_.runtime.tile;auto& point=shot->motion;
    for(const auto& plant:*world_.plant_roster) {
        if(plant->kind!="萝卜伞" || plant->hp.or_missing(0.)<=0. || plant->dead.present() || plant->sleep.present() || world_.heroes.owner(source_ref(plant))==shot_owner(*shot))continue;
        const Point center{(plant->cell.x+.5)*tile,(plant->cell.y+.5)*tile};
        if(std::abs(wrap_delta(center.x,point.x,world_.world_width.get()))>tile*1.5 || std::abs(point.y-center.y)>tile*1.5)continue;
        defuse(*shot);point.vx=-point.vx;point.vy=std::min(point.vy,-500.*world_.runtime.plk);shot->age=0;
        if(plant->shooting.or_missing(0.)==0. && plant->shoot_cd.or_missing(0.)<=0.)plant->shooting.set(1.);
        services_.zombie70_event({Zombie70Event::Kind::grenade_reflected,shot->source,plant->source.id});return true;
    }
    if(shot_owner(*shot)!=Seat::plant)return false;
    for(const auto& target:*world_.targets) {
        const auto unit=target.unit;
        if(!unit || !alive(target) || world_.heroes.owner(source_ref(unit))==shot_owner(*shot) || factor(*unit)==0. || unit->body.kind!="萝卜伞僵尸")continue;
        const auto center=plant_zombie_head(*unit,tile,collision_);if(!center)continue;
        if(std::abs(wrap_delta(center->center.x,point.x,world_.world_width.get()))>1.5*tile || std::abs(center->center.y-point.y)>1.5*tile)continue;
        defuse(*shot);point.vx=-point.vx;point.vy=std::min(point.vy,-500.*world_.runtime.plk);shot->age=0;unit->patch.shoot.set(1.);
        Zombie70Event event{Zombie70Event::Kind::projectile_reflected,shot->source,unit->source.id};event.projectile=shot_kind(*shot);services_.zombie70_event(event);return true;
    }
    return false;
}
template<class Shot> void ContentZombies70::wind_shot(const std::shared_ptr<Shot>& shot) {
    if(shot_kind(*shot)=="hook")return;
    for(const auto& plant:*world_.plant_roster)if(plant->kind=="三叶草" && plant->hp.or_missing(0.)>0. && !plant->dead.present()) {
        const auto point=targets_.point(plant);
        if(wrap_delta(point.x,shot->motion.x,world_.world_width.get())*plant->facing>=0.) {
            shot->motion.vx+=plant->facing*world_.runtime.plk;if(shot->motion.vx*plant->facing>0.)shot_direction(*shot,plant->facing);
        }
    }
}
bool ContentZombies70::reflect(const ContentProjectileRef& shot){return reflect_shot(shot);}
bool ContentZombies70::reflect(const GrenadeRef& shot){return reflect_shot(shot);}
void ContentZombies70::wind(const ContentProjectileRef& shot){wind_shot(shot);}
void ContentZombies70::wind(const GrenadeRef& shot){wind_shot(shot);}
void ContentZombies70::impact_bone(const ContentProjectileRef& shot,Cell cell) {
    const auto source_object=world_.native_objects.get(shot->source.get());BoneSource source;source.object=source_object;source.direction=shot->direction;
    if(source_object)source.metadata=std::visit([](const auto& value){return source_ref(value);},*source_object);
    else {source.metadata=std::make_shared<AttackSource>();source.metadata->id=shot->source;}
    const auto index=graves();
    if(shot->owner.get()==Seat::zombie) {
        if(!grave_cell(cell,index))return;const auto unit=services_.spawn_bone_grave(cell,source);if(!unit)return;
        unit->source.seat=shot->seat.get();unit->content70.bone_grave.set(true);
        services_.zombie70_event({Zombie70Event::Kind::bone_grave,shot->source,unit->source.id});
    }else {
        const auto found=index.find({cell.y,cell.x});if(found==index.end() || world_.heroes.owner(source_ref(found->second))!=Seat::zombie)return;
        for(const auto& plant:*world_.plant_roster)if(alive(plant) && !head(plant) && plant->cell==cell)return;
        const auto plant=services_.spawn_bone_gravebuster(cell,shot->direction,shot->source);if(!plant)return;
        plant->source.seat=shot->seat.get();binding_.attach(plant,found->second->source.id.get());
        services_.zombie70_event({Zombie70Event::Kind::bone_gravebuster,shot->source,plant->source.id,found->second->source.id});
    }
}
void ContentZombies70::projectiles() {
    const double tile=world_.runtime.tile,width=world_.world_width.get(),gravity=4.*world_.runtime.plk;
    std::vector<ContentProjectileRef> kept;std::optional<Graves> index;
    // The native list iterator admits append-only callbacks until assignment.
    auto& shots=world_.content_projectiles.shots;
    for(size_t i=0;i<shots.size();++i) {
        const auto shot=shots[i];auto& point=shot->motion;++shot->age;if(shot->age>2000.)continue;
        if(yes(shot->defused)) {
            point.vy+=gravity;point.x=py::mod(point.x+point.vx,width);point.y+=point.vy;
            if(shot->age<125. && point.y>0. && point.y<world_.world_height.get())kept.push_back(shot);continue;
        }
        if(named(shot->kind,"hook")) {
            const auto hit=target(world_.native_objects.get(shot->target.get())),source=target(world_.native_objects.get(shot->source.get()));
            if(!hit || !source || !alive(*hit) || !alive(*source) || target_owner(world_,*hit)==shot->owner.get())continue;
            const auto goal=targets_.point(*hit);const double dx=wrap_delta(point.x,goal.x,width),dy=goal.y-point.y,distance=std::hypot(dx,dy),step=tile*.16;
            if(distance>step){point.x=py::mod(point.x+dx/distance*step,width);point.y+=dy/distance*step;}else {point.x=goal.x;point.y=goal.y;}
            if(reflect(shot)){kept.push_back(shot);continue;}
            if(distance<=step) {
                auto packet=std::make_shared<AttackSource>();packet->owner.set(std::string(seat_name(shot->owner.get())));packet->id=shot->source;
                const auto* body=std::get_if<CombatTarget>(&*hit);targets_.damage(packet,*hit,body?30.:3.,shot->direction,false,HeroHit::hook);
                const auto* owner=std::get_if<CombatTarget>(&*source);if(!owner || owner->is_hero())throw std::logic_error("hook source requires native zombie");
                const auto* plant=std::get_if<PlantRef>(&*hit);
                owner->unit->content70.hook_pull.set({goal.x,plant?((*plant)->cell.y+1.)*tile:body->unit->body.motion.get().y});
                if(yes(shot->anchor))owner->unit->protection.anchor_until.set(double(world_.heroes.tick)+750.);
                services_.zombie70_event({Zombie70Event::Kind::hook_hit,shot->source,{},shot->target});continue;
            }
        }else {
            wind(shot);point.vy+=gravity;point.x=py::mod(point.x+point.vx,width);point.y+=point.vy;
            if(reflect(shot)){kept.push_back(shot);continue;}
            const Cell cell{int(std::floor(point.y/tile)),world_.terrain.wrap(int64_t(std::floor(point.x/tile)))};
            if(cell.y<0 || cell.y>=world_.terrain.rows())continue;
            if(shot->owner.get()==Seat::plant) {
                if(!index)index=graves();if(index->contains({cell.y,cell.x})){impact_bone(shot,cell);index.reset();continue;}
            }
            if(solid({point.x,point.y})){impact_bone(shot,{cell.y-1,cell.x});continue;}
        }
        kept.push_back(shot);
    }
    shots=std::move(kept);
    for(const auto& target:*world_.targets)if(target.unit && target.unit->content70.hook_pull.present() && alive(target)) {
        const auto unit=target.unit;auto& point=unit->body.motion.get();const auto goal=unit->content70.hook_pull.get();
        const double dx=wrap_delta(point.x,goal.x,width),dy=goal.y-point.y,distance=std::hypot(dx,dy),step=tile*.2*factor(*unit);
        if(distance<=std::max(step,1e-6)){point={goal.x,goal.y,0.,0.};unit->content70.hook_pull.erase();}
        else if(step!=0.)point={py::mod(point.x+dx/distance*step,width),point.y+dy/distance*step,0.,0.};
    }
    services_.draw_zombie70_effects();
}
} // namespace pvz::typed72
