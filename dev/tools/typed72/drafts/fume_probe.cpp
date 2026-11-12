#define PVZ72_SERVICE_PROBE_EMBEDDED
#include "service_probe.cpp"
#include "sim/typed/fume_effects.h"
#define FUME_CONFIG(X) X(fire_anim) X(cooldown) X(visual_tick) X(damage_tick) X(damage_pulses) X(range_tiles) X(attack_length) X(visual_bubbles)
namespace {
struct FumeProbe:ServiceProbe,FumeCallbacks {
    FumeEffects fume;
    explicit FumeProbe(int64_t seed):ServiceProbe(seed),fume(battle,*this,collision){}
    void zombie_damage(size_t index,double direction,double amount)override {
        calls.push_back(J::array({"fume_damage",index,direction,amount}));before("fume_damage");chain.damage.ordinary(battle.targets->at(index),direction,amount);after("fume_damage");
    }
    void player_damage(double amount)override {calls.push_back(J::array({"fume_player",amount}));before("fume_player");world.player_damage(amount);after("fume_player");}
    void clear_plant(Cell c)override{PlantProbe::clear(c);}
    void fume_fields(CombatZombie& u,const J& v) {
        J other=v;for(const auto k:{"__pvz_sb_fumeshroom_zombie_cd","__pvz_sb_fumeshroom_zombie_attack_angle","__pvz_sb_fumeshroom_zombie_damage_done","__pvz_sb_fumeshroom_zombie_bubble_tick","眩晕"})other.erase(k);
        fields(u,other);read(v,"眩晕",u.body.stun);read(v,"__pvz_sb_fumeshroom_zombie_cd",u.patch.fume_cooldown);read(v,"__pvz_sb_fumeshroom_zombie_attack_angle",u.patch.fume_attack_angle);
        read(v,"__pvz_sb_fumeshroom_zombie_damage_done",u.patch.fume_damage_done);read(v,"__pvz_sb_fumeshroom_zombie_bubble_tick",u.patch.fume_bubble_tick);
    }
    PlantZombieConfig fume_config(const J& op) {
        PlantZombieConfig c=*native_plant_zombie_config("大喷菇僵尸");const auto v=op.value("config",J::object());keys(v,{
#define NAME(n) #n,
            FUME_CONFIG(NAME)
#undef NAME
            "missing"});
#define READ(n) read(v,#n,c.n);
        FUME_CONFIG(READ)
#undef READ
        for(const auto& k:v.value("missing",J::array())){
#define ERASE(n) if(k==#n){c.n.erase();continue;}
            FUME_CONFIG(ERASE)
#undef ERASE
            throw std::invalid_argument("fume config field");
        }return c;
    }
    J describe(const std::optional<NativeAimTarget>& a) {
        if(!a)return nullptr;J kind="player",label_value=nullptr,index=-1;
        if(const auto* p=std::get_if<PlantRef>(&a->object)){kind="plant";index=a->index;for(size_t i=0;i<battle.plants.order().size();++i)if(plant_ref(i)==*p){label_value={{"plant",i}};break;}}
        else if(const auto* z=std::get_if<CombatTarget>(&a->object)){kind="zombie";index=a->index;label_value=label(*z);}
        return J::array({kind,index,label_value,J::array({a->captured_point.x,a->captured_point.y}),a->direction,a->angle});
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="fume_unit"){keys(op,{"op","unit","values"});fume_fields(*units.at(op.at("unit").get<size_t>()),op.at("values"));}
        else if(action=="fume_environment"){keys(op,{"op","time","width","height"});if(op.contains("time"))battle.native_time=op["time"];read(op,"width",battle.world_width);read(op,"height",battle.world_height);}
        else if(action=="fume_ray"){keys(op,{"op","origin","point","angle","radius","length"});result=fume.ray(point(op.at("origin")),op.at("angle"),point(op.at("point")),op.at("radius"),op.at("length"));}
        else if(action=="fume_within"){keys(op,{"op","center","point","radius"});result=fume.within(point(op.at("center")),point(op.at("point")),op.at("radius"));}
        else if(action=="fume_metal"||action=="fume_stun"){keys(op,{"op","target","point"});const auto t=target(op.at("target"));result=action=="fume_metal"?fume.has_metal(t):fume.stun(t,point(op.at("point")));}
        else if(action=="fume_thunder"){keys(op,{"op","unit"});result=fume.thunder(units.at(op.at("unit").get<size_t>()));}
        else if(action=="fume_damage_plant"){keys(op,{"op","plant","amount"});result=fume.damage_plant(plant_ref(op.at("plant").get<size_t>()),op.at("amount"));}
        else if(action=="fume_damage_player"){keys(op,{"op","direction"});result=fume.damage_player(op.value("direction",1.));}
        else if(action=="fume_damage_unit"){keys(op,{"op","index","target","amount","direction"});result=fume.damage_zombie(op.at("index").get<size_t>(),target(op.at("target")),op.at("amount"),op.value("direction",1.));}
        else if(action=="fume_bubbles"){keys(op,{"op","center","angle","config","blue"});fume.bubbles(point(op.at("center")),op.at("angle"),fume_config(op),op.value("blue",false));}
        else if(action=="fume_bubble_tick"){keys(op,{"op","time"});fume.update_bubbles(op.contains("time")&&!op["time"].is_null()?std::optional<double>(op["time"].get<double>()):std::nullopt);}
        else if(action=="fume_shoot_tick"||action=="fume_pick"||action=="fume_animate"||action=="fume_update"||action=="fume_line") {
            keys(op,{"op","unit","config","center","angle","sourced"});const auto u=units.at(op.at("unit").get<size_t>());const auto c=fume_config(op);
            if(action=="fume_shoot_tick")result=J::array({fume.shoot_tick(u,c),fume.fire_frames(c),fume.visual_tick(c)});
            else if(action=="fume_pick"){const auto a=fume.pick(u,c);result=J::array({describe(a.target),J::array({a.center.x,a.center.y})});}
            else if(action=="fume_animate")result=fume.fire_animation(u,c);
            else if(action=="fume_update"){if(op.value("sourced",true))fume.update(u,c);else fume.raw_update(u,c);}
            else result=op.value("sourced",true)?fume.line(u,point(op.at("center")),op.at("angle"),c):fume.raw_line(u,point(op.at("center")),op.at("angle"),c);
        }else return ServiceProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        ServiceProbe::extra_snapshot(row);row["fume_units"]=J::array();for(const auto& u:units){J j=J::object();const auto& p=u->patch;write(j,"眩晕",u->body.stun);
            write(j,"__pvz_sb_fumeshroom_zombie_cd",p.fume_cooldown);write(j,"__pvz_sb_fumeshroom_zombie_attack_angle",p.fume_attack_angle);write(j,"__pvz_sb_fumeshroom_zombie_damage_done",p.fume_damage_done);write(j,"__pvz_sb_fumeshroom_zombie_bubble_tick",p.fume_bubble_tick);row["fume_units"].push_back(std::move(j));}
        row["fume_bubbles"]=J::array();for(const auto& b:battle.fume.bubbles)row["fume_bubbles"].push_back({{"name",b.name},{"x",b.motion.x},{"y",b.motion.y},{"vx",b.motion.vx},{"vy",b.motion.vy},{"age",b.age},{"life",b.life}});
        row["fume_state"]={{"attacks",fume.attack_count},{"last_update",battle.fume.last_update},{"time",battle.native_time}};
    }
};
J run_fume(const J& j) {
    FumeProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.at("services");base.erase("services");const auto fc=base.at("fume");base.erase("fume");const auto dc=base.value("death_config",J::object());base.erase("death_config");keys(cfg,{"units"});keys(fc,{"units"});configure_doom(p,base);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);for(size_t i=0;i<fc.at("units").size();++i)p.fume_fields(*p.units.at(i),fc.at("units")[i]);p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: fume72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("fume fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_fume(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("fume output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
