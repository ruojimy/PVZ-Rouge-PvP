// Cold fixture codecs only: the battle implementation never parses JSON.
#define PVZ72_ENTITY_PROBE_EMBEDDED
#include "entity_probe.cpp"
#include "sim/typed/projectile_rules.h"
namespace {
void read_flight(const J& s,ProjectileFlight& f) {
    read_point(s,"_pvp_basket_last",f.basket_last);read_point(s,"_pvp_flight_last",f.last);read(s,"_pvp_flight_distance",f.distance);
    if(s.contains("_pvp_flight_form")) {
        if(s["_pvp_flight_form"].is_null())f.form.set_null();else {const auto& a=s["_pvp_flight_form"];f.form.set({a.at(0),a.at(1),a.at(2)});}
    }
}
struct ProjectileProbe : EntityProbe {
    CollisionCatalog catalog;
    ProjectileRules rules;
    double width;
    J hit_hook=J::array();
    explicit ProjectileProbe(int64_t seed,double width,double splash):EntityProbe(seed),rules(battle,damage,catalog,width,splash),width(width){}
    HitResult ordinary(const ZombieRef& unit,double facing,double amount)override {
        const auto result=TargetProbe::ordinary(unit,facing,amount);
        const auto body=std::exchange(hit_hook,J::array());if(!body.empty())operations(body,false);return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="fixture_entity") {
            keys(op,{"op","values","facing"});const auto& s=op.at("values");
            visual.spawn(s.at("名"),op.value("facing",1.),motion(s.at("位置")));
            const auto id=visual.entities.order().back();auto e=visual.entities.at(id);e->source=*source(s);read_flight(s,e->flight);
            handles.push_back(id);retained.push_back(e);
        }else if(action=="projectile_write") {
            keys(op,{"op","entity","values","erase"});auto e=retained.at(op.at("entity").get<size_t>());
            auto s=source_state(e->source,e->motion.get(),e->flight);s.erase("_pvp_instant_attack_text");
            for(const auto& key:op.value("erase",J::array()))s.erase(key.get<std::string>());
            s.update(op.value("values",J::object()));const auto identity=e->source.instant_attack;
            e->source=*source(s);e->source.instant_attack=identity;
            if(op.contains("values") && op["values"].contains("位置"))e->motion.replace(motion(s.at("位置")));
            e->flight={};read_flight(s,e->flight);
        }else if(action=="expired") {
            keys(op,{"op","entity"});result=rules.expired(retained.at(op.at("entity").get<size_t>()));
        }else if(action=="cull") {
            keys(op,{"op"});rules.cull_flight();
        }else if(action=="entity_roster_replace") {
            keys(op,{"op","entities"});auto list=std::make_shared<EntityRoster>();for(const auto& i:op.at("entities"))list->push_back(retained.at(i.get<size_t>()));visual.entities.replace(list);
        }else if(action=="entity_roster_append") {
            keys(op,{"op","entity"});visual.entities.emplace(retained.at(op.at("entity").get<size_t>()));
        }else if(action=="hit_hook") {
            keys(op,{"op","body"});hit_hook=op.at("body");
        }else if(action=="impact") {
            keys(op,{"op","entity","throw_raw","catch"});throw_raw=op.value("throw_raw",false);
            try{rules.impact(retained.at(op.at("entity").get<size_t>()));}
            catch(const std::exception&){throw_raw=false;if(!op.value("catch",false))throw;result={{"caught",true}};}
            throw_raw=false;
        }else if(action=="head_geometry") {
            keys(op,{"op","unit"});const auto e=plant_zombie_head(*units.at(op.at("unit").get<size_t>()),visual.tile,catalog);
            if(e)result=J::array({J::array({e->center.x,e->center.y}),J::array({e->rx,e->ry})});
        }else if(action=="head_area") {
            keys(op,{"op","unit","center","radii"});const auto& p=op.at("center");const auto& r=op.at("radii");
            result=head_overlaps_area(*units.at(op.at("unit").get<size_t>()),{p.at(0),p.at(1)},r.at(0),r.at(1),visual.tile,width,catalog);
        }else if(action=="contact") {
            keys(op,{"op","unit","start","delta"});const auto& a=op.at("start");const auto& d=op.at("delta");
            result=flying_target_contact(*units.at(op.at("unit").get<size_t>()),{a.at(0),a.at(1)},{d.at(0),d.at(1)},visual.tile,width,catalog);
        }else if(action=="segment") {
            keys(op,{"op","a","b","center","radii"});const auto& a=op.at("a");const auto& b=op.at("b");const auto& c=op.at("center");const auto& r=op.at("radii");
            result=segment_hits_ellipse({a.at(0),a.at(1)},{b.at(0),b.at(1)},{{c.at(0),c.at(1)},r.at(0),r.at(1)});
        }else return EntityProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        EntityProbe::extra_snapshot(row);row["projectile_events"]=J::array();
        for(const auto& e:rules.events)if(std::holds_alternative<BasketballHitEvent>(e)||std::holds_alternative<MelonSplashEvent>(e))row["projectile_events"].push_back(event_state(e));
    }
};
J run_projectiles(const J& j) {
    const auto& cfg=j.at("projectiles");keys(cfg,{"width","scale","flyers","heads","units","melon_splash_damage"});ProjectileProbe p(j.value("seed",int64_t(1)),cfg.value("width",1920.),cfg.at("melon_splash_damage"));
    J base=j;base.erase("projectiles");configure_targets(p,base);
    p.catalog.unit_scale=cfg.value("scale",std::unordered_map<std::string,double>{});p.catalog.flyer_image_height=cfg.value("flyers",std::unordered_map<std::string,double>{});
    const auto heads=cfg.value("heads",J::object());
    for(auto it=heads.begin();it!=heads.end();++it) {
        const auto& a=it.value();keys(a,{"head_x","head_y","duck_head_x","duck_head_y","head_scale","fire_anim","fumeshroom"});
        p.catalog.plant_heads[it.key()]={a.value("head_x",.08),a.value("head_y",1.35),a.value("duck_head_x",.08),a.value("duck_head_y",1.35),a.value("head_scale",.68),a.value("fire_anim",24.),a.value("fumeshroom",false)};
    }
    const auto fields=cfg.value("units",J::array());
    for(size_t i=0;i<fields.size();++i) {
        const auto& f=fields[i];auto& u=*p.units.at(i);keys(f,{"植物僵尸","植物僵尸名","植物僵尸鸭子","植物僵尸发射动画","_pvp_head_point","_pvp_orphan_barrel"});
        read(f,"植物僵尸",u.patch.plant_zombie);read(f,"植物僵尸名",u.patch.plant_name);read(f,"植物僵尸鸭子",u.patch.duck);read(f,"植物僵尸发射动画",u.patch.fire_animation);
        read_point(f,"_pvp_head_point",u.head_point);u.orphan_barrel=f.value("_pvp_orphan_barrel",false);
    }
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: projectiles72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open projectile fixture files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_projectiles(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write projectile results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
