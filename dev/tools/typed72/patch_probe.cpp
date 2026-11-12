// Isolated AST/original-bytecode differential boundary, not a game entry.
#define PVZ72_TARGET_PROBE_EMBEDDED
#include "targets_probe.cpp"
#include "sim/typed/damage_patch.h"
namespace {
struct PatchProbe : TargetProbe,DamagePatchEffects {
    DamagePatch patch;
    J effect_calls=J::array();
    std::string fail_effect,mutate_kind;
    bool effect_result=true;
    explicit PatchProbe(int64_t seed,bool adjust):TargetProbe(seed,adjust),patch(visual,world,*this){patch.bind(damage);}
    int64_t zombie_index(const ZombieRef& u)override {
        const auto i=std::find(battle.targets->begin(),battle.targets->end(),CombatTarget::zombie(u));
        if(i==battle.targets->end())throw std::out_of_range("missing raw target index");return i-battle.targets->begin();
    }
    bool plant_zombie_deaths(const DeathTarget& t)override {
        if(const auto* u=std::get_if<ZombieRef>(&t))return patch.trigger_deaths(*u);
        const auto n=std::get<int64_t>(t);if(n<0||uint64_t(n)>=battle.targets->size()||battle.targets->at(size_t(n)).is_hero())return false;
        return patch.trigger_deaths(battle.targets->at(size_t(n)).unit);
    }
    HitResult ordinary(const ZombieRef& u,double f,double a)override{raw_calls.push_back(J::array({"ordinary",index(u),f,a}));return patch.ordinary(u,f,a);}
    HitResult surface(const ZombieRef& u,double f,double a)override{raw_calls.push_back(J::array({"surface",index(u),f,a}));return patch.surface(u,f,a);}
    HitResult ash(const ZombieRef& u)override{raw_calls.push_back(J::array({"ash",index(u)}));return patch.ash(u);}
    void armor_broken(const ZombieRef& u,ArmorSlot s,const std::string& k,double m)override{TargetProbe::armor_broken(u,s,k,m);}
    bool effect(const char* name,const ZombieRef& u,std::optional<bool> flag={}) {
        J call=J::array({name,index(u)});if(flag)call.push_back(*flag);effect_calls.push_back(std::move(call));
        if(!mutate_kind.empty())u->patch.plant_name.set(mutate_kind);
        if(fail_effect==name)throw std::runtime_error("injected effect failure");return effect_result;
    }
    void chili_row_hint(const ZombieRef& u,bool force)override{effect("hint",u,force);}
    bool chili_fire_row(const ZombieRef& u,bool friendly)override{return effect("chili",u,friendly);}
    bool doom_explosion(const ZombieRef& u)override{return effect("doom",u);}
    bool grave_remnant(const ZombieRef& u)override{return effect("remnant",u);}
    bool gravebuster_plant(const ZombieRef& u)override{return effect("plant",u);}
    NativeDamageOrigin origin(const J& j) {
        keys(j,{"entity","current","other","charm_bite","horizontal_chili"});NativeDamageOrigin o;
        if(j.contains("entity")&&!j["entity"].is_null()) {
            const auto& e=j["entity"];keys(e,{"enemy_squash","blue","tracking"});
            o.entity=NativeDamageOrigin::EntityContact{e.value("enemy_squash",false),e.value("blue",false),e.value("tracking",false)};
        }
        if(j.contains("current"))o.current_charmed=units.at(j["current"].get<size_t>());
        if(j.contains("other"))o.other=units.at(j["other"].get<size_t>());
        o.charm_bite_site=j.value("charm_bite",false);o.native_horizontal_chili=j.value("horizontal_chili",false);return o;
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="direct_hit") {
            keys(op,{"op","unit","kind","facing","amount","origin"});const auto& u=units.at(op.at("unit").get<size_t>());
            const auto o=origin(op.value("origin",J::object()));const std::string kind=op.at("kind");HitResult hit;
            if(kind=="ordinary")hit=patch.ordinary_from(u,op.value("facing",1.),op.at("amount"),o);
            else if(kind=="surface")hit=patch.surface_from(u,op.value("facing",1.),op.at("amount"),o);
            else if(kind=="ash")hit=patch.ash_from(u,o);else throw std::invalid_argument("unknown patch hit");
            result=hit.kind==HitResult::Kind::none?J(nullptr):hit.kind==HitResult::Kind::boolean?J(hit.value!=0.):J(hit.value);
        }else if(action=="death_trigger") {
            keys(op,{"op","unit"});result=patch.trigger_deaths(units.at(op.at("unit").get<size_t>()));
        }else if(action=="knockback") {
            keys(op,{"op","unit","amount"});patch.knockback(units.at(op.at("unit").get<size_t>()),op.at("amount"));
        }else if(action=="max_hp") {
            keys(op,{"op","unit","hp"});auto& u=*units.at(op.at("unit").get<size_t>());u.body.hp=op.at("hp");DamagePatch::remember_max_hp(u);
        }else return TargetProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        TargetProbe::extra_snapshot(row);row["patch_units"]=J::array();
        for(const auto& u:units) {
            J j=J::object();write(j,"植物僵尸",u->patch.plant_zombie);write(j,"植物僵尸名",u->patch.plant_name);
            write(j,"__pvz_sb_chili_zombie_exploded",u->patch.chili_exploded);write(j,"__pvz_sb_doom_zombie_exploded",u->patch.doom_exploded);
            write(j,"__pvz_sb_gravebuster_zombie_done",u->patch.gravebuster_done);write(j,"__pvz_sb_zombie_observed_max_hp",u->patch.observed_max_hp);
            write(j,"__pvz_sb_plant_zombie_max_hp",u->patch.plant_max_hp);row["patch_units"].push_back(std::move(j));
        }
        const auto& c=patch.counters;row["patch_counters"]={{"charm_bite",c.charm_bite},{"blue_damage",c.blue_damage},{"blue_surface",c.blue_surface},
            {"squash_skipped",c.squash_skipped},{"chili_skipped",c.chili_skipped},{"pumpkin_sound",c.pumpkin_sound}};
        row["effect_calls"]=effect_calls;
    }
};
J run_patch(const J& j) {
    J base=j;const auto cfg=base.at("patch");base.erase("patch");
    keys(cfg,{"units","fail_effect","mutate_kind","effect_result"});
    PatchProbe p(j.value("seed",int64_t(1)),j.value("damage",J::object()).value("adjust",true));configure_targets(p,base);p.patch.bosses=p.bosses;
    p.fail_effect=cfg.value("fail_effect",std::string{});p.mutate_kind=cfg.value("mutate_kind",std::string{});p.effect_result=cfg.value("effect_result",true);
    if(cfg.at("units").size()!=p.units.size())throw std::invalid_argument("patch fixture unit count");
    for(size_t i=0;i<p.units.size();++i) {
        const auto& s=cfg["units"][i];auto& u=*p.units[i];
        keys(s,{"植物僵尸","植物僵尸名","__pvz_sb_chili_zombie_exploded","__pvz_sb_doom_zombie_exploded","__pvz_sb_gravebuster_zombie_done",
            "__pvz_sb_zombie_observed_max_hp","__pvz_sb_plant_zombie_max_hp","植物僵尸抗击退","大小","狂暴","撑杆","跳舞","入水"});
        read(s,"植物僵尸",u.patch.plant_zombie);read(s,"植物僵尸名",u.patch.plant_name);read(s,"__pvz_sb_chili_zombie_exploded",u.patch.chili_exploded);
        read(s,"__pvz_sb_doom_zombie_exploded",u.patch.doom_exploded);read(s,"__pvz_sb_gravebuster_zombie_done",u.patch.gravebuster_done);
        read(s,"__pvz_sb_zombie_observed_max_hp",u.patch.observed_max_hp);read(s,"__pvz_sb_plant_zombie_max_hp",u.patch.plant_max_hp);
        if(s.contains("植物僵尸抗击退")&&s["植物僵尸抗击退"].is_boolean()){u.patch.knockback_is_boolean=true;u.patch.knockback.set(s["植物僵尸抗击退"].get<bool>()?1.:0.);}
        else read(s,"植物僵尸抗击退",u.patch.knockback);
        read(s,"大小",u.body.size);read(s,"狂暴",u.body.berserk);read(s,"撑杆",u.body.pole_vault);read(s,"跳舞",u.body.dancing);read(s,"入水",u.body.in_water);
    }
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: patch72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open patch fixture files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_patch(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write patch results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
