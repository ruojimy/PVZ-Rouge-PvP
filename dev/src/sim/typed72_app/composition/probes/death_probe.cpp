#define PVZ72_SOURCED_PROBE_EMBEDDED
#include "sourced_probe.cpp"
#include "sim/typed/death_chain.h"
namespace {
struct DeathProbe:SourcedProbe,DeathServices {
    NativeDeathChain chain;
    explicit DeathProbe(int64_t seed):SourcedProbe(seed),chain(battle,*this,*this,collision){}
    void add_entity(std::string n,double f,Motion p)override{ChiliProbe::add_entity(std::move(n),f,p);}
    void damage_player(double amount)override{ChiliProbe::damage_player(amount);}
    void destroy_block(Cell c)override{DoomProbe::destroy_block(c);}
    std::optional<TargetRoster> extra_targets()override{return DoomProbe::extra_targets();}
    void armor_broken(const ZombieRef& u,ArmorSlot s,const std::string& k,double m)override{TargetProbe::armor_broken(u,s,k,m);}
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="native_write_unit") {
            keys(op,{"op","unit","values"});auto& u=*units.at(op.at("unit").get<size_t>());const auto& v=op.at("values");
            keys(v,{"血量","防具血量","死","灰烬","位置","植物僵尸名","植物僵尸","__pvz_sb_chili_zombie_exploded","__pvz_sb_doom_zombie_exploded","__pvz_sb_gravebuster_zombie_done","__pvz_sb_doom_zombie_life_ticks","__pvz_sb_doom_zombie_life_time"});
            if(v.contains("血量"))u.body.hp=v["血量"];if(v.contains("防具血量"))u.body.armor_hp=v["防具血量"];if(v.contains("位置"))u.body.motion=motion(v["位置"]);
            read_death(v,"死",u.body.dead);read(v,"灰烬",u.body.ash);read(v,"植物僵尸名",u.patch.plant_name);read(v,"植物僵尸",u.patch.plant_zombie);
            read(v,"__pvz_sb_chili_zombie_exploded",u.patch.chili_exploded);read(v,"__pvz_sb_doom_zombie_exploded",u.patch.doom_exploded);read(v,"__pvz_sb_gravebuster_zombie_done",u.patch.gravebuster_done);
            read(v,"__pvz_sb_doom_zombie_life_ticks",u.patch.doom_life_ticks);read(v,"__pvz_sb_doom_zombie_life_time",u.patch.doom_life_time);
        }else if(action.starts_with("native_")) {
            keys(op,{"op","unit","index","target","entity","kind","facing","amount","friendly","now","box","scale","rows","charmed_only","force","catch"});
            try {
                const double scale=op.value("scale",visual.tile);
                if(action=="native_deaths")result=chain.plant_zombie_deaths(op.contains("index")?DeathTarget(op["index"].get<int64_t>()):DeathTarget(units.at(op.at("unit").get<size_t>())));
                else if(action=="native_auto")result=chain.auto_explode(units.at(op.at("unit").get<size_t>()),op.contains("now")&&!op["now"].is_null()?std::optional<double>(op["now"].get<double>()):std::nullopt);
                else if(action=="native_spawn_chili")result=chain.chili_fire_row(units.at(op.at("unit").get<size_t>()),op.value("friendly",false));
                else if(action=="native_doom")result=chain.doom_explosion(units.at(op.at("unit").get<size_t>()));
                else if(action=="native_scan")chain.chili.scan();
                else if(action=="native_hint"||action=="native_hint_cached"){
                    const auto t=action=="native_hint_cached"?CombatTarget::player(parse_seat(op.at("target").get<std::string>())):target(op.at("target"));
                    if(auto r=chain.row_hint(t,op.value("force",false)))result=*r;
                }
                else if(action=="native_player_hit")chain.player_hit(births.at(op.at("entity").get<size_t>()),bounds(op),scale);
                else if(action=="native_enemy")chain.enemy_scan(births.at(op.at("entity").get<size_t>()),bounds(op),scale);
                else if(action=="native_hit_units")chain.hit_zombies(births.at(op.at("entity").get<size_t>()),bounds(op),scale,op.value("charmed_only",false),rows(op));
                else if(action=="native_hit"||action=="native_hit_slot") {
                    const std::string kind=op.at("kind");
                    const auto hit=[&](const CombatTarget& t){
                        if(kind=="ordinary")return chain.damage.ordinary(t,op.value("facing",1.),op.at("amount"));
                        if(kind=="surface")return chain.damage.surface(t,op.value("facing",1.),op.at("amount"));
                        if(kind=="ash")return chain.damage.ash(t);throw std::invalid_argument("unknown native hit");
                    };
                    const auto r=action=="native_hit_slot"?hit(battle.targets->at(op.at("index").get<size_t>())):hit(target(op.at("target")));
                    result=r.kind==HitResult::Kind::none?J(nullptr):r.kind==HitResult::Kind::boolean?J(r.value!=0.):J(r.value);
                }else throw std::invalid_argument("unknown death chain operation");
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return SourcedProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        SourcedProbe::extra_snapshot(row);row["doom_state"]["explosions"]=chain.doom.explosions;row["grave_counts"]=J::array({chain.graves.graves_created,chain.graves.plants_created});
        const auto& c=chain.chili.counters;row["chili_counts"]=J::array({c.patched,c.explosions,c.unit_damage,c.charmed_damage,c.plant_damage,c.player_damage,c.player_launch,c.launch_block,c.launch_timeout});
        row["packets"]=J::array();row["death_units"]=J::array();
        for(const auto& u:units){row["packets"].push_back(chain.damage.has_packet(u));J v=J::object();auto& p=u->patch;
            write(v,"__pvz_sb_chili_zombie_exploded",p.chili_exploded);write(v,"__pvz_sb_doom_zombie_exploded",p.doom_exploded);write(v,"__pvz_sb_gravebuster_zombie_done",p.gravebuster_done);
            write(v,"__pvz_sb_doom_zombie_life_ticks",p.doom_life_ticks);write(v,"__pvz_sb_doom_zombie_life_time",p.doom_life_time);write(v,"__pvz_sb_zombie_observed_max_hp",p.observed_max_hp);write(v,"__pvz_sb_plant_zombie_max_hp",p.plant_max_hp);row["death_units"].push_back(std::move(v));}
        const auto& p=chain.patch.counters;row["patch_counters"]={{"charm_bite",p.charm_bite},{"blue_damage",p.blue_damage},{"blue_surface",p.blue_surface},{"squash_skipped",p.squash_skipped},{"chili_skipped",p.chili_skipped},{"pumpkin_sound",p.pumpkin_sound}};
    }
};
J run_death(const J& j){DeathProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.value("death_config",J::object());base.erase("death_config");keys(cfg,{"fast"});configure_doom(p,base);p.chain.sourced_fastpath=cfg.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_DEATH_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: death72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("death fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_death(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("death output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
