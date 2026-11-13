#include "sim/typed/plant_region.h"
#include "sim/typed/shooter.h"
#include "sim/typed/plant_queries.h"
#include "core/pymath.h"
#include "core/number_text.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
bool contains(const std::vector<std::string>& values,std::string_view key){return std::find(values.begin(),values.end(),key)!=values.end();}
}
CombatPlant& PlantRegion::plant(size_t index)const{return *world_.plant_roster->at(index);}
ZombieRecordFields& PlantRegion::body(size_t index)const {
    const auto target=world_.targets->at(index);
    return target.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero)):target.unit->body;
}
Motion& PlantRegion::position(size_t index)const {
    const auto target=world_.targets->at(index);
    return target.is_hero()?*world_.heroes.cached_proxy(target.hero).position:target.unit->body.motion.get();
}
ZombieNativeState& PlantRegion::zombie_native(size_t index)const {
    const auto target=world_.targets->at(index);
    return target.is_hero()?world_.heroes.cached_proxy(target.hero).native:target.unit->native;
}
bool PlantRegion::secret(std::string_view key)const{return contains(*world_.heroes.globals.secrets.get(),key);}
Point PlantRegion::center(size_t index)const {
    const auto cell=plant(index).cell;const auto tile=world_.runtime.tile;
    return {cell.x*tile+tile*.5,cell.y*tile+tile*.5};
}
bool PlantRegion::needs_support(size_t index)const {
    return plant_needs_support(world_,index,rules_.air_plants,rules_.flying_plants);
}
const std::vector<int64_t>* PlantRegion::row(int64_t key)const {
    const auto& rows=*indexes_.rows;
    const auto found=std::find_if(rows.begin(),rows.end(),[&](const auto& item){return item.first==key;});
    return found==rows.end()?nullptr:&found->second;
}
bool PlantRegion::ahead(const Frame& frame,double facing,double range)const {
    const auto* targets=row(frame.cell.y);if(!targets)return false;
    for(const auto column:*targets) {
        const auto current=plant(frame.index).cell.x;
        if(((facing==1. && column>=current) || (facing==-1. && column<=current)) &&
            std::abs(double(column)-double(current))<=range)return true;
    }
    return false;
}
bool PlantRegion::nearby_row(Cell cell,int radius)const {
    const auto* targets=row(cell.y);if(!targets)return false;
    return std::any_of(targets->begin(),targets->end(),[&](auto x){return std::abs(double(x)-double(cell.x))<=radius;});
}
Entity& PlantRegion::spawn(std::string name,double facing,Motion point) {
    services_.add_entity(std::move(name),facing,point);
    const auto entities=world_.runtime.entities.list();
    return *entities->at(entities->size()-1);
}
void PlantRegion::sound(std::string name,size_t index){const auto p=center(index);world_.runtime.sound(std::move(name),{p.x,p.y,0.,0.});}
void PlantRegion::imitation_clouds(const Frame& frame) {
    auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;
    globals.xx.set(frame.cell.x*runtime.tile+runtime.tile);globals.yy.set(frame.cell.y*runtime.tile+runtime.tile/2.);
    const auto count=runtime.rng.randint(6,8);
    for(int i=0;i<count;++i) {
        const double facing=i%2==0?-1.:1.,vertical=i/2%2==0?1.:-1.;
        auto& entity=spawn("模仿",facing,{globals.xx.get(),globals.yy.get(),
            facing*runtime.plk*runtime.rng.randint(50,150),runtime.plk*runtime.rng.randint(50,150)*vertical});
        entity.expires.set(900.);entity.rotation.set(double(runtime.rng.randint(0,360)));
    }
}
void PlantRegion::cannon(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const auto tile=runtime.tile;
    if(++plant(index).cannon_flash.get()==200.)plant(index).cannon_flash.set(0.);
    if(plant(index).cannon_cd.get()>0.)--plant(index).cannon_cd.get();
    else if(!state_.selected_cannon && plant(index).cell==state_.pointer && state_.held_card.empty())state_.placement_status="适宜开炮";
    if(plant(index).cannon_animation.get()<=0.)return;
    if(++plant(index).cannon_animation.get()==250.) {
        runtime.screen_shake.set({50.,0.,0.});sound("加农炮",index);
        const auto cell=plant(index).cell;
        auto& entity=spawn("玉米炮",plant(index).facing,{cell.x*tile+tile*.5-plant(index).facing*tile*.2,cell.y*tile-tile,0.,0.});
        entity.cannon_column=plant(index).cannon_column;entity.gravity.set(0.);entity.cannon_lock.set(0.);
        if(plant(index).monochrome.present()){plant(index).dead.set(DeathMarker(0.));imitation_clouds(frame);}
    }
    if(plant(index).cannon_animation.get()==500.)plant(index).cannon_animation.set(0.);
}
void PlantRegion::squash(const Frame& frame) {
    const auto index=frame.index;
    if(!ahead(frame,plant(index).facing,2.))return;
    auto& runtime=world_.runtime;const auto tile=runtime.tile;
    plant(index).dead.set(DeathMarker(0.));sound("窝瓜"+std::to_string(runtime.rng.randint(1,2)),index);
    const auto cell=plant(index).cell;
    auto& entity=spawn("窝瓜x",plant(index).facing,{cell.x*tile+tile*.5,cell.y*tile+tile*.9,plant(index).facing*300.*runtime.plk,-400.*runtime.plk});
    entity.gravity.set(0.);entity.squash.big_sit.set(100.);entity.squash.sit.set(0.);
    if(plant(index).monochrome.present())entity.monochrome.set(DeathMarker(0.));
    entity.expires.set(-1.);
}
void PlantRegion::fume(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).shoot_cd.get()<=0.) {
        if(ahead(frame,plant(index).facing,6.)) {
            plant(index).shooting.set(1.);
            if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(double(runtime.rng.randint(0,200)));
            plant(index).shoot_cd.get()+=500.;sound("大喷菇",index);
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<200.) {
        if(++plant(index).shooting.get()==150.) {
            const auto point=center(index);globals.xx.set(point.x);globals.yy.set(point.y);
            const auto count=world_.targets->size();
            for(size_t target=0;target<count;++target) {
                const auto& pos=position(target);
                const bool in_front=plant(index).facing==1.?pos.x>=globals.xx.get():pos.x<=globals.xx.get();
                if(!in_front || std::abs(pos.x-globals.xx.get())>tile*7. || std::abs(pos.y-tile-globals.yy.get())>tile)continue;
                services_.ordinary(target,plant(index).facing,10.);
                runtime.sound("splat"+std::to_string(runtime.rng.randint(1,3)),position(target));
                if(frame.name=="雷蘑菇" && (contains(rules_.metal,body(target).hand) || contains(rules_.metal,body(target).armor))) {
                    const auto selected=world_.targets->at(target);
                    if(selected.is_hero())world_.heroes.write_proxy_status(selected.hero,HeroStatus::stun,200.);
                    else selected.unit->body.stun.set(200.);
                    runtime.sound("电击",position(target));
                }
            }
        }
        if(py::mod(plant(index).shooting.get(),15.)==0.) {
            const auto cell=plant(index).cell;const auto facing=plant(index).facing;
            auto& entity=spawn(frame.name=="大喷菇"?"大泡泡":"蓝泡泡",facing,
                {cell.x*tile+tile+facing*tile*.5,cell.y*tile+tile*.6,facing*800.*runtime.plk,runtime.rng.randint(-70,70)*runtime.plk});
            entity.expires.set(800.);
        }
    }
    --plant(index).shoot_cd.get();
}
void PlantRegion::puff(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(frame.name=="胆小菇") {
        if(plant(index).scared.get()<100.)if(const auto* targets=row(plant(index).cell.y)) {
            for(const auto target:*targets)if(std::abs(double(target)-double(plant(index).cell.x))<=2.) {
                if(secret("胆大"))plant(index).shoot_cd.get()-=2.;else plant(index).scared.get()+=2.;
            }
        }
        if(plant(index).scared.get()>0.)--plant(index).scared.get();
    }
    if(plant(index).shoot_cd.get()<=0.) {
        bool shoot=false;
        if(row(frame.cell.y)) {
            globals.yy.set(tile*.3);
            if(frame.name=="胆小菇")globals.yy.set(tile*.15);
            shoot=ahead(frame,plant(index).facing,frame.name=="胆小菇"?48.:4.);
        }
        if(frame.name=="胆小菇" && plant(index).scared.get()>0.)shoot=false;
        if(shoot) {
            plant(index).shooting.set(1.);double cooldown=200.;
            if(frame.name=="海蘑菇")cooldown=100.;
            if(frame.name=="胆小菇")cooldown=150.;
            if(plant(index).small_puff.present()) {
                cooldown=30.;if(--plant(index).small_puff.get()==0.)plant(index).small_puff.erase();
            }
            if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(double(runtime.rng.randint(0,200)));
            plant(index).shoot_cd.get()+=cooldown;
            std::string projectile="泡泡";
            if(frame.name=="海蘑菇") {
                globals.yy.set(native_.water_offset);if(!secret("水兵"))globals.yy.get()-=tile*.5;
                projectile="海泡泡";
            }
            sound("泡泡",index);const auto cell=plant(index).cell;const auto facing=plant(index).facing;
            services_.add_entity(std::move(projectile),facing,{cell.x*tile+tile*.5+facing*tile*.1,cell.y*tile+tile*.5+globals.yy.get(),facing*200.*runtime.plk,0.});
        }else plant(index).shoot_cd.set(-1.);
    }else --plant(index).shoot_cd.get();
    if(plant(index).shooting.get()>0. && plant(index).shooting.get()<100.)++plant(index).shooting.get();
}
void PlantRegion::split(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const auto tile=runtime.tile;
    for(int side=0;side<2;++side) {
        auto& cooldown=side==0?plant(index).shoot_cd:plant(index).secondary_cd;
        auto& animation=side==0?plant(index).shooting:plant(index).secondary_shot;
        const auto facing=plant(index).facing*(side==0?1.:-1.);
        if(cooldown.get()<=0.) {
            if(ahead(frame,facing,side==0?16.:32.)) {
                animation.set(1.);
                if(cooldown.get()==-1.)cooldown.set(double(runtime.rng.randint(0,200)));
                cooldown.get()+=500.;
                if(side==1) {
                    if(plant(index).secondary_double.get()==0.){cooldown.set(100.);++plant(index).secondary_double.get();}
                    else plant(index).secondary_double.set(0.);
                }
                const auto cell=plant(index).cell;
                services_.add_entity("豌豆",facing,{cell.x*tile+tile*.5+facing*tile*.3,cell.y*tile+tile*.5,facing*200.*runtime.plk,0.});
            }else cooldown.set(-1.);
        }else --cooldown.get();
        // Constructors may replace the live plant list.
        auto& current=side==0?plant(index).shooting:plant(index).secondary_shot;
        if(current.get()>0. && current.get()<100.)++current.get();
    }
}
void PlantRegion::shooters(const Frame& frame) {
    ShooterKind kind=ShooterKind::pea;
    if(frame.name=="寒冰射手")kind=ShooterKind::ice_pea;
    if(frame.name=="双发射手")kind=ShooterKind::repeater;
    if(frame.name=="杨桃")kind=ShooterKind::star;
    if(frame.name=="仙人掌")kind=ShooterKind::cactus;
    if(frame.name=="机枪射手")kind=ShooterKind::gatling;
    const bool star_target=kind==ShooterKind::star && plant(frame.index).shoot_cd.get()<=0. && services_.star_target();
    shooter_attack(world_,frame.index,kind,row(frame.cell.y),secret("大帝"),star_target);
}
void PlantRegion::cattail(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const auto tile=runtime.tile;
    if(plant(index).shooting.get()==0.) {
        if(indexes_.nearest) {
            plant(index).shooting.set(1.);
            if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(-double(runtime.rng.randint(0,200)));
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<100. && ++plant(index).shooting.get()==50.) {
        const auto cell=plant(index).cell;
        auto& entity=spawn("尖刺",1.,{cell.x*tile+tile*.5,cell.y*tile-tile*.7,plant(index).facing*200.*runtime.plk,0.});
        entity.tracking.set(0.);entity.through_wall.set(0.);entity.expires.set(-1000.);entity.rotation.set(0.);
    }
    if(++plant(index).shoot_cd.get()==150.){plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);}
}
void PlantRegion::spikes(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).shooting.get()==0.) {
        if(nearby_row(frame.cell,1)) {
            plant(index).shooting.set(1.);if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(0.);
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<100. && ++plant(index).shooting.get()==50.) {
        globals.xx.set(frame.cell.x*tile);globals.yy.set(frame.cell.y*tile);
        const auto count=world_.targets->size();
        for(size_t target=0;target<count;++target) {
            const auto& pos=position(target);
            if(std::abs(pos.x-globals.xx.get()-tile/2.)>tile || std::abs(pos.y-globals.yy.get()-tile)>tile/2.)continue;
            if(body(target).kind=="投篮车僵尸" || body(target).kind=="雪橇车僵尸") {
                services_.ordinary(target,body(target).facing,1000.);
                if(frame.name=="地刺")plant(index).dead.set(DeathMarker(0.));
            }else {
                services_.ordinary(target,plant(index).facing,5.);
                runtime.sound("splat"+std::to_string(runtime.rng.randint(1,3)),position(target));
            }
            position(target).vx/=5.;
        }
    }
    if(++plant(index).shoot_cd.get()==(frame.name=="地刺王"?100.:200.)) {
        plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);
    }
}
void PlantRegion::umbrella(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    globals.xx.set(frame.cell.x*tile+tile/2.);globals.yy.set(frame.cell.y*tile+tile/2.);
    if(plant(index).shooting.get()==0.) {
        bool shoot=false;const auto count=runtime.entities.list()->size();
        for(size_t target=0;target<count;++target) {
            auto& entity=*runtime.entities.list()->at(target);auto& pos=entity.motion.get();
            if(entity.kind=="篮球" && std::abs(globals.xx.get()-pos.x)<=tile && std::abs(globals.yy.get()-pos.y)<=tile*1.5 && globals.yy.get()>=pos.y) {
                shoot=true;pos.vy=0.;
            }
        }
        if(nearby_row({frame.cell.y-1,frame.cell.x},1) || nearby_row(frame.cell,1))shoot=true;
        const auto& hero=*globals.position.get();
        if(std::abs(hero.x-globals.xx.get())+std::abs(hero.y-globals.yy.get())<=tile*2. && hero.vy>200.*runtime.plk)shoot=true;
        if(shoot) {
            plant(index).shooting.set(1.);if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(0.);
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<100. && ++plant(index).shooting.get()==20.) {
        const auto count=runtime.entities.list()->size();
        for(size_t target=0;target<count;++target) {
            auto& entity=*runtime.entities.list()->at(target);auto& pos=entity.motion.get();
            if(!contains(rules_.thrown,entity.kind) || std::abs(globals.xx.get()-pos.x)>tile || std::abs(globals.yy.get()-pos.y)>tile*1.5 || globals.yy.get()<pos.y)continue;
            pos.vy=-500.*runtime.plk;
            if(entity.kind=="篮球"){entity.kind="篮球x";entity.expires.set(900.);}
        }
        sound("弹飞",index);auto& hero=*globals.position.get();
        if(std::abs(hero.x-globals.xx.get())+std::abs(hero.y-globals.yy.get())<=tile*2.) {
            hero.vx=(hero.x>globals.xx.get()?300.:-300.)*runtime.plk;hero.vy=-600.*runtime.plk;
        }
        const auto targets=world_.targets->size();
        for(size_t target=0;target<targets;++target) {
            auto& pos=position(target);
            if(std::abs(pos.x-globals.xx.get())>tile*2. || std::abs(pos.y-globals.yy.get()-tile/2.)>tile*1.2)continue;
            pos.vx=(pos.x>globals.xx.get()?300.:-300.)*runtime.plk;pos.vy=-300.*runtime.plk;
            auto& native=zombie_native(target);
            if(body(target).kind=="飞贼僵尸" && !native.leaving.present()) {
                native.leaving.set(0.);native.entry.set(0.);native.entry_end=native.entry_start;native.entry_start.set({pos.x,pos.y});
            }
        }
    }
    if(++plant(index).shoot_cd.get()==1200.){plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);}
}
void PlantRegion::chomper(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).eating.get()>0.)--plant(index).eating.get();
    if(plant(index).shooting.get()==0.) {
        if(plant(index).eating.get()>0.)return;
        const auto* targets=row(frame.cell.y-1);
        if(targets && (std::find(targets->begin(),targets->end(),frame.cell.x)!=targets->end() ||
            std::find(targets->begin(),targets->end(),frame.cell.x+plant(index).facing)!=targets->end())) {
            plant(index).shooting.set(1.);plant(index).shoot_cd.set(frame.name=="龙蒺藜"?300.:500.);
        }
        return;
    }
    if(plant(index).shooting.get()<150. && ++plant(index).shooting.get()==75.) {
        globals.xx.set(frame.cell.x*tile+tile/2.);globals.yy.set(frame.cell.y*tile+tile/2.);sound("大嘴",index);
        const auto count=world_.targets->size();std::optional<size_t> selected;
        for(size_t target=0;target<count;++target) {
            const auto record=world_.targets->at(target);const auto& pos=position(target);const auto& fields=body(target);
            const bool in_front=plant(index).facing==1.?pos.x>=globals.xx.get():pos.x<=globals.xx.get();
            if(!in_front || (!record.is_hero() && record.unit->source.charmed.present()) || (fields.hp<=0. && fields.hand!="玩偶匣") ||
                std::abs(pos.x-globals.xx.get())>tile*2. || std::abs(pos.y-tile-globals.yy.get())>tile)continue;
            selected=target;break;
        }
        if(selected) {
            const auto target=*selected;
            if(services_.edible(target) && !contains(rules_.bosses,body(target).kind)) {
                const auto record=world_.targets->at(target);
                if(record.is_hero())world_.heroes.write_proxy_hp(record.hero,-1024.);else record.unit->body.hp=-1024.;
                plant(index).eating.set(frame.name=="龙蒺藜"?1400.:7000.);
            }else services_.ordinary(target,plant(index).facing,50.);
        }
    }
    if(--plant(index).shoot_cd.get()<=0.){plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);}
}
void PlantRegion::gloom(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).shooting.get()==0.) {
        if(nearby_row(frame.cell,1)) {
            plant(index).shooting.set(1.);if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(0.);
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<50.) {
        ++plant(index).shooting.get();
        if(plant(index).shooting.get()==25.)for(int i=0;i<12;++i) {
            const double angle=std::acos(-1.)*2.*(i/12.);globals.angle.set(angle);
            const auto cell=plant(index).cell;
            auto& entity=spawn("大泡泡",plant(index).facing,{cell.x*tile+tile+std::cos(angle)*tile/2.,cell.y*tile+tile*.6+std::sin(angle)*tile/2.,
                std::cos(angle)*runtime.plk*150.,std::sin(angle)*runtime.plk*150.});
            entity.expires.set(900.);
        }
        if(plant(index).shooting.get()==50.) {
            globals.xx.set(frame.cell.x*tile);globals.yy.set(frame.cell.y*tile);const auto count=world_.targets->size();
            for(size_t target=0;target<count;++target) {
                const auto& pos=position(target);
                if(body(target).hp<=0. || std::abs(pos.x-globals.xx.get()-tile/2.)>tile*1.6 || std::abs(pos.y-globals.yy.get()-tile)>tile*1.6)continue;
                services_.ordinary(target,plant(index).facing,10.);runtime.sound("splat"+std::to_string(runtime.rng.randint(1,3)),position(target));
            }
        }
    }
    if(++plant(index).shoot_cd.get()==50.){plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);}
}
void PlantRegion::pitcher(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).shooting.get()==0.) {
        bool shoot=false;globals.xx.set(double(plant(index).cell.x));const auto facing=plant(index).facing;
        for(const auto distance:services_.pitcher_columns()) {
            const auto column=globals.xx.get()+facing*distance;
            if(std::any_of(indexes_.columns->begin(),indexes_.columns->end(),[&](const auto& item){return item.first==column;})){shoot=true;break;}
        }
        if(shoot) {
            plant(index).shooting.set(1.);
            if(plant(index).shoot_cd.get()==-1.)plant(index).shoot_cd.set(double(runtime.rng.randint(0,200)));
            plant(index).shoot_cd.get()+=frame.name=="西瓜投手" || frame.name=="冰瓜投手"?700.:500.;
        }else plant(index).shoot_cd.set(-1.);
        return;
    }
    if(plant(index).shooting.get()<200. && ++plant(index).shooting.get()==120.) {
        sound("投掷",index);std::string projectile="卷心菜";
        if(frame.name=="西瓜投手")projectile="西瓜";
        if(frame.name=="冰瓜投手")projectile="冰瓜";
        if(frame.name=="玉米投手")projectile=runtime.rng.randint(1,secret("黄油")?2:3)==1?"黄油":"玉米粒";
        const int count=projectile=="玉米粒"?3:1;
        for(int i=0;i<count;++i) {
            const auto cell=plant(index).cell;const auto facing=plant(index).facing;
            const auto horizontal=projectile=="玉米粒"?runtime.rng.randint(250,350):300;
            const auto vertical=projectile=="玉米粒"?runtime.rng.randint(450,500):500;
            const double velocity=projectile=="玉米粒"?facing*horizontal*runtime.plk:facing*runtime.plk*300.;
            auto& entity=spawn(projectile,facing,{cell.x*tile+tile*.5,cell.y*tile,velocity,-vertical*runtime.plk});
            entity.gravity.set(0.);entity.rotation.set(double(runtime.rng.randint(0,360)));
            if(projectile=="卷心菜" && secret("卷心菜"))entity.squash.bounce_x.set(5.);
        }
    }
    if(--plant(index).shoot_cd.get()==0.){plant(index).shoot_cd.set(0.);plant(index).shooting.set(0.);}
}
void PlantRegion::lantern(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    const auto needy=[&](size_t target){const auto& p=plant(target);return p.kind!="大蒜" && std::abs(double(p.cell.x)-frame.cell.x)<=3. &&
        std::abs(p.cell.y-frame.cell.y)<=3 && p.hp.get()<p.max_hp.get();};
    if(plant(index).burst.get()>0.) {
        if(++plant(index).burst.get()==125.) {
            sound("治疗",index);int amount=rules_.lantern_secret?12:6;const auto count=world_.plant_roster->size();
            for(size_t target=0;target<count;++target) {
                globals.xx.set(double(plant(target).cell.x));globals.yy.set(double(plant(target).cell.y));
                if(!needy(target))continue;
                plant(target).hurt.set(1.);
                for(int i=0;i<amount/6;++i) {
                    auto& entity=spawn("光疗",1.,{globals.xx.get()*tile+tile+runtime.rng.randint(-10,10)*tile*.03,
                        globals.yy.get()*tile+tile*.7+runtime.rng.randint(-10,10)*tile*.03,0.,-50.*runtime.plk});
                    entity.expires.set(800.);
                }
                // The source carries the halved value into subsequent plants.
                if(plant(target).kind=="南瓜头")amount/=2;
                plant(target).hp.get()+=amount;
                if(plant(target).hp.get()>plant(target).max_hp.get())plant(target).hp=plant(target).max_hp;
            }
        }
        if(plant(index).burst.get()>250.)plant(index).burst.set(0.);
    }
    if(--plant(index).lamp.get()==0.) {
        plant(index).lamp.set(1200.);const auto count=world_.plant_roster->size();
        for(size_t target=0;target<count;++target) {
            globals.xx.set(double(plant(target).cell.x));globals.yy.set(double(plant(target).cell.y));
            if(needy(target)){plant(index).burst.set(1.);break;}
        }
    }
}
void PlantRegion::marigold(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;
    if(plant(index).burst.get()>0.) {
        if(++plant(index).burst.get()==125.) {
            std::string kind="银币";
            if(plant(index).money.present()){plant(index).money.erase();kind="金币";}
            const auto point=center(index);
            zombie_state_.coins.push_back({0.,{point.x,point.y,runtime.rng.randint(-200,200)*runtime.plk*1.5,
                -runtime.rng.randint(350,450)*runtime.plk},-300.,std::move(kind)});
        }
        if(plant(index).burst.get()>250.) {
            plant(index).burst.set(0.);if(world_.heroes.globals.mode.get()!="我是僵尸")plant(index).money_cd.set(5000.);
        }
    }
    if(--plant(index).money_cd.get()==0.) {
        if(state_.wave==0.)plant(index).burst.set(1.);else plant(index).money_cd.set(5000.);
    }
}
void PlantRegion::magnet(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).magnet.get()!=0.) {
        if(--plant(index).magnet.get()==0. && frame.name=="吸金磁") {
            const auto point=center(index);
            zombie_state_.coins.push_back({0.,{point.x,point.y,0.,-runtime.rng.randint(350,450)*runtime.plk},-300.,"金币"});
        }
        return;
    }
    const auto point=center(index);globals.xx.set(point.x);globals.yy.set(point.y);
    std::optional<size_t> selected;double nearest=0.;const auto count=world_.targets->size();
    for(size_t target=0;target<count;++target) {
        const auto& fields=body(target);if(contains(rules_.bosses,fields.kind))continue;
        const auto& pos=position(target);const auto distance=std::abs(pos.x-globals.xx.get())+std::abs(pos.y-globals.yy.get());
        if(distance>tile*9. && !(secret("磁力") && frame.name=="磁力菇"))continue;
        if(!contains(rules_.metal,fields.hand) && !contains(rules_.metal,fields.armor))continue;
        if(!selected || distance<nearest){selected=target;nearest=distance;}
    }
    // A giant's carried imp has a separate head slot. Preserve the original
    // body/hand selection above, then consider this slot only as its fallback.
    bool carried_imp=false;
    if(!selected)for(size_t target=0;target<count;++target){
        const auto& zombie=world_.targets->at(target).unit;
        if(!zombie||zombie->body.hp<=0.||zombie->body.ash.present()||zombie->body.kind!="巨人僵尸"||zombie->native.throw_imp.present())continue;
        const auto& armor=zombie->poison.imp_armor;
        if(!armor.present()||armor.is_null()||zombie->poison.imp_armor_hp.or_missing(0.)<=0.)continue;
        const auto& name=armor.get();const auto logical=name=="黑铁桶"?"铁桶":name=="黑路障"?"路障":name;
        if(!contains(rules_.metal,logical))continue;
        const auto& pos=position(target);const auto distance=std::abs(pos.x-globals.xx.get())+std::abs(pos.y-globals.yy.get());
        if(distance>tile*9.&&!(secret("磁力")&&frame.name=="磁力菇"))continue;
        if(!selected||distance<nearest){selected=target;nearest=distance;carried_imp=true;}
    }
    if(!selected)return;
    const auto target=*selected;auto& fields=body(target);std::string kind;
    if(carried_imp){
        auto& zombie=*world_.targets->at(target).unit;kind=zombie.poison.imp_armor.get();
        zombie.poison.imp_armor.set("");zombie.poison.imp_armor_hp.set(0.);
        if(zombie.registration.secondhand.present()&&!zombie.registration.secondhand.is_null())zombie.registration.secondhand.get().carried_imp.erase();
    }else if(contains(rules_.metal,fields.hand)) {
        kind=fields.hand;
        if(kind=="矿镐" && !world_.targets->at(target).is_hero())zombie_native(target).emerged.set(true);
        globals.yy.get()-=kind=="弹跳杆"?tile:tile/2.;
        if(!world_.targets->at(target).is_hero()){fields.hand.clear();fields.hand_hp=0.;}
    }else if(contains(rules_.metal,fields.armor)) {
        kind=fields.armor;
        if(!world_.targets->at(target).is_hero()){fields.armor.clear();fields.armor_hp=0.;}
    }
    auto& entity=spawn(std::move(kind),body(target).facing,position(target));
    entity.expires.set(-12000.);entity.service.attract.set(0.);entity.service.attract_is_boolean=false;
    entity.service.attract_start.set({position(target).x,position(target).y-tile*1.5});
    entity.service.attract_end.set({globals.xx.get(),globals.yy.get()});plant(index).magnet.set(13000.);
    if(plant(index).kind=="吸金磁"){plant(index).magnet.set(9000.);entity.expires.set(-8000.);}
    sound("磁力",index);
}
void PlantRegion::freezing(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;
    if(++plant(index).expires.get()!=200.)return;
    world_.heroes.globals.water_ice.set(1500.);runtime.freeze_flash.set(80.);plant(index).dead.set(DeathMarker(0.));
    const auto count=world_.targets->size();
    for(size_t target=0;target<count;++target) {
        services_.ordinary(target,body(target).facing,10.);
        const auto record=world_.targets->at(target);
        if(record.is_hero())world_.heroes.write_proxy_status(record.hero,HeroStatus::ice,2500.);
        else record.unit->body.ice.set(2500.);
    }
    sound("冰冻",index);
}
void PlantRegion::imitation(const Frame& frame) {
    const auto index=frame.index;if(plant(index).imitator_cd.get()<=0.)return;
    --plant(index).imitator_cd.get();++plant(index).root_animation.get();
    if(plant(index).imitator_cd.get()!=0.)return;
    imitation_clouds(frame);if(plant(index).imitation.get()=="模仿者")return;
    plant(index).dead.set(DeathMarker(0.));const auto kind=plant(index).imitation.get();
    auto& runtime=world_.runtime;const auto tile=runtime.tile;
    if(contains(world_.plant_catalog.lottery_zombies,kind)) {
        services_.summon_zombie(kind,{frame.cell.x*tile+tile*.5,frame.cell.y*tile+tile,0.,0.},plant(index).facing);
        if(kind!="飞贼僵尸")zombie_native(world_.targets->size()-1).entry.set(400.);
        runtime.sound("groan"+std::to_string(runtime.rng.randint(1,8)),{frame.cell.x*tile,frame.cell.y*tile,0.,0.});
    }else {
        if(!services_.imitate(world_.plant_roster->at(index),frame.cell,plant(index).facing))lifecycle_.plant(frame.cell,kind,plant(index).facing);
        auto& made=*world_.plant_roster->back();made.monochrome.set(DeathMarker(0.));
        if(world_.heroes.globals.mode.get()=="我是僵尸") {
            made.sleep.erase();if(made.expires.present() || kind=="窝瓜")made.sleep.set(0.);
        }
    }
}
void PlantRegion::gravebuster(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const auto tile=runtime.tile;
    if(plant(index).grave_eating.get()==0.)sound("吃坟墓",index);
    ++plant(index).grave_eating.get();
    const auto& cell=world_.terrain.native_at(frame.cell.y,frame.cell.x);
    if(py::mod(plant(index).grave_eating.get(),100.)==0. && cell.grave_art.present())
        runtime.emit_particles(cell.block.get()+native_number_text(cell.grave_art.get()),{frame.cell.x*tile+tile*.5,frame.cell.y*tile+tile*.5},4);
    if(plant(index).grave_eating.get()==1000.) {
        plant(index).dead.set(DeathMarker(0.));const auto point=center(index);
        zombie_state_.coins.push_back({0.,{point.x,point.y,0.,-runtime.rng.randint(350,450)*runtime.plk},-300.,"银币"});
        services_.destroy_block(frame.cell);
    }
}
void PlantRegion::blover(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;auto& globals=world_.heroes.globals;const auto tile=runtime.tile;
    if(plant(index).expires.get()==0.)sound("三叶草",index);
    globals.xx.set(plant(index).cell.x*tile+tile*.5);
    const auto entities=runtime.entities.list()->size();const bool left=plant(index).facing==-1.;
    for(size_t target=0;target<entities;++target) {
        if(!services_.wind_target(target))continue;
        auto& entity=*runtime.entities.list()->at(target);auto& point=entity.motion.get();
        if(left?point.x>=globals.xx.get():point.x<=globals.xx.get())continue;
        point.vx+=(left?-1.:1.)*runtime.plk;
        if(left?point.vx<0.:point.vx>0.)entity.facing=left?-1.:1.;
    }
    const auto rain=world_.wind_environment.rain->size();
    for(size_t target=0;target<rain;++target)world_.wind_environment.rain->at(target)->at(0)+=plant(index).facing*runtime.plk*600.;
    const auto targets=world_.targets->size();const bool right=plant(index).facing==1.;
    const auto speed_max=world_.wind_environment.zombie_speed_max;
    for(size_t target=0;target<targets;++target) {
        if(right?position(target).x<globals.xx.get():position(target).x>globals.xx.get())continue;
        if(body(target).hand=="报纸")services_.surface(target,plant(index).facing,body(target).hand_hp);
        if(body(target).hand=="气球") {
            position(target).vx+=(right?1.:-1.)*runtime.plk*20.;
            // The native left balloon branch also uses greater-than.
            if(position(target).vx>(right?1.:-1.)*speed_max*10.)position(target).vx=(right?1.:-1.)*speed_max*10.;
        }else {
            const auto size=body(target).size.get();if(size==0.)throw std::domain_error("zero blover target size");
            position(target).vx+=(right?1.:-1.)*runtime.plk*6.;
            const auto limit=(right?1.:-1.)*speed_max*36./std::pow(size,3.);
            if(right?position(target).vx>limit:position(target).vx<limit)position(target).vx=limit;
        }
    }
    if(++plant(index).expires.get()==500.)plant(index).dead.set(DeathMarker(0.));
}
void PlantRegion::mine(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const auto tile=runtime.tile;
    if(nearby_row(plant(index).cell,0) && world_.heroes.globals.mode.get()!="我是僵尸" && plant(index).buried.get()==0.)plant(index).dead.set(DeathMarker(0.));
    if(plant(index).buried.get()>0. && --plant(index).buried.get()==0.)sound("出坟墓",index);
    if(plant(index).buried.get()!=0.)return;
    if(plant(index).emerged.get()<200.) {
        ++plant(index).emerged.get();
        if(py::mod(plant(index).emerged.get(),60.)==0.) {
            const auto cell=plant(index).cell;const auto& tile_state=world_.terrain.native_at(cell.y+1,cell.x);
            runtime.emit_particles(tile_state.block.get(),{cell.x*tile+tile*.5,(cell.y+1)*tile+tile*.5},6);
        }
    }
    ++plant(index).flash.get();
}
void PlantRegion::producers(const Frame& frame) {
    const auto index=frame.index;auto& runtime=world_.runtime;const bool mushroom=frame.name=="阳光菇";
    if(mushroom) {
        if(plant(index).growth.get()>0. && --plant(index).growth.get()==0.){plant(index).grown.set(1.);sound("阳光菇",index);}
        if(plant(index).grown.get()>0. && plant(index).grown.get()<200.)++plant(index).grown.get();
    }
    if(plant(index).burst.get()>0.) {
        if(++plant(index).burst.get()==125.) {
            const double facing=runtime.rng.randint(0,1)==1?1.:-1.;
            const int count=frame.name=="双子向日葵"?2:1;
            for(int i=0;i<count;++i) {
                const auto point=center(index);auto sun=std::make_shared<NativeSun>();
                sun->motion={point.x,point.y,(i==0?facing:-facing)*runtime.rng.randint(100,200)*runtime.plk*1.5,-runtime.rng.randint(200,250)*runtime.plk};
                sun->animation=-200.;sun->size=mushroom && plant(index).grown.get()==0.?0.:1.;native_.loose_suns.push_back(std::move(sun));
            }
        }
        if(plant(index).burst.get()>250.) {
            plant(index).burst.set(0.);
            if(world_.heroes.globals.mode.get()!="我是僵尸")
                plant(index).sun.get()+=mushroom || world_.placement.sky=="红天" || world_.placement.day=="白天"?2000.:4000.;
        }
    }
    if(plant(index).sun.get()>0. && plant(index).burst.get()==0. && --plant(index).sun.get()==0.) {
        plant(index).burst.set(1.);
        if(world_.heroes.globals.mode.get()=="我是僵尸")plant(index).sun.set(0.);
        else {
            const double delay=frame.name=="双子向日葵"?150.:100.;const auto count=world_.plant_roster->size();
            for(size_t target=0;target<count;++target) {
                const auto& kind=plant(target).kind;
                if(mushroom?kind=="阳光菇":kind=="向日葵" || kind=="双子向日葵")plant(target).sun.get()+=delay;
            }
        }
    }
}
void PlantRegion::run() {
    LiveBattleSources sources(world_);NativeBirthScope births(world_.runtime,services_);
    const auto count=world_.plant_roster->size();auto& runtime=world_.runtime;const auto tile=runtime.tile;
    for(size_t index=0;index<count;++index) {
        world_.heroes.source_index=int64_t(index);services_.plant_gate(index);
        Frame frame{index,plant(index).cell,{}};
        if(plant(index).hurt.get()>0. && ++plant(index).hurt.get()==50.)plant(index).hurt.set(0.);
        if(needs_support(index) && world_.terrain.native_at(frame.cell.y+1,frame.cell.x).block.get()=="空")plant(index).dead.set(DeathMarker(0.));
        if(plant(index).sleep.present()) {
            if(++plant(index).sleep.get()==400.)plant(index).sleep.set(0.);
            const auto sleep=plant(index).sleep.get();
            if(sleep==50. || sleep==100. || sleep==150.) {
                world_.heroes.globals.yy.set(plant(index).kind=="海蘑菇" && !secret("水兵")?-tile*.6:0.);
                const auto cell=plant(index).cell;
                auto& entity=spawn("睡觉",1.,{cell.x*tile+tile,cell.y*tile+tile*.5+world_.heroes.globals.yy.get(),plant(index).facing*runtime.plk*50.,-50.*runtime.plk});
                entity.expires.set(900.);
            }
            continue;
        }
        if(py::mod(plant(index).hurt.get(),2.)==0. && ++plant(index).root_animation.get()>250.)plant(index).root_animation.set(0.);
        frame.name=plant(index).kind;
        if(frame.name=="花盆")world_.terrain.native_at(frame.cell.y,frame.cell.x).root_animation=plant(index).root_animation;
        if(frame.name=="玉米加农炮")cannon(frame);
        if(frame.name=="大蒜" && plant(index).root_animation.get()==125.) {
            const auto facing=runtime.rng.randint(0,1)==0?-1.:1.;const auto cell=plant(index).cell;
            auto& entity=spawn("臭气",facing,{cell.x*tile+tile+runtime.rng.randint(-10,10)*tile*.03,cell.y*tile+tile*.5,0.,-50.*runtime.plk});entity.expires.set(900.);
        }
        if(frame.name=="窝瓜")squash(frame);
        if(frame.name=="大喷菇" || frame.name=="雷蘑菇")fume(frame);
        if(frame.name=="小喷菇" || frame.name=="胆小菇" || frame.name=="海蘑菇")puff(frame);
        if(frame.name=="裂荚射手")split(frame);
        if(frame.name=="豌豆射手" || frame.name=="寒冰射手" || frame.name=="双发射手" || frame.name=="杨桃" || frame.name=="仙人掌" || frame.name=="机枪射手")shooters(frame);
        if(frame.name=="香蒲")cattail(frame);
        if(frame.name=="地刺" || frame.name=="地刺王")spikes(frame);
        if(frame.name=="萝卜伞")umbrella(frame);
        if(frame.name=="大嘴花" || frame.name=="龙蒺藜")chomper(frame);
        if(frame.name=="忧郁蘑菇")gloom(frame);
        if(frame.name=="卷心菜投手" || frame.name=="西瓜投手" || frame.name=="玉米投手" || frame.name=="冰瓜投手")pitcher(frame);
        if(frame.name=="路灯花")lantern(frame);
        if(frame.name=="金盏花")marigold(frame);
        if(frame.name=="毁灭菇" && ++plant(index).expires.get()==200.)plant(index).dead.set(DeathMarker(0.));
        // The installed PvP66 stone-wear predicate always returns false.
        if(frame.name=="磁力菇" || frame.name=="吸金磁")magnet(frame);
        if(frame.name=="寒冰菇")freezing(frame);
        if(frame.name=="模仿者")imitation(frame);
        if(frame.name=="火爆辣椒" && ++plant(index).expires.get()==200.)plant(index).dead.set(DeathMarker(0.));
        if(frame.name=="墓碑吞噬者")gravebuster(frame);
        if(frame.name=="三叶草")blover(frame);
        if(frame.name=="樱桃炸弹" && ++plant(index).expires.get()==200.)plant(index).dead.set(DeathMarker(0.));
        if(frame.name=="土豆地雷")mine(frame);
        if(frame.name=="阳光菇" || frame.name=="向日葵" || frame.name=="双子向日葵")producers(frame);
    }
}
} // namespace pvz::typed72
