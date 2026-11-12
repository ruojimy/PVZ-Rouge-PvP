#include "sim/typed/service_plants.h"
#include "sim/typed/mortar_plants.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
double sign(double n,double=1.){return n<0.?-1.:1.;}
bool charmed(const CombatTarget& t){return !t.is_hero()&&t.unit->source.charmed.present();}
bool metal(std::string_view name){return name=="梯子"||name=="钢门"||name=="矿镐"||name=="弹跳杆"||name=="铁桶"||name=="橄榄球头盔"||name=="黑橄榄球头盔"||name=="南瓜头防具";}
}
ZombieRecordFields& ServicePlants::body(const CombatTarget& t)const {
    return t.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):t.unit->body;
}
bool ServicePlants::live(const CombatTarget& t)const {const auto& b=body(t);return !b.dead.present()&&!b.ash.present()&&b.hp>0.;}
bool ServicePlants::head_armor(const CombatTarget& t)const {
    const auto& b=body(t);return b.armor_hp>0.&&(b.armor=="路障"||b.armor=="铁桶"||b.armor=="橄榄球头盔"||b.armor=="黑橄榄球头盔");
}
bool ServicePlants::in_range(Point a,Point b,double tiles)const {
    const double r=std::max(1.,world_.runtime.tile)*tiles;return std::abs(a.x-b.x)<=r&&std::abs(a.y-b.y)<=r;
}
void ServicePlants::animate(const ZombieRef& u,const PlantZombieConfig& c,double spread) {
    const double dir=sign(u->body.facing),frames=std::max(1.,number(c.fire_anim,24.)),anim=number(u->patch.fire_animation);
    if(anim<=0.){u->patch.aim_angle.set(native_direction_angle(dir));return;}
    const double elapsed=std::max(0.,frames-anim),phase=std::sin(pi*std::min(frames,elapsed)/frames);
    u->patch.aim_angle.set(native_direction_angle(dir)+dir*spread*phase);
}
size_t ServicePlants::reflect(const ZombieRef& source,Point center,double tiles) {
    size_t hits=0;const auto entities=*world_.runtime.entities.list();
    for(const auto& e:entities) {
        const auto& n=e->kind;if(n!="卷心菜"&&n!="西瓜"&&n!="冰瓜"&&n!="玉米粒"&&n!="黄油")continue;
        auto& f=e->service;if(f.reflected_by.present()&&!f.reflected_by.is_null()&&f.reflected_by.get()==source->identity)continue;
        auto& p=e->motion.get();if(!in_range(center,{p.x,p.y},tiles))continue;
        const double vx=std::abs(p.vx)<=.001?120.*sign(p.x-center.x):p.vx;
        p.vx=-vx;e->facing=sign(p.vx,e->facing);f.smart.erase();f.smart_skip.set(true);f.reflected_by.set(source->identity);++hits;
    }
    return hits+reflect_mortar_projectiles(world_,source->source,center,tiles);
}
size_t ServicePlants::bounce(Point center,double tiles) {
    size_t hits=0;const double plk=world_.runtime.plk;const auto entities=*world_.runtime.entities.list();
    for(const auto& e:entities)if(e->kind=="篮球"||e->kind=="篮球x") {
        auto& p=e->motion.get();if(!in_range(center,{p.x,p.y},tiles))continue;
        p.vy=std::min(p.vy,-500.*plk);e->kind="篮球x";e->expires.set(std::max(number(e->expires),900.));++hits;
    }return hits;
}
size_t ServicePlants::knock_zombies(const ZombieRef& source,Point center,double tiles) {
    size_t hits=0;const bool friendly=source->source.charmed.present();const double plk=world_.runtime.plk;const auto targets=*world_.targets;
    for(const auto& t:targets)try {
        if(!live(t)||t.unit==source||(friendly&&charmed(t)))continue;
        const auto point=aim_.zombie_point(t);if(!in_range(center,point,tiles))continue;
        auto& b=body(t);auto& p=t.is_hero()?*world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.get();
        p.vx=sign(point.x-center.x,sign(b.facing))*300.*plk;p.vy=std::min(p.vy,-500.*plk);b.gravity.set(std::max(number(b.gravity),2.*plk));++hits;
    }catch(const std::exception&){}return hits;
}
size_t ServicePlants::knock_player(Point center,double tiles) {
    auto& g=world_.heroes.globals;if(!g.position.present()||g.position.is_null()||!g.position.get())return 0;
    auto& p=*g.position.get();if(!in_range(center,{p.x,p.y},tiles))return 0;
    p.vx=sign(p.x-center.x)*300.*world_.runtime.plk;p.vy=std::min(p.vy,-600.*world_.runtime.plk);g.hurt.set(1.);return 1;
}
void ServicePlants::raw_umbrella(const ZombieRef& u,const PlantZombieConfig& c) {
    animate(u,c,55.);auto& p=u->patch;
    const auto cd=p.umbrella_cooldown.present()&&!p.umbrella_cooldown.is_null()?int64_t(p.umbrella_cooldown.get()):world_.runtime.rng.randint(0,25);
    if(cd>0){p.umbrella_cooldown.set(double(cd-1));return;}
    const auto center=native_plant_zombie_head_center(*u,world_.runtime.tile,catalog_);const double radius=number(c.radius,2.);
    size_t hits=knock_zombies(u,center,radius);
    if(u->source.charmed.present()){hits+=bounce(center,radius);hits+=knock_player(center,radius);}else hits+=reflect(u,center,radius);
    if(!hits){p.umbrella_cooldown.set(5.);return;}
    p.fire_animation.set(double(std::max<int64_t>(1,int64_t(number(c.fire_anim,50.)))));p.aim_angle.set(native_direction_angle(sign(u->body.facing)));p.shoot.set(1.);
    p.umbrella_cooldown.set(double(std::max<int64_t>(1,int64_t(number(c.cooldown,100.)))));
    world_.runtime.sound("弹飞",{center.x,center.y,0.,0.});++umbrella_triggers;
}
void ServicePlants::raw_pvp_umbrella(const ZombieRef& u,const PlantZombieConfig& config,bool sourced) {
    PlantZombieConfig c=config;
    if(yes(u->patch.umbrella_secret)) {
        // Python's wrapper deliberately does not coerce None before multiply.
        if(c.cooldown.is_null())throw std::invalid_argument("null umbrella secret cooldown");
        c.cooldown.set(double(std::max<int64_t>(1,int64_t(c.cooldown.or_missing(100.)*.25))));
        if(!yes(u->patch.umbrella_initialized)) {
            u->patch.umbrella_initialized.set(true);const double current=u->patch.umbrella_cooldown.present()&&!u->patch.umbrella_cooldown.is_null()?u->patch.umbrella_cooldown.get():double(world_.runtime.rng.randint(0,25));
            u->patch.umbrella_cooldown.set(double(std::max<int64_t>(0,int64_t(current*.25))));
        }
    }
    if(sourced){SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_umbrella(u,c);scope.finish();}
    else raw_umbrella(u,c);
}
void ServicePlants::umbrella(const ZombieRef& u,const PlantZombieConfig& c) {
    raw_pvp_umbrella(u,c,true);
}
std::optional<MagnetTarget> ServicePlants::bucket_target(const ZombieRef& source,Point center,double tiles) {
    std::optional<MagnetTarget> best;double distance=0.;const auto targets=*world_.targets;
    for(const auto& t:targets)try {
        if(!live(t)||t.unit==source||t.is_hero()||charmed(t)||head_armor(t))continue;
        const auto point=aim_.zombie_point(t);if(!in_range(center,point,tiles))continue;const double dx=point.x-center.x,dy=point.y-center.y,d=dx*dx+dy*dy;
        if(!best||d<distance){best=MagnetTarget{t,point,false};distance=d;}
    }catch(const std::exception&){}return best;
}
std::optional<MagnetTarget> ServicePlants::absorb_target(const ZombieRef& source,Point center,double tiles) {
    std::optional<MagnetTarget> best;double distance=0.;const auto targets=*world_.targets;
    for(const auto& t:targets)try {
        if(!live(t)||t.unit==source||charmed(t))continue;const auto point=aim_.zombie_point(t);if(!in_range(center,point,tiles))continue;
        const auto& b=body(t);const bool hand=metal(b.hand)&&b.hand_hp>0.,armor=metal(b.armor)&&b.armor_hp>0.;if(!hand&&!armor)continue;
        const double dx=point.x-center.x,dy=point.y-center.y,d=dx*dx+dy*dy;if(!best||d<distance){best=MagnetTarget{t,point,hand};distance=d;}
    }catch(const std::exception&){}return best;
}
bool ServicePlants::gift(const CombatTarget& t,Point center) {
    int multiplier=1;const auto& mode=world_.heroes.globals.mode;
    if(mode.present()&&!mode.is_null()){
        if(mode.get()=="末日模式")multiplier=4;
        else if(mode.get()=="极难模式"||mode.get()=="无尽模式"||mode.get()=="测试模式"||mode.get()=="植物僵尸")multiplier=2;
    }
    auto& b=body(t);if(!t.is_hero()){b.armor="铁桶";b.armor_hp=500.*multiplier;}b.hurt=1.;world_.runtime.sound("磁力",{center.x,center.y,0.,0.});return true;
}
EntityRef ServicePlants::attract(std::string name,Point start,Point end) {
    const auto entities=world_.runtime.entities.list();const auto before=entities->size();
    try{callbacks_.add_entity(std::move(name),sign(end.x-start.x),{start.x,start.y,0.,0.});}catch(const std::exception&){return {};}
    if(entities->size()<=before)return {};const auto e=entities->back();e->expires.set(-8000.);e->service.attract.set(1.);e->service.attract_is_boolean=true;e->service.attract_start.set(start);e->service.attract_end.set(end);return e;
}
bool ServicePlants::absorb(const CombatTarget& t,Point target,Point center,bool handheld) {
    auto& b=body(t);auto& slot=handheld?b.hand:b.armor;auto& hp=handheld?b.hand_hp:b.armor_hp;
    if(!metal(slot)||hp<=0.)return false;const std::string name=slot;if(!t.is_hero()){slot="";hp=0.;}b.hurt=1.;attract(name,target,center);
    world_.runtime.sound("磁力",{center.x,center.y,0.,0.});return true;
}
void ServicePlants::raw_magnet(const ZombieRef& u,const PlantZombieConfig& c) {
    animate(u,c,28.);auto& p=u->patch;
    const auto cd=p.magnet_cooldown.present()&&!p.magnet_cooldown.is_null()?int64_t(p.magnet_cooldown.get()):world_.runtime.rng.randint(0,25);
    if(cd>0){p.magnet_cooldown.set(double(cd-1));return;}
    const auto center=native_plant_zombie_head_center(*u,world_.runtime.tile,catalog_);bool fired=false;
    if(u->source.charmed.present()){
        if(auto t=absorb_target(u,center,9.)){fired=absorb(t->target,t->point,center,t->handheld);if(fired)++magnet_absorbs;}
    }else if(auto t=bucket_target(u,center,number(c.radius,5.))){fired=gift(t->target,center);if(fired)++magnet_gifts;}
    if(!fired){p.magnet_cooldown.set(15.);return;}
    p.fire_animation.set(double(std::max<int64_t>(1,int64_t(number(c.fire_anim,90.)))));p.aim_angle.set(native_direction_angle(sign(u->body.facing)));p.shoot.set(1.);
    p.magnet_cooldown.set(double(std::max<int64_t>(1,int64_t(number(c.cooldown,500.)))));
}
void ServicePlants::magnet(const ZombieRef& u,const PlantZombieConfig& c) {
    SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_magnet(u,c);scope.finish();
}
} // namespace pvz::typed72
