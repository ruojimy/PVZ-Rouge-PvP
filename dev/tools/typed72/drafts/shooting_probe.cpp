#define PVZ72_PEA_PROBE_EMBEDDED
#include "pea_probe.cpp"
#include "sim/typed/plant_zombie_shooting.h"
namespace {
#define SHOOT_FIELDS(X) X(shooting_cooldown,"植物僵尸射cd") X(burst_left,"植物僵尸连发") X(burst_cooldown,"植物僵尸连发cd") X(jump_assist_cooldown,"__pvz_sb_plant_zombie_jump_cd") X(blover_cooldown,"__pvz_sb_blover_zombie_cd") X(blover_wind_tick,"__pvz_sb_blover_zombie_wind_tick") X(lantern_cooldown,"__pvz_sb_lantern_zombie_cd") X(fume_cooldown,"__pvz_sb_fumeshroom_zombie_cd") X(fume_attack_angle,"__pvz_sb_fumeshroom_zombie_attack_angle") X(fume_damage_done,"__pvz_sb_fumeshroom_zombie_damage_done") X(fume_bubble_tick,"__pvz_sb_fumeshroom_zombie_bubble_tick")
struct ShootingProbe:PeaProbe,WindServices,LanternServices,FumeCallbacks {
    WindEffects wind;
    LanternEffects lantern;
    FumeEffects fume;
    PlantZombieShooting shooting;
    std::vector<PlantZombieConfig> shoot_catalog;
    explicit ShootingProbe(int64_t seed):PeaProbe(seed),wind(battle,*this,collision,960.),lantern(battle,*this,collision),fume(battle,*this,collision),
        shooting(battle,{chain,wind,lantern,services,fume,squash,peas},collision),shoot_catalog(native_plant_zombie_catalog().begin(),native_plant_zombie_catalog().end()){}
    void add_entity(std::string n,double f,Motion p)override{PeaProbe::add_entity(std::move(n),f,p);}
    void clear_plant(Cell c)override{PeaProbe::clear_plant(c);}
    void player_damage(double a)override{PeaProbe::player_damage(a);}
    void zombie_damage(size_t i,double f,double a)override{PeaProbe::ordinary_damage(i,f,a);}
    void damage_zombie(size_t i,double f,double a)override{PeaProbe::ordinary_damage(i,f,a);}
    void wind_surface(size_t i,double f,double a)override{PeaProbe::surface_damage(i,f,a);}
    void shoot_fields(CombatZombie& u,const J& v){J other=v;
#define REMOVE(n,k) other.erase(k);
        SHOOT_FIELDS(REMOVE)
#undef REMOVE
        for(const auto k:{"跳跃cd","撑杆","眩晕","气球"})other.erase(k);pea_unit(u,other);
#define READ(n,k) read(v,k,u.patch.n);
        SHOOT_FIELDS(READ)
#undef READ
        read(v,"跳跃cd",u.native.jump_cd);read(v,"撑杆",u.body.pole_vault);read(v,"眩晕",u.body.stun);read(v,"气球",u.body.balloon);
    }
    void shoot_erase(CombatZombie& u,const std::string& k){
#define ERASE(n,key) if(k==key){u.patch.n.erase();return;}
        SHOOT_FIELDS(ERASE)
#undef ERASE
        if(k=="移速")u.native.move_speed.erase();else if(k=="撑杆")u.body.pole_vault.erase();else if(k=="跳跃cd")u.native.jump_cd.erase();else if(k=="魅惑")u.source.charmed.erase();else if(k=="死")u.body.dead.erase();else if(k=="灰烬")u.body.ash.erase();else throw std::invalid_argument("shoot field erase");
    }
    PlantZombieConfig& shoot_config(std::string_view kind){for(auto& c:shoot_catalog)if(c.kind==kind)return c;throw std::invalid_argument("unknown shoot config");}
    void config_fields(PlantZombieConfig& c,const J& v){J other=v;other.erase("missing");keys(other,{
#define KEY(n) #n,
        PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(KEY) PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(KEY)
#undef KEY
        });
#define READ(n) read(v,#n,c.n);
        PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(READ) PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(READ)
#undef READ
        for(const auto& k:v.value("missing",J::array())){
#define ERASE(n) if(k==#n){c.n.erase();continue;}
            PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(ERASE) PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(ERASE)
#undef ERASE
            throw std::invalid_argument("shoot config erase");
        }
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="shoot_unit"){keys(op,{"op","unit","values","erase"});auto& u=*units.at(op.at("unit").get<size_t>());shoot_fields(u,op.value("values",J::object()));for(const auto& k:op.value("erase",J::array()))shoot_erase(u,k);}
        else if(action=="shoot_config"){keys(op,{"op","kind","values"});config_fields(shoot_config(op.at("kind").get<std::string>()),op.at("values"));}
        else if(action=="shoot_live"){keys(op,{"op","names"});if(!op.contains("names")||op["names"].is_null())result=PlantZombieShooting::live(*battle.targets);else{auto names=op["names"].get<std::vector<std::string>>();result=PlantZombieShooting::live(*battle.targets,std::span<const std::string>(names));}}
        else if(action=="shoot_motion"||action=="shoot_jump"){keys(op,{"op","unit","kind"});const auto u=units.at(op.at("unit").get<size_t>());const auto& c=shoot_config(op.value("kind",u->patch.plant_name.get()));if(action=="shoot_motion")shooting.enforce_motion(u,c);else shooting.jump_assist(u,c);}
        else if(action=="shoot_step"){keys(op,{"op"});shooting.step(shoot_catalog);}
        else if(action=="shoot_projectiles"){keys(op,{"op"});peas.update_all();squash.finish_entities();squash.update_entities();}
        else return PeaProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        PeaProbe::extra_snapshot(row);row["shoot_counts"]=J::array({shooting.motion_fixes,wind.blows,lantern.zombie_heals,lantern.native_charmed_heals,fume.attack_count});row["shoot_units"]=J::array();
        for(const auto& u:units){J j=J::object();
#define WRITE(n,k) write(j,k,u->patch.n);
            SHOOT_FIELDS(WRITE)
#undef WRITE
            write(j,"移速",u->native.move_speed);write(j,"跳跃cd",u->native.jump_cd);write(j,"撑杆",u->body.pole_vault);write(j,"眩晕",u->body.stun);write(j,"气球",u->body.balloon);write(j,"牛顿",u->body.gravity);row["shoot_units"].push_back(std::move(j));
        }
        row["shoot_bubbles"]=J::array();for(const auto& b:battle.fume.bubbles)row["shoot_bubbles"].push_back({{"name",b.name},{"x",b.motion.x},{"y",b.motion.y},{"vx",b.motion.vx},{"vy",b.motion.vy},{"age",b.age},{"life",b.life}});
    }
};
J run_shooting(const J& j){ShootingProbe p(j.value("seed",int64_t(1)));J base=j;const auto fields=base.at("shooting");base.erase("shooting");const auto cfg=base.at("services");base.erase("services");const auto sc=base.at("squash");base.erase("squash");const auto pc=base.at("peas");base.erase("peas");const auto dc=base.value("death_config",J::object());base.erase("death_config");configure_doom(p,base);p.battle.world_width.set(p.visual.presentation.screen_width);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);for(size_t i=0;i<sc.at("units").size();++i)p.squash_fields(*p.units.at(i),sc.at("units")[i]);for(size_t i=0;i<pc.at("units").size();++i)p.pea_unit(*p.units.at(i),pc.at("units")[i]);for(size_t i=0;i<fields.at("units").size();++i)p.shoot_fields(*p.units.at(i),fields.at("units")[i]);p.operations(j.at("operations"));return p.states;}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: shooting72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("shoot fixtures");std::string line;while(std::getline(in,line))if(!line.empty())out<<run_shooting(J::parse(line)).dump()<<'\n';return out?0:2;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
