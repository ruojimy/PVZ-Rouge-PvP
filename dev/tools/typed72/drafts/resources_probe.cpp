#define PVZ72_WORLD_RULES_PROBE_EMBEDDED
#include "world_rules_probe.cpp"
#include "sim/typed/resources.h"
#include "sim/typed/path_tracking.h"

namespace {
struct ResourcesProbe:WorldRulesProbe {
    WorldRegionState world_region;
    WorldRegions regions{battle,world_region,*this};
    uint64_t resource_ids=0;
    Resources resources{battle,regions,resource_ids};
    NativePathRules path_rules;
    PathTracking paths{battle,navigation,path_rules};
    bool observe_paths=false;
    explicit ResourcesProbe(int64_t seed,double width,double splash):WorldRulesProbe(seed,width,splash){}
    static NativeSun sun(const J& j){return {j.at(0),motion(j.at(1)),j.at(2),j.at(3),{},{}};}
    static J sun_json(const NativeSun& s){return J::array({s.age,as_json(s.motion),s.animation,s.size});}
    bool extra_operation(const J& op,J& result)override{
        const auto name=op.at("op").get<std::string>();
        if(name=="path_setup"){
            observe_paths=true;
            path_rules.targets=op.at("targets").get<std::vector<std::string>>();
            path_rules.producers=op.at("producers").get<std::vector<std::string>>();
            navigation.hold_plant=op.at("hold");navigation.running=op.at("running");navigation.output_plants=op.at("output");
            const auto p=op.at("point");paths.initialize({p.at(0),p.at(1)});
        }else if(name=="path_step"){
            const auto p=op.at("point");paths.advance({p.at(0),p.at(1)},op.at("follow").get<bool>()?PathMode::follow_hero:PathMode::attack_plants);
        }else if(name=="path_goal")navigation.target_position=cell(op.at("cell"));
        else if(name=="resources_setup"){
            resource_ids=op.value("sequence",uint64_t(0));resources.coins=op.value("coins",0.);
            for(const auto& [seat,values]:op.at("accounts").items()){
                auto& a=resources.accounts.at(seat_index(parse_seat(seat)));
                a.balance=values.at(0);a.earned=values.at(1);
                if(values.size()>2)a.coins.set(values.at(2));
            }
            world_region.water_wave=op.value("wave",0.);
        }else if(name=="resource"){
            const auto p=op.at("point");
            result=resources.create(parse_seat(op.at("side").get<std::string>()),op.at("amount"),{p.at(0),p.at(1)},op.at("source"));
        }else if(name=="coin"){
            const auto p=op.at("point");result=resources.drop_coin(op.at("amount"),{p.at(0),p.at(1)},op.value("kind",std::string("coin")));
        }else if(name=="resource_fields"){
            auto& r=*resources.find(op.at("id").get<std::string>());
            read(op,"shared",r.shared);read(op,"coin",r.coin);
            if(op.contains("born"))r.born=op.at("born");
            if(op.contains("sun"))resources.set_motion(r.id,sun(op.at("sun")));
        }else if(name=="collect"){
            std::optional<Seat> seat;if(op.contains("seat"))seat=parse_seat(op.at("seat").get<std::string>());
            resources.collect(op.at("id"),seat);
        }else if(name=="resource_expire")resources.expire(op.at("id"));
        else if(name=="resource_remove_motion")resources.remove_motion(op.at("id"));
        else if(name=="sun_advance")resources.advance_suns();
        else if(name=="suns_merge")resources.merge_suns();
        else if(name=="resource_settle")resources.settle(op.at("lifetime"));
        else if(name=="resource_auto")result=resources.auto_shared_sky(op.at("id"));
        else if(name=="important")important(cell(op.at("cell")),op.at("block"));
        else if(name=="world_water")regions.water_animation();
        else if(name=="world_important")regions.important_blocks();
        else if(name=="world_ice")regions.ice_clock();
        else return WorldRulesProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override{
        WorldRulesProbe::extra_snapshot(row);row["resource_ids"]=resource_ids;row["coins"]=resources.coins;
        if(observe_paths){
            auto& value=row["paths"]=J::object();
            value["fields"]=J::array();
            for(const auto& f:navigation.flood){
                J grid=J::array(),queue=J::array();const auto cols=battle.terrain.cols();
                for(int y=0;y<battle.terrain.rows();++y){J r=J::array();for(int x=0;x<cols;++x)r.push_back(f.field.at(size_t(y)*cols+x));grid.push_back(std::move(r));}
                for(const auto c:f.queue)queue.push_back({c.y,c.x});
                value["fields"].push_back({f.cooldown,f.sign,grid,queue});
            }
            value["target"]=navigation.target_plant;value["goal"]={navigation.target_position.y,navigation.target_position.x};
            value["hold"]=navigation.hold_plant;value["running"]=navigation.running;value["output"]=navigation.output_plants;
        }
        row["world_region"]=J::array({world_region.water_wave,world_region.water_offset,world_region.landing});
        auto& records=row["resources"]=J::array();
        for(const auto& r:resources.records()){
            J item={{"id",r.id},{"side",seat_name(r.side)},{"amount",r.amount},{"born",r.born},{"x",r.position.x},{"y",r.position.y},{"source",r.source}};
            write(item,"shared",r.shared);write(item,"coin",r.coin);records.push_back(std::move(item));
        }
        auto& suns=row["sun_motions"]=J::array();
        for(const auto& s:resources.motions())suns.push_back({s.id,sun_json(s.sun)});
        auto& accounts=row["resource_accounts"]=J::object();
        for(size_t i=0;i<world.players.size();++i)if(world.players[i]){
            const auto& a=resources.accounts[i];
            J item={{"balance",a.balance},{"earned",a.earned}};write(item,"coins",a.coins);accounts[seat_name(Seat(i))]=std::move(item);
        }
    }
};
J run_resources(const J& j){
    J base=j;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ResourcesProbe p(j.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));configure_shooting(p,base);
    p.battle.world_width.set(cfg.at("width"));p.battle.dense_planting=cfg.at("dense");
    p.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){p.battle.protection.secrets.team.set(size_t(DamageSecret::rage));p.battle.protection.secrets.enabled=true;}
    p.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();p.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    p.rules.homing_height=cfg.at("heights").get<decltype(p.rules.homing_height)>();p.collision.unit_scale=cfg.at("scale").get<decltype(p.collision.unit_scale)>();
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("usage: resources72_probe inputs output");
        std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("resource fixture streams");
        std::string line;while(std::getline(in,line))if(!line.empty())out<<run_resources(J::parse(line)).dump()<<'\n';
        return out?0:2;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
