#define PVZ72_DEATH_PROBE_EMBEDDED
#include "death_probe.cpp"
#include "sim/typed/service_plants.h"
namespace {
struct ServiceProbe:DeathProbe,ServicePlantCallbacks {
    ServicePlants services;
    explicit ServiceProbe(int64_t seed):DeathProbe(seed),services(battle,*this,collision){load_native_plant_zombie_heads(collision);}
    void add_entity(std::string n,double f,Motion p)override{ChiliProbe::add_entity(std::move(n),f,p);}
    void fields(CombatZombie& u,const J& v) {
        keys(v,{"位置","方向","血量","防具","防具血量","手持","手持血量","大小","牛顿","死","灰烬","魅惑","植物僵尸","植物僵尸名","植物僵尸鸭子","植物僵尸发射动画","植物僵尸角","射","__pvz_sb_umbrella_zombie_cd","__pvz_sb_gold_magnet_zombie_cd","_pvp_umbrella_secret","_pvp_umbrella_initialized"});
        if(v.contains("位置"))u.body.motion=motion(v["位置"]);if(v.contains("方向"))u.body.facing=v["方向"];if(v.contains("血量"))u.body.hp=v["血量"];
        if(v.contains("防具"))u.body.armor=v["防具"];if(v.contains("防具血量"))u.body.armor_hp=v["防具血量"];
        if(v.contains("手持"))u.body.hand=v["手持"];if(v.contains("手持血量"))u.body.hand_hp=v["手持血量"];
        read(v,"大小",u.body.size);read(v,"牛顿",u.body.gravity);read_death(v,"死",u.body.dead);read(v,"灰烬",u.body.ash);read(v,"魅惑",u.source.charmed);
        read(v,"植物僵尸",u.patch.plant_zombie);read(v,"植物僵尸名",u.patch.plant_name);read(v,"植物僵尸鸭子",u.patch.duck);
        read(v,"植物僵尸发射动画",u.patch.fire_animation);read(v,"植物僵尸角",u.patch.aim_angle);read(v,"射",u.patch.shoot);
        read(v,"__pvz_sb_umbrella_zombie_cd",u.patch.umbrella_cooldown);read(v,"__pvz_sb_gold_magnet_zombie_cd",u.patch.magnet_cooldown);
        read(v,"_pvp_umbrella_secret",u.patch.umbrella_secret);read(v,"_pvp_umbrella_initialized",u.patch.umbrella_initialized);
    }
    void entity_fields(Entity& e,const J& v) {
        keys(v,{"智能弹道","__pvz_sb_smart_projectile_skip","__pvz_sb_umbrella_reflected_by","吸引","吸引初位置","吸引末位置","消亡","牛顿","位置","方向"});auto& f=e.service;
        read(v,"__pvz_sb_smart_projectile_skip",f.smart_skip);read(v,"吸引",f.attract);read(v,"消亡",e.expires);read(v,"牛顿",e.gravity);
        if(v.contains("位置"))e.motion=motion(v["位置"]);if(v.contains("方向"))e.facing=v["方向"];
        const char* id="__pvz_sb_umbrella_reflected_by";if(v.contains(id)){if(v[id].is_null())f.reflected_by.set_null();else f.reflected_by.set(record(v[id]));}
        for(auto [key,p]:{std::pair{"吸引初位置",&f.attract_start},std::pair{"吸引末位置",&f.attract_end}})if(v.contains(key)){const auto& x=v[key];if(x.is_null())p->set_null();else p->set({x.at(0),x.at(1)});}
        if(v.contains("智能弹道")){const auto& s=v["智能弹道"];if(s.is_null())f.smart.set_null();else{keys(s,{"target_index","initial_speed","gravity","hit_t","lead_scale","created"});SmartProjectile smart;
            read(s,"target_index",smart.target_index);read(s,"initial_speed",smart.initial_speed);read(s,"gravity",smart.gravity);read(s,"hit_t",smart.hit_time);read(s,"lead_scale",smart.lead_scale);read(s,"created",smart.created);f.smart.set(smart);}}
    }
    PlantZombieConfig config(const J& op,std::string_view kind) {
        PlantZombieConfig c=*native_plant_zombie_config(kind);const auto v=op.value("config",J::object());keys(v,{"fire_anim","cooldown","radius","missing"});
        read(v,"fire_anim",c.fire_anim);read(v,"cooldown",c.cooldown);read(v,"radius",c.radius);
        for(const auto& k:v.value("missing",J::array())){if(k=="fire_anim")c.fire_anim.erase();else if(k=="cooldown")c.cooldown.erase();else if(k=="radius")c.radius.erase();else throw std::invalid_argument("service config erase");}return c;
    }
    static Point point(const J& p){return {p.at(0),p.at(1)};}
    J magnet_result(const std::optional<MagnetTarget>& t,bool absorbing) {
        if(!t)return nullptr;J j=J::array({label(t->target),J::array({t->point.x,t->point.y})});if(absorbing)j.push_back(t->handheld?"handheld":"armor");return j;
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="service_unit"){keys(op,{"op","unit","values"});fields(*units.at(op.at("unit").get<size_t>()),op.at("values"));}
        else if(action=="service_entity") {keys(op,{"op","name","position","facing","values"});add_entity(op.at("name"),op.value("facing",1.),motion(op.at("position")));entity_fields(*births.back(),op.value("values",J::object()));}
        else if(action=="service_entity_write"){keys(op,{"op","entity","values"});entity_fields(*births.at(op.at("entity").get<size_t>()),op.at("values"));}
        else if(action=="service_live"||action=="service_armor"){keys(op,{"op","target"});const auto t=target(op.at("target"));result=action=="service_live"?services.live(t):services.head_armor(t);}
        else if(action=="service_animate"){keys(op,{"op","unit","config","spread"});services.animate(units.at(op.at("unit").get<size_t>()),config(op,"萝卜伞僵尸"),op.value("spread",35.));}
        else if(action=="service_reflect"||action=="service_bounce"||action=="service_knock_units"||action=="service_knock_player") {
            keys(op,{"op","unit","center","radius"});const auto center=point(op.at("center"));const double r=op.value("radius",2.);
            if(action=="service_reflect")result=services.reflect(units.at(op.at("unit").get<size_t>()),center,r);
            else if(action=="service_bounce")result=services.bounce(center,r);else if(action=="service_knock_player")result=services.knock_player(center,r);
            else result=services.knock_zombies(units.at(op.at("unit").get<size_t>()),center,r);
        }else if(action=="service_umbrella"||action=="service_magnet") {
            keys(op,{"op","unit","config","sourced","pvp","catch"});const auto u=units.at(op.at("unit").get<size_t>());const auto c=config(op,action=="service_umbrella"?"萝卜伞僵尸":"吸金磁僵尸");
            try{if(action=="service_magnet"){if(op.value("sourced",true))services.magnet(u,c);else services.raw_magnet(u,c);}
                else if(op.value("sourced",true))services.umbrella(u,c);else if(op.value("pvp",true))services.raw_pvp_umbrella(u,c);else services.raw_umbrella(u,c);}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="service_pick") {
            keys(op,{"op","unit","center","radius","absorb"});const bool a=op.value("absorb",false);const auto u=units.at(op.at("unit").get<size_t>());const auto c=point(op.at("center"));
            result=magnet_result(a?services.absorb_target(u,c,op.value("radius",9.)):services.bucket_target(u,c,op.value("radius",5.)),a);
        }else if(action=="service_gift") {keys(op,{"op","target","center"});result=services.gift(target(op.at("target")),point(op.at("center")));}
        else if(action=="service_absorb") {keys(op,{"op","target","point","center","slot"});result=services.absorb(target(op.at("target")),point(op.at("point")),point(op.at("center")),op.at("slot")=="handheld");}
        else if(action=="service_attract") {keys(op,{"op","name","start","end"});const auto e=services.attract(op.at("name"),point(op.at("start")),point(op.at("end")));result=e?J(entity_index(e)):J(nullptr);}
        else return DeathProbe::extra_operation(op,result);return true;
    }
    J service_entity(const EntityRef& e) {
        auto j=fire_state(e);const auto& f=e->service;write(j,"吸引",f.attract);write(j,"__pvz_sb_smart_projectile_skip",f.smart_skip);
        if(f.reflected_by.present())j["__pvz_sb_umbrella_reflected_by"]=f.reflected_by.is_null()?J(nullptr):key_json(ChiliKey::object(f.reflected_by.get()));
        for(auto [key,p]:{std::pair{"吸引初位置",&f.attract_start},std::pair{"吸引末位置",&f.attract_end}})if(p->present())j[key]=p->is_null()?J(nullptr):J::array({p->get().x,p->get().y});
        if(f.smart.present()){if(f.smart.is_null())j["智能弹道"]=nullptr;else{const auto& s=f.smart.get();J x=J::object();write(x,"target_index",s.target_index);write(x,"initial_speed",s.initial_speed);write(x,"gravity",s.gravity);write(x,"hit_t",s.hit_time);write(x,"lead_scale",s.lead_scale);write(x,"created",s.created);j["智能弹道"]=std::move(x);}}
        return j;
    }
    void extra_snapshot(J& row)override {
        DeathProbe::extra_snapshot(row);row["service_counts"]=J::array({services.umbrella_triggers,services.magnet_gifts,services.magnet_absorbs});row["service_units"]=J::array();
        for(const auto& u:units){J j=J::object();const auto& p=u->patch;write(j,"植物僵尸发射动画",p.fire_animation);write(j,"植物僵尸角",p.aim_angle);write(j,"射",p.shoot);
            write(j,"__pvz_sb_umbrella_zombie_cd",p.umbrella_cooldown);write(j,"__pvz_sb_gold_magnet_zombie_cd",p.magnet_cooldown);write(j,"_pvp_umbrella_secret",p.umbrella_secret);write(j,"_pvp_umbrella_initialized",p.umbrella_initialized);row["service_units"].push_back(std::move(j));}
        row["entities"]=J::array();row["effect_births"]=J::array();for(const auto& e:*visual.entities.list())row["entities"].push_back(service_entity(e));for(const auto& e:births)row["effect_births"].push_back(service_entity(e));
    }
};
J run_services(const J& j) {
    ServiceProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.at("services");base.erase("services");const auto dc=base.value("death_config",J::object());base.erase("death_config");keys(cfg,{"units"});configure_doom(p,base);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: service72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("service fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_services(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("service output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
