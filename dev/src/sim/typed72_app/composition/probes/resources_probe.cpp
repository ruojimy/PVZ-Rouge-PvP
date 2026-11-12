#define PVZ72_WORLD_RULES_PROBE_EMBEDDED
#include "world_rules_probe.cpp"
#include "sim/typed/resources.h"
#include "sim/typed/path_tracking.h"
#include "sim/typed/hero_recovery.h"
#include "sim/typed/economy.h"

namespace {
struct ResourcesProbe:WorldRulesProbe {
    WorldRegionState world_region;
    WorldRegions regions{battle,world_region,*this};
    uint64_t resource_ids=0;
    Resources resources{battle,regions,resource_ids};
    NativePathRules path_rules;
    PathTracking paths{battle,navigation,path_rules};
    bool observe_paths=false;
    HeroRecovery recovery{battle,resources,sight};
    HeroRecoveryRules recovery_rules;
    std::vector<Seat> present;
    bool observe_recovery=false;
    EconomyState economy_state;
    EconomyRules economy_rules;
    Economy economy{battle,world_region,resources,economy_state,sight,path_rules.producers};
    std::vector<std::shared_ptr<NativeSun>> sun_records;
    bool observe_economy=false;
    explicit ResourcesProbe(int64_t seed,double width,double splash):WorldRulesProbe(seed,width,splash){}
    static NativeSun sun(const J& j){return {j.at(0),motion(j.at(1)),j.at(2),j.at(3),{},{}};}
    static J sun_json(const NativeSun& s){return J::array({s.age,as_json(s.motion),s.animation,s.size});}
    bool extra_operation(const J& op,J& result)override{
        const auto name=op.at("op").get<std::string>();
        if(name=="economy_setup"){
            observe_economy=true;present.clear();
            for(const auto& side:op.at("present"))present.push_back(parse_seat(side.get<std::string>()));
            path_rules.producers=op.at("producers").get<std::vector<std::string>>();
            economy_rules={op.at("day_interval"),op.at("day_amount"),op.at("sky_amount"),op.at("lifetime")};
            economy_state.previous_tick=op.at("previous_tick");economy_state.sky_progress=op.at("progress");
            economy_state.sky_interval=op.at("interval");economy_state.subsidy=op.at("subsidy");
            economy_state.subsidy_phase=op.at("subsidy_phase");economy_state.night=op.at("night");
            battle.world_height.set(op.at("height"));
        }else if(name=="economy_state"){
            if(op.contains("night"))economy_state.night=op.at("night");
            if(op.contains("subsidy"))economy_state.subsidy=op.at("subsidy");
        }else if(name=="producer_card"){
            auto& policy=battle.protection.cards[op.at("id").get<std::string>()];const auto& v=op.at("fields");
            policy.producer=v.value("producer",false);read(v,"period",policy.period);read(v,"yield_amount",policy.yield_amount);
            read(v,"mature_at",policy.mature_at);read(v,"mature_hp",policy.mature_hp);read(v,"mature_yield",policy.mature_yield);
        }else if(name=="producer_fields"){
            auto& p=*plant_ref(op.at("plant").get<size_t>());const auto& f=op.at("fields");
            read(f,"植物血",p.hp);read(f,"爆了",p.burst);read(f,"_pvp_sun_due",p.sun_due);
            read(f,"_pvp_rest_hp",p.rest_hp);read(f,"_pvp_rest_since",p.rest_since);read(f,"_pvp_aura_factor",p.aura_factor);
        }else if(name=="production_step"){
            economy.plant_production({op.at("quiet"),op.at("ramp"),op.at("bonus"),op.at("multiplier"),op.at("deathmatch")});
        }else if(name=="grave_economy"){
            auto& u=*units.at(op.at("unit").get<size_t>());const auto& f=op.at("fields");
            read(f,"_pvp_max_hp",u.max_hp);read(f,"_pvp_born",u.born);read(f,"_pvp_mature",u.mature);read(f,"_pvp_produced",u.produced);
            if(f.contains("_pvp_seat"))u.source.seat=parse_seat(f.at("_pvp_seat").get<std::string>());
            if(f.contains("_pvp_grave"))u.protection.grave=f.at("_pvp_grave");
            if(f.contains("_pvp_orphan_barrel"))u.orphan_barrel=f.at("_pvp_orphan_barrel");
            if(f.contains("血量"))u.body.hp=f.at("血量");
            read(f,"_pvp_card",u.protection.card);
        }else if(name=="economy_native"){
            if(op.contains("unit"))battle.native_objects.set(op.at("id"),units.at(op.at("unit").get<size_t>()));
            else battle.native_objects.erase(op.at("id"));
        }else if(name=="producer_seat")plant_ref(op.at("plant").get<size_t>())->source.seat=parse_seat(op.at("side").get<std::string>());
        else if(name=="grave_progress")economy_state.grave_progress[op.at("id").get<std::string>()]=op.at("value");
        else if(name=="sun_add"){
            auto s=std::make_shared<NativeSun>(sun(op.at("value")));
            if(op.contains("seat"))s->producer=parse_seat(op.at("seat").get<std::string>());
            if(op.contains("bloom"))s->bloom_amount=op.at("bloom").get<double>();
            world_region.loose_suns.push_back(s);sun_records.push_back(std::move(s));
        }else if(name=="sun_alias")world_region.loose_suns.push_back(sun_records.at(op.at("index").get<size_t>()));
        else if(name=="death_point")economy_state.death_points.push_back({op.at("point").at(0),op.at("point").at(1)});
        else if(name=="economy_step")economy.advance(present,op.at("elapsed"),economy_rules);
        else if(name=="recovery_setup"){
            observe_recovery=true;present.clear();
            for(const auto& side:op.at("present"))present.push_back(parse_seat(side.get<std::string>()));
            sight.water=op.at("water").get<std::vector<std::vector<uint8_t>>>();
            recovery_rules={op.at("delay"),op.at("interval"),op.at("amount"),op.at("deathmatch")};
            for(const auto& [side,values]:op.at("cooldowns").items()){
                auto& cooldowns=world.players.at(seat_index(parse_seat(side))).value().cooldowns;cooldowns.clear();
                for(const auto& [key,ready]:values.items())cooldowns.emplace_back(key,ready.get<double>());
            }
        }else if(name=="recovery_status")read_hero(op.at("fields"),world.hero(parse_seat(op.at("side").get<std::string>())));
        else if(name=="hero_recover")recovery.advance(present,op.at("elapsed"),recovery_rules);
        else if(name=="path_setup"){
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
        if(observe_economy){
            J points=J::array(),suns=J::array(),metadata=J::array(),grave_fields=J::array(),rng=J::array();
            const auto state=battle.room_rng.state();for(const auto word:state.mt)rng.push_back(word);rng.push_back(state.mti);
            for(const auto p:economy_state.death_points)points.push_back({p.x,p.y});
            for(const auto& s:world_region.loose_suns)suns.push_back(sun_json(*s));
            for(const auto& s:sun_records)metadata.push_back({s->producer?J(seat_name(*s->producer)):J(nullptr),s->bloom_amount?J(*s->bloom_amount):J(nullptr)});
            for(const auto& u:units){J f=J::object();write(f,"_pvp_max_hp",u->max_hp);write(f,"_pvp_born",u->born);write(f,"_pvp_mature",u->mature);write(f,"_pvp_produced",u->produced);grave_fields.push_back(std::move(f));}
            row["economy"]={{"previous_tick",economy_state.previous_tick},{"sky_progress",economy_state.sky_progress},{"subsidy_phase",economy_state.subsidy_phase},
                {"death_points",points},{"loose_suns",suns},{"sun_metadata",metadata},{"grave_progress",economy_state.grave_progress},{"grave_fields",grave_fields},{"rng",rng}};
        }
        if(observe_recovery){
            auto& cooldowns=row["cooldowns"]=J::object();
            for(size_t i=0;i<world.players.size();++i)if(world.players[i]){
                J fields=J::object();for(const auto& [key,ready]:world.players[i]->cooldowns)fields[key]=ready;
                cooldowns[seat_name(Seat(i))]=std::move(fields);
            }
        }
        if(observe_paths){
            auto& value=row["paths"]=J::object();
            value["fields"]=J::array();
            for(const auto& f:navigation.flood){
                J grid=J::array(),queue=J::array();const auto cols=battle.terrain.cols();
                for(int y=0;y<battle.terrain.rows();++y){J r=J::array();for(int x=0;x<cols;++x)r.push_back(f.field->at(size_t(y)*cols+x));grid.push_back(std::move(r));}
                for(const auto c:*f.queue)queue.push_back({c.y,c.x});
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
#ifndef PVZ72_RESOURCES_PROBE_EMBEDDED
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("usage: resources72_probe inputs output");
        std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("resource fixture streams");
        std::string line;while(std::getline(in,line))if(!line.empty())out<<run_resources(J::parse(line)).dump()<<'\n';
        return out?0:2;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
