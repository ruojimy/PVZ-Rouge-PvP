#include "sim/typed/plant_zombie_shooting.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& n,double fallback=0.){return n.present()&&!n.is_null()?n.get():fallback;}
double integer(const Field<double>& n,double fallback=0.){return std::trunc(number(n,fallback));}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?std::string_view(f.get()):std::string_view{};}
double sign(double x){return x<0.?-1.:1.;}
}
bool PlantZombieShooting::live(std::span<const CombatTarget> units,std::optional<std::span<const std::string>> names) {
    for(const auto& t:units) {
        if(t.is_hero())continue;const auto& u=*t.unit;
        if(!flag(u.patch.plant_zombie)||(names&&std::find(names->begin(),names->end(),name(u.patch.plant_name))==names->end()))continue;
        if(u.body.dead.present()||u.body.ash.present()||u.body.hp<=0.)continue;return true;
    }return false;
}
void PlantZombieShooting::enforce_motion(const ZombieRef& u,const PlantZombieConfig& c) {
    const double plk=world_.runtime.plk;bool changed=false;std::optional<double> desired;
    if(c.move_speed.present()&&!c.move_speed.is_null()) {
        desired=std::max(1.,c.move_speed.get()*plk);const double old=number(u->native.move_speed,*desired);
        if(std::abs(old-*desired)>std::max(.5,std::abs(*desired)*.05)){u->native.move_speed.set(*desired);changed=true;}
    }
    if(number(c.jump_speed)!=0.)return;
    bool marker=u->body.pole_vault.present();auto& b=u->body;
    if(b.hand=="撑杆"||b.hand=="弹跳杆"){b.hand.clear();b.hand_hp=0.;marker=true;changed=true;}
    if(marker){b.pole_vault.erase();u->native.jump_cd.set(0.);auto& p=b.motion.get();
        const double max_vx=std::max(desired.value_or(std::abs(number(u->native.move_speed,40.))),1.)*1.6;
        if(std::abs(p.vx)>max_vx)p.vx=sign(p.vx)*max_vx;if(p.vy< -90.*plk)p.vy=-90.*plk;
    }
    u->patch.jump_assist_cooldown.erase();if(changed)++motion_fixes;
}
bool PlantZombieShooting::solid(int64_t row,int64_t col)const {
    const auto tile=world_.terrain.at(row,col);return tile&&tile->block.present()&&!tile->block.is_null()&&!world_.terrain.is_empty(tile->block.get());
}
void PlantZombieShooting::jump_assist(const ZombieRef& u,const PlantZombieConfig& c) {
    const double jump=number(c.jump_speed);if(jump==0.)return;auto retained=u->body.motion.retain();auto& p=*retained;
    const double cd=integer(u->patch.jump_assist_cooldown);if(cd>0.){u->patch.jump_assist_cooldown.set(cd-1.);return;}if(std::abs(p.vy)>1.)return;
    const double scale=std::max(1.,world_.runtime.tile),direction=sign(u->body.facing);
    const auto row=int64_t(py::floordiv(p.y-scale*.20,scale)),col=int64_t(py::floordiv(p.x+direction*scale*.58,scale));
    if(!solid(row,col)&&!solid(row-1,col)){u->patch.jump_assist_cooldown.set(5.);return;}
    const double speed=std::max(1.,jump*world_.runtime.plk);p.vx+=direction*speed*.12;p.vy=std::min(p.vy,-speed);
    u->body.gravity.set(std::max(number(u->body.gravity),2.*world_.runtime.plk));u->patch.jump_assist_cooldown.set(75.);
}
void PlantZombieShooting::step(std::span<const PlantZombieConfig> catalog) {
    const auto roster=world_.targets;if(!live(*roster))return;const auto captured=*roster;
    for(const auto& t:captured)try {
        if(t.is_hero())continue;const auto u=t.unit;auto& p=u->patch;if(!flag(p.plant_zombie)||u->body.hp<=0.)continue;
        const auto found=std::find_if(catalog.begin(),catalog.end(),[&](const auto& c){return c.kind==name(p.plant_name);});if(found==catalog.end())continue;const auto& c=*found;
        enforce_motion(u,c);systems_.deaths.row_hint(t,false);const bool friendly=u->source.charmed.present();
        const double cooldown=std::max(1.,integer(c.cooldown,100.)),initial=std::max(0.,integer(c.initial_cooldown_max,25.)),gap=std::max(1.,integer(c.burst_gap,6.)),frames=std::max(1.,integer(c.fire_anim,24.));
        const double animation=number(p.fire_animation);if(animation>0.)p.fire_animation.set(animation-1.);else if(number(p.shoot)!=0.)p.shoot.set(0.);
        jump_assist(u,c);
        if(flag(c.squash)){systems_.squash.update(u,c);continue;}
        if(flag(c.blover)){systems_.wind.update(u,c);continue;}
        if(flag(c.lantern)){systems_.lantern.update(u,c);continue;}
        if(flag(c.umbrella)){systems_.services.umbrella(u,c);continue;}
        if(flag(c.gold_magnet)){systems_.services.magnet(u,c);continue;}
        if(flag(c.fumeshroom)){systems_.fume.update(u,c);continue;}
        // Admission requires a complete four-coordinate position, so the
        // literal helper's malformed-position/None-center branch is excluded
        // at the boundary. Target absence still updates the facing angle.
        auto aim=aim_.update(u);if(!flag(c.shoot))continue;
        double left=integer(p.burst_left),burst_cd=integer(p.burst_cooldown);
        if(left>0.) {
            if(burst_cd>0.){p.burst_cooldown.set(burst_cd-1.);continue;}
            aim=aim_.update(u);
            if(systems_.peas.spawn(aim.center,sync_native_head_angle(*u).second,friendly,t)){p.shoot.set(1.);p.fire_animation.set(frames);}
            left-=1.;p.burst_left.set(left);if(left>0.)p.burst_cooldown.set(gap);else p.shooting_cooldown.set(cooldown);continue;
        }
        const double cd=integer(p.shooting_cooldown);if(cd>0.){p.shooting_cooldown.set(cd-1.);continue;}
        const double burst=std::max(1.,integer(c.burst,1.));aim=aim_.update(u);
        if(systems_.peas.spawn(aim.center,sync_native_head_angle(*u).second,friendly,t)){p.shoot.set(1.);p.fire_animation.set(frames);}
        if(burst>1.){p.burst_left.set(burst-1.);p.burst_cooldown.set(gap);}else p.shooting_cooldown.set(cooldown+(cd== -1.?world_.runtime.rng.randint(0,int64_t(initial)):0.));
    }catch(const std::exception&){}
}
} // namespace pvz::typed72
