#define PVZ72_TARGET_PROBE_EMBEDDED
#include "targets_probe.cpp"
#include "sim/typed/terrain_effects.h"
#include "sim/typed/flood.h"
#include "sim/typed/content_target.h"
#include "sim/typed/projectile_rules.h"
namespace {
Cell cell(const J& j){return {j.at(0).get<int>(),j.at(1).get<int64_t>()};}
TileRef tile(const J& j) {
    if(j.is_null())return {};keys(j,{"方块","里方块","睡莲","根动画","摧","雪消失","长出","水纹","水纹cd","坟墓","植物","kong","花盆","智能石块占位","_pvp_belt","_pvp_block_color","_pvp_wall_color"});
    auto t=std::make_shared<TerrainCell>();read(j,"方块",t->block);read(j,"里方块",t->inner_block);read(j,"_pvp_block_color",t->block_color);read(j,"_pvp_wall_color",t->wall_color);
#define NUM(n,k) read(j,k,t->n);
    PVZ72_TILE_NUMBERS(NUM)
    PVZ72_TILE_FLAGS(NUM)
#undef NUM
    return t;
}
J tile_state(const TileRef& t) {
    if(!t)return nullptr;J j=J::object();write(j,"方块",t->block);write(j,"里方块",t->inner_block);write(j,"_pvp_block_color",t->block_color);write(j,"_pvp_wall_color",t->wall_color);
#define NUM(n,k) write(j,k,t->n);
    PVZ72_TILE_NUMBERS(NUM)
    PVZ72_TILE_FLAGS(NUM)
#undef NUM
    return j;
}
void death_state(J& j,const char* key,const Field<DeathMarker>& f) {
    if(!f.present())return;if(f.is_null()){j[key]=nullptr;return;}const auto& m=f.get();j[key]=m.boolean_encoding()?J(m.number()!=0.):J(m.number());
}
J plant_state(const CombatPlant& p) {
    J j={{"植物",p.kind},{"坐标",J::array({p.cell.y,p.cell.x})},{"方向",p.facing}};
    write(j,"植物血",p.hp);write(j,"植物血上限",p.max_hp);write(j,"受伤",p.hurt);write(j,"模仿",p.imitation);
    write(j,"_pvp_copy_card",p.copy_card);
    write(j,"_pvp_grave_target",p.grave_target);
#define NUM(n,k) write(j,k,p.n);
    PVZ72_PLANT_NUMBERS(NUM)
#undef NUM
    death_state(j,"死",p.dead);death_state(j,"铲死",p.shovel_dead);
    death_state(j,"黑白",p.monochrome);
    if(p.expansion_clock.delta.present()&&!p.expansion_clock.delta.is_null()){J d=J::object();constexpr std::array<const char*,10> names{"射cd","射","吃","发射cd","发射动画","埋藏","滚蛋","吸","爆了","路灯"};for(size_t i=0;i<names.size();++i)write(d,names[i],p.expansion_clock.delta.get()[i]);j["_pvp_clock_delta"]=d;}write(j,"_pvp_max_hp",p.content_state.maximum_hp);write(j,"_pvp_armor_max",p.registration.armor_max);write(j,"_pvp_born",p.registration.born);write(j,"_pvp_zs_killed",p.secret_killed);write(j,"_pvp_temporary",p.temporary);write(j,"_pvp_transform_succeeded",p.transform_succeeded);
    write(j,"__pvz_sb_native_lantern_charm_heal_mark",p.lantern_charm_healed);
    write(j,"_pvp_owner",p.source.owner);write(j,"_pvp_id",p.source.id);write(j,"魅惑",p.source.charmed);
    if(p.source.seat)j["_pvp_seat"]=seat_name(*p.source.seat);
    write(j,"_pvp_sun_due",p.sun_due);write(j,"_pvp_rest_hp",p.rest_hp);write(j,"_pvp_rest_since",p.rest_since);write(j,"_pvp_aura_factor",p.aura_factor);
    write(j,"_pvp_content",p.source.content);write(j,"_pvp_variant",p.source.variant);write_point(j,"_pvp_head_point",p.head_point);
    write(j,"_pvp_card",p.protection.card);write(j,"_pvp_anchor_until",p.protection.anchor_until);write(j,"_pvp_reaper_hurt",p.protection.reaper_hurt);return j;
}
struct PlantProbe : TargetProbe,PlantLifecycle {
    GravebusterEffects graves;
    CollisionCatalog collision;
    ContentTargets content;
    J calls=J::array(),hooks=J::object();
    std::vector<TileRef> held;
    std::vector<PlantRef> all_plants;
    explicit PlantProbe(int64_t seed):TargetProbe(seed,true),graves(battle,*this),content(battle,damage,collision,1920.){}
    PlantRef plant_ref(size_t index){return all_plants.at(index);}
    void retain_plants(){
        for(const auto& plant:*battle.plant_roster)
            if(std::find(all_plants.begin(),all_plants.end(),plant)==all_plants.end())all_plants.push_back(plant);
    }
    void spawn_plant(Cell cell,std::string name,double facing){
        try{plant_original(battle,cell,std::move(name),facing);}
        catch(...){retain_plants();throw;}
        retain_plants();
    }
    ContentTarget content_target(const J& label){return label.is_object()?ContentTarget(plant_ref(label.at("plant").get<size_t>())):ContentTarget(target(label));}
    void before(const std::string& name){if(hooks.contains(name)&&hooks[name].value("fail_before",false))throw std::runtime_error("injected lifecycle failure");}
    void after(const std::string& name) {
        if(!hooks.contains(name))return;const auto cfg=hooks[name];hooks.erase(name);
        if(cfg.contains("body"))operations(cfg.at("body"),false);
        if(cfg.value("fail_after",false))throw std::runtime_error("injected lifecycle failure");
    }
    bool clear(Cell c)override {
        calls.push_back(J::array({"clear",c.y,c.x}));before("clear");const auto result=clear_original_plant(battle,c);after("clear");return result;
    }
    void plant(Cell c,std::string name,double facing)override {
        calls.push_back(J::array({"plant",c.y,c.x,name,facing}));before("plant");spawn_plant(c,std::move(name),facing);after("plant");
    }
    void important(Cell c,std::string name)override {
        calls.push_back(J::array({"important",c.y,c.x,name}));before("important");battle.terrain.important.push_back({c,std::move(name)});after("important");
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="plant_original") {
            keys(op,{"op","cell","name","facing","catch"});
            try{spawn_plant(cell(op.at("cell")),op.at("name"),op.value("facing",1.));}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="plant_write") {
            keys(op,{"op","plant","values"});auto& p=*plant_ref(op.at("plant").get<size_t>());const auto& v=op.at("values");
            keys(v,{"_pvp_owner","_pvp_id","魅惑","_pvp_content","_pvp_variant","_pvp_head_point","_pvp_card","_pvp_anchor_until","植物血","消亡","出来","睡觉"});
            read(v,"消亡",p.expires);read(v,"出来",p.emerged);read(v,"睡觉",p.sleep);
            read(v,"_pvp_owner",p.source.owner);read(v,"_pvp_id",p.source.id);read(v,"魅惑",p.source.charmed);
            read(v,"_pvp_content",p.source.content);read(v,"_pvp_variant",p.source.variant);read_point(v,"_pvp_head_point",p.head_point);
            read(v,"_pvp_card",p.protection.card);read(v,"_pvp_anchor_until",p.protection.anchor_until);read(v,"植物血",p.hp);
        }else if(action=="content_hit") {
            keys(op,{"op","source","unit_source","plant_source","target","amount","facing","surface","kind","catch","throw_raw"});
            const auto s=op.contains("plant_source")?source_ref(plant_ref(op["plant_source"].get<size_t>())):selected_source(op);
            throw_raw=op.value("throw_raw",false);
            try{content.damage(s,content_target(op.at("target")),op.at("amount"),op.value("facing",1.),op.value("surface",false),hit(op.value("kind",J("content"))));}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
            throw_raw=false;
        }else if(action=="content_point"||action=="content_contact") {
            keys(op,{"op","target","start","delta"});const auto t=content_target(op.at("target"));
            if(action=="content_point"){const auto p=content.point(t);result=J::array({p.x,p.y});}
            else {const auto& a=op.at("start");const auto& b=op.at("delta");result=content.contact(t,{a.at(0),a.at(1)},{b.at(0),b.at(1)});}
        }else if(action=="find_plant") {
            keys(op,{"op","cell","exclude_pumpkin"});auto found=find_plant(*battle.plant_roster,cell(op.at("cell")),op.value("exclude_pumpkin",false));result=found?J(*found):J(-1);
        }else if(action=="clear_plant") {
            keys(op,{"op","cell"});result=clear(cell(op.at("cell")));
        }else if(action=="destroy_block") {
            keys(op,{"op","cell","solid_only","pvp","catch"});
            try{if(op.value("pvp",false))destroy_pvp_block(battle,*this,cell(op.at("cell")));else destroy_original_block(battle,*this,cell(op.at("cell")),op.value("solid_only",false));}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="tile_replace") {
            keys(op,{"op","cell","value"});const auto c=cell(op.at("cell"));battle.terrain.grid.at(c.y).at(size_t(c.x))=tile(op.at("value"));
        }else if(action=="hold_tile") {
            keys(op,{"op","cell"});const auto c=cell(op.at("cell"));held.push_back(battle.terrain.at(c.y,c.x));
        }else if(action=="plant_roster_replace") {
            keys(op,{"op","plants"});auto roster=std::make_shared<PlantRoster>();for(const auto& id:op.at("plants"))roster->push_back(plant_ref(id.get<size_t>()));battle.plant_roster=std::move(roster);
        }else if(action=="lifecycle_hook") {
            keys(op,{"op","name","fail_before","fail_after","body"});J cfg=op;cfg.erase("op");cfg.erase("name");hooks[op.at("name").get<std::string>()]=std::move(cfg);
        }else if(action=="grave"||action=="grave_plant"||action=="grave_cell"||action=="chili_hint") {
            keys(op,{"op","unit","force"});const auto& u=units.at(op.at("unit").get<size_t>());
            if(action=="grave")result=graves.grave(u);
            else if(action=="grave_plant")result=graves.plant(u);
            else if(action=="grave_cell"){const auto f=gravebuster_cell(battle.terrain,*u,visual.tile);if(f)result=J::array({f->coordinate.y,f->coordinate.x});}
            else {const auto row=update_chili_row_hint(battle.terrain,*u,visual.tile,op.value("force",false));if(row)result=*row;}
        }else if(action=="chili_lane") {
            keys(op,{"op","position"});const auto& p=op.at("position");const auto row=chili_lane_row(battle.terrain,{p.at(0),p.at(1)},visual.tile);if(row)result=*row;
        }else if(action=="terrain_query") {
            keys(op,{"op","cell"});const auto c=cell(op.at("cell"));result=J::array({battle.terrain.empty(c.y,c.x),battle.terrain.water(c.y,c.x)});
        }else if(action=="displace") {
            keys(op,{"op","position","size","periodic"});auto p=motion(op.at("position"));const auto hit=displace_body(p,op.value("size",0.),battle.terrain,visual.tile,visual.plk,op.value("periodic",false));result={{"motion",as_json(p)},{"collision",hit}};
        }else return TargetProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        TargetProbe::extra_snapshot(row);row["plants"]=J::array();row["all_plants"]=J::array();row["terrain"]=J::array();row["held_tiles"]=J::array();
        for(const auto& p:*battle.plant_roster)row["plants"].push_back(plant_state(*p));
        for(const auto& plant:all_plants)row["all_plants"].push_back(plant_state(*plant));
        for(const auto& cells:battle.terrain.grid){J r=J::array();for(const auto& t:cells)r.push_back(tile_state(t));row["terrain"].push_back(std::move(r));}
        for(const auto& t:held)row["held_tiles"].push_back(tile_state(t));
        row["important_blocks"]=J::array();for(const auto& b:battle.terrain.important)row["important_blocks"].push_back({{"坐标",J::array({b.cell.y,b.cell.x})},{"方块",b.block}});
        row["imitation"]=battle.placement.imitation;row["lifecycle_calls"]=calls;row["grave_counts"]=J::array({graves.graves_created,graves.plants_created});
        row["row_hints"]=J::array();for(const auto& u:units){J f=J::object();write(f,"__pvz_sb_chili_zombie_row_hint",u->patch.chili_row_hint);write(f,"牛顿",u->body.gravity);row["row_hints"].push_back(std::move(f));}
    }
};
void configure_plants(PlantProbe& p,const J& j) {
    J base=j;base.erase("plant_world");configure_targets(p,base);
    const auto& cfg=j.at("plant_world");keys(cfg,{"grid","empty_blocks","water_surface","tile","day","sky","imitation","boss_battle","catalog","units"});
    auto& w=p.battle;w.runtime.tile=cfg.value("tile",48.);w.runtime.plk=w.runtime.tile/10000.;
    for(const auto& r:cfg.at("grid")){std::vector<TileRef> row;for(const auto& c:r)row.push_back(tile(c));w.terrain.grid.push_back(std::move(row));}
    w.terrain.empty_blocks=cfg.at("empty_blocks").get<std::vector<std::string>>();w.terrain.water_surface=cfg.at("water_surface");
    w.placement={cfg.value("imitation",std::string{}),cfg.value("day",std::string{}),cfg.value("sky",std::string{}),cfg.value("boss_battle",false)};
    const auto& catalog=cfg.at("catalog");keys(catalog,{"plants","lobbers","night_plants","lottery_zombies"});
    w.plant_catalog={catalog.at("plants").get<std::vector<std::string>>(),catalog.at("lobbers").get<std::vector<std::string>>(),catalog.at("night_plants").get<std::vector<std::string>>(),catalog.at("lottery_zombies").get<std::vector<std::string>>()};
    const auto fields=cfg.value("units",J::array());for(size_t i=0;i<fields.size();++i){keys(fields[i],{"牛顿","__pvz_sb_chili_zombie_row_hint"});read(fields[i],"牛顿",p.units.at(i)->body.gravity);read(fields[i],"__pvz_sb_chili_zombie_row_hint",p.units.at(i)->patch.chili_row_hint);}
}
J run_plants(const J& j) {PlantProbe p(j.value("seed",int64_t(1)));configure_plants(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_PLANT_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: plants72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);if(!input||!output)throw std::runtime_error("plant fixture files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_plants(J::parse(line)).dump()<<'\n';if(!output)throw std::runtime_error("plant result write");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
