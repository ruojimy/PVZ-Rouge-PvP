#include "sim/typed/grenadiers.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <tuple>

namespace pvz::typed72 {
void Grenadiers::advance(const ZombieRef& unit,bool alive) {
    auto& state=unit->grenadier;
    const auto phase=state.phase;
    if(!alive) {
        if(phase.present() && !phase.is_null() && phase.get()==GrenadierPhase::wind) {
            state.phase.set(GrenadierPhase::cancelled);
            services_.grenade_event({GrenadeEvent::Kind::cancelled,unit->source.id});
        }
        return;
    }
    const double hp=unit->body.hp;
    if(phase.present() && !phase.is_null() && phase.get()==GrenadierPhase::ready && hp<state.seen_hp.or_missing(hp)-1e-9) {
        state.phase.set(GrenadierPhase::wind);state.clock.set(0.);
        state.hold_x.set(state.before.present()?state.before.get().x:unit->body.motion.get().x);
    }
    state.seen_hp.set(hp);
    if(!state.phase.present() || state.phase.is_null() || state.phase.get()!=GrenadierPhase::wind)return;
    auto& position=unit->body.motion.get();position.x=state.hold_x.or_missing(position.x);position.vx=0.;
    const auto& body=unit->body;
    const bool held=body.ice.or_missing(0.)>1000. || body.butter.or_missing(0.)>0. || body.stun.or_missing(0.)>0.;
    state.clock.get()+=held?0.:body.ice.or_missing(0.)>0.?.5:1.;
    if(state.clock.get()>=250.){state.phase.set(GrenadierPhase::thrown);throw_grenade(unit);}
}
std::optional<ContentTarget> Grenadiers::target(const ZombieRef& unit) {
    struct Candidate {double negative_cost,distance;std::string id;ContentTarget target;};
    std::optional<Candidate> plant,other;
    const double tile=world_.runtime.tile;const auto& position=unit->body.motion.get();
    const Point origin{position.x,position.y-tile};const auto owner=world_.heroes.owner(source_ref(unit));
    for(const auto& candidate:queries_.enemies(source_ref(unit))) {
        const auto* p=std::get_if<PlantRef>(&candidate);
        const auto* body=std::get_if<CombatTarget>(&candidate);
        const double hp=p?(*p)->hp.or_missing(1.):body->is_hero()?world_.heroes.cached_proxy(body->hero).hp:body->unit->body.hp;
        if(hp<=0.)continue;
        const auto point=targets_.point(candidate);
        const double distance=py::hypot(wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y);
        if(distance>6.*tile+1e-9)continue;
        const auto source=queries_.source(candidate);const auto id=world_.heroes.source_id(source);
        Field<std::string> card;
        if(p)card=(*p)->protection.card;
        else if(!body->is_hero())card=body->unit->protection.card;
        const bool priced=p || (card.present() && card.get().starts_with("zombie:") && owner==Seat::plant);
        double cost=0.;
        if(priced && card.present() && !card.is_null() && !card.get().empty()) {
            try{cost=services_.card_cost(world_.heroes.owner(source),card.get());}catch(const std::exception&){}
        }
        auto& best=priced?plant:other;
        if(!best || std::tuple{-cost,distance,id}<std::tuple{best->negative_cost,best->distance,best->id})
            best=Candidate{-cost,distance,id,candidate};
    }
    if(plant)return plant->target;
    if(other)return other->target;
    return {};
}
void Grenadiers::throw_grenade(const ZombieRef& unit) {
    const auto aim=target(unit);
    if(!aim){services_.grenade_event({GrenadeEvent::Kind::no_target,unit->source.id});return;}
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    const double direction=unit->body.facing>=0.?1.:-1.;const auto& position=unit->body.motion.get();
    const Point start{position.x+direction*tile*.2,position.y-tile*1.9};
    Point point;
    if(const auto* plant=std::get_if<PlantRef>(&*aim))point={((*plant)->cell.x+.5)*tile,((*plant)->cell.y+.6)*tile};
    else point=targets_.point(*aim);
    point.x=start.x+wrap_delta(start.x,point.x,width);
    const double speed=700.*world_.runtime.plk;
    const auto solution=NativeBallistics::intercept(start,point,{},speed,gravity_,2000.,BallisticArc::high);
    double vx,vy;
    if(solution){vx=solution->vx;vy=solution->vy;}
    else {
        const double time=std::max(1.,std::abs(point.x-start.x)/(speed*.7071));
        vx=(point.x-start.x)/time;vy=(point.y-start.y-.5*gravity_*time*time)/time;
    }
    const Seat owner=world_.heroes.owner(source_ref(unit)).value();
    const Seat carrier=unit->source.seat?*unit->source.seat:parse_seat(unit->source.owner.or_missing("zombie"));
    const auto& secrets=world_.heroes.players.at(seat_index(carrier)).value().secrets;
    const bool empowered=std::find(secrets.begin(),secrets.end(),"zsecret:手雷")!=secrets.end();
    Seat seat=unit->source.seat.value_or(owner);if(team_of(seat)!=team_of(owner))seat=owner;
    auto grenade=std::make_shared<Grenade>();grenade->motion={py::mod(start.x,width),start.y,vx,vy};
    grenade->owner=owner;grenade->seat.set(seat);grenade->direction.set(direction);grenade->source=unit->source.id;
    if(!grenade->source.present())grenade->source.set_null();
    grenade->target=world_.heroes.source_id(queries_.source(*aim));grenade->instant.set(empowered);
    grenade->cell={int(std::floor(point.y/tile)),int64_t(py::mod(std::floor(point.x/tile),world_.terrain.cols()))};
    grenades->push_back(grenade);
    GrenadeEvent event{GrenadeEvent::Kind::thrown,unit->source.id};event.other.set(grenade->target);services_.grenade_event(event);
}
bool Grenadiers::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));
    if(row<0)return false;
    if(uint64_t(row)>=published_.solid.size())return true;
    const auto& line=published_.solid.at(size_t(row));
    if(line.empty())throw std::domain_error("empty published grenade row");
    const auto column=size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile));
    return line.at(column%line.size())!=0;
}
void Grenadiers::update() {
    const auto original=grenades;auto kept=std::make_shared<GrenadeRoster>();
    for(size_t index=0;index<original->size();++index) {
        const auto grenade=original->at(index);auto& p=grenade->motion;
        ++grenade->age;p.vy+=gravity_;p.x=py::mod(p.x+p.vx,world_.world_width.get());p.y+=p.vy;
        if(grenade->defused) {
            if(grenade->age<900 && p.y<world_.world_height.get()+world_.runtime.tile && !solid({p.x,p.y}))kept->push_back(grenade);
            continue;
        }
        if(reflect(grenade)){kept->push_back(grenade);continue;}
        const Cell cell{int(std::floor(p.y/world_.runtime.tile)),int64_t(py::mod(std::floor(p.x/world_.runtime.tile),world_.terrain.cols()))};
        if(solid({p.x,p.y}) || (cell==grenade->cell && p.vy>0.) || p.y>world_.world_height.get()+world_.runtime.tile || grenade->age>2000)
            explode(grenade,cell);
        else kept->push_back(grenade);
    }
    grenades=std::move(kept);
}
bool Grenadiers::reflect(GrenadeRef grenade) {
    const double tile=world_.runtime.tile;const auto plants=world_.plant_roster;
    for(size_t index=0;index<plants->size();++index) {
        const auto plant=plants->at(index);
        if(plant->kind!="萝卜伞" || plant->hp.or_missing(0.)<=0. || plant->dead.present() || plant->sleep.present())continue;
        if(world_.heroes.owner(source_ref(plant))==grenade->owner)continue;
        const Point center{(plant->cell.x+.5)*tile,(plant->cell.y+.5)*tile};auto& p=grenade->motion;
        if(std::abs(wrap_delta(center.x,p.x,world_.world_width.get()))>tile*1.5 || std::abs(p.y-center.y)>tile*1.5)continue;
        p.vx=-p.vx;p.vy=std::min(p.vy,-500.*world_.runtime.plk);grenade->defused=true;grenade->age=0;
        if(plant->shooting.or_missing(0.)==0. && plant->shoot_cd.or_missing(0.)<=0.)plant->shooting.set(1.);
        GrenadeEvent event{GrenadeEvent::Kind::reflected,grenade->source};event.other=plant->source.id;
        services_.grenade_event(event);return true;
    }
    return false;
}
bool Grenadiers::zombie_vs_zombie(const ContentTarget& target) {
    const auto* body=std::get_if<CombatTarget>(&target);
    return body && !body->is_hero() && !body->unit->protection.grave && !body->unit->orphan_barrel;
}
void Grenadiers::explode(GrenadeRef grenade,Cell cell) {
    const double tile=world_.runtime.tile;const Seat owner=grenade->owner;
    std::optional<NativeObject> origin;
    if(grenade->source.present() && !grenade->source.is_null())origin=world_.native_objects.get(grenade->source.get());
    Seat seat=owner;double direction=1.;
    if(origin)std::visit([&](const auto& unit){seat=unit->source.seat.value_or(owner);
        if constexpr(std::is_same_v<std::decay_t<decltype(unit)>,PlantRef>)direction=unit->facing;
        else direction=unit->body.facing;
    },*origin);
    if(grenade->seat.present())seat=grenade->seat.is_null()?owner:grenade->seat.get();
    if(team_of(seat)!=team_of(owner))seat=owner;
    direction=grenade->direction.or_missing(direction);
    auto source=std::make_shared<AttackSource>();source->zombie.set("掷弹兵僵尸");source->owner.set(std::string(seat_name(owner)));
    source->seat=seat;source->id=grenade->source;
    const bool instant=grenade->instant.present() && !grenade->instant.is_null() && grenade->instant.get();
    const int reach=instant?1:0;
    const auto inside=[&](Point point) {
        return std::abs(std::floor(point.y/tile)-cell.y)<=reach &&
            std::abs(wrap_delta(double(cell.x),py::mod(std::floor(point.x/tile),world_.terrain.cols()),world_.terrain.cols()))<=reach;
    };
    std::vector<ContentTarget> bodies;
    for(const auto& plant:*world_.plant_roster)if(inside({(plant->cell.x+.5)*tile,(plant->cell.y+.5)*tile}) && plant->hp.or_missing(0.)>0. && !plant->dead.present())
        bodies.push_back(plant);
    for(const auto& target:*world_.targets)if(!target.is_hero() && target.unit->body.hp>0.) {
        const auto& p=target.unit->body.motion.get();
        if(inside({p.x,p.y-tile*.5}) || inside({p.x,p.y-tile*1.5}))bodies.push_back(target);
    }
    std::vector<std::string> hits;
    for(const auto& target:bodies) {
        const auto record=queries_.source(target);
        if(world_.heroes.owner(record)==owner)continue;
        if(instant) {
            const auto* plant=std::get_if<PlantRef>(&target);
            const auto& protection=plant?(*plant)->protection:std::get<CombatTarget>(target).unit->protection;
            if(double(world_.heroes.tick)<protection.anchor_until.or_missing(0.))continue;
            if(plant){(*plant)->hp.set(0.);(*plant)->dead.set(DeathMarker(0.));}
            else {auto& body=std::get<CombatTarget>(target).unit->body;body.hp=0.;body.ash.set(0.);}
        }else targets_.damage(source,target,6.*(zombie_vs_zombie(target)?10.:1.),direction,false,HeroHit::grenade);
        hits.push_back(world_.heroes.source_id(record));
    }
    for(const auto enemy:seats_for(world_.mode)) {
        if(team_of(enemy)!=(owner==Seat::plant?Seat::zombie:Seat::plant))continue;
        const auto& hero=world_.heroes.hero(enemy).frame;const auto& p=*hero.position.get();
        if(hero.hp.or_missing(0.)<=0. || (!inside({p.x,p.y-tile*.4}) && !inside({p.x,p.y-tile*1.2})))continue;
        world_.heroes.proxy(enemy);
        const auto proxy=world_.heroes.proxy_source(enemy);
        targets_.damage(source,CombatTarget::player(enemy),instant?1e6:6.,direction,false,instant?HeroHit::ash:HeroHit::grenade);
        hits.push_back(proxy->id.or_missing("hero:"+std::string(seat_name(enemy))));
    }
    blasts.push_back({world_.heroes.tick,{(cell.x+.5)*tile,(cell.y+.5)*tile},instant});
    try{world_.runtime.play_sound("土豆地雷");}catch(const std::exception&){}
    GrenadeEvent event{GrenadeEvent::Kind::explode,grenade->source};event.cell=cell;event.targets=std::move(hits);event.instant=instant;
    services_.grenade_event(event);
}
} // namespace pvz::typed72
