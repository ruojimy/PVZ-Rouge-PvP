#define PVZ72_DEATH_PROBE_EMBEDDED
#include "death_probe.cpp"
#include "sim/typed/lantern_effects.h"
namespace {
struct LanternProbe:DeathProbe,LanternServices {
    LanternEffects lantern;
    explicit LanternProbe(int64_t seed):DeathProbe(seed),lantern(battle,*this,collision){load_native_plant_zombie_heads(collision);}
    void add_entity(std::string n,double f,Motion p)override{ChiliProbe::add_entity(std::move(n),f,p);}
    void fields(CombatZombie& u,const J& v) {
        keys(v,{"血量","灰烬","死","魅惑","方向","位置","大小","植物僵尸","植物僵尸名","植物僵尸鸭子","植物僵尸发射动画","植物僵尸角","射","__pvz_sb_lantern_zombie_cd","__pvz_sb_zombie_observed_max_hp","__pvz_sb_plant_zombie_max_hp"});
        if(v.contains("血量"))u.body.hp=v["血量"];if(v.contains("方向"))u.body.facing=v["方向"];if(v.contains("位置"))u.body.motion=motion(v["位置"]);
        read(v,"灰烬",u.body.ash);read_death(v,"死",u.body.dead);read(v,"魅惑",u.source.charmed);read(v,"大小",u.body.size);
        read(v,"植物僵尸",u.patch.plant_zombie);read(v,"植物僵尸名",u.patch.plant_name);read(v,"植物僵尸鸭子",u.patch.duck);
        read(v,"植物僵尸发射动画",u.patch.fire_animation);read(v,"植物僵尸角",u.patch.aim_angle);read(v,"射",u.patch.shoot);
        read(v,"__pvz_sb_lantern_zombie_cd",u.patch.lantern_cooldown);read(v,"__pvz_sb_zombie_observed_max_hp",u.patch.observed_max_hp);read(v,"__pvz_sb_plant_zombie_max_hp",u.patch.plant_max_hp);
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="lantern_unit") {
            keys(op,{"op","unit","values","erase"});auto& u=*units.at(op.at("unit").get<size_t>());fields(u,op.value("values",J::object()));
            for(const auto& k:op.value("erase",J::array())){if(k=="魅惑")u.source.charmed.erase();else if(k=="灰烬")u.body.ash.erase();else if(k=="死")u.body.dead.erase();else throw std::invalid_argument("lantern unit erase");}
        }else if(action=="lantern_plant") {
            keys(op,{"op","plant","values"});auto& p=*plant_ref(op.at("plant").get<size_t>());const auto& v=op.at("values");
            keys(v,{"植物血","植物血上限","爆了","死","铲死","__pvz_sb_native_lantern_charm_heal_mark"});read(v,"植物血",p.hp);read(v,"植物血上限",p.max_hp);read(v,"爆了",p.burst);
            read_death(v,"死",p.dead);read_death(v,"铲死",p.shovel_dead);read(v,"__pvz_sb_native_lantern_charm_heal_mark",p.lantern_charm_healed);
        }else if(action=="lantern_proxy") {
            keys(op,{"op","target","values"});auto& p=world.proxy(parse_seat(op.at("target").get<std::string>()));const auto& v=op.at("values");
            keys(v,{"__pvz_sb_zombie_observed_max_hp","__pvz_sb_plant_zombie_max_hp"});read(v,"__pvz_sb_zombie_observed_max_hp",p.observed_max_hp);read(v,"__pvz_sb_plant_zombie_max_hp",p.plant_max_hp);
        }else if(action=="lantern_track") {keys(op,{"op"});lantern.track_max_hp();}
        else if(action=="lantern_heal_zombie") {keys(op,{"op","target","amount"});result=lantern.heal_zombie(target(op.at("target")),op.at("amount"));}
        else if(action=="lantern_heal_plant") {keys(op,{"op","plant","amount"});result=lantern.heal_plant(plant_ref(op.at("plant").get<size_t>()),op.at("amount"));}
        else if(action=="lantern_targets") {
            keys(op,{"op","unit","point"});const auto& p=op.at("point");result=lantern.heal_targets(units.at(op.at("unit").get<size_t>()),{p.at(0),p.at(1)});
        }else if(action=="lantern_effects") {
            keys(op,{"op","point","count"});const auto& p=op.at("point");lantern.effects({p.at(0),p.at(1)},op.value("count",int64_t(1)));
        }else if(action=="lantern_range") {
            keys(op,{"op","center","point","tiles"});const auto& c=op.at("center");const auto& p=op.at("point");result=lantern.in_range({c.at(0),c.at(1)},{p.at(0),p.at(1)},op.value("tiles",3.));
        }else if(action=="lantern_update") {
            keys(op,{"op","unit","config","sourced"});const auto u=units.at(op.at("unit").get<size_t>());PlantZombieConfig c=*native_plant_zombie_config("路灯花僵尸");
            const auto v=op.value("config",J::object());keys(v,{"fire_anim","cooldown","missing"});read(v,"fire_anim",c.fire_anim);read(v,"cooldown",c.cooldown);
            for(const auto& k:v.value("missing",J::array())){if(k=="fire_anim")c.fire_anim.erase();else if(k=="cooldown")c.cooldown.erase();else throw std::invalid_argument("lantern config erase");}
            if(op.value("sourced",true))lantern.update(u,c);else lantern.raw_update(u,c);
        }else if(action=="lantern_native") {keys(op,{"op"});lantern.native_charmed_healing();}
        else return DeathProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        DeathProbe::extra_snapshot(row);row["lantern_counts"]=J::array({lantern.zombie_heals,lantern.native_charmed_heals});row["lantern_units"]=J::array();row["lantern_plants"]=J::array();
        for(const auto& u:units){J j=J::object();const auto& p=u->patch;write(j,"植物僵尸发射动画",p.fire_animation);write(j,"植物僵尸角",p.aim_angle);write(j,"射",p.shoot);write(j,"__pvz_sb_lantern_zombie_cd",p.lantern_cooldown);row["lantern_units"].push_back(std::move(j));}
        for(const auto id:battle.plants.order()){J j=J::object();write(j,"__pvz_sb_native_lantern_charm_heal_mark",battle.plants.at(id)->lantern_charm_healed);row["lantern_plants"].push_back(std::move(j));}
    }
};
J run_lantern(const J& j) {
    LanternProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.at("lantern");base.erase("lantern");const auto dc=base.value("death_config",J::object());base.erase("death_config");keys(cfg,{"units"});configure_doom(p,base);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: lantern72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("lantern fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_lantern(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("lantern output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
