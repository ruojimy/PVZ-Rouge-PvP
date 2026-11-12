#define PVZ72_SEAT_PATHS_PROBE_EMBEDDED
#include "seat_paths_probe.cpp"
#include "sim/typed/content_queries.h"
#include "sim/typed/sweet_taunts.h"

namespace {
struct ContentQueriesProbe : SeatPathsProbe {
    std::unique_ptr<SweetTaunts> taunts;
    std::unique_ptr<ContentQueries> queries;
    ContentTargets query_points;
    bool observe_content=false;
    explicit ContentQueriesProbe(int64_t seed,double width,double splash)
        :SeatPathsProbe(seed,width,splash),query_points(battle,damage,collision,width){}
    J content_label(const ContentTarget& target)const {
        if(const auto* plant=std::get_if<PlantRef>(&target)) {
            const auto found=std::find(all_plants.begin(),all_plants.end(),*plant);
            if(found==all_plants.end())throw std::logic_error("unregistered fixture plant");
            return J{{"plant",size_t(found-all_plants.begin())}};
        }
        return label(std::get<CombatTarget>(target));
    }
    J content_label(const std::optional<ContentTarget>& target)const {
        return target?content_label(*target):J(nullptr);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="content_queries_setup") {
            observe_content=true;
            taunts=std::make_unique<SweetTaunts>(battle,navigation,banks,path_rules,op.at("resist"));
            queries=std::make_unique<ContentQueries>(battle,query_points,*taunts);
        }else if(name=="content_unit_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());
            const auto& f=op.at("fields");
            read(f,"_pvp_content",unit.source.content);read(f,"_pvp_owner",unit.source.owner);
            read(f,"_pvp_id",unit.source.id);read(f,"魅惑",unit.source.charmed);
            read(f,"_pvp_no_hero_attack",unit.source.no_hero_attack);
            read_point(f,"_pvp_head_point",unit.head_point);
            if(f.contains("血量"))unit.body.hp=f.at("血量");
            if(f.contains("位置"))unit.body.motion=motion(f.at("位置"));
            if(f.contains("_pvp_grave"))unit.protection.grave=f.at("_pvp_grave");
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="魅惑")unit.source.charmed.erase();
                else if(key=="_pvp_content")unit.source.content.erase();
                else throw std::invalid_argument("unknown unit erase");
            }
        }else if(name=="content_plant_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());
            const auto& f=op.at("fields");
            read(f,"_pvp_content",plant.source.content);read(f,"_pvp_owner",plant.source.owner);
            read(f,"_pvp_id",plant.source.id);read(f,"植物血",plant.hp);read(f,"睡觉",plant.sleep);
            if(f.contains("死")) {
                if(f.at("死").is_null())plant.dead.set_null();
                else plant.dead.set(DeathMarker(f.at("死").get<double>()));
            }
            if(f.contains("坐标"))plant.cell=cell(f.at("坐标"));
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="死")plant.dead.erase();else if(key=="睡觉")plant.sleep.erase();
                else throw std::invalid_argument("unknown plant erase");
            }
        }else if(name=="content_enemies") {
            const auto source=content_target(op.at("source"));
            result=J::array();
            for(const auto& target:queries->enemies(queries->source(source)))result.push_back(content_label(target));
        }else if(name=="content_nearest")result=content_label(queries->nearest(content_target(op.at("source"))));
        else if(name=="content_route") {
            const auto source=content_target(op.at("source"));
            std::optional<ContentTarget> goal;
            if(!op.at("goal").is_null())goal=content_target(op.at("goal"));
            std::vector<ContentTarget> candidates;
            for(const auto& target:op.at("candidates"))candidates.push_back(content_target(target));
            result=content_label(queries->route(source,goal,candidates));
        }else if(name=="taunt_update")taunts->update();
        else if(name=="taunt_dirty")taunts->mark_dirty();
        else if(name=="taunt_find") {
            const auto plant=taunts->taunting(content_target(op.at("source")));
            result=plant?content_label(ContentTarget(plant)):J(nullptr);
        }else if(name=="taunt_apply")taunts->apply(units.at(op.at("unit").get<size_t>()));
        else if(name=="taunt_restore")taunts->restore();
        else return SeatPathsProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        SeatPathsProbe::extra_snapshot(row);
        if(!observe_content)return;
        identities.clear();
        J state={{"current",path_json(banks.capture())}};
        state["fields"]=J::array();
        for(const auto& [id,path]:taunts->fields())state["fields"].push_back({id?J(*id):J(nullptr),path_json(path)});
        state["baseline"]=taunts->baseline()?path_json(*taunts->baseline()):J(nullptr);
        state["saved"]=taunts->saved()?chase_json(*taunts->saved()):J(nullptr);
        state["cached"]=J::array();
        for(const auto& plant:taunts->cached())state["cached"].push_back(content_label(ContentTarget(plant)));
        state["hidden"]=taunts->hidden_count();
        state["units"]=J::array();
        for(const auto& unit:units) {
            J fields=J::object();
            write(fields,"_pvp_taunted_by",unit->taunted_by);
            write(fields,"_pvp_content",unit->source.content);
            write(fields,"_pvp_no_hero_attack",unit->source.no_hero_attack);
            state["units"].push_back(std::move(fields));
        }
        row["content_queries"]=std::move(state);
    }
};
J run_content_queries(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ContentQueriesProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);
    probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;
    }
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: content_queries72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("content query fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_content_queries(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
