#define PVZ72_SQUASH_PROBE_EMBEDDED
#include "squash_probe.cpp"
#include "sim/typed/zombie_pea.h"
#include "sim/typed/torch_rules.h"
namespace {
struct PeaProbe:SquashProbe,ZombiePeaCallbacks,DamagePatch::NestedOrdinary,TorchRewards {
    TorchRules torches;
    ZombiePeas peas;
    bool surface_available=true;
    std::optional<size_t> surface_index;
    explicit PeaProbe(int64_t seed,bool installed=false):SquashProbe(seed),torches(battle,*this),
        peas(installed?ZombiePeas(battle,*this,collision,torches):ZombiePeas(battle,*this,collision)){chain.patch.bind_nested_ordinary(*this);}
    void petrified_resource(double amount,Point p)override {
        ;
        ;;
    }
    HitResult ordinary(const ZombieRef& u,double direction,double amount)override{const auto index=surface_index?*surface_index:size_t(chain.zombie_index(u));ordinary_damage(index,direction,amount);return {};}
    void ensure_plant_zombie_assets()override{;;;}
    void add_entity(std::string n,double f,Motion m)override{ChiliProbe::add_entity(std::move(n),f,m);}
    void clear_plant(Cell c)override{PlantProbe::clear(c);}
    std::optional<bool> surface_damage(size_t index,double direction,double amount)override{if(!surface_available)return {};;;const auto saved=surface_index;surface_index=index;HitResult r;try{r=chain.damage.surface(battle.targets->at(index),direction,amount);}catch(...){surface_index=saved;throw;}surface_index=saved;;return r.kind!=HitResult::Kind::none&&r.value!=0.;}
    void ordinary_damage(size_t index,double direction,double amount)override{;;chain.damage.ordinary(battle.targets->at(index),direction,amount);;}
    void knockback(size_t index,double force)override{;;const auto t=battle.targets->at(index);if(t.is_hero())throw std::invalid_argument("native knockback only accepts a unit");chain.patch.knockback(t.unit,force);;}
    void player_damage(double amount)override{;;ChiliProbe::damage_player(amount);;}
    void pea_unit(CombatZombie& u,const J& v){J other=v;other.erase("_pvp_card");other.erase("_pvp_zs_volley");other.erase("_pvp_owner");squash_fields(u,other);read(v,"_pvp_card",u.protection.card);read(v,"_pvp_owner",u.source.owner);read(v,"_pvp_zs_volley",u.patch.shotgun_volley);}
    void pea_fields(Entity& e,const J& v){J other=v;for(const auto k:{"x","y","prev_x","prev_y","vx","vy","age","僵尸豌豆弹","__pvz_sb_native_move","__pvz_sb_charmed_plant_zombie_pea","追踪","__pvz_sb_zombie_pea_fire","_pvp_owner"})other.erase(k);squash_entity(e,other);auto& p=e.pea;
        read(v,"x",p.x);read(v,"y",p.y);read(v,"prev_x",p.previous_x);read(v,"prev_y",p.previous_y);read(v,"vx",p.vx);read(v,"vy",p.vy);read(v,"age",p.age);read(v,"僵尸豌豆弹",p.zombie_pea);read(v,"__pvz_sb_native_move",p.native_move);read(v,"__pvz_sb_charmed_plant_zombie_pea",p.charmed_pea);read(v,"追踪",e.tracking);read(v,"__pvz_sb_zombie_pea_fire",e.source.zombie_fire);read(v,"_pvp_owner",e.source.owner);
    }
    J pea_state(const EntityRef& e){auto j=squash_entity_json(e);const auto& p=e->pea;write(j,"x",p.x);write(j,"y",p.y);write(j,"prev_x",p.previous_x);write(j,"prev_y",p.previous_y);write(j,"vx",p.vx);write(j,"vy",p.vy);write(j,"age",p.age);write(j,"僵尸豌豆弹",p.zombie_pea);write(j,"__pvz_sb_native_move",p.native_move);write(j,"__pvz_sb_charmed_plant_zombie_pea",p.charmed_pea);write(j,"追踪",e->tracking);
        const auto& f=e->flight;if(f.torch_previous.present())j["_pvp_torch_previous"]=J::array({f.torch_previous.get().x,f.torch_previous.get().y});
        if(f.torch_visits.present())j["_pvp_torch_visits"]=*f.torch_visits.get();return j;}
    bool extra_operation(const J& op,J& result)override{
        const std::string action=op.at("op");
        if(action=="pea_unit"){keys(op,{"op","unit","values"});pea_unit(*units.at(op.at("unit").get<size_t>()),op.at("values"));}
        else if(action=="pea_write"){keys(op,{"op","entity","values"});pea_fields(*births.at(op.at("entity").get<size_t>()),op.at("values"));}
        else if(action=="pea_environment"){keys(op,{"op","pvp","enabled","shotgun","surface","tick","width","height"});auto& s=battle.zombie_peas;if(op.contains("pvp"))s.pvp_active=op["pvp"];if(op.contains("enabled"))s.secret_system_enabled=op["enabled"];if(op.contains("shotgun"))s.shotgun=op["shotgun"];if(op.contains("surface"))surface_available=op["surface"];if(op.contains("tick"))world.tick=op["tick"];read(op,"width",battle.world_width);read(op,"height",battle.world_height);}
        else if(action=="pea_legacy"){keys(op,{"op","entities"});auto list=std::make_shared<EntityRoster>();for(const auto& i:op.at("entities"))list->push_back(births.at(i.get<size_t>()));battle.zombie_peas.legacy=std::move(list);}
        else if(action=="pea_segment"){keys(op,{"op","start","end","center","radii"});result=ZombiePeas::segment_hits(point(op.at("start")),point(op.at("end")),point(op.at("center")),point(op.at("radii")));}
        else if(action=="pea_spawn"||action=="pea_volley"){
            keys(op,{"op","source","point","angle","friendly","mode","catch"});std::optional<CombatTarget> t;if(op.contains("source")&&!op["source"].is_null())t=target(op["source"]);
            try{if(action=="pea_volley"){const auto r=peas.shotgun_volley(t);result=r?J(*r):J(nullptr);}
                else{const auto p=point(op.at("point"));const double a=op.at("angle");const bool friendly=op.value("friendly",false);const auto mode=op.value("mode",std::string("pvp"));result=mode=="raw"?peas.raw_spawn(p,a,friendly,t):mode=="sourced"?peas.sourced_spawn(p,a,friendly,t):peas.spawn(p,a,friendly,t);}}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="pea_player"){keys(op,{"op","direction"});if(!peas.damage_player(op.value("direction",1.)))result=false;}
        else if(action=="pea_all"){keys(op,{"op"});peas.update_all();}
        else if(action=="pea_hero"){keys(op,{"op","seat","enemies","width","catch"});std::vector<Seat> enemies;for(const auto& s:op.at("enemies"))enemies.push_back(parse_seat(s.get<std::string>()));try{peas.hero_pea(parse_seat(op.at("seat").get<std::string>()),enemies,op.value("width",960.));}catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}}
        else if(action.starts_with("pea_")){
            keys(op,{"op","entity","target","index","direction","point","plant","direct_zombie","direct_player","scale","width","height","sourced","catch"});const auto e=births.at(op.at("entity").get<size_t>());
            try{if(action=="pea_is")result=peas.is_pea(e);else if(action=="pea_xy"){const auto p=peas.xy(e);result=J::array({p.x,p.y});}
                else if(action=="pea_multiplier")result=peas.fire_multiplier(e);else if(action=="pea_torch")peas.torch_check(e);
                else if(action=="pea_damage_charmed")result=peas.damage_charmed(op.at("index").get<size_t>(),target(op.at("target")),e,op.value("direction",1.));
                else if(action=="pea_hit")result=op.value("sourced",true)?peas.hit(e):peas.raw_hit(e);
                else if(action=="pea_tick")result=op.value("sourced",true)?peas.update_one(e,op.value("scale",48.),op.value("width",960.),op.value("height",576.)):peas.raw_update_one(e,op.value("scale",48.),op.value("width",960.),op.value("height",576.));
                else if(action=="pea_splash")peas.fire_splash(e,point(op.at("point")),op.contains("plant")&&!op["plant"].is_null()?plant_ref(op["plant"].get<size_t>()):PlantRef{},op.contains("direct_zombie")&&!op["direct_zombie"].is_null()?std::optional<CombatTarget>(target(op["direct_zombie"])):std::nullopt,op.value("direct_player",false));
                else throw std::invalid_argument("unknown pea operation");
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return SquashProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override{
        SquashProbe::extra_snapshot(row);row["pea_shots"]=peas.shots;row["pea_units"]=J::array();for(const auto& u:units){J j=J::object();write(j,"_pvp_card",u->protection.card);write(j,"_pvp_zs_volley",u->patch.shotgun_volley);row["pea_units"].push_back(std::move(j));}
        row["entities"]=J::array();row["effect_births"]=J::array();row["legacy_peas"]=J::array();for(const auto& e:*visual.entities.list())row["entities"].push_back(pea_state(e));for(const auto& e:births)row["effect_births"].push_back(pea_state(e));for(const auto& e:*battle.zombie_peas.legacy)row["legacy_peas"].push_back(pea_state(e));
    }
};
J run_peas(const J& j){PeaProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.at("services");base.erase("services");const auto sc=base.at("squash");base.erase("squash");const auto pc=base.at("peas");base.erase("peas");const auto dc=base.value("death_config",J::object());base.erase("death_config");configure_doom(p,base);p.battle.world_width.set(p.visual.presentation.screen_width);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);for(size_t i=0;i<sc.at("units").size();++i)p.squash_fields(*p.units.at(i),sc.at("units")[i]);for(size_t i=0;i<pc.at("units").size();++i)p.pea_unit(*p.units.at(i),pc.at("units")[i]);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_PEA_PROBE_EMBEDDED
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: pea72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("pea fixtures");std::string line;while(std::getline(in,line))if(!line.empty())out<<run_peas(J::parse(line)).dump()<<'\n';return out?0:2;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}

#endif
