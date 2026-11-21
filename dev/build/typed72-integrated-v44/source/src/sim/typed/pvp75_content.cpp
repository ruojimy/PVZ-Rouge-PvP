#include "sim/typed/pvp75_content.h"
#include "sim/typed/projectile_rules.h"
#include "sim/typed/combat_events.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>
namespace pvz::typed72 {
namespace {
constexpr double pi=3.14159265358979323846;
// Presentation only (never battle state): PVP75_LASER_TILES=0 restores the stretched single-image beam.
bool laser_tiles(){static const bool on=[]{const char* v=std::getenv("PVP75_LASER_TILES");return !(v&&std::string(v)=="0");}();return on;}
std::string_view text(const Field<std::string>& f){return f.present()&&!f.is_null()?std::string_view(f.get()):std::string_view{};}
bool alive(const ZombieRef& u){return u&&u->body.hp>0.&&!u->body.ash.present();}
bool plant_alive(const CombatPlant& p){return p.hp.or_missing(0.)>0.&&!p.dead.present();}
double positive(const Field<double>& f){return f.present()&&!f.is_null()?f.get():0.;}
}
namespace pvp75 {
Point laser_eye(const CombatPlant& p,double tile){
    const double px=p.facing<0.?17.:31.;
    return {(double(p.cell.x)+px/48.)*tile,(double(p.cell.y)+20.5/48.)*tile};
}
std::string laser_target_error(const CombatPlant& p,Point target,double tile,double width){
    const auto eye=laser_eye(p,tile);
    const double dx=wrap_delta(eye.x,target.x,width),dy=target.y-eye.y,distance=std::hypot(dx,dy)/tile;
    if(!std::isfinite(distance))return "激光目标无效";
    if(distance<kLaserMinCells-1e-9)return "激光目标太近（需8到20格）";
    if(distance>kLaserMaxCells+1e-9)return "激光目标超出范围（需8到20格）";
    const double facing=p.facing<0.?-1.:1.;
    if(dx*facing<std::hypot(dx,dy)*std::cos(kLaserHalfAngle*pi/180.)-1e-9)return "激光目标不在激光豆面朝的±80°内";
    return {};
}
bool shield_guard(const CombatZombie& u){return text(u.source.content)=="盾卫僵尸";}
bool guard_active(const CombatZombie& u){return shield_guard(u)&&u.pvp75.guard==GuardPhase::guarding;}
void convert_boss_control(CombatZombie& u){
    auto& b=u.body;auto& s=u.pvp75;
    const auto take=[&](Field<double>& f)->double{if(!f.present()||f.is_null()||f.get()<=0.)return 0.;const double v=f.get();f.set(0.);return v;};
    const double ice=positive(b.ice);
    if(ice>1000.){s.boss_slow+=ice-1000.;b.ice.set(1000.);}
    // A control of length D keeps the Boss slowed for at least D ticks from now.
    for(auto* f:{&b.butter,&b.stun}){const double d=take(*f);if(d>0.)s.boss_slow=std::max(s.boss_slow,d-positive(b.ice));}
    if(s.boss_slow>0.&&positive(b.ice)<=1.){const double next=std::min(1000.,s.boss_slow);b.ice.set(next);s.boss_slow-=next;}
}
}
bool Pvp75Content::is_boss(const CombatZombie& u)const{
    if(u.terraria)return u.terraria->type!=5;
    return std::find(bosses_.begin(),bosses_.end(),u.body.kind)!=bosses_.end();
}
bool Pvp75Content::configure(const PlantRef& plant,std::string_view content){
    if(content!="巴豆"&&content!="激光豆")return false;
    plant->source.content.set(std::string(content));plant->kind=std::string(content);
    plant->content_age.set(0.);plant->burst.erase();plant->pvp75=Pvp75PlantState{};
    if(content=="巴豆")plant->one_shot.set(true);else plant->one_shot.erase();
    return true;
}
bool Pvp75Content::configure(const ZombieRef& unit,std::string_view content){
    if(content!="盾卫僵尸")return false;
    unit->source.content.set(std::string(content));unit->body.defense.set(pvp75::kGuardBaseDefense);
    unit->pvp75=Pvp75ZombieState{};unit->base_speed=unit->native.move_speed;
    return true;
}
void Pvp75Content::zombie_gate(const ZombieRef& unit,const std::function<void(const std::string&,const std::string&)>& alias){
    if(!unit)return;
    if(is_boss(*unit))pvp75::convert_boss_control(*unit);
    if(!pvp75::shield_guard(*unit))return;
    const auto& s=unit->pvp75;std::string pose="盾卫僵尸";
    if(s.guard==GuardPhase::raising)pose+="-举盾"+std::to_string(std::min(3,int(s.guard_clock/(pvp75::kGuardRaiseTicks/4.))));
    else if(s.guard==GuardPhase::guarding)pose+="-举盾3";
    for(const std::string part:{"-身","-首"})for(const std::string suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})
        alias(unit->body.kind+part+suffix,pose+part+suffix);
}
void Pvp75Content::before_tick(){
    // Bites recorded by the native and content melee paths during the previous phases.
    auto bites=std::move(world_.pvp75.bites);world_.pvp75.bites.clear();
    for(const auto& bite:bites)if(const auto u=bite.biter.lock())croton(u,bite.plant);
    const auto roster=*world_.targets;
    for(const auto& t:roster)if(t.unit){
        if(is_boss(*t.unit))pvp75::convert_boss_control(*t.unit);
        if(pvp75::shield_guard(*t.unit))guard(t.unit);
    }
}
void Pvp75Content::after_plants(){gases();lasers();}
void Pvp75Content::croton(const ZombieRef& biter,const PlantRef& plant){
    if(!alive(biter)||!plant)return;++croton_triggers;
    const auto source=source_ref(plant);const auto tile=world_.runtime.tile;
    const auto origin=biter->body.motion.get();const double facing=biter->body.facing<0.?-1.:1.;
    targets_.damage(source,CombatTarget::zombie(biter),pvp75::kCrotonDamage,plant->facing,false,HeroHit::content);
    if(alive(biter)){
        biter->body.stun.set(std::max(positive(biter->body.stun),pvp75::kCrotonStunTicks));
        status_.apply(CombatTarget::zombie(biter),2,pvp75::kCrotonPoisonSeconds,Seat::plant);
        if(is_boss(*biter))pvp75::convert_boss_control(*biter);
    }
    CrotonGas gas;gas.tick=world_.heroes.tick;gas.direction=-facing;gas.source=source;
    gas.origin={origin.x-facing*tile*.3,origin.y-tile*.7};gas.touched.push_back(biter->identity.value);
    world_.pvp75.gases.push_back(std::move(gas));
    world_.runtime.sound("吃掉",{origin.x,origin.y,0.,0.});
}
void Pvp75Content::gases(){
    const auto tile=world_.runtime.tile,width=world_.world_width.get();const auto now=world_.heroes.tick;
    std::erase_if(world_.pvp75.gases,[&](const CrotonGas& g){return double(now-g.tick)>=pvp75::kGasTicks;});
    for(auto& gas:world_.pvp75.gases){
        const double age=double(now-gas.tick);
        // The cloud grows from the biter's back to six cells, then lingers until it fades.
        if(age>=pvp75::kGasTicks*.8)continue;
        const double reach=pvp75::kGasCells*tile*std::min(1.,age/pvp75::kGasSpreadTicks);
        for(const auto& target:queries_.enemies(gas.source)){
            const auto* body=std::get_if<CombatTarget>(&target);
            if(!body||body->is_hero()||!alive(body->unit)||body->unit->protection.grave)continue;
            const auto& u=body->unit;
            if(std::find(gas.touched.begin(),gas.touched.end(),u->identity.value)!=gas.touched.end())continue;
            const auto& m=u->body.motion.get();const double along=wrap_delta(gas.origin.x,m.x,width)*gas.direction;
            const double half=tile*.28*u->body.size.or_missing(2.);
            if(along<-half||along>reach+half)continue;
            if(m.y<gas.origin.y-tile*.4||m.y-tile*u->body.size.or_missing(2.)>gas.origin.y+tile*.6)continue;
            gas.touched.push_back(u->identity.value);++gas_hits;
            u->body.stun.set(std::max(positive(u->body.stun),pvp75::kGasStunTicks));
            status_.apply(CombatTarget::zombie(u),1,pvp75::kGasPoisonSeconds,Seat::plant);
            if(is_boss(*u))pvp75::convert_boss_control(*u);
        }
    }
}
void Pvp75Content::lasers(){
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    const auto plants=*world_.plant_roster;
    for(const auto& plant:plants){
        if(plant->kind!="激光豆"||!plant->pvp75.firing)continue;
        auto& s=plant->pvp75;
        if(!plant_alive(*plant)||plant->sleep.present()||plant->crushed.or_missing(false)){s=Pvp75PlantState{};continue;}
        if(++s.clock<pvp75::kLaserPulseTicks)continue;
        s.clock=0.;++beam_pulses;
        const auto eye=pvp75::laser_eye(*plant,tile);
        const Point delta{wrap_delta(eye.x,s.target.x,width),s.target.y-eye.y};
        const double cells=std::max(1e-6,std::hypot(delta.x,delta.y)/tile),amount=pvp75::kLaserDamage/cells;
        const auto source=source_ref(plant);
        for(const auto& target:queries_.enemies(source)){
            if(!targets_.contact(target,eye,delta))continue;
            const auto* body=std::get_if<CombatTarget>(&target);
            if(body&&body->is_hero()){
                // Like deathmatch water: one hit point, never a knockdown or control.
                auto& hp=world_.heroes.hero(body->hero).frame.hp.get();if(hp<=0.)continue;
                hp=std::max(0.,hp-1.);world_.runtime.events.emplace_back(EnvironmentalDamageEvent{body->hero,1.});continue;
            }
            if(body&&!alive(body->unit))continue;
            targets_.damage(source,target,amount,plant->facing,false,HeroHit::content);
        }
    }
}
void Pvp75Content::guard(const ZombieRef& u){
    auto& s=u->pvp75;auto& b=u->body;
    const bool hurt=s.seen_hp>=0.&&(b.hp<s.seen_hp-1e-9||b.armor_hp<s.seen_armor-1e-9||b.hand_hp<s.seen_hand-1e-9);
    s.seen_hp=b.hp;s.seen_armor=b.armor_hp;s.seen_hand=b.hand_hp;
    if(!alive(u)){
        if(s.guard==GuardPhase::guarding&&s.walk_speed){u->native.move_speed.set(*s.walk_speed);s.walk_speed.reset();}
        return;
    }
    switch(s.guard){
    case GuardPhase::ready:if(hurt){s.guard=GuardPhase::raising;s.guard_clock=0.;++guards;}break;
    case GuardPhase::raising:
        if(++s.guard_clock>=pvp75::kGuardRaiseTicks){
            s.guard=GuardPhase::guarding;s.guard_clock=0.;b.defense.set(pvp75::kGuardDefense);
            const double speed=u->native.move_speed.or_missing(0.);s.walk_speed=speed;u->native.move_speed.set(speed*pvp75::kGuardSpeed);
        }break;
    case GuardPhase::guarding:
        if(++s.guard_clock>=pvp75::kGuardTicks){
            s.guard=GuardPhase::cooldown;s.guard_clock=0.;b.defense.set(pvp75::kGuardBaseDefense);
            // Undo only the guard factor: other speed changes made meanwhile stay.
            const double now=u->native.move_speed.or_missing(0.);u->native.move_speed.set(now/pvp75::kGuardSpeed);s.walk_speed.reset();
        }break;
    case GuardPhase::cooldown:if(++s.guard_clock>=pvp75::kGuardCooldownTicks){s.guard=GuardPhase::ready;s.guard_clock=0.;}break;
    }
}
void Pvp75Content::draw(NativeCanvas& c){
    if(!c.drawing())return;
    const double tile=world_.runtime.tile,width=world_.world_width.get(),scale=tile/48.;const auto now=world_.heroes.tick;
    for(const auto& gas:world_.pvp75.gases){
        const double age=double(now-gas.tick);
        static constexpr double ends[]={30.,70.,120.,190.,270.,345.,420.,500.};
        int frame=0;while(frame<7&&age>=ends[frame])++frame;
        const std::string key="巴豆毒气-帧"+std::to_string(frame);if(!c.has(key))continue;
        auto art=c.resize(c.image(key),pvp75::kGasCells*tile,64.*scale);
        if(gas.direction<0.)art=NativeCanvas::flip(art);
        const double left=gas.direction>0.?gas.origin.x:gas.origin.x-pvp75::kGasCells*tile;
        c.display(art,{left,gas.origin.y-34.*scale});
    }
    for(const auto& plant:*world_.plant_roster){
        if(plant->kind!="激光豆"||!plant->pvp75.firing||!plant_alive(*plant))continue;
        const auto eye=pvp75::laser_eye(*plant,tile);
        const Point delta{wrap_delta(eye.x,plant->pvp75.target.x,width),plant->pvp75.target.y-eye.y};
        const double length=std::hypot(delta.x,delta.y);const Point end{eye.x+delta.x,eye.y+delta.y};
        const int phase=int((now/20)%4);
        if(length>1e-6){
            const std::string key="激光豆激光-束"+std::to_string(phase);
            if(c.has(key)){
                const double degrees=std::atan2(delta.y,delta.x)*180./pi,height=32.*scale;
                if(!laser_tiles()){  // PVP75_LASER_TILES=0: the first version, one stretched image per beam
                    auto art=c.resize(c.image(key),length,height);
                    const Point mid{eye.x+delta.x/2.,eye.y+delta.y/2.};
                    c.rotated(art,{mid.x-art->width/2.,mid.y-art->height/2.},degrees);
                }else{
                    // The art's tiled beam: the segment texture repeats along the axis in quarter-texture pieces,
                    // each cut straight from the scaled strip and rotated. A piece's recipe is identical every
                    // frame (4 offsets x 4 phases per beam angle, ~20 KiB each), so the replay cache keeps them;
                    // one stretched diagonal image per phase was ~1 MiB and evicted the cache every frame.
                    const auto texture=c.image(key);
                    const int span=std::max(8,int(std::lround(texture->width*height/std::max(1,texture->height))));
                    const auto strip=c.resize(texture,span,height);
                    const int piece=std::max(8,span/4);const Point dir{delta.x/length,delta.y/length};
                    for(double at=0.;at<length;at+=piece){
                        const double part_length=std::min(double(piece),length-at);
                        const int offset=int(at)%span;
                        // 1 px of overlap on each inner side hides seams between neighbouring rotated pieces.
                        const int left=std::max(0,offset-1),right=std::min(span,offset+int(std::ceil(part_length))+1);
                        const auto part=c.crop(strip,left,0.,right-left,height);
                        const double middle=at+(left-offset)+(right-left)/2.;
                        const Point centre{eye.x+dir.x*middle,eye.y+dir.y*middle};
                        c.rotated(part,{centre.x-part->width/2.,centre.y-part->height/2.},degrees);
                    }
                }
            }
        }
        for(const auto& [key,point,size]:{std::tuple{"激光豆激光-终点"+std::to_string(phase%2),end,48.},std::tuple{"激光豆激光-起点"+std::to_string(phase%2),eye,32.}}){
            if(!c.has(key))continue;auto art=c.resize(c.image(key),size*scale,size*scale);
            c.display(art,{point.x-art->width/2.,point.y-art->height/2.});
        }
    }
}
} // namespace pvz::typed72
