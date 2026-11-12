#include "sim/typed/fume_effects.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool charmed(const CombatTarget& t){return !t.is_hero()&&t.unit->source.charmed.present();}
bool metal(std::string_view name){return name=="梯子"||name=="钢门"||name=="矿镐"||name=="弹跳杆"||name=="铁桶"||name=="橄榄球头盔"||name=="黑橄榄球头盔"||name=="南瓜头防具";}
double angle_to(Point from,Point to){return py::mod(std::atan2(to.y-from.y,to.x-from.x)*(180./pi)+360.,360.);}
}
ZombieRecordFields& FumeEffects::body(const CombatTarget& t)const{return t.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):t.unit->body;}
bool FumeEffects::i_zombie()const {const auto& f=world_.heroes.globals.mode;return f.present()&&!f.is_null()&&f.get()=="我是僵尸";}
bool FumeEffects::thunder(const ZombieRef& u)const {
    if(!u->source.charmed.present()||!u->patch.plant_name.present()||u->patch.plant_name.is_null()||u->patch.plant_name.get()!="大喷菇僵尸")return false;
    const auto& f=world_.heroes.globals.secrets;return f.present()&&!f.is_null()&&f.get()&&std::find(f.get()->begin(),f.get()->end(),"雷霆")!=f.get()->end();
}
bool FumeEffects::has_metal(const CombatTarget& t)const {const auto& b=body(t);return (metal(b.hand)&&b.hand_hp>0.)||(metal(b.armor)&&b.armor_hp>0.);}
bool FumeEffects::stun(const CombatTarget& t,Point point) {
    if(!has_metal(t))return false;const double amount=std::max(number(body(t).stun),200.);
    if(t.is_hero())world_.heroes.write_proxy_status(t.hero,HeroStatus::stun,amount);else body(t).stun.set(amount);
    world_.runtime.sound("电击",{point.x,point.y,0.,0.});return true;
}
bool FumeEffects::within(Point a,Point b,double tiles)const {
    const double r=std::max(1.,world_.runtime.tile)*tiles,dx=b.x-a.x,dy=b.y-a.y;return dx*dx+dy*dy<=r*r;
}
bool FumeEffects::ray(Point origin,double angle,Point point,double radius,double length_tiles)const {
    const double scale=std::max(1.,world_.runtime.tile),length=scale*std::max(.1,length_tiles);radius=std::max(1.,radius);
    const double rad=angle*(pi/180.),ux=std::cos(rad),uy=std::sin(rad),dx=point.x-origin.x,dy=point.y-origin.y,ahead=dx*ux+dy*uy;
    if(ahead<-radius*.25||ahead>length+radius*.25)return false;return std::abs(dx*uy-dy*ux)<=radius;
}
NativeAim FumeEffects::pick(const ZombieRef& source,const PlantZombieConfig& c)const {
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);const double range=number(c.range_tiles,9.),dir=source->body.facing<0.?-1.:1.;
    const bool friendly=source->source.charmed.present();std::optional<NativeAimTarget> best;double score=0.;
    auto candidate=[&](std::variant<PlantRef,CombatTarget,std::monostate> obj,size_t index,Point point){
        if(!within(center,point,range))return;const auto angle=angle_to(center,point);if(!native_angle_in_direction(angle,dir))return;
        const double dx=point.x-center.x,dy=point.y-center.y,d=dx*dx+dy*dy;if(!best||d<score){best=NativeAimTarget{std::move(obj),index,point,dir,angle};score=d;}
    };
    if(!friendly){const auto plants=*world_.plant_roster;for(size_t i=0;i<plants.size();++i){const auto& p=plants[i];if(p->dead.present()||p->shovel_dead.present()||number(p->hp,1.)<=0.)continue;candidate(p,i,aim_.plant_aim(*p,center));}}
    const auto targets=*world_.targets;for(size_t i=0;i<targets.size();++i)try {
        const auto& t=targets[i];if(t.unit==source||charmed(t)==friendly||body(t).ash.present()||body(t).hp<=0.)continue;candidate(t,i,aim_.zombie_point(t));
    }catch(const std::exception&){}
    const auto& player=world_.heroes.globals.position;
    if(!friendly&&!i_zombie()&&player.present()&&!player.is_null()&&player.get())candidate(std::monostate{},size_t(-1),{player.get()->x,player.get()->y-world_.runtime.tile});
    return {best,center};
}
bool FumeEffects::damage_plant(const PlantRef& p,double amount) {
    p->hurt.set(1.);double hp=number(p->hp);static const std::string no_hand;
    hp-=world_.protection.amount({hp,no_hand,p->source,p->protection},amount);p->hp.set(hp);
    if(hp<=0.)try{callbacks_.clear_plant(p->cell);}catch(const std::exception&){}return true;
}
bool FumeEffects::damage_player(double direction) {
    if(i_zombie())return false;auto& g=world_.heroes.globals;const auto before=g.hp;
    try{callbacks_.player_damage(1.);}catch(const std::exception&){}
    if(before.present()&&!before.is_null()&&g.hp.present()&&!g.hp.is_null()&&g.hp.get()==before.get()){g.hp.set(before.get()-1.);g.hurt.set(1.);}
    if(g.position.present()&&!g.position.is_null()&&g.position.get())g.position.get()->vx=(direction<0.?-1.:1.)*120.*world_.runtime.plk;return true;
}
bool FumeEffects::damage_zombie(size_t index,CombatTarget t,double amount,double direction) {
    try{callbacks_.zombie_damage(index,direction,amount);return true;}catch(const std::exception&){}
    const double hp=body(t).hp-amount;if(t.is_hero())world_.heroes.write_proxy_hp(t.hero,hp);else body(t).hp=hp;body(t).hurt=1.;return true;
}
void FumeEffects::splat(Point p) {world_.runtime.sound("splat"+std::to_string(world_.runtime.rng.randint(1,3)),{p.x,p.y,0.,0.});}
void FumeEffects::bubbles(Point center,double angle,const PlantZombieConfig& c,bool blue) {
    auto& rt=world_.runtime;const std::string name=blue?"蓝泡泡":"大泡泡";
    if(std::find(rt.other_images.begin(),rt.other_images.end(),name)==rt.other_images.end())rt.other_images.push_back(name);
    const double scale=std::max(1.,rt.tile),rad=angle*(pi/180.),ux=std::cos(rad),uy=std::sin(rad),px=-uy,py=ux;
    const int64_t count=std::max<int64_t>(1,int64_t(number(c.visual_bubbles,36.)));const double length=std::max(.5,number(c.attack_length,6.));const int64_t tiles=std::max<int64_t>(1,int64_t(length+.999));
    const double drift=scale*.018*std::max(.5,rt.plk);auto& list=world_.fume.bubbles;
    for(int64_t i=0;i<count;++i){const auto tile=i%tiles,ring=i/tiles;const double along_jitter=std::sin(i*2.17+angle*.03)*.20,side_lane=((ring%5)-2)*.16,side_jitter=std::cos(i*1.43+angle*.05)*.09;
        const double along=std::min(length-.10,std::max(.25,tile+.55+along_jitter)),side=(side_lane+side_jitter)*scale;
        const double sx=ux*std::sin(i*.91)+px*std::cos(i*1.29),sy=uy*std::sin(i*.91)+py*std::cos(i*1.29);
        list.push_back({name,{center.x+ux*scale*along+px*side,center.y+uy*scale*along+py*side,sx*drift,sy*drift},0,22+(i%9)});
    }
    if(list.size()>600)list.erase(list.begin(),list.end()-600);world_.fume.last_update=world_.native_time;
}
void FumeEffects::update_bubbles(std::optional<double> when) {
    auto& f=world_.fume;if(f.bubbles.empty()){f.last_update=0.;return;}const double now=when.value_or(world_.native_time);int64_t step=1;
    if(f.last_update>0.){const double dt=std::max(0.,now-f.last_update);if(dt<.006)return;if(dt<=.20)step=std::max<int64_t>(1,std::min<int64_t>(4,int64_t(py::round0(dt*60.))));}
    f.last_update=now;const double scale=std::max(1.,world_.runtime.tile),width=number(world_.world_width,20.*scale),height=number(world_.world_height,12.*scale);
    auto& list=f.bubbles;size_t kept=0;for(auto& b:list){b.motion.x+=b.motion.vx*step;b.motion.y+=b.motion.vy*step;b.age+=step;
        if(b.age>b.life||b.motion.x<-scale*2.||b.motion.x>width+scale*2.||b.motion.y<-scale*2.||b.motion.y>height+scale*2.)continue;
        if(&b!=&list[kept])list[kept]=std::move(b);++kept;
    }list.resize(kept);
}
int64_t FumeEffects::fire_frames(const PlantZombieConfig& c)const{return std::max<int64_t>(1,int64_t(number(c.fire_anim,100.)));}
int64_t FumeEffects::visual_tick(const PlantZombieConfig& c)const{return std::max<int64_t>(1,int64_t(number(c.visual_tick,8.)));}
int64_t FumeEffects::shoot_tick(const ZombieRef& u,const PlantZombieConfig& c)const {
    const auto shoot=int64_t(number(u->patch.shoot));if(shoot<=0&&number(u->patch.fire_animation)<=0.)return 0;return std::max<int64_t>(1,std::min(fire_frames(c),shoot<=0?1:shoot));
}
size_t FumeEffects::raw_line(const ZombieRef& source,Point center,double angle,const PlantZombieConfig& c) {
    const bool friendly=source->source.charmed.present(),electric=thunder(source),legacy_view=i_zombie();
    const auto view_targets=world_.targets;const double length=number(c.attack_length,6.),scale=std::max(1.,world_.runtime.tile),direction=std::cos(angle*(pi/180.))>=0.?1.:-1.;size_t hits=0;
    if(!friendly){const auto plants=*world_.plant_roster;for(const auto& p:plants)try {
        if(p->dead.present()||p->shovel_dead.present()||number(p->hp,1.)<=0.)continue;
        const Point point{p->cell.x*world_.runtime.tile+world_.runtime.tile*.5,p->cell.y*world_.runtime.tile+world_.runtime.tile*.45};
        if(ray(center,angle,point,scale*.56,length)&&damage_plant(p,1.)){++hits;splat(point);}
    }catch(const std::exception&){} }
    const auto targets=*(legacy_view?view_targets:world_.targets);
    for(size_t index=0;index<targets.size();++index)try {
        const auto& t=targets[index];if(t.unit==source||charmed(t)==friendly||body(t).ash.present()||body(t).hp<=0.)continue;const auto point=aim_.zombie_point(t);
        double radius=scale*.55*std::max(.35,number(body(t).size,1.));if(!t.is_hero())if(auto head=plant_zombie_head(*t.unit,world_.runtime.tile,catalog_))radius=std::max(head->rx,head->ry)*.90;
        if(!ray(center,angle,point,radius,length))continue;
        if(damage_zombie(index,t,friendly?10.:20.,direction)){++hits;splat(point);if(friendly&&electric)stun(t,point);}
    }catch(const std::exception&){}
    if(!friendly&&!legacy_view){const auto& player=world_.heroes.globals.position;if(player.present()&&!player.is_null()&&player.get()){
        const Point point{player.get()->x,player.get()->y-scale};if(ray(center,angle,point,scale*.48,length)&&damage_player(direction)){++hits;splat(point);}
    }}return hits;
}
size_t FumeEffects::line(const ZombieRef& u,Point p,double angle,const PlantZombieConfig& c) {
    SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);const auto hits=raw_line(u,p,angle,c);scope.finish();return hits;
}
bool FumeEffects::fire_animation(const ZombieRef& u,const PlantZombieConfig& c) {
    auto& p=u->patch;const double direction=u->body.facing<0.?-1.:1.,anim=number(p.fire_animation);auto shoot=int64_t(number(p.shoot));if(anim<=0.&&shoot<=0)return false;
    const auto frames=fire_frames(c);if(shoot<=0)shoot=1;else if(shoot<frames)++shoot;shoot=std::max<int64_t>(1,std::min(frames,shoot));p.shoot.set(double(shoot));
    const auto& chosen=p.fume_attack_angle.present()?p.fume_attack_angle:p.aim_angle;const double angle=number(chosen,native_direction_angle(direction));p.aim_angle.set(angle);
    const auto cd=int64_t(number(p.fume_cooldown));if(cd>0)p.fume_cooldown.set(double(cd-1));
    const auto damage_tick=std::max<int64_t>(1,std::min(frames,int64_t(number(c.damage_tick,75.)))),vt=std::max<int64_t>(1,std::min(frames,visual_tick(c))),pulses=std::max<int64_t>(1,int64_t(number(c.damage_pulses,3.)));
    const auto center=native_plant_zombie_head_center(*u,world_.runtime.tile,catalog_);auto done=std::max<int64_t>(0,int64_t(number(p.fume_damage_done)));
    while(done<pulses&&shoot>=damage_tick+vt*done){line(u,center,angle,c);bubbles(center,angle,c,thunder(u));++done;p.fume_damage_done.set(double(done));p.fume_bubble_tick.set(double(shoot));++attack_count;}
    if(shoot>=frames&&anim<=0.){p.shoot.set(0.);p.fire_animation.set(0.);p.fume_damage_done.set(0.);p.fume_bubble_tick.set(0.);}return true;
}
void FumeEffects::raw_update(const ZombieRef& u,const PlantZombieConfig& c) {
    const double direction=u->body.facing<0.?-1.:1.;if(fire_animation(u,c))return;
    const auto aim=pick(u,c);double angle=aim.target?aim.target->angle:number(u->patch.aim_angle,native_direction_angle(direction));
    if(!aim.target&&!native_angle_in_direction(angle,direction))angle=native_direction_angle(direction);auto& p=u->patch;p.aim_angle.set(angle);
    const auto cd=int64_t(number(p.fume_cooldown));if(cd>0){p.fume_cooldown.set(double(cd-1));return;}
    p.shoot.set(1.);p.fire_animation.set(double(fire_frames(c)));p.fume_attack_angle.set(angle);p.fume_damage_done.set(0.);p.fume_bubble_tick.set(0.);
    p.fume_cooldown.set(double(std::max<int64_t>(1,int64_t(number(c.cooldown,100.)))));world_.runtime.sound("大喷菇",{aim.center.x,aim.center.y,0.,0.});
}
void FumeEffects::update(const ZombieRef& u,const PlantZombieConfig& c) {SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_update(u,c);scope.finish();}
} // namespace pvz::typed72
