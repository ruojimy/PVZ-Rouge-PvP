#define PVZ72_PLANT_PROBE_EMBEDDED
#include "plants_probe.cpp"
#include "sim/typed/plant_zombie_target.h"
namespace {
void aim_death(const J& j,const char* k,Field<DeathMarker>& field) {
    if(!j.contains(k))return;const auto& v=j.at(k);if(v.is_null())field.set_null();else if(v.is_boolean())field.set(DeathMarker(v.get<bool>()));else field.set(DeathMarker(v.get<double>()));
}
void aim_fields(CombatZombie& u,const J& f) {
    keys(f,{"位置","方向","血量","大小","灰烬","死","魅惑","植物僵尸","植物僵尸名","植物僵尸鸭子","植物僵尸发射动画","植物僵尸角"});
    if(f.contains("位置"))u.body.motion=motion(f.at("位置"));if(f.contains("方向"))u.body.facing=f.at("方向");if(f.contains("血量"))u.body.hp=f.at("血量");
    read(f,"大小",u.body.size);read(f,"灰烬",u.body.ash);aim_death(f,"死",u.body.dead);read(f,"魅惑",u.source.charmed);
    read(f,"植物僵尸",u.patch.plant_zombie);read(f,"植物僵尸名",u.patch.plant_name);read(f,"植物僵尸鸭子",u.patch.duck);
    read(f,"植物僵尸发射动画",u.patch.fire_animation);read(f,"植物僵尸角",u.patch.aim_angle);
}
struct AimProbe:PlantProbe {
    PlantZombieTargeting aim;
    std::vector<std::optional<NativeAimTarget>> held_aims;
    explicit AimProbe(int64_t seed):PlantProbe(seed),aim(battle,collision){load_native_plant_zombie_heads(collision);}
    J describe(const std::optional<NativeAimTarget>& a) {
        if(!a)return nullptr;J target=nullptr,kind="player",index=nullptr;
        if(const auto* p=std::get_if<PlantRef>(&a->object)) {
            kind="plant";index=a->index;
            for(size_t i=0;i<battle.plants.order().size();++i)if(plant_ref(i)==*p){target={{"plant",i}};break;}
        }else if(const auto* z=std::get_if<CombatTarget>(&a->object)){kind="zombie";index=a->index;target=label(*z);}
        return J::array({kind,index,target,J::array({a->captured_point.x,a->captured_point.y}),a->direction,a->angle});
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="aim_catalog") {
            keys(op,{"op"});result=J::object();for(const auto& c:native_plant_zombie_catalog()) {
                J f={{"head",c.head}};
#define CONFIG(n) write(f,#n,c.n);
                PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(CONFIG) PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(CONFIG)
#undef CONFIG
                result[c.kind]=std::move(f);
            }
        }else if(action=="aim_write") {
            keys(op,{"op","unit","values","erase"});auto& u=*units.at(op.at("unit").get<size_t>());aim_fields(u,op.value("values",J::object()));
            for(const auto& key:op.value("erase",J::array())){if(key=="魅惑")u.source.charmed.erase();else if(key=="灰烬")u.body.ash.erase();else if(key=="死")u.body.dead.erase();else if(key=="植物僵尸角")u.patch.aim_angle.erase();else throw std::invalid_argument("aim erased field");}
        }else if(action=="aim_plant") {
            keys(op,{"op","plant","values"});auto& p=*plant_ref(op.at("plant").get<size_t>());const auto& f=op.at("values");keys(f,{"坐标","植物血","死","铲死"});
            if(f.contains("坐标"))p.cell=cell(f.at("坐标"));read(f,"植物血",p.hp);aim_death(f,"死",p.dead);aim_death(f,"铲死",p.shovel_dead);
        }else if(action=="aim_head"||action=="aim_pick"||action=="aim_update"||action=="aim_sync") {
            keys(op,{"op","unit","sourced","hold"});const auto u=units.at(op.at("unit").get<size_t>());
            if(action=="aim_head"){const auto p=native_plant_zombie_head_center(*u,visual.tile,collision);result=J::array({p.x,p.y});}
            else if(action=="aim_sync"){const auto p=sync_native_head_angle(*u);result=J::array({p.first,p.second});}
            else {std::optional<NativeAimTarget> target;
                if(action=="aim_pick"){target=aim.pick(u);result=describe(target);}
                else {const auto a=op.value("sourced",true)?aim.update(u):aim.raw_update(u);target=a.target;result=J::array({describe(target),J::array({a.center.x,a.center.y})});}
                if(op.value("hold",false))held_aims.push_back(target);
            }
        }else if(action=="aim_point") {
            keys(op,{"op","held","center"});const auto& a=held_aims.at(op.at("held").get<size_t>());
            if(a){const auto& c=op.at("center");if(const auto p=aim.point(*a,{c.at(0),c.at(1)}))result=J::array({p->x,p->y});}
        }else if(action=="aim_cone") {
            keys(op,{"op","angle","direction","limit"});const double a=op.at("angle"),d=op.at("direction");
            const double limit=op.contains("limit")?(op.at("limit").is_null()?45.:op.at("limit").get<double>()):90.;
            result=J::array({native_direction_angle(d),native_direction_angle_diff(a,d),native_angle_in_direction(a,d,limit)});
        }else return PlantProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        PlantProbe::extra_snapshot(row);row["aim_fields"]=J::array();row["held_aims"]=J::array();
        for(const auto& u:units){J f=J::object();write(f,"大小",u->body.size);write(f,"植物僵尸角",u->patch.aim_angle);death_state(f,"死",u->body.dead);row["aim_fields"].push_back(std::move(f));}
        for(const auto& a:held_aims)row["held_aims"].push_back(describe(a));
    }
};
J run_aim(const J& request) {
    AimProbe probe(request.value("seed",int64_t(1)));J base=request;const auto cfg=base.at("aim");base.erase("aim");keys(cfg,{"units"});configure_plants(probe,base);
    for(size_t i=0;i<cfg.at("units").size();++i)aim_fields(*probe.units.at(i),cfg.at("units")[i]);
    probe.operations(request.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {if(argc!=3)throw std::invalid_argument("usage: aim72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);if(!input||!output)throw std::runtime_error("aim fixture files");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_aim(J::parse(line)).dump()<<'\n';if(!output)throw std::runtime_error("aim results write");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
