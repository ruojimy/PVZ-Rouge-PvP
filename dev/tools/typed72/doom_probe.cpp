#define PVZ72_PLANT_PROBE_EMBEDDED
#include "plants_probe.cpp"
#include "sim/typed/doom_effects.h"
namespace {
void read_death(const J& j,const char* k,Field<DeathMarker>& f) {
    if(!j.contains(k))return;const auto& v=j[k];if(v.is_null())f.set_null();else if(v.is_boolean())f.set(DeathMarker(v.get<bool>()));else f.set(DeathMarker(v.get<double>()));
}
struct DoomProbe : PlantProbe,DoomServices {
    DoomEffects doom;
    std::optional<TargetRoster> extras=TargetRoster{};
    std::vector<EntityRef> births;
    explicit DoomProbe(int64_t seed):PlantProbe(seed),doom(battle,damage,*this,*this,collision){}
    void add_entity(std::string name,double facing,Motion pos)override {
        calls.push_back(J::array({"add",name,facing,as_json(pos)}));before("add");visual.spawn(std::move(name),facing,pos);
        births.push_back(visual.entities.list()->back());after("add");
    }
    void destroy_block(Cell c)override {
        calls.push_back(J::array({"destroy",c.y,c.x}));before("destroy");destroy_pvp_block(battle,*this,c);after("destroy");
    }
    std::optional<TargetRoster> extra_targets()override {
        if(extras){calls.push_back(J::array({"extras"}));before("extras");after("extras");}return extras;
    }
    HitResult ash(const ZombieRef& unit)override {
        const auto result=TargetProbe::ash(unit);after("ash");return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="doom"||action=="doom_targets") {
            keys(op,{"op","unit","point","scale","catch","throw_raw"});const auto& u=units.at(op.at("unit").get<size_t>());throw_raw=op.value("throw_raw",false);
            try{if(action=="doom")result=doom.explode(u);else{const auto& p=op.at("point");result=doom.ash_targets(u,{p.at(0),p.at(1)},op.value("scale",visual.tile));}}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}throw_raw=false;
        }else if(action=="doom_visuals"||action=="doom_blocks"||action=="doom_knock") {
            keys(op,{"op","point","scale"});const auto& p=op.at("point");const Point point{p.at(0),p.at(1)};const double scale=op.value("scale",visual.tile);
            if(action=="doom_visuals")doom.visuals(point,scale);else if(action=="doom_blocks")result=doom.destroy_blocks(point,scale);else doom.knock_player(point,scale);
        }else if(action=="kill_plant") {
            keys(op,{"op","plant"});doom.kill_plant(plant_ref(op.at("plant").get<size_t>()));
        }else if(action=="effect_roster_replace") {
            keys(op,{"op","births"});auto roster=std::make_shared<EntityRoster>();for(const auto& n:op.at("births"))roster->push_back(births.at(n.get<size_t>()));visual.entities.replace(std::move(roster));
        }else if(action=="doom_write_unit") {
            keys(op,{"op","unit","values"});auto& u=*units.at(op.at("unit").get<size_t>());const auto& v=op.at("values");keys(v,{"死","大小","植物僵尸","植物僵尸名","魅惑"});
            read_death(v,"死",u.body.dead);read(v,"大小",u.body.size);read(v,"植物僵尸",u.patch.plant_zombie);read(v,"植物僵尸名",u.patch.plant_name);
            read(v,"魅惑",u.source.charmed);
        }else if(action=="doom_write_proxy") {
            keys(op,{"op","target","values"});auto& p=world.proxy(parse_seat(op.at("target").get<std::string>()));const auto& v=op.at("values");keys(v,{"大小","死"});read(v,"大小",p.size);read_death(v,"死",p.dead);
        }else return PlantProbe::extra_operation(op,result);return true;
    }
    J entity(const EntityRef& e) {
        J j=source_state(e->source,e->motion.get(),e->flight);j["方向"]=e->facing;write(j,"牛顿",e->gravity);write(j,"消亡",e->expires);write(j,"穿墙",e->through_wall);write(j,"旋转",e->rotation);return j;
    }
    void extra_snapshot(J& row)override {
        PlantProbe::extra_snapshot(row);auto& fx=row["doom_state"]=J::object();fx["images"]=visual.other_images;fx["explosions"]=doom.explosions;
        write(fx,"核爆",visual.nuclear_flash);write(fx,"抖屏",visual.screen_shake);row["entities"]=J::array();row["effect_births"]=J::array();
        for(const auto& e:*visual.entities.list())row["entities"].push_back(entity(e));for(const auto& e:births)row["effect_births"].push_back(entity(e));
        row["doom_unit_fields"]=J::array();for(const auto& u:units){J j=J::object();write(j,"大小",u->body.size);death_state(j,"死",u->body.dead);write(j,"植物僵尸",u->patch.plant_zombie);write(j,"植物僵尸名",u->patch.plant_name);row["doom_unit_fields"].push_back(std::move(j));}
        row["doom_proxy_fields"]=J::object();for(size_t i=0;i<world.proxies.size();++i)if(world.proxies[i]){J j=J::object();write(j,"大小",world.proxies[i]->size);death_state(j,"死",world.proxies[i]->dead);row["doom_proxy_fields"][seat_name(Seat(i))]=std::move(j);}
    }
};
void configure_doom(DoomProbe& p,const J& j) {
    J base=j;base.erase("doom_world");configure_plants(p,base);
    const auto& cfg=j.at("doom_world");keys(cfg,{"extras","images"});p.visual.other_images=cfg.value("images",std::vector<std::string>{});
    if(cfg.contains("extras")){if(cfg["extras"].is_null())p.extras.reset();else for(const auto& t:cfg["extras"])p.extras->push_back(p.target(t));}
}
J run_doom(const J& j) {DoomProbe p(j.value("seed",int64_t(1)));configure_doom(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_DOOM_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: doom72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("doom fixture files");std::string line;while(std::getline(in,line))if(!line.empty())out<<run_doom(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("doom output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
