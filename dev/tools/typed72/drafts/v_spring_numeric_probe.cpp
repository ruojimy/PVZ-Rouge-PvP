// Same-rule V integration entry for the retained spring target tie fixture.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/pymath.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_native_content.h"
#include "sim/pvp/gen/pm_pvp64_content.h"
#include <fstream>
#include <iostream>

using namespace pvz;
using J=nlohmann::json;
namespace {
V decode(const J& value) {
    if(value.is_null())return V::none();
    if(value.is_boolean())return V(value.get<bool>());
    if(value.is_number())return V(value.get<double>());
    if(value.is_string())return V(value.get<std::string>());
    if(value.is_array()){V result=V::list();for(const auto& item:value)result.append(decode(item));return result;}
    V result=V::dict();for(const auto& [key,item]:value.items())setitem(result,V(key),decode(item));return result;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: v_spring_numeric_probe fixture output");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");
        SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);
        SDL_setenv("PVP_USERDATA","test_results/typed72-20261105/v-spring-userdata",1);
        pg::install_pygame();init_pvp_modules();
        std::ifstream input(argv[1]);J fixture;input>>fixture;
        auto match=battle_from_scenario({{"seed",fixture.at("seed")},{"mode","duel"},
            {"decks",{{"plant",{"plant:弹簧草","plant:向日葵"}},
                      {"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}}}});
        auto* battle=as<pm_native_battle::C_NativeBattle>(match.battle);
        if(!battle)throw std::runtime_error("V NativeBattle construction failed");
        battle->a_width=V(fixture.at("world_rules").at("width").get<double>());
        setitem(battle->a_g,SV("僵尸"),V::list());
        const auto spawn=[&](const char* card,const char* side) {
            const auto unit=battle->m_spawn(Args{V(card),V(side),V(264.),V(432.),V(1.)});
            return rd(battle->a__native_objects,rd(unit,SV("id")));
        };
        V plant=spawn("plant:弹簧草","plant");
        setitem(plant,SV("坐标"),V::nums({8.,5.}));setitem(plant,SV("方向"),V(1.));
        std::vector<V> units;
        for(int index=0;index<4;++index)units.push_back(spawn("zombie:普通僵尸","zombie"));
        // The reference coop fixture contains ordinary units only. Admit them
        // through the actual duel spawn path, then exclude its hero target.
        setitem(rd(battle->a_avatars,SV("zombie")),SV("玩家血量"),V(0.));
        for(const auto& operation:fixture.at("operations")) {
            const auto name=operation.at("op").get<std::string>();
            if(name=="plant_unit") {
                const V unit=units.at(operation.at("unit").get<size_t>());
                for(const auto& [key,value]:operation.at("fields").items())setitem(unit,V(key),decode(value));
                for(const auto& key:operation.value("erase",std::vector<std::string>{}))
                    callm(unit,SY("pop"),Args{V(key),V::none()});
            }else if(name=="source_write" && operation.contains("unit_source")) {
                const V unit=units.at(operation.at("unit_source").get<size_t>());
                for(const auto& [key,value]:operation.at("values").items())setitem(unit,V(key),decode(value));
            }
        }
        auto* content=as<pm_native_content::C_NativeContent>(battle->a_content);
        auto* controller=as<pm_pvp64_content::C_PvP64Content>(content->a_pvp64);
        if(!controller)throw std::runtime_error("V PvP64 controller missing");
        J rows=J::array();
        for(const auto& unit:units) {
            const V point=content->m_point(Args{unit});
            const double dx=point.idx(0).num()-264.,dy=point.idx(1).num()-(8.+.45)*48.;
            rows.push_back({{"id",py_str(rd(unit,SV("_pvp_id")))},{"before_hp",rd(unit,SV("血量")).num()},
                {"dx",dx},{"dy",dy},{"std_hypot",std::hypot(dx,dy)},{"python38_hypot",py::hypot(dx,dy)}});
        }
        const V fired=controller->m_spring(Args{plant});
        for(size_t index=0;index<units.size();++index)rows[index]["after_hp"]=rd(units[index],SV("血量")).num();
        const V swipe=controller->a_swipes.idx(int64_t(controller->a_swipes.len())-1);
        J report={{"backend_actual","existing-v-battle-controller"},{"full_product_acceptance",false},
            {"fired",fired.truthy()},{"axis",swipe.idx(3).num()},{"units",rows}};
        callm(match.battle,SY("close"),Args{});
        std::ofstream output(argv[2]);output<<report.dump(2)<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
