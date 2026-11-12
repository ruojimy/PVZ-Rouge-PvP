#define PVZ72_TARGET_PROBE_EMBEDDED
#include "targets_probe.cpp"
#include "sim/typed/zombie_spawn.h"
namespace {
J original_unit(const CombatZombie& u) {
    J j=body_state(u.body);const auto& n=u.native;const auto& b=u.body;
#define NUM(field,key) write(j,key,n.field);
    PVZ72_ZOMBIE_NATIVE_NUMBERS(NUM)
#undef NUM
    write(j,"大小",b.size);write(j,"气球",b.balloon);write(j,"撑杆",b.pole_vault);write(j,"跳舞",b.dancing);write(j,"入水",b.in_water);
    write(j,"眩晕",b.stun);write(j,"篮球",u.protection.basketball);write(j,"出土",n.emerged);write(j,"手持动画",n.hand_animation);
    const auto point=[&](const char* key,const Field<Point>& p){if(p.present())j[key]=p.is_null()?J(nullptr):J::array({p.get().x,p.get().y});};
    point("出场初位置",n.entry_start);point("出场末位置",n.entry_end);point("绳初位置",n.rope_start);return j;
}
NativeSpawnMode spawn_mode(const std::string& s) {
    if(s=="正常模式")return NativeSpawnMode::normal;if(s=="极难模式")return NativeSpawnMode::extreme;
    if(s=="末日模式")return NativeSpawnMode::doomsday;if(s=="无尽模式")return NativeSpawnMode::endless;
    if(s=="测试模式")return NativeSpawnMode::test;if(s=="抽奖模式")return NativeSpawnMode::lottery;return NativeSpawnMode::other;
}
J run_spawn(const J& j) {
    keys(j,{"seed","tile","plk","mode","player","rows","cols","height","bosses","operations"});TypedBattleState world(j.value("seed",int64_t(1)));
    auto& w=world.runtime;w.tile=j.at("tile");w.plk=j.at("plk");ZombieSpawnInput input;
    input.mode=spawn_mode(j.at("mode"));input.player={j.at("player")[0],j.at("player")[1]};input.map_rows=j.at("rows");input.map_cols=j.at("cols");
    input.screen_height=j.at("height");input.bosses=j.at("bosses").get<std::vector<std::string>>();J states=J::array();
    for(const auto& op:j.at("operations")) {
        keys(op,{"name","position","facing","mutate_after"});auto pos=motion(op.at("position"));spawn_original_zombie(world,op.at("name"),pos,op.at("facing"),input);
        J row={{"input_after",as_json(pos)},{"units",J::array()},{"entities",J::array()},{"sounds",J::array()},{"source_kinds",J::array()}};
        if(op.value("mutate_after",false))pos={9000.,8000.,7000.,6000.};
        for(const auto id:world.units.order()){const auto& u=*world.units.at(id);row["units"].push_back(original_unit(u));row["source_kinds"].push_back(u.source.zombie_name());}
        for(const auto& entity:*w.entities.list()) {
            const auto& e=*entity;J item={{"名",e.kind},{"方向",e.facing},{"位置",as_json(e.motion.get())}};
            write(item,"牛顿",e.gravity);write(item,"消亡",e.expires);row["entities"].push_back(std::move(item));
        }
        for(const auto& s:w.sounds)row["sounds"].push_back(J::array({s.name,J::array({s.position.x,s.position.y})}));
        auto rng=w.rng.state();row["rng"]=J::array();for(auto value:rng.mt)row["rng"].push_back(value);row["rng"].push_back(rng.mti);
        row["roster_matches_store"]=world.targets->size()==world.units.size();states.push_back(std::move(row));
    }
    return states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: spawn72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open spawn probe files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_spawn(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write spawn results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
