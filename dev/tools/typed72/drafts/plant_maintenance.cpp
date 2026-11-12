#include "sim/typed/plant_maintenance.h"
#include <cmath>

namespace pvz::typed72 {
ZombieRecordFields& PlantMaintenance::body(size_t index)const {
    const auto target=world_.targets->at(index);
    return target.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero)):target.unit->body;
}
Motion& PlantMaintenance::motion(size_t index)const {
    const auto target=world_.targets->at(index);
    return target.is_hero()?*world_.heroes.cached_proxy(target.hero).position:target.unit->body.motion.get();
}
Point PlantMaintenance::center(size_t index)const {
    const auto cell=plant(index).cell;const auto tile=world_.runtime.tile;
    return {cell.x*tile+tile*.5,cell.y*tile+tile*.5};
}
Entity& PlantMaintenance::spawn(std::string name,double facing,Motion position,double expires){
    combat_.add_entity(std::move(name),facing,position);
    auto& entity=*world_.runtime.entities.list()->back();entity.expires.set(expires);return entity;
}
void PlantMaintenance::knock(Point point,double radius,double horizontal,double vertical){
    auto& hero=*world_.heroes.globals.position.get();const auto& runtime=world_.runtime;
    if(std::abs(hero.x-point.x)>runtime.tile*radius || std::abs(hero.y-point.y)>runtime.tile*radius)return;
    if(point.x>hero.x)hero.vx-=horizontal*runtime.plk;else hero.vx+=horizontal*runtime.plk;
    hero.vy-=vertical*runtime.plk;
}
void PlantMaintenance::doom(size_t index){
    auto& runtime=world_.runtime;const auto tile=runtime.tile;
    const auto point=center(index);world_.heroes.globals.xx.set(point.x);world_.heroes.globals.yy.set(point.y);
    runtime.nuclear_flash.set(80.);knock(point,5.,900.,800.);
    const auto count=world_.targets->size();
    for(size_t z=0;z<count;++z){
        const auto& position=motion(z);
        if(std::abs(position.x-world_.heroes.globals.xx.get())>tile*5. || std::abs(position.y-world_.heroes.globals.yy.get())>tile*5.)continue;
        combat_.ash_zombie(z);
        if(policy_.second_doom_ash(int64_t(z)))combat_.ash_zombie(z);
    }
    for(int i=0;i<10;++i){
        const auto facing=runtime.rng.randint(0,1)==0?-1.:1.;
        const auto vertical=i/2%2==0?1.:-1.;const auto cell=plant(index).cell;
        auto& entity=spawn("毁灭3",facing,{cell.x*tile-tile*1.5+i*tile/2.,cell.y*tile-tile*.5-tile*4.+vertical*tile/2.,0.,-runtime.plk*30.},700.);
        entity.rotation.set(double(runtime.rng.randint(0,360)));
    }
    for(const auto* name:{"毁灭2","毁灭1"}){
        const auto cell=plant(index).cell;
        spawn(name,plant(index).facing,{cell.x*tile-tile*1.5,cell.y*tile-tile*.5-tile*3.5,0.,0.},700.);
    }
    runtime.screen_shake.set({200.,0.,0.});const auto sound=center(index);
    runtime.sound("毁灭菇",{sound.x,sound.y,0.,0.});
    const auto cell=plant(index).cell;
    for(int y=0;y<5;++y) {
        world_.heroes.globals.yy.set(double(y));
        for(int x=0;x<5;++x) {
            world_.heroes.globals.xx.set(double(x));
            if(std::abs(y-2)+std::abs(x-2)<=3)destroy_pvp_block(world_,plants_,{cell.y-2+y,cell.x-2+x});
        }
    }
}
void PlantMaintenance::cherry(size_t index){
    auto& runtime=world_.runtime;const auto tile=runtime.tile;const auto point=center(index);
    world_.heroes.globals.xx.set(point.x);world_.heroes.globals.yy.set(point.y);knock(point,2.5,500.,500.);
    const auto cell=plant(index).cell;
    for(int y=0;y<5;++y)for(int x=0;x<5;++x){
        const Cell target{cell.y-2+y,cell.x-2+x};
        if(std::abs(y-2)+std::abs(x-2)>3 || world_.terrain.outside(target.y,target.x))continue;
        if(world_.terrain.native_at(target.y,target.x).block.get()=="梯子块")destroy_pvp_block(world_,plants_,target);
    }
    const auto count=world_.targets->size();
    for(size_t z=0;z<count;++z){
        const auto& position=motion(z);
        if(std::abs(position.x-world_.heroes.globals.xx.get())<=tile*2.5 && std::abs(position.y-world_.heroes.globals.yy.get())<=tile*2.5)combat_.ash_zombie(z);
    }
    const auto clouds=runtime.rng.randint(4,5);
    for(int i=0;i<clouds;++i){
        const auto facing=i%2==0?-1.:1.;const auto vertical=i/2%2==0?1.:-1.;const auto position=plant(index).cell;
        auto& entity=spawn("爆炸",facing,{position.x*tile,position.y*tile-tile,facing*runtime.plk*runtime.rng.randint(300,400),runtime.plk*runtime.rng.randint(200,300)*vertical},900.);
        entity.rotation.set(double(runtime.rng.randint(0,360)));
    }
    const auto facing=runtime.rng.randint(0,1)==0?-1.:1.;const auto position=plant(index).cell;
    auto& entity=spawn("爆炸",facing,{position.x*tile,position.y*tile-tile,0.,0.},900.);
    entity.rotation.set(double(runtime.rng.randint(0,360)));
    runtime.screen_shake.set({100.,0.,0.});const auto sound=center(index);runtime.sound("樱桃炸弹",{sound.x,sound.y,0.,0.});
}
bool PlantMaintenance::burnable(Cell cell)const {
    if(world_.terrain.outside(cell.y,cell.x))return false;
    const auto& block=world_.terrain.native_at(cell.y,cell.x).block.get();
    return block=="梯子块" || block=="雪";
}
void PlantMaintenance::chili(size_t index){
    auto& runtime=world_.runtime;const auto tile=runtime.tile;const auto cell=plant(index).cell;
    world_.heroes.globals.yy.set(cell.y*tile+tile*.5);
    int64_t left=cell.x,right=cell.x;
    for(int side=0;side<2;++side){
        auto& edge=side==0?left:right;
        for(int distance=0;distance<8;++distance){
            edge=cell.x+(side==0?-distance:distance);
            for(const auto y:{cell.y+1,cell.y-1})
                if(burnable({y,edge}))destroy_pvp_block(world_,plants_,{y,edge});
            const bool blocked=world_.terrain.outside(cell.y,edge) || world_.terrain.native_at(cell.y,edge).block.get()!="空";
            if(blocked){
                if(burnable({cell.y,edge})){
                    destroy_pvp_block(world_,plants_,{cell.y,edge});
                    // Original wordcode at 116750 reads zuox in both arms.
                    spawn("火",-1.,{left*tile+tile,cell.y*tile,0.,0.},900.-distance*5.);
                    continue;
                }
                edge+=side==0?1:-1;break;
            }
            spawn("火",-1.,{edge*tile+tile,cell.y*tile,0.,0.},900.-distance*5.);
        }
    }
    const auto count=world_.targets->size();
    for(size_t z=0;z<count;++z){
        const auto radius=tile*(body(z).size.get()-1.);const auto& position=motion(z);
        if(position.x>left*tile-tile*.5 && position.x<right*tile+tile*1.5 && std::abs(position.y-world_.heroes.globals.yy.get())<=radius){
            combat_.ash_zombie(z);body(z).ice.erase();
        }
    }
    // NativeRuntime's installed jump 117182 -> 117296 owns Dave launch removal.
    runtime.screen_shake.set({50.,0.,0.});const auto sound=center(index);runtime.sound("辣椒",{sound.x,sound.y,0.,0.});
}
void PlantMaintenance::kelp(size_t index){
    const auto cell=plant(index).cell;const auto tile=world_.runtime.tile;
    auto& entity=spawn("缠绕海草x",plant(index).facing,{cell.x*tile+tile/2.,cell.y*tile,0.,0.},0.);
    if(plant(index).monochrome.present())entity.monochrome.set(DeathMarker(0.));
    entity.gravity.set(0.);const auto sound=center(index);world_.runtime.sound("取走",{sound.x,sound.y,0.,0.});
}
void PlantMaintenance::mine(size_t index){
    if(plant(index).buried.get()!=0.)return;
    auto& runtime=world_.runtime;const auto tile=runtime.tile;const auto point=center(index);
    world_.heroes.globals.xx.set(point.x);world_.heroes.globals.yy.set(point.y);knock(point,1.,300.,300.);
    const auto count=world_.targets->size();
    for(size_t z=0;z<count;++z){
        const auto& position=motion(z);
        const auto center_x=world_.heroes.globals.xx.get(),center_y=world_.heroes.globals.yy.get();
        const auto& content=plant(index).source.content;
        if(content.present() && !content.is_null() && content.get()=="原始土豆地雷") {
            const auto size=body(z).size.present() && !body(z).size.is_null() && body(z).size.get()!=0.?body(z).size.get():2.;
            const auto head=position.y-tile*size;
            const auto dy=head<=center_y && center_y<=position.y?0.:std::min(std::abs(center_y-position.y),std::abs(center_y-head));
            const auto dx=wrap_delta(center_x,position.x,world_.world_width.get());
            if(std::hypot(dx,dy)<=2.4*tile+1e-9)combat_.ash_zombie(z);
        }else if(std::abs(position.x-center_x)<=tile*body(z).size.get()/2. && std::abs(position.y-center_y)<=tile*2.)combat_.ash_zombie(z);
    }
    const auto facing=runtime.rng.randint(0,1)==0?-1.:1.;const auto cell=plant(index).cell;
    spawn("炸雷",facing,{cell.x*tile,cell.y*tile-tile,0.,0.},800.);
    runtime.screen_shake.set({50.,0.,0.});const auto sound=center(index);runtime.sound("土豆地雷",{sound.x,sound.y,0.,0.});
}
void PlantMaintenance::supplement(size_t index){
    if(!policy_.supplement(index))return;
    auto& runtime=world_.runtime;const auto point=center(index);
    auto sun=std::make_shared<NativeSun>();sun->animation=-200.;sun->size=0.;
    sun->motion={point.x,point.y,runtime.rng.randint(-200,200)*runtime.plk*1.5,-runtime.rng.randint(200,250)*runtime.plk};
    region_.loose_suns.push_back(std::move(sun));
}
void PlantMaintenance::run(){
    LiveBattleSources sources(world_);
    NativeBirthScope births(world_.runtime,constructor_);
    HeroContext context(world_.heroes,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
    const auto count=world_.plant_roster->size();
    for(size_t remaining=count;remaining>0;--remaining){
        const auto index=remaining-1;world_.heroes.source_index=int64_t(index);
        if(!plant(index).dead.present())continue;
        world_.runtime.emit_particles(plant(index).kind,center(index),9);
        const auto name=plant(index).kind;
        if(!plant(index).sleep.present() && !plant(index).shovel_dead.present()){
            if(name=="毁灭菇")doom(index);
            if(name=="樱桃炸弹")cherry(index);
            if(name=="火爆辣椒")chili(index);
            if(name=="缠绕海草")kelp(index);
            if(name=="土豆地雷")mine(index);
        }
        supplement(index);const auto cell=plant(index).cell;
        if(name=="花盆")world_.terrain.native_at(cell.y,cell.x).block.set("空");
        if(name=="睡莲"){
            plants_.clear({cell.y-1,cell.x});world_.terrain.native_at(cell.y,cell.x).lily.erase();
        }
        world_.erase_plant_at(index);
        auto& tile=world_.terrain.native_at(cell.y,cell.x);
        if(tile.plant.present() && !lookup_pvp_plant(world_,cell,false))tile.plant.erase();
    }
}
} // namespace pvz::typed72
