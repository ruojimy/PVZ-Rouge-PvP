#define PVZ72_DEATH_PROBE_EMBEDDED
#include "death_probe.cpp"
#include "sim/typed/wind_effects.h"
namespace {
struct WindProbe:DeathProbe,WindServices {
    WindEffects wind;
    std::vector<std::shared_ptr<Motion>> held_positions;
    std::shared_ptr<EntityRoster> original_entities;
    std::shared_ptr<RainRoster> original_rain;
    std::shared_ptr<std::vector<std::string>> original_names;
    J wind_callbacks=J::array();
    explicit WindProbe(int64_t seed,double width):DeathProbe(seed),wind(battle,*this,collision){battle.world_width.set(width);load_native_plant_zombie_heads(collision);}
    void wind_surface(size_t index,double direction,double amount)override {
        J roster=J::array(),entities=J::array();for(const auto& t:*battle.targets)roster.push_back(label(t));for(const auto& e:*visual.entities.list())entities.push_back(e->kind);
        wind_callbacks.push_back({{"index",index},{"roster",roster},{"entities",entities},{"rain",battle.wind_environment.rain->size()},{"names",*battle.wind_environment.damage_entities}});
        before("wind_surface");chain.damage.surface(battle.targets->at(index),direction,amount);after("wind_surface");
    }
    void fields(CombatZombie& u,const J& v) {
        keys(v,{"位置","方向","血量","手持","手持血量","气球","大小","牛顿","死","灰烬","魅惑","植物僵尸","植物僵尸名","植物僵尸鸭子","植物僵尸发射动画","植物僵尸角","射","__pvz_sb_blover_zombie_cd","__pvz_sb_blover_zombie_wind_tick"});
        if(v.contains("位置"))u.body.motion=motion(v["位置"]);if(v.contains("方向"))u.body.facing=v["方向"];if(v.contains("血量"))u.body.hp=v["血量"];
        if(v.contains("手持"))u.body.hand=v["手持"];if(v.contains("手持血量"))u.body.hand_hp=v["手持血量"];
        read(v,"气球",u.body.balloon);read(v,"大小",u.body.size);read(v,"牛顿",u.body.gravity);read_death(v,"死",u.body.dead);read(v,"灰烬",u.body.ash);read(v,"魅惑",u.source.charmed);
        read(v,"植物僵尸",u.patch.plant_zombie);read(v,"植物僵尸名",u.patch.plant_name);read(v,"植物僵尸鸭子",u.patch.duck);
        read(v,"植物僵尸发射动画",u.patch.fire_animation);read(v,"植物僵尸角",u.patch.aim_angle);read(v,"射",u.patch.shoot);
        read(v,"__pvz_sb_blover_zombie_cd",u.patch.blover_cooldown);read(v,"__pvz_sb_blover_zombie_wind_tick",u.patch.blover_wind_tick);
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="wind_unit") {keys(op,{"op","unit","values"});fields(*units.at(op.at("unit").get<size_t>()),op.at("values"));}
        else if(action=="wind_hold") {
            keys(op,{"op","unit","entity","hero"});
            if(op.contains("entity"))held_positions.push_back(births.at(op["entity"].get<size_t>())->motion.retain());
            else if(op.contains("hero"))held_positions.push_back(world.proxy(parse_seat(op["hero"].get<std::string>())).position);
            else held_positions.push_back(units.at(op.at("unit").get<size_t>())->body.motion.retain());
        }else if(action=="wind_alias") {
            keys(op,{"op","from","to"});units.at(op.at("to").get<size_t>())->body.motion=units.at(op.at("from").get<size_t>())->body.motion;
        }else if(action=="wind_entity") {
            keys(op,{"op","name","position","direction"});add_entity(op.at("name"),op.value("direction",1.),motion(op.at("position")));
        }else if(action=="wind_flying") {
            keys(op,{"op","entities"});battle.content_projectiles.flying.clear();for(const auto& i:op.at("entities"))battle.content_projectiles.flying.push_back(births.at(i.get<size_t>()));
        }else if(action=="wind_shot") {
            keys(op,{"op","list","values"});
            const auto& value=op.at("values");keys(value,{"kind","x","y","vx","vy"});
            const auto configure=[&](auto& shot) {
                read(value,"kind",shot.kind);
                shot.motion={value.at("x"),value.at("y"),value.at("vx"),value.at("vy")};
            };
            if(op.at("list")=="shots") {
                auto shot=std::make_shared<ContentProjectile>();configure(*shot);
                battle.content_projectiles.shots.push_back(std::move(shot));
            }else {
                auto grenade=std::make_shared<Grenade>();configure(*grenade);
                battle.content_projectiles.grenades->push_back(std::move(grenade));
            }
        }else if(action=="wind_rain") {
            keys(op,{"op","values"});auto r=std::make_shared<RainRoster>();for(const auto& p:op.at("values"))r->push_back(std::make_shared<std::vector<double>>((p.is_object()?p.at("位置"):p).get<std::vector<double>>()));battle.wind_environment.rain=std::move(r);
        }else if(action=="wind_environment") {
            keys(op,{"op","speed","plk","names"});if(op.contains("speed"))battle.wind_environment.zombie_speed_max=op["speed"];if(op.contains("plk"))visual.plk=op["plk"];
            if(op.contains("names"))battle.wind_environment.damage_entities=std::make_shared<std::vector<std::string>>(op.at("names").get<std::vector<std::string>>());
        }else if(action=="wind_capture_lists") {
            keys(op,{"op"});original_entities=visual.entities.list();original_rain=battle.wind_environment.rain;original_names=battle.wind_environment.damage_entities;
        }else if(action=="wind_apply"||action=="wind_update") {
            keys(op,{"op","unit","raw","strength","sourced","config"});const auto u=units.at(op.at("unit").get<size_t>());
            if(action=="wind_apply"){if(op.value("raw",false))wind.raw_wind(u,op.value("strength",1.));else wind.wind(u,op.value("strength",1.));}
            else {PlantZombieConfig cfg=*native_plant_zombie_config("三叶草僵尸");if(op.contains("config")){const auto& c=op.at("config");keys(c,{"fire_anim","cooldown","missing"});read(c,"fire_anim",cfg.fire_anim);read(c,"cooldown",cfg.cooldown);for(const auto& n:c.value("missing",J::array())){if(n=="fire_anim")cfg.fire_anim.erase();else if(n=="cooldown")cfg.cooldown.erase();else throw std::invalid_argument("config erase");}}
                if(op.value("sourced",true))wind.update(u,cfg);else wind.raw_update(u,cfg);}
        }else if(action=="wind_before_plants") {keys(op,{"op"});wind.before_plants();}
        else if(action=="wind_after_plants") {keys(op,{"op"});wind.after_plants();}
        else if(action=="wind_after_zombies") {keys(op,{"op"});wind.after_zombies();}
        else return DeathProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        DeathProbe::extra_snapshot(row);row["wind_units"]=J::array();for(const auto& u:units){J j=J::object();const auto& p=u->patch;
            write(j,"植物僵尸发射动画",p.fire_animation);write(j,"植物僵尸角",p.aim_angle);write(j,"射",p.shoot);write(j,"__pvz_sb_blover_zombie_cd",p.blover_cooldown);write(j,"__pvz_sb_blover_zombie_wind_tick",p.blover_wind_tick);row["wind_units"].push_back(std::move(j));}
        row["wind_held"]=J::array();for(const auto& p:held_positions)row["wind_held"].push_back(as_json(*p));
        row["wind_rain"]=J::array();for(const auto& p:*battle.wind_environment.rain)row["wind_rain"].push_back(*p);
        row["wind_names"]=*battle.wind_environment.damage_entities;row["wind_blows"]=wind.blows;row["wind_callbacks"]=wind_callbacks;
        row["wind_list_identity"]=J::array({visual.entities.list()==original_entities,battle.wind_environment.rain==original_rain,battle.wind_environment.damage_entities==original_names});
        row["wind_pre"]=J::object();for(size_t i=0;i<4;++i)if(wind.plant_baselines()[i])row["wind_pre"][seat_name(Seat(i))]={{"vx",*wind.plant_baselines()[i]}};
        const auto record=[](const auto& roster) {
            J list=J::array();
            for(const auto& shot:roster) {
                const auto& position=shot->motion;
                J item={{"x",position.x},{"y",position.y},{"vx",position.vx},{"vy",position.vy}};
                write(item,"kind",shot->kind);list.push_back(std::move(item));
            }
            return list;
        };
        row["shots"]=record(battle.content_projectiles.shots);
        row["grenades"]=record(*battle.content_projectiles.grenades);
    }
};
J run_wind(const J& j) {
    J base=j;const auto cfg=base.at("wind");base.erase("wind");const auto dc=base.value("death_config",J::object());base.erase("death_config");
    keys(cfg,{"units","width","mode","names"});WindProbe p(j.value("seed",int64_t(1)),cfg.value("width",1920.));configure_doom(p,base);
    p.chain.sourced_fastpath=dc.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    const auto mode=cfg.value("mode",std::string("duel"));if(mode=="duel")p.battle.mode=MatchMode::duel;else if(mode=="duo")p.battle.mode=MatchMode::duo;else if(mode=="pve")p.battle.mode=MatchMode::pve;else if(mode=="coop")p.battle.mode=MatchMode::coop;else throw std::invalid_argument("wind mode");
    for(size_t i=0;i<cfg.at("units").size();++i)p.fields(*p.units.at(i),cfg.at("units")[i]);
    *p.battle.wind_environment.damage_entities=cfg.at("names").get<std::vector<std::string>>();p.original_entities=p.visual.entities.list();p.original_rain=p.battle.wind_environment.rain;p.original_names=p.battle.wind_environment.damage_entities;
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: wind72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("wind fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_wind(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("wind output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
