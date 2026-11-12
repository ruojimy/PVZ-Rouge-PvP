// Offline typed-stage probe. JSON occurs at the test boundary, never in stages.
#include "sim/typed/state.h"
#include "sim/typed/flood.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>

using namespace pvz::typed72;
using Json = nlohmann::json;

static void require(bool value, const char* text) { if (!value) throw std::runtime_error(text); }
static void keys(const Json& j, std::initializer_list<const char*> allowed) {
    for (auto i = j.begin(); i != j.end(); ++i)
        if (std::none_of(allowed.begin(), allowed.end(), [&](const char* key) { return i.key() == key; }))
            throw std::invalid_argument("unsupported field: " + i.key());
}
static Motion motion(const Json& j) {
    require(j.is_array() && j.size() == 4, "motion must have four numbers");
    return {j.at(0).get<double>(), j.at(1).get<double>(), j.at(2).get<double>(), j.at(3).get<double>()};
}
static Json json_motion(const Motion& m) { return Json::array({m.x,m.y,m.vx,m.vy}); }
static void read_field(const Json& j, const char* key, Field<double>& field) {
    if (!j.contains(key)) return;
    if (j.at(key).is_null()) field.set_null(); else field.set(j.at(key).get<double>());
}
static void write_field(Json& j, const char* key, const Field<double>& field) {
    if (field.present()) j[key] = field.is_null() ? Json(nullptr) : Json(field.get());
}
static Zombie zombie(const Json& j) {
    keys(j, {"僵尸","防具","手持","血量","防具血量","手持血量","方向","位置","受伤","手持受伤","灰烬","气球"});
    Zombie z;
    z.kind=j.at("僵尸"); z.armor=j.at("防具"); z.hand=j.at("手持");
    z.hp=j.at("血量"); z.armor_hp=j.at("防具血量"); z.hand_hp=j.at("手持血量");
    z.facing=j.at("方向"); z.motion=motion(j.at("位置"));
    z.hurt=j.at("受伤"); z.hand_hurt=j.at("手持受伤");
    read_field(j,"灰烬",z.ash); read_field(j,"气球",z.balloon);
    return z;
}
static Json json_zombie(const Zombie& z) {
    Json j={{"僵尸",z.kind},{"防具",z.armor},{"手持",z.hand},{"血量",z.hp},
        {"防具血量",z.armor_hp},{"手持血量",z.hand_hp},{"方向",z.facing},
        {"位置",json_motion(z.motion.get())},{"受伤",z.hurt},{"手持受伤",z.hand_hurt}};
    write_field(j,"灰烬",z.ash); write_field(j,"气球",z.balloon); return j;
}
static void configure_particles(CombatStages& w,const Json& j) {
    keys(j,{"enabled","camera","screen_width","atlas"});
    w.presentation.enabled=j.value("enabled",false);
    const auto camera=j.value("camera",Json::array({0.,0.}));
    w.presentation.camera={camera.at(0),camera.at(1)};
    w.presentation.screen_width=j.value("screen_width",1152.);
    const auto atlas=j.value("atlas",Json::object());
    for(auto i=atlas.begin();i!=atlas.end();++i) {
        keys(i.value(),{"width","height","pixels"});
        const auto& p=i.value();
        w.presentation.atlas.emplace(i.key(),SpritePixels{p.at("width"),p.at("height"),p.at("pixels").get<std::vector<Color>>()});
    }
}
static Json snapshot(const CombatStages& w) {
    Json j={{"zombies",Json::array()},{"entities",Json::array()},
            {"sounds",Json::array()},{"particles",Json::array()},{"particle_state",Json::array()},
            {"particle_rects",Json::array()},{"rng_index",w.rng.state().mti}};
    for (auto id:w.zombies.order()) j["zombies"].push_back(json_zombie(w.zombies.at(id)));
    for (const auto& entity:*w.entities.list()) {
        const auto& e=*entity;
        Json item={{"名",e.kind},{"方向",e.facing},{"位置",json_motion(e.motion.get())}};
        write_field(item,"牛顿",e.gravity); write_field(item,"消亡",e.expires); write_field(item,"穿墙",e.through_wall);
        j["entities"].push_back(std::move(item));
    }
    for (const auto& s:w.sounds) j["sounds"].push_back(Json::array({s.name,Json::array({s.position.x,s.position.y})}));
    for (const auto& p:w.particles) j["particles"].push_back(Json::array({p.name,Json::array({p.position.x,p.position.y}),p.count}));
    for (const auto& p:w.particle_state) j["particle_state"].push_back(Json::array({p.color,json_motion(p.motion),p.age}));
    for (const auto& p:w.particle_rects) j["particle_rects"].push_back(Json::array({p.color,Json::array({p.x,p.y,p.width,p.height})}));
    return j;
}
static Json rng_state(const pvz::PyRandom& rng) {
    const auto s=rng.state(); Json result=Json::array();
    for (auto n:s.mt) result.push_back(n);
    result.push_back(s.mti); return result;
}
static Json capabilities() {
    return {{"backend_actual","typed72-stages"},{"full_battle_supported",false},
            {"fallback_count",0},{"stage_apis",{"original_damage","original_six_shooters","periodic_flood","original_particles","body_displacement"}},
            {"unmigrated",{"PvP wrappers","zombie step","entity step","plant maintenance and gates",
                "hero physics and damage","bonus_scan","AI","UI/network/replay integration"}},
            {"particle_boundary","typed pixel atlas input and ordered draw events; production asset/UI integration pending"}};
}
static Json damage_case(const Json& request) {
    keys(request,{"mode","seed","tile","plk","zombies","operations","instrument","presentation"});
    CombatStages w(request.value("seed",int64_t(1)));
    w.tile=request.value("tile",48.); w.plk=request.value("plk",w.tile/10000.); w.instrument=request.value("instrument",false);
    configure_particles(w,request.value("presentation",Json::object()));
    std::vector<Handle<Zombie>> ids;
    for (auto& j:request.at("zombies")) ids.push_back(w.zombies.emplace(zombie(j)));
    Json states=Json::array();
    for (auto& op:request.at("operations")) {
        keys(op,{"index","surface","facing","amount"});
        const auto id=ids.at(op.at("index").get<size_t>());
        Json result=nullptr;
        if (op.value("surface",false)) result=surface_damage_zombie(w,id,op.at("facing"),op.at("amount"));
        else damage_zombie(w,id,op.at("facing"),op.at("amount"));
        auto s=snapshot(w); s["return"]=result; ;
    }
    return {{"states",states},{"rng",rng_state(w.rng)},{"branches",w.branches},
            {"damage_calls",w.damage_calls},{"surface_calls",w.surface_calls}};
}
static ShooterKind shooter_kind(const std::string& name) {
    if(name=="豌豆射手")return ShooterKind::pea;
    if(name=="寒冰射手")return ShooterKind::ice_pea;
    if(name=="双发射手")return ShooterKind::repeater;
    if(name=="杨桃")return ShooterKind::star;
    if(name=="仙人掌")return ShooterKind::cactus;
    if(name=="机枪射手")return ShooterKind::gatling;
    throw std::invalid_argument("unsupported shooter: "+name);
}
static Json shooter_case(const Json& request) {
    keys(request,{"mode","seed","tile","plk","plant","inputs","instrument"});
    CombatStages w(request.value("seed",int64_t(1)));
    w.tile=request.value("tile",48.); w.plk=request.value("plk",w.tile/10000.); w.instrument=request.value("instrument",false);
    const auto& j=request.at("plant");
    keys(j,{"植物","坐标","方向","射cd","射","双发","机枪"});
    Shooter p; p.kind=shooter_kind(j.at("植物")); p.row=j.at("坐标").at(0);p.col=j.at("坐标").at(1);
    p.facing=j.at("方向");p.cooldown=j.at("射cd");p.animation=j.at("射");
    p.double_shot=j.value("双发",0.);p.gatling_shot=j.value("机枪",0.);
    Json states=Json::array();
    for(const auto& input:request.at("inputs")) {
        keys(input,{"row_targets","zombie_count","emperor"});
        std::vector<double> targets;
        const bool present=input.contains("row_targets")&&!input.at("row_targets").is_null();
        if(present) targets=input.at("row_targets").get<std::vector<double>>();
        shooter_attack(w,p,present?&targets:nullptr,input.value("zombie_count",size_t(0)),input.value("emperor",false));
        auto s=snapshot(w);
        auto plant=j;plant["射cd"]=p.cooldown;plant["射"]=p.animation;
        if(p.kind==ShooterKind::repeater||j.contains("双发"))plant["双发"]=p.double_shot;
        if(p.kind==ShooterKind::gatling||j.contains("机枪"))plant["机枪"]=p.gatling_shot;
        s["plant"]=std::move(plant);;
    }
    return {{"states",states},{"rng",rng_state(w.rng)},{"branches",w.branches},{"shot_calls",w.shot_calls}};
}
static Json cell_json(Cell p) { return Json::array({p.y,p.x}); }
static Json cells_json(const std::vector<Cell>& cells) { Json j=Json::array();for(auto p:cells)j.push_back(cell_json(p));return j; }
static Json flood_case(const Json& request) {
    keys(request,{"mode","rows","cols","empty","valid","field","queue","cooldown","sign","inputs"});
    int rows=request.at("rows"), cols=request.at("cols");
    FloodTerrain map(rows,cols,request.at("empty").get<std::vector<uint8_t>>(),request.at("valid").get<std::vector<uint8_t>>());
    FloodState s;*s.field=request.at("field").get<std::vector<int>>();
    s.cooldown=request.value("cooldown",0);s.sign=request.value("sign",1);
    for(auto& p:request.at("queue"))s.queue->push_back({p.at(0),p.at(1)});
    Json states=Json::array();
    for(auto& input:request.at("inputs")) {
        keys(input,{"seed","player_position","tile","plants","has_target","surface","changes","valid_changes"});
        for(auto& c:input.value("changes",Json::array()))map.set_empty(c.at(0),c.at(1),c.at(2).get<int>()!=0);
        for(auto& c:input.value("valid_changes",Json::array()))map.set_valid(c.at(0),c.at(1).get<int>()!=0);
        Cell seed;
        if(input.contains("player_position"))seed=player_flood_seed({input.at("player_position").at(0),input.at("player_position").at(1)},input.at("tile"));
        else seed={input.at("seed").at(0),input.at("seed").at(1)};
        advance_flood(map,s,{input.value("plants",false),input.value("has_target",false),seed,input.value("surface",23.)});
        ;
    }
    return {{"states",states},{"calls",s.calls},{"expansions",s.expansions},{"neighbours",s.neighbours}};
}
static Json particles_case(const Json& request) {
    keys(request,{"mode","seed","tile","plk","presentation","terrain","state","inputs"});
    CombatStages w(request.value("seed",int64_t(1)));
    w.tile=request.value("tile",48.);w.plk=request.value("plk",w.tile/10000.);
    configure_particles(w,request.at("presentation"));
    const auto& terrain=request.at("terrain");
    keys(terrain,{"rows","cols","empty","valid","water"});
    FloodTerrain map(terrain.at("rows"),terrain.at("cols"),terrain.at("empty").get<std::vector<uint8_t>>(),
        terrain.at("valid").get<std::vector<uint8_t>>(),terrain.at("water").get<std::vector<uint8_t>>());
    for(const auto& p:request.at("state"))w.particle_state.push_back({p.at(0).get<Color>(),motion(p.at(1)),p.at(2)});
    Json states=Json::array();
    for(const auto& op:request.at("inputs")) {
        keys(op,{"emit","draw","shake"});
        w.particle_rects.clear();
        for(const auto& e:op.value("emit",Json::array()))
            w.emit_particles(e.at(0),{e.at(1).at(0),e.at(1).at(1)},e.at(2));
        const auto shake=op.value("shake",Json::array({0.,0.}));
        advance_particles(w,map,op.value("draw",true),{shake.at(0),shake.at(1)});
        ;
    }
    return {{"states",states},{"rng",rng_state(w.rng)}};
}
static Json physics_case(const Json& request) {
    keys(request,{"mode","tile","plk","terrain","state","inputs","periodic"});
    const double tile=request.value("tile",48.),plk=request.value("plk",tile/10000.);
    const auto& terrain=request.at("terrain");
    keys(terrain,{"rows","cols","empty","valid","water"});
    FloodTerrain map(terrain.at("rows"),terrain.at("cols"),terrain.at("empty").get<std::vector<uint8_t>>(),
        terrain.at("valid").get<std::vector<uint8_t>>());
    Motion m=motion(request.at("state"));Json states=Json::array();
    for(const auto& input:request.at("inputs")){
        keys(input,{"size","velocity","position","changes"});
        if(input.contains("velocity")){m.vx=input.at("velocity").at(0);m.vy=input.at("velocity").at(1);}
        if(input.contains("position")){m.x=input.at("position").at(0);m.y=input.at("position").at(1);}
        for(const auto& c:input.value("changes",Json::array()))map.set_empty(c.at(0),c.at(1),c.at(2).get<int>()!=0);
        const int collision=displace_body(m,input.at("size"),map,tile,plk,request.value("periodic",true));
        ;
    }
    return {{"states",states}};
}
static Json self_test() {
    size_t checks=0;
    auto test=[&](bool value,const char* message){require(value,message);++checks;};
    Store<Zombie> store;
    Zombie z;z.kind="ordinary";z.hp=100;
    auto first=store.emplace(z);auto* address=&store.at(first);
    auto second=store.emplace(z);auto third=store.emplace(z);
    for(int i=0;i<10000;++i)store.emplace(z);
    test(address==&store.at(first),"store invalidated live address");
    test(store.erase(second),"erase failed");
    auto recycled=store.emplace(z);
    test(recycled.index==second.index&&recycled.generation!=second.generation,"generation not changed");
    test(!store.find(second),"stale ID resolved");
    test(store.order().at(0)==first&&store.order().at(1)==third&&store.order().back()==recycled,"order changed");
    test(!store.erase(second),"stale erase affected live slot");
    Field<double> f;test(!f.present(),"missing value is present");
    f.set_null();test(f.present()&&f.is_null(),"None lost");
    bool threw=false;try{f.get();}catch(const std::logic_error&){threw=true;}test(threw,"None silently coerced");
    f.set(0);test(f.present()&&!f.is_null()&&f.get()==0,"zero confused with missing");
    f.erase();test(!f.present(),"field erase failed");
    Store<Zombie> independent=store;independent.at(first).hp=17;
    test(store.at(first).hp==100,"snapshot aliased mutable source");
    auto seed=player_flood_seed({-1,23},48);test(seed.y==-1&&seed.x==-1,"Python negative floor lost");
    return {{"passed",true},{"checks",checks}};
}
int main(int argc,char** argv) {
    try {
        if(argc==2&&std::string(argv[1])=="--self-test"){std::cout<<self_test().dump()<<'\n';return 0;}
        if(argc==2&&std::string(argv[1])=="--capabilities"){std::cout<<capabilities().dump()<<'\n';return 0;}
        std::ifstream file;std::istream* input=&std::cin;
        if(argc==2){file.open(argv[1],std::ios::binary);require(bool(file),"cannot open input");input=&file;}
        std::string line;
        while(std::getline(*input,line)) {
            if(line.empty())continue;
            const auto request=Json::parse(line);
            const std::string mode=request.at("mode");
            Json result;
            if(mode=="damage")result=damage_case(request);
            else if(mode=="shooter")result=shooter_case(request);
            else if(mode=="flood")result=flood_case(request);
            else if(mode=="particles")result=particles_case(request);
            else if(mode=="physics")result=physics_case(request);
            else throw std::invalid_argument("unsupported typed capability: "+mode+"; full PvP72 battle is not migrated");
            result["backend_actual"]="typed72-stages";result["fallback_count"]=0;
            std::cout<<result.dump()<<'\n';
        }
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<Json({{"error",e.what()},{"backend_actual","typed72-stages"},{"fallback_count",0}}).dump()<<'\n';
        return 2;
    }
}
