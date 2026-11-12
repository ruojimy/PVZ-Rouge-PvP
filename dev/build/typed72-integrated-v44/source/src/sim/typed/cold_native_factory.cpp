#include "cold_native_factory.h"
#include "core/pymath.h"
#include <unordered_set>
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
template<class T>void missing(Field<T>& f,T value){if(!f.present())f.set(std::move(value));}
}
std::string ColdNativeFactory::mode()const{return world_.heroes.globals.mode.or_missing("");}
double ColdNativeFactory::hp_multiplier()const{const auto m=mode();if(m=="末日模式")return 4.;return m=="极难模式"||m=="无尽模式"||m=="测试模式"||m=="植物僵尸"?2.:1.;}
ZombieRef ColdNativeFactory::raw(const std::string& name,Motion& p,double facing,bool bridge){
    auto m=mode();if(bridge&&m=="植物僵尸")m="极难模式";
    ZombieSpawnInput input;input.mode=m=="极难模式"?NativeSpawnMode::extreme:m=="末日模式"?NativeSpawnMode::doomsday:m=="无尽模式"?NativeSpawnMode::endless:m=="测试模式"?NativeSpawnMode::test:m=="抽奖模式"?NativeSpawnMode::lottery:NativeSpawnMode::normal;
    const auto& hero=*world_.heroes.globals.position.get();input.player={hero.x,hero.y};input.map_rows=world_.terrain.rows();input.map_cols=world_.terrain.cols();input.screen_height=settings_.screen_height;input.bosses=settings_.bosses;
    return spawn_original_zombie(world_,name,p,facing,input);
}
PlantRef ColdNativeFactory::plant(Cell cell,const std::string& name,double facing){
    if(name=="石块"){
        if(cell.y<0||cell.y>=world_.terrain.rows()||cell.x<0||cell.x>=world_.terrain.cols())return {};
        ColdPlacementRules rules(world_.terrain,{},*world_.heroes.globals.secrets.get());if(!rules.stone_cell(cell.y,cell.x))return {};
        auto& tile=world_.terrain.native_at(cell.y,world_.terrain.wrap(cell.x));tile.block.set("石");tile.plant.erase();tile.inner_block.erase();tile.destroyed.erase();tile.snow_gone.erase();tile.growing.erase();tile.wave.erase();tile.wave_cd.erase();
        world_.runtime.emit_particles("石",{cell.x*world_.runtime.tile+world_.runtime.tile*.5,cell.y*world_.runtime.tile+world_.runtime.tile*.5},4);return {};
    }
    auto p=plant_original(world_,cell,name,facing);
    if(name=="三向射手"&&p){missing(p->shooting,0.);missing(p->shoot_cd,0.);
        if(!p->bonus.tripea_angles.present()){std::vector<Field<double>> values;const std::array<double,3> tripea_angles=facing>=0.?std::array<double,3>{-15.,0.,15.}:std::array<double,3>{195.,180.,165.};for(double angle:tripea_angles){Field<double> a;a.set(angle);values.push_back(a);}p->bonus.tripea_angles.set(std::move(values));}
        if(!p->bonus.tripea_targets.present()){std::vector<Field<RecordId>> values(3);for(auto& v:values)v.set_null();p->bonus.tripea_targets.set(std::move(values));}
    }return p;
}
bool ColdNativeFactory::duck(Point p)const{
    const double scale=std::max(1.,world_.runtime.tile);const auto col=int64_t(p.x/scale);const auto row=int64_t(p.y/scale);
    for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){const auto cell=world_.terrain.at(row+dy,col+dx);if(cell&&cell->block.present()&&!cell->block.is_null()&&(cell->block.get()=="水"||cell->block.get()=="黑水"))return true;}return false;
}
void ColdNativeFactory::random_armor(const ZombieRef& z,double factor){
    const auto roll=world_.runtime.rng.randint(0,99);if(roll<45)return;
    if(roll<70){z->body.armor="路障";z->body.armor_hp=std::max(0.,std::trunc(200.*factor));}
    else if(roll<85||roll>=95){z->body.armor="铁桶";z->body.armor_hp=std::max(0.,std::trunc(500.*factor));}
    if(roll>=85){z->body.hand="钢门";z->body.hand_hp=std::max(0.,std::trunc(500.*factor));}
}
void ColdNativeFactory::init_plant_zombie(const ZombieRef& z,const std::string& name,bool ducked,bool armor){
    const auto* config=native_plant_zombie_config(name);if(!z||!config)return;const auto base=z->body.kind;
    ducked=ducked||base=="鸭子僵尸"||base.starts_with("鸭子");const auto display=ducked?"鸭子"+name:name;
    z->patch.plant_zombie.set(true);z->patch.plant_name.set(name);z->factory.plant_head.set(name+"-植物头");z->factory.plant_base.set(base);z->factory.plant_display.set(display);z->patch.duck.set(ducked);z->body.kind=display;
    const double factor=hp_multiplier();z->body.hp=std::max(0.,std::trunc(config->hp.or_missing(z->body.hp)*factor));z->patch.plant_max_hp.set(z->body.hp);z->patch.observed_max_hp.set(z->body.hp);
    z->patch.shooting_cooldown.set(-1.);z->patch.burst_left.set(0.);z->patch.burst_cooldown.set(0.);z->patch.fire_animation.set(0.);z->patch.aim_angle.set(z->body.facing>=0.?0.:180.);
    if(name=="毁灭菇僵尸"){z->patch.doom_life_ticks.set(0.);z->patch.doom_life_time.set(world_.native_time);}
    chili_.row_hint(CombatTarget::zombie(z),true);
    if(config->jump_speed.present()&&!config->jump_speed.is_null()&&config->jump_speed.get()!=0.)z->patch.jump_assist_cooldown.set(0.);else z->patch.jump_assist_cooldown.erase();
    if(config->move_speed.present()&&!config->move_speed.is_null())z->native.move_speed.set(std::max(1.,config->move_speed.get()*world_.runtime.plk));
    if(config->knockback.present()&&!config->knockback.is_null()&&config->knockback.get()!=0.)z->patch.knockback=config->knockback;
    if(armor)random_armor(z,factor);shooting_.enforce_motion(z,*config);
}
ZombieRef ColdNativeFactory::plant_zombie(const std::string& name,Motion& p,double facing,bool armor,bool ladder){
    const bool aquatic=duck({p.x,p.y});auto z=raw(aquatic?"鸭子普通僵尸":"普通僵尸",p,facing);init_plant_zombie(z,name,aquatic,armor);
    if(ladder){z->body.armor.clear();z->body.armor_hp=0.;z->body.hand="梯子";z->body.hand_hp=std::max(0.,std::trunc(250.*hp_multiplier()));}return z;
}
void ColdNativeFactory::note(size_t before){
    if(mode()=="我是僵尸"){
        if(state_.board_zombies.lock()!=world_.targets||state_.board_plants.lock()!=world_.plant_roster){state_.board_zombies=world_.targets;state_.board_plants=world_.plant_roster;state_.i_zombie_placed=false;}
        for(const auto& target:*world_.targets)if(target.unit&&!target.unit->body.dead.present()&&!target.unit->body.ash.present()&&target.unit->body.hp>0.)state_.i_zombie_placed=true;
        if(world_.targets->size()>before)state_.i_zombie_placed=true;return;
    }
    std::unordered_set<std::string> kinds;for(const auto& name:settings_.current_zombies)if(native_plant_zombie_config(name))kinds.insert(name);for(const auto& name:settings_.spawn_zombies)if(native_plant_zombie_config(name))kinds.insert(name);
    const auto chance=settings_.pumpkin_chance?*settings_.pumpkin_chance:std::clamp(4+int(kinds.size()),0,95);
    for(size_t i=std::min(before,world_.targets->size());i<world_.targets->size();++i)if(auto z=world_.targets->at(i).unit)if(z->body.hp>0.&&chance>0&&world_.runtime.rng.randint(1,100)<=chance){z->body.armor="南瓜头防具";z->body.armor_hp=800.;}
}
std::string ColdNativeFactory::test_name(const std::string& original){
    if(native_plant_zombie_config(original))return original;
    for(const auto& [key,names]:settings_.test_source_mapping)if(key==original&&!names.empty())return names.at(size_t(world_.runtime.rng.randint(0,int64_t(names.size())-1)));
    const auto all=native_plant_zombie_catalog();return all.empty()?std::string{}:std::string(all[size_t(world_.runtime.rng.randint(0,int64_t(all.size())-1))].kind);
}
ZombieRef ColdNativeFactory::sunflower(Motion& p,double facing){
    auto z=raw("舞王僵尸",p,facing,true);state_.sunflower_active=state_.sunflower_spawned=true;
    if(!yes(z->factory.sunflower_boss)){const double old=std::max(1.,z->body.hp);z->factory.sunflower_boss.set(true);z->body.kind="向日葵舞王僵尸";z->body.hp=std::max(1.,pvz::py::round0(old*.75));z->patch.observed_max_hp.set(z->body.hp);
        missing(z->body.dancing,0.);missing(z->native.dance_cd,1000.);missing(z->native.light,1.);z->factory.dancer_pending.erase();}
    if(!settings_.battle_zombies.empty()&&settings_.battle_zombies.back()=="向日葵舞王僵尸"){settings_.battle_zombies.back()="舞王僵尸";state_.sunflower_restore_tail=true;}return z;
}
std::optional<ZombieRef> ColdNativeFactory::backup(const std::string& name,Motion& p,double facing){
    if(name!="伴舞僵尸")return {};ZombieRef boss;
    if(settings_.dancer_index&&*settings_.dancer_index<world_.targets->size()){auto current=world_.targets->at(*settings_.dancer_index).unit;if(current&&yes(current->factory.sunflower_boss))boss=current;}
    const bool caller=bool(boss);
    if(!boss)for(const auto& target:*world_.targets)if(target.unit&&yes(target.unit->factory.sunflower_boss)&&target.unit->body.hp>0.){boss=target.unit;break;}
    const bool force=mode()=="植物僵尸"&&(settings_.sunflower_context||state_.sunflower_active||state_.sunflower_spawned);
    if(!boss&&!force)return {};
    auto& field=boss?boss->factory.dancer_pending:state_.dancer_pending;
    if((caller&&settings_.dancer_slot==0)||!field.present()||field.is_null()||field.get().empty()){
        std::vector<std::string> names;for(const auto& cfg:native_plant_zombie_catalog())names.emplace_back(cfg.kind);
        // The exact four-without-replacement sampler is bound to PyRandom.
        std::vector<std::string> chosen;for(int i=0;i<4&&!names.empty();++i){const auto index=size_t(world_.runtime.rng.randint(0,int64_t(names.size())-1));chosen.push_back(names[index]);names.erase(names.begin()+index);}field.set(std::move(chosen));
    }
    std::string chosen;if(!field.get().empty()){chosen=field.get().front();field.get().erase(field.get().begin());}
    if(!native_plant_zombie_config(chosen)){if(force)chosen="豌豆僵尸";else return raw(name,p,facing,true);}
    return plant_zombie(chosen,p,facing,false);
}
ZombieRef ColdNativeFactory::zombie(const std::string& name,Motion& p,double facing){
    const auto before=world_.targets->size();ZombieRef result;
    if(name=="向日葵舞王僵尸"||(name=="舞王僵尸"&&mode()=="植物僵尸"&&(settings_.sunflower_context||state_.sunflower_active||state_.sunflower_spawned)))result=sunflower(p,facing);
    else if(const auto mapped=backup(name,p,facing))result=*mapped;
    else if(name=="梯子僵尸"&&mode()!="我是僵尸"){
        std::string mapped=name;if(settings_.ladder_support_call){const auto all=native_plant_zombie_catalog();const auto index=world_.runtime.rng.randint(0,int64_t(all.size()));if(index>0)mapped=all[size_t(index)-1].kind;}
        result=native_plant_zombie_config(mapped)?plant_zombie(mapped,p,facing,false,true):raw(name,p,facing,true);
    }else if(settings_.plant_zombie_test){const auto selected=test_name(name);result=native_plant_zombie_config(selected)?plant_zombie(selected,p,facing,mode()!="我是僵尸"):raw(name,p,facing,true);
    }else result=native_plant_zombie_config(name)?plant_zombie(name,p,facing,mode()!="我是僵尸"):raw(name,p,facing,true);
    note(before);return result;
}
} // namespace pvz::typed72
