#include "sim/typed/entity_contacts.h"
#include "sim/typed/flood.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool yes(const Field<bool>& f) {return f.present() && !f.is_null() && f.get();}
bool contains(const std::vector<std::string>& names,std::string_view name) {
    return std::find(names.begin(),names.end(),name)!=names.end();
}
const std::string& unit_root(const AttackSource& s,const ZombieRecordFields& b) {
    if (s.content.present() && !s.content.is_null() && !s.content.get().empty()) return s.content.get();
    if (s.variant.present() && !s.variant.is_null() && !s.variant.get().empty()) return s.variant.get();
    return b.kind;
}
double corpse_offset(const ZombieRecordFields& b,double tile) {
    if (b.hp>=0.) return 0.;
    const double angle=std::clamp(-std::abs(b.hp)*b.facing,-90.,90.);
    return std::abs(angle)*tile*.008;
}
}
ZombieRecordFields& EntityContacts::body(const CombatTarget& t) const {
    if(t.is_hero())return world_.heroes.cached_proxy(t.hero);
    return t.unit->body;
}
Motion& EntityContacts::motion(const CombatTarget& t) const {
    if(t.is_hero())return *world_.heroes.cached_proxy(t.hero).position;
    return t.unit->body.motion.get();
}
bool EntityContacts::allows_contact(const Entity& e,const CombatTarget& t) const {
    const auto& p=e.motion.get();
    const double tile=world_.runtime.tile;
    if(!t.is_hero() && t.unit->orphan_barrel) {
        const auto& b=*t.unit->barrel_position.get();
        const double dx=wrap_delta(b.x,p.x,world_.world_width.get())/(tile*.65);
        const double dy=(p.y-(b.y-tile*.6))/(tile*.65);
        return std::pow(dx,2.)+std::pow(dy,2.)<=1.;
    }
    const double feet=motion(t).y;
    if(p.y>=feet)return false;
    if(yes(e.source.melon_splash) || yes(e.source.area_damage))return true;
    const auto& source=t.is_hero()?world_.heroes.cached_proxy(t.hero).source:t.unit->source;
    const auto found=collision_.unit_scale.find(unit_root(source,body(t)));
    return found==collision_.unit_scale.end() || found->second>=1. ||
           std::abs(feet-p.y)<=1.75*tile*found->second;
}
std::optional<size_t> EntityContacts::find_contact(size_t l) const {
    const auto& e=entity(l);
    if(yes(e.squash.zombie_entity))return {};
    const auto& p=e.motion.get();
    const auto tile=world_.runtime.tile;
    for(size_t z=world_.targets->size();z-- >0;) {
        const auto t=target(z);
        const auto& source=t.is_hero()?world_.heroes.cached_proxy(t.hero).source:t.unit->source;
        const auto& b=body(t);
        if(source.charmed.present() || b.ash.present())continue;
        const auto& m=motion(t);
        const double dx=b.size.get(), offset=corpse_offset(b,tile);
        if(p.x>m.x-tile*.15*dx && p.x<m.x+tile*.15*dx &&
           p.y>m.y-tile*.85*dx+offset && allows_contact(e,t))return z;
    }
    return {};
}
void EntityContacts::set_status(size_t z,HeroStatus status,double value) {
    const auto t=target(z);
    if(t.is_hero())world_.heroes.write_proxy_status(t.hero,status,value);
    else if(status==HeroStatus::ice)t.unit->body.ice.set(value);
    else if(status==HeroStatus::butter)t.unit->body.butter.set(value);
    else t.unit->body.stun.set(value);
}
void EntityContacts::ice_hit(size_t z,double ticks) {
    const auto t=target(z);
    const auto& ice=body(t).ice;
    if(!ice.present() || (!ice.is_null() && ice.get()==0.))
        world_.runtime.sound("冰冻",motion(t));
    set_status(z,HeroStatus::ice,ticks);
}
void EntityContacts::splat(size_t z) {
    auto& runtime=world_.runtime;
    runtime.sound("splat"+std::to_string(runtime.rng.randint(1,3)),motion(target(z)));
}
bool EntityContacts::strike(size_t l,const std::string& name,double driving) {
    if(!contains(rules_.damaging,name))return false;
    auto& w=world_.runtime;
    auto& shot=entity(l);
    auto& p=shot.motion.get();
    const Cell cell=terrain_cell({p.x,p.y},w.tile);
    if(driving>0. && cell.y<9) {
        p.vx-=w.plk;
        if(p.vx<0.)shot.facing=-1.;
    }
    const bool thrown=contains(rules_.thrown,name);
    if(thrown || name=="窝瓜" || name=="篮球x")p.vx+=shot.facing*w.plk*2.;
    // TorchRules installs a constant-false predicate at 101468. Conversion
    // is run by the dedicated pre-entity phase, before the owner split.
    const auto hit=find_contact(l);
    if(!hit)return false;
    const size_t z=*hit;
    const auto t=target(z);
    bool surface=!(thrown && p.y<motion(t).y-w.tile);
    double damage=10.;
    if(name=="泡泡" || name=="海泡泡" || name=="玉米粒")damage=5.;
    else if(name=="卷心菜")damage=30.;
    else if(name=="火豆") {
        damage=contains(*world_.heroes.globals.secrets.get(),"蓝火")?30.:20.;
        surface=body(t).hand=="报纸" || body(t).hand=="气球";
    } else if(name=="西瓜" || name=="冰瓜") {
        damage=150.;
        motion(t).vx+=shot.facing*w.plk*200.;
    }
    if(shot.facing==body(t).facing && !shot.tracking.present())surface=false;
    if(surface) {
        surface=callbacks_.surface_damage(z,shot.facing,damage).value();
        if(!surface && damage>5. && !entity(l).tracking.present()) {
            callbacks_.knockback(z,entity(l).facing*w.plk*200.);
            if(name=="冰豆")ice_hit(z,1150.);
        }
    } else {
        if(damage>5.)callbacks_.knockback(z,entity(l).facing*w.plk*200.);
        callbacks_.ordinary_damage(z,entity(l).facing,damage);
        if(name=="冰豆")ice_hit(z,1200.);
    }
    if(name=="黄油") {
        w.sound("黄油",motion(target(z)));
        set_status(z,HeroStatus::butter,3000.);
    }
    if(name=="火豆") {
        // HeroProxy has a write interceptor, but inherits raw delitem.
        body(target(z)).ice.erase();
        w.sound("火豆"+std::to_string(w.rng.randint(1,2)),entity(l).motion.get());
    } else if(name!="西瓜" && name!="冰瓜" && !surface)splat(z);
    return true;
}
void EntityContacts::home(size_t l,std::optional<size_t> nearest) {
    auto& e=entity(l);
    if(!e.tracking.present())return;
    e.tracking.set(e.tracking.get()+1.);
    if(!nearest)return;
    const auto t=target(*nearest);
    const auto& m=motion(t);
    auto& p=e.motion.get();
    const double x=m.x-p.x;
    if(x==0.)return;
    const auto& source=t.is_hero()?world_.heroes.cached_proxy(t.hero).source:t.unit->source;
    const auto found=rules_.homing_height.find(unit_root(source,body(t)));
    const double height=found==rules_.homing_height.end()?2.:found->second;
    const double y=m.y-world_.runtime.tile*std::min(1.,height/2.)-p.y;
    e.rotation.set(std::atan2(y,x)*(180./pi));
    const double angle=pi*2.*(-e.rotation.get()/360.);
    const double speed=py::floordiv(e.tracking.get(),2.);
    p.vy=-std::sin(angle)*speed*world_.runtime.plk;
    p.vx=std::cos(angle)*speed*world_.runtime.plk;
}
void EntityContacts::freeze_melon(size_t l) {
    bool sounded=false;
    const double tile=world_.runtime.tile;
    for(size_t z=world_.targets->size();z-- >0;) {
        const auto t=target(z);
        const auto& source=t.is_hero()?world_.heroes.cached_proxy(t.hero).source:t.unit->source;
        if(source.charmed.present())continue;
        const auto& b=body(t);
        const auto& m=motion(t);
        const auto& p=entity(l).motion.get();
        if(p.x<=m.x-tile*1.3 || p.x>=m.x+tile*1.3 ||
           p.y<=m.y-tile*2.7+corpse_offset(b,tile) || p.y>=m.y+tile)continue;
        if(!sounded && (!b.ice.present() || (!b.ice.is_null() && b.ice.get()==0.))) {
            world_.runtime.sound("冰冻",m);
            sounded=true;
        }
        set_status(z,HeroStatus::ice,1000.);
    }
}
} // namespace pvz::typed72
