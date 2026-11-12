#include "sim/typed/squash_effects.h"
#include "core/pymath.h"
#include <cmath>
#include <tuple>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& n,double fallback=0.){return n.present()&&!n.is_null()?n.get():fallback;}
bool truth(const Field<bool>& b){return b.present()&&!b.is_null()&&b.get();}
bool truth(const Field<SquashLock>& l){return l.present()&&!l.is_null()&&!l.get().empty();}
double sign(double n){return n<0.?-1.:1.;}
Point plant_point(const CombatPlant& p,double tile){return {p.cell.x*tile+tile*.50,p.cell.y*tile+tile*.45};}
}
bool SquashEffects::i_zombie()const {const auto& mode=world_.heroes.globals.mode;return mode.present()&&!mode.is_null()&&mode.get()=="我是僵尸";}
std::optional<std::pair<double,double>> SquashEffects::candidate(Point origin,Point point,double direction,double scale,double size) {
    const double ahead=(point.x-origin.x)*direction,lane=std::abs(point.y-origin.y);
    if(ahead<-scale*.10||ahead>scale*2.35||lane>scale*std::max(.90,.38*std::max(.8,size)))return {};
    return std::pair{std::max(0.,ahead)+lane*3.,py::mod(std::atan2(point.y-origin.y,point.x-origin.x)*(180./0x1.921fb54442d18p+1)+360.,360.)};
}
NativeAim SquashEffects::pick(const ZombieRef& u)const {
    const auto& p=u->body.motion.get();const Point origin{p.x,p.y};const double tile=world_.runtime.tile,direction=sign(u->body.facing);
    NativeAim aim{{},origin};std::optional<double> best_score;const bool friendly=u->source.charmed.present();
    auto consider=[&](NativeAimTarget t,double size){const auto c=candidate(origin,t.captured_point,direction,tile,size);if(c&&(!best_score||c->first<*best_score)){best_score=c->first;t.angle=c->second;aim.target=std::move(t);}};
    if(!friendly) {const auto plants=world_.plant_roster;for(size_t i=0;i<plants->size();++i)try {const auto t=plants->at(i);if(t->dead.present()||t->shovel_dead.present()||number(t->hp,1.)<=0.)continue;consider({t,i,plant_point(*t,tile),direction,0.},2.);}catch(const std::exception&){} }
    const auto zombies=world_.targets;
    for(size_t i=0;i<zombies->size();++i)try {
        const auto t=zombies->at(i);if(t.unit==u)continue;const bool charmed=!t.is_hero()&&t.unit->source.charmed.present();
        if(charmed==friendly||ballistics.body(t).ash.present()||ballistics.body(t).hp<=0.)continue;
        const double size=std::max(.8,number(ballistics.body(t).size,2.));const auto& z=ballistics.motion(t);
        const Point point=friendly?Point{z.x,z.y-tile*.12*size}:aim_.zombie_point(t);consider({t,i,point,direction,0.},size);
    }catch(const std::exception&){}
    const auto& player=world_.heroes.globals.position;
    if(!friendly&&!i_zombie()&&player.present()&&!player.is_null())consider({std::monostate{},0,{player.get()->x,player.get()->y-tile*.65},direction,0.},2.2);
    return aim;
}
std::optional<SquashTargetRecord> SquashEffects::record(const std::optional<NativeAimTarget>& t)const {
    if(!t)return {};SquashTargetRecord r;r.point.set(t->captured_point);r.direction.set(t->direction);
    if(const auto* p=std::get_if<PlantRef>(&t->object)){r.kind.set("plant");r.index.set(int64_t(t->index));r.identity.set((*p)->identity);}
    else if(const auto* z=std::get_if<CombatTarget>(&t->object)){r.kind.set("zombie");r.index.set(int64_t(t->index));r.identity.set(ballistics.identity(*z));}
    else{r.kind.set("player");r.index.set(-1);r.identity.set_null();}return r;
}
BallisticTarget SquashEffects::ballistic(const NativeAimTarget& t) {
    if(const auto* p=std::get_if<PlantRef>(&t.object))return {int64_t(t.index),(*p)->identity,t.captured_point,t.direction};
    if(const auto* z=std::get_if<CombatTarget>(&t.object))return {int64_t(t.index),ballistics.identity(*z),t.captured_point,t.direction};
    // Native ballistic metadata retains the identity of its temporary player
    // target record; this must not alias any persistent object in the world.
    return {-1,world_.runtime.identities.assign(),t.captured_point,t.direction};
}
Point SquashEffects::velocity(const NativeAimTarget& t){if(const auto* z=std::get_if<CombatTarget>(&t.object))return ballistics.velocity(*z,t.direction);return {};}
bool SquashEffects::apply_solution(const EntityRef& e,const BallisticTarget& t,Point v,double speed,bool late) {
    auto position=e->motion.retain();auto [solution,gravity]=ballistics.compute(e,t,v,speed);
    if(!solution&&(std::abs(v.x)>.001||std::abs(v.y)>.001))std::tie(solution,gravity)=ballistics.compute(e,t,{},speed);
    if(!solution)return false;const double ahead=(t.point.x-position->x)*t.direction/std::max(1.,world_.runtime.tile);const auto& s=*solution;
    position->vx=s.vx;position->vy=s.vy;e->facing=t.direction;e->gravity.set(gravity);auto& q=e->squash;
    q.big_sit.set(double(std::clamp(int64_t(s.time+2.),int64_t(4),int64_t(100))));
    if(!q.sit.present())q.sit.set(0.);if(q.bounce_x.present())q.bounce_x.set(double(std::clamp(int64_t(s.time+4.),int64_t(1),int64_t(100))));
    if(!q.lock.present())q.lock.set(SquashLock{});auto& lock=q.lock.get();
    lock.target_index.set(t.index);lock.target_id.set(t.identity);lock.initial_speed.set(speed);lock.gravity.set(gravity);lock.hit_time.set(s.time);lock.direction.set(t.direction);lock.ahead_tiles.set(ahead);lock.late_armed.set(late);return true;
}
void SquashEffects::patch_entity(const EntityRef& e) {
    try{if(e->kind!="窝瓜x"||truth(e->squash.lock))return;const auto& p=e->motion.get();const double speed=std::sqrt(p.vx*p.vx+p.vy*p.vy);if(speed<=.01)return;
        const auto a=ballistics.pick(e,true);if(!a.target||!apply_solution(e,*a.target,a.velocity,speed))return;e->squash.lock.get().created.set(world_.native_time);++patches;
    }catch(const std::exception&){}
}
void SquashEffects::finish_entities() {
    const auto entities=*world_.runtime.entities.list();const double now=world_.native_time;
    for(const auto& e:entities)try{if(e->kind!="窝瓜x")continue;auto& field=e->squash.lock;if(!truth(field)){patch_entity(e);continue;}const auto& l=field.get();if(truth(l.late_armed)||now-number(l.created,now)<.01)continue;
        const double speed=std::max(.01,number(l.initial_speed));auto a=ballistics.squash_locked(e,l);if(!a.target)a=ballistics.pick(e,true);if(a.target)apply_solution(e,*a.target,a.velocity,speed,true);
    }catch(const std::exception&){}
}
bool SquashEffects::raw_spawn(const ZombieRef& u,const std::optional<NativeAimTarget>& target,Point origin,const PlantZombieConfig& c) {
    const auto entities=world_.runtime.entities.list();const Point center=native_plant_zombie_head_center(*u,world_.runtime.tile,catalog_);
    const double direction=target?target->direction:sign(u->body.facing),speed=std::max(1.,number(c.jump_speed,330.)*world_.runtime.plk);
    const Point start{center.x,center.y-world_.runtime.tile*.08};const auto before=entities->size();
    try{callbacks_.add_entity("窝瓜x",direction,{start.x,start.y,direction*speed*.35,-speed*.85});}catch(const std::exception&){return false;}
    if(entities->size()<=before)return false;const auto e=entities->back();auto& q=e->squash;
    q.zombie_entity.set(true);q.friendly.set(u->source.charmed.present());if(auto r=record(target))q.target.set(*r);else q.target.set_null();q.age.set(0.);q.source_zombie.set(u->identity);
    if(target){const auto bt=ballistic(*target);const auto v=velocity(*target);if(!apply_solution(e,bt,v,speed,true)) {
        auto& p=e->motion.get();p.vx=direction*speed*.35;p.vy=-speed*.85;e->gravity.set(2.*world_.runtime.plk);q.big_sit.set(18.);
        if(!q.lock.present())q.lock.set(SquashLock{});if(!q.lock.is_null()){auto& lock=q.lock.get();lock.target_index.set(std::holds_alternative<std::monostate>(target->object)?-1:int64_t(target->index));
            lock.target_id=q.target.get().identity;lock.initial_speed.set(speed);lock.hit_time.set(18.);lock.direction.set(direction);lock.late_armed.set(true);}
    }}world_.runtime.sound("窝瓜",{start.x,start.y,0.,0.});return true;
}
bool SquashEffects::spawn(const ZombieRef& u,const std::optional<NativeAimTarget>& t,Point o,const PlantZombieConfig& c){SourcedContext scope(world_,source_ref(u),CombatPhase::zombies,SourcedCall::spawn);const bool result=raw_spawn(u,t,o,c);scope.finish();return result;}
void SquashEffects::raw_update(const ZombieRef& u,const PlantZombieConfig& c) {
    if(truth(u->patch.squash_used))return;const auto a=pick(u);if(!a.target){u->patch.aim_angle.set(native_direction_angle(u->body.facing));return;}
    u->patch.aim_angle.set(a.target->angle);if(!spawn(u,a.target,a.center,c))return;u->patch.squash_used.set(true);u->body.hp=0.;u->patch.shoot.set(1.);u->patch.fire_animation.set(std::max(12.,std::trunc(number(c.fire_anim,24.))));++attacks;
}
void SquashEffects::update(const ZombieRef& u,const PlantZombieConfig& c){SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_update(u,c);scope.finish();}
SquashResolved SquashEffects::resolve(const Field<SquashTargetRecord>& field)const {
    if(!field.present()||field.is_null())return {};const auto& r=field.get();const auto kind=r.kind.present()&&!r.kind.is_null()?std::optional<std::string>(r.kind.get()):std::nullopt;
    const auto index=r.index.present()&&!r.index.is_null()?r.index.get():-1;const auto id=r.identity.present()&&!r.identity.is_null()?std::optional<RecordId>(r.identity.get()):std::nullopt;
    if(kind=="plant") {
        const auto list=world_.plant_roster;std::optional<size_t> found;
        if(index>=0&&uint64_t(index)<list->size()&&(!id||list->at(size_t(index))->identity==*id))found=size_t(index);
        else if(id)for(size_t i=0;i<list->size();++i)if(list->at(i)->identity==*id){found=i;break;}
        if(!found)return {};const auto p=list->at(*found);if(p->dead.present()||p->shovel_dead.present()||number(p->hp,1.)<=0.)return {};const auto point=plant_point(*p,world_.runtime.tile);return {kind,NativeAimTarget{p,*found,point,1.,0.},point};
    }
    if(kind=="zombie") {
        const auto list=world_.targets;std::optional<size_t> found;
        if(index>=0&&uint64_t(index)<list->size()&&(!id||ballistics.identity(list->at(size_t(index)))==*id))found=size_t(index);
        else if(id)for(size_t i=0;i<list->size();++i)if(ballistics.identity(list->at(i))==*id){found=i;break;}
        if(!found)return {};const auto t=list->at(*found);if(t.is_hero()||!t.unit->source.charmed.present()||t.unit->body.ash.present()||t.unit->body.hp<=0.)return {};const auto point=aim_.zombie_point(t);return {kind,NativeAimTarget{t,*found,point,1.,0.},point};
    }
    if(kind=="player") {if(i_zombie())return {};const auto& p=world_.heroes.globals.position;if(p.present()&&!p.is_null())return {kind,{},Point{p.get()->x,p.get()->y-world_.runtime.tile*.65}};}
    if(r.point.present()&&!r.point.is_null())return {kind,{},r.point.get()};return {};
}
void SquashEffects::kill_plant(const PlantRef& p){p->hurt.set(1.);p->hp.set(0.);try{callbacks_.clear_plant(p->cell);return;}catch(const std::exception&){}p->dead.set(DeathMarker(true));}
void SquashEffects::damage_charmed(size_t index,CombatTarget target,double direction){try{callbacks_.ash_zombie(index);return;}catch(const std::exception&){}try{callbacks_.damage_zombie(index,direction,99999.);return;}catch(const std::exception&){}if(!target.is_hero())target.unit->body.hp=0.;}
bool SquashEffects::damage_player(const EntityRef& e,double impact_x,double direction) {
    if(i_zombie())return false;auto& g=world_.heroes.globals;const auto before=g.hp;
    try{callbacks_.player_damage(10.);}catch(const std::exception&){}
    if(before.present()&&!before.is_null()&&g.hp.present()&&!g.hp.is_null()&&g.hp.get()==before.get()){g.hp.set(before.get()-10.);g.hurt.set(1.);}
    if(g.position.present()&&!g.position.is_null()){auto& p=*g.position.get();const double knock=direction?direction:(p.x>=impact_x?1.:-1.);p.vx+=knock*500.*world_.runtime.plk;p.vy-=500.*world_.runtime.plk;}
    g.hurt.set(1.);e->squash.hit.set(true);return true;
}
void SquashEffects::raw_hit(const EntityRef& e,const Field<SquashTargetRecord>& record,double impact_x) {
    const auto r=resolve(record);if(!r.kind){e->squash.hit.set(true);return;}const auto& field=record.get().direction;const double direction=sign(number(field,field.present()?0.:e->facing));
    if(r.kind=="plant"&&r.target)kill_plant(std::get<PlantRef>(r.target->object));
    else if(r.kind=="zombie"&&r.target)damage_charmed(r.target->index,std::get<CombatTarget>(r.target->object),direction);
    else if(r.kind=="player")damage_player(e,impact_x,direction);
    else{e->squash.hit.set(true);return;}
    e->squash.hit.set(true);world_.runtime.screen_shake.set({80.,0.,0.});++damages;
}
void SquashEffects::hit(const EntityRef& e,const Field<SquashTargetRecord>& r,double x){SourcedContext scope(world_,source_ref(e),CombatPhase::entities);raw_hit(e,r,x);scope.finish();}
bool SquashEffects::enemy(const EntityRef& e){return truth(e->squash.zombie_entity)&&!truth(e->squash.friendly);}
bool SquashEffects::pending()const {for(const auto& e:*world_.runtime.entities.list())if(enemy(e)&&!truth(e->squash.hit))return true;return false;}
void SquashEffects::update_entities() {
    const auto entities=*world_.runtime.entities.list();const double tile=world_.runtime.tile;
    for(const auto& e:entities)try {auto& q=e->squash;if(!enemy(e)||truth(q.hit))continue;auto r=resolve(q.target);if(!r.point&&q.target.present()&&!q.target.is_null()&&q.target.get().point.present()&&!q.target.get().point.is_null())r.point=q.target.get().point.get();if(!r.point)continue;
        const double age=std::trunc(number(q.age))+1.;q.age.set(age);const auto& p=e->motion.get();const double hit_time=q.lock.present()&&!q.lock.is_null()?std::max(4.,number(q.lock.get().hit_time,18.)):18.;
        const bool close=std::abs(p.x-r.point->x)<=tile*.72&&std::abs(p.y-r.point->y)<=tile*1.05;
        if(close||age>=hit_time+3.)hit(e,q.target,p.x);
    }catch(const std::exception&){}
}
bool SquashEffects::splash_secret(bool enabled,std::optional<int64_t> index,double width) {
    if(!enabled)return false;const auto roster=world_.targets;
    if(!index||*index<0||uint64_t(*index)>=roster->size())return true;
    const auto center=roster->at(size_t(*index));const auto& position=ballistics.motion(center);
    const double cx=position.x,cy=position.y-world_.runtime.tile*.5,reach=2.4*world_.runtime.tile;
    const auto owner=world_.heroes.owner();const auto recipients=*roster;
    for(size_t i=0;i<recipients.size();++i) {
        const auto other=recipients[i];if(i==size_t(*index)||other.is_hero()||other.unit->body.hp<=0.||other.unit->body.ash.present())continue;
        if(world_.heroes.owner(source_ref(other.unit))==owner)continue;
        const auto& p=other.unit->body.motion.get();const double dx=py::mod(p.x-cx+width/2.,width)-width/2.,dy=p.y-world_.runtime.tile*.5-cy;
        if(std::hypot(dx,dy)<=reach)callbacks_.damage_zombie(i,1.,500.);
    }
    const auto& id=center.is_hero()?world_.heroes.cached_proxy(center.hero).source.id:center.unit->source.id;
    world_.runtime.events.emplace_back(SquashSplashEvent{id.present()&&!id.is_null()?std::optional<std::string>(id.get()):std::nullopt});return true;
}
} // namespace pvz::typed72
