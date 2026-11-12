#include "sim/typed/plant_spawn.h"
namespace pvz::typed72 {
namespace {
bool has(const std::vector<std::string>& values,std::string_view value){return std::find(values.begin(),values.end(),value)!=values.end();}
bool one_of(std::string_view s,std::initializer_list<std::string_view> values){return std::find(values.begin(),values.end(),s)!=values.end();}
}
PlantRef plant_original(TypedBattleState& world,Cell cell,std::string name,double facing) {
    auto& rt=world.runtime;auto& map=world.terrain;auto& placement=world.placement;const auto& catalog=world.plant_catalog;
    const auto& secrets=*world.heroes.globals.secrets.get();const auto& mode=world.heroes.globals.mode.get();
    if(name=="高坚果"&&has(secrets,"石果"))name="石果子";
    if(name=="大嘴花"&&has(secrets,"龙蒺藜"))name="龙蒺藜";
    if(name=="大喷菇"&&has(secrets,"雷霆"))name="雷蘑菇";
    if(name=="睡莲")map.native_at(cell.y,cell.x).lily.set(facing);
    if(name=="花盆") {
        map.native_at(cell.y,cell.x).block.set("花盆块");map.native_at(cell.y,cell.x).root_animation.set(0.);
        rt.emit_particles("花盆",{cell.x*rt.tile+rt.tile*.5,cell.y*rt.tile+rt.tile},6);
    }
    auto plant=std::make_shared<CombatPlant>(name,cell,facing);world.add_plant(plant);auto& p=*plant;
    p.root_animation.set(0.);p.head_animation.set(0.);
    if(one_of(name,{"向日葵","阳光菇","双子向日葵"})) {
        p.sun.set(mode=="我是僵尸"?0.:1.);p.burst.set(0.);
        if(name=="阳光菇"){p.grown.set(0.);p.growth.set(20000.);}
    }
    if(one_of(name,{"大嘴花","龙蒺藜"})){p.eating.set(0.);p.shooting.set(0.);p.shoot_cd.set(0.);}
    if(name=="地刺王")p.virtual_hp.set(3.);
    if(name=="模仿者") {
        p.imitation.set(placement.imitation);
        if(mode=="抽奖模式") {
            // Preserve the RNG call before the boss shortcut and both retry
            // loops; catalog order is part of the native random stream.
            const auto upper=3+int64_t(world.targets->size()/10);
            if(rt.rng.randint(1,upper)!=1||placement.boss_battle) {
                std::string selected;
                do{selected=catalog.plants.at(size_t(rt.rng.randint(0,int64_t(catalog.plants.size())-1)));}while(selected=="睡莲"||selected=="咖啡豆");
                p.imitation.set(std::move(selected));
            }else p.imitation.set(catalog.lottery_zombies.at(size_t(rt.rng.randint(0,int64_t(catalog.lottery_zombies.size())-1))));
        }
        p.imitator_cd.set(300.);
    }
    if(name=="萝卜伞"){p.shoot_cd.set(0.);p.shooting.set(0.);}
    if(name=="路灯花"){p.lamp.set(600.);p.burst.set(0.);}
    if(name=="土豆地雷"){p.buried.set(has(secrets,"地雷")?3000.:6000.);p.emerged.set(0.);p.flash.set(0.);}
    if(name=="金盏花"){p.money_cd.set(mode=="我是僵尸"?0.:1.);p.burst.set(0.);p.money.set(0.);}
    if(name=="裂荚射手"){p.shooting.set(0.);p.shoot_cd.set(0.);p.secondary_shot.set(0.);p.secondary_cd.set(0.);p.secondary_double.set(0.);}
    if(name=="小喷菇"&&has(secrets,"小喷"))p.small_puff.set(15.);
    if(one_of(name,{"豌豆射手","海蘑菇","香蒲","机枪射手","寒冰射手","双发射手","小喷菇","大喷菇","雷蘑菇","忧郁蘑菇","胆小菇","杨桃","地刺","地刺王"})||has(catalog.lobbers,name)) {
        p.shooting.set(0.);p.shoot_cd.set(0.);
        if(name=="胆小菇")p.scared.set(0.);if(name=="双发射手")p.double_shot.set(0.);if(name=="机枪射手")p.gatling.set(0.);
    }
    if((placement.day=="白天"&&has(catalog.night_plants,name)&&placement.sky!="红天")||has(secrets,"早八"))p.sleep.set(0.);
    map.native_at(cell.y,cell.x).plant.set(true);p.hp.set(6.);
    if(one_of(name,{"樱桃炸弹","毁灭菇","寒冰菇","火爆辣椒","三叶草"}))p.expires.set(0.);
    if(name=="墓碑吞噬者")p.grave_eating.set(0.);
    if(name=="玉米加农炮"){p.cannon_cd.set(0.);p.cannon_animation.set(0.);p.cannon_flash.set(0.);}
    if(one_of(name,{"磁力菇","吸金磁"}))p.magnet.set(0.);
    if(name=="仙人掌"){p.shooting.set(0.);p.shoot_cd.set(0.);p.hp.set(36.);}
    if(name=="大蒜")p.hp.set(18.);
    if(one_of(name,{"坚果","南瓜头"}))p.hp.set(72.);
    if(name=="高坚果")p.hp.set(144.);
    if(name=="石果子"){p.virtual_hp.set(3.);p.expires.set(0.);p.hp.set(144.);}
    if(has(secrets,"硬化"))p.hp.get()+=3.;p.hurt.set(0.);p.max_hp.set(p.hp.get());
    if(!one_of(name,{"花盆","睡莲","墓碑吞噬者"}))placement.imitation=name;
    return plant;
}
std::optional<size_t> find_plant(const PlantRoster& roster,Cell cell,bool exclude_pumpkin) {
    std::optional<size_t> found;
    for(size_t i=0;i<roster.size();++i) {
        const auto& p=*roster[i];if(p.cell.y!=cell.y||p.cell.x!=cell.x)continue;
        if(p.kind=="南瓜头"){if(exclude_pumpkin)continue;return i;}found=i;
    }
    return found;
}
bool clear_original_plant(TypedBattleState& world,Cell cell) {
    const auto index=find_plant(*world.plant_roster,cell);if(!index)return false;
    world.plant_roster->at(*index)->dead.set(DeathMarker(0.));return true;
}
void destroy_pvp_block(TypedBattleState& world,PlantLifecycle& plants,Cell cell) {
    const auto& rows=world.terrain.grid;
    if(cell.y>=0&&size_t(cell.y)<rows.size()) {
        const auto& row=rows[size_t(cell.y)];if(row.empty())throw std::domain_error("empty bedrock row");
        const auto size=int64_t(row.size());const auto& tile=row[size_t((cell.x%size+size)%size)];
        if(!tile)throw std::invalid_argument("null bedrock tile");
        if(tile->block.present()&&!tile->block.is_null()&&tile->block.get()=="基岩")return;
    }
    destroy_original_block(world,plants,cell);
}
void destroy_original_block(TypedBattleState& world,PlantLifecycle& plants,Cell cell,bool solid_only) {
    auto& map=world.terrain;auto& rt=world.runtime;
    if(map.outside(cell.y,cell.x)||cell.y==map.rows()-1)return;
    if(solid_only&&map.empty(cell.y,cell.x))return;
    const auto name=map.native_at(cell.y,cell.x).block.get();const Point center{cell.x*rt.tile+rt.tile*.5,cell.y*rt.tile+rt.tile*.5};
    if(name!="空")rt.emit_particles(name,center,9);
    if(name=="花盆块") {
        map.native_at(cell.y,cell.x).block.set("空");
        if(!map.outside(cell.y-1,cell.x)&&map.native_at(cell.y-1,cell.x).plant.present())plants.clear({cell.y-1,cell.x});
    }
    if(cell.y<map.water_surface&&name!="车底") {
        if(!map.is_empty(name)&&name!="雪") {
            map.native_at(cell.y,cell.x).inner_block.set(name);
            rt.sound("方块"+std::to_string(rt.rng.randint(1,4)),{center.x,center.y,0.,0.});
        }
        map.native_at(cell.y,cell.x).block.set("空");
        if(!map.is_empty(name)&&name!="雪")map.native_at(cell.y,cell.x).destroyed.set(0.);
    }
    if(map.native_at(cell.y,cell.x).plant.present())plants.clear(cell);
}
} // namespace pvz::typed72
