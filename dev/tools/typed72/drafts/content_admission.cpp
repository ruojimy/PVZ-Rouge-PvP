#include "sim/typed/content_admission.h"
#include "sim/typed/zombie_spawn.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
std::string_view name(const Field<std::string>& value){return value.present()&&!value.is_null()?value.get():std::string_view{};}
bool one(std::string_view value,std::initializer_list<std::string_view> values){return std::find(values.begin(),values.end(),value)!=values.end();}
}
Field<double> ContentAdmission::template_speed(std::string_view name) {
    // These two templates have no factory effects beyond their native body
    // and RNG draws. Retain the same original constructor and restore its RNG.
    const auto previous=world_.runtime.rng.state();
    struct Restore {PyRandom& rng;PyRandom::State state;~Restore(){rng.set_state(state);}} restore{world_.runtime.rng,previous};
    CombatZombie temporary;Motion position{};ZombieSpawnInput input;
    const auto& player=*world_.heroes.globals.position.get();input.player={player.x,player.y};
    populate_original_zombie(world_.runtime,temporary,std::string(name),position,1.,input);
    return temporary.native.move_speed;
}
void ContentAdmission::configure(const PlantRef& plant,const ColdCard& card) {
    if(!plant)throw std::invalid_argument("null content plant admission");
    const auto content=name(card.content);
    if(one(content,{"水盆","抓人草","冰冻生菜"})) {
        if(!systems_.plants70.configure(plant,content,card.hp.get()))throw std::logic_error("plant70 catalog/controller mismatch");
        return;
    }
    if(content=="原始土豆地雷"){plant->source.content.set(std::string(content));return;}
    if(content=="甜薯") {
        plant->kind=std::string(content);plant->source.content.set(std::string(content));plant->content_age.set(0.);plant->attack_clock.set(0.);plant->one_shot.erase();
        systems_.sweet.mark_dirty();const double hp=card.hp.get();plant->hp.set(hp);plant->max_hp.set(hp);plant->content_state.maximum_hp.set(hp);return;
    }
    if(systems_.mortar.configure(plant,content)||systems_.reeds.configure(plant,content)||systems_.vines.configure(plant,content)||
       systems_.flying.configure(plant,content)||systems_.september.configure(plant,content))return;
    if(content.empty())return;
    plant->source.content.set(std::string(content));
    double interval;
    if(content=="甜椒投手"||content=="原始豌豆射手")interval=3.;
    else if(content=="回旋镖射手"||content=="毒镖射手")interval=1.6;
    else if(content=="寒冰辣椒")interval=0.;
    else throw std::out_of_range("unconfigured NativeContent plant");
    plant->content_state.interval.set(py::round0(interval*250.));plant->shoot_cd.set(0.);
}
void ContentAdmission::configure(const ZombieRef& unit,const ColdCard& card) {
    if(!unit)throw std::invalid_argument("null content zombie admission");
    systems_.carts.configure(unit,card.id);const auto content=name(card.content);
    if(systems_.zombies70.configure(unit,content))return;
    if(one(content,{"红眼巨人","史莱姆僵尸","中型史莱姆","小型史莱姆","传送带僵尸","掷弹兵僵尸"})) {
        if(!systems_.zombies64.configure(unit,content,card.hp.get(),true))throw std::logic_error("zombie64 catalog/controller mismatch");return;
    }
    if(content=="稻草人"||content=="乌鸦"){systems_.scarecrows.configure(unit,content,card.hp.get());return;}
    if(one(content,{"舞王僵尸","雪橇车小队","雪橇车小队僵尸"})) {systems_.zombies56.configure(unit,content,card.native_hp.get(),true);return;}
    if(content=="雪人僵尸"||content=="垃圾桶僵尸") {
        unit->source.content.set(std::string(content));unit->body.hp=card.native_hp.get();unit->max_hp.set(unit->body.hp);unit->patch.observed_max_hp.set(unit->body.hp);
        if(content=="雪人僵尸")unit->source.no_hero_attack.set(true);
        else{unit->body.hand="钢门";unit->body.hand_hp=200.;unit->native.move_speed.get()*=.25;}
        unit->base_speed=unit->native.move_speed;return;
    }
    const auto variant=name(unit->source.variant);
    if(std::find(black_variants_.begin(),black_variants_.end(),variant)!=black_variants_.end())unit->patch.bite_plant.set(3.);
    if(content.empty())return;
    unit->source.content.set(std::string(content));
    if(content=="滚桶僵尸")unit->body.hp=75.;else if(content=="小鬼炮")unit->body.hp=150.;
    else if(content=="海盗船长")unit->body.hp=160.;else if(content=="海盗鹦鹉")unit->body.hp=30.;
    else throw std::out_of_range("unconfigured NativeContent zombie");
    unit->max_hp.set(unit->body.hp);
    if(content=="滚桶僵尸"||content=="小鬼炮")unit->native.move_speed=template_speed(content=="滚桶僵尸"?"巨人僵尸":"撑杆跳僵尸");
    unit->base_speed=unit->native.move_speed;unit->content.summon_clock.set(0.);
    if(content=="滚桶僵尸") {
        unit->body.hand="滚桶";unit->body.hand_hp=400.;unit->content.barrel_direction.set(unit->body.facing);
        const auto point=unit->body.motion.get();unit->barrel_position.set(std::make_shared<Motion>(Motion{py::mod(point.x+unit->body.facing*world_.runtime.tile*.9,world_.world_width.get()),point.y,0.,0.}));
        systems_.barrels.track(unit);
    }
    if(content=="海盗船长")unit->patch.bite_plant.set(4.);
    if(content=="海盗鹦鹉"){unit->body.hand.clear();unit->body.hand_hp=0.;unit->body.size.set(2.);unit->body.balloon.erase();unit->flight.set(true);}
}
} // namespace pvz::typed72
