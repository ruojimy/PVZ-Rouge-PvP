// Diagnostic only: reveal the original native exception before CPython traceback-only logging.
#include "cpptests/gen/pm_test_pvp_native_units.h"
#include <nlohmann/json.hpp>
#include <fstream>
namespace pvz::cpptests {
void install_units_probe() {
    py::register_native_hook("test.units.probe",[](const Args& a){
        using json=nlohmann::json;json report;
        pm_test_pvp_native_units::init();
        pm_test_pvp_native_units::C_NativeUnits::m_setUpClass(Args{});
        V test=pm_test_pvp_native_units::new_NativeUnits(Args{});
        V engine=callm(test,Sym("make"),Args{});
        callm(engine,Sym("spawn_plant"),Args{V("豌豆射手"),V(12),V(9)});
        V zombie=rd(callm(engine,Sym("spawn_zombie"),Args{V("普通僵尸"),V(580),V(624)}),V(0));
        pvz::setitem(zombie,V("出场"),V(500));
        auto trace=[](const V& value){
            auto steps=std::make_shared<std::vector<std::string>>();
            for(const char* name:{"execute","draw_plants"}){
                V original=pvz::getattr(value,Sym(name));std::string method(name);
                pvz::setattr(value,Sym(name),V::func([original,method,steps](const Args& args){
                    if(steps->size()==16)steps->erase(steps->begin());
                    steps->push_back(method+(args.pos.empty()?"":":"+py_str(args.pos[0])));
                    return original.call(args);
                }));
            }
            return steps;
        };
        auto steps=trace(engine);
        try{callm(test,Sym("ticks"),Args{engine,V(1)});report["success"]=true;}
        catch(const PyError& error){report["success"]=false;report["error"]=error.what();}
        report["steps"]=*steps;
        report["night"]=json::array();
        V base=pvz::getattr(test,Sym("base"));
        V names=py::iter_list(rd(pvz::getattr(base,Sym("g")),V("夜间植物")));
        for(const V& name:names.items()){
            if(!pm_test_pvp_native_units::PLANTS.contains(name))continue;
            bool water=name==V("海蘑菇");V row(water?10:12);json result{{"plant",name.str()}};
            V night=callm(test,Sym("make"),Args{V(water)});auto trail=trace(night);
            try{
                callm(night,Sym("spawn_plant"),Args{name,row,V(9)});
                V game=pvz::getattr(night,Sym("g"));
                pvz::setitem(game,V("sbx"),V(9));pvz::setitem(game,V("sby"),row);pvz::setitem(game,V("fx"),V(1));
                callm(night,Sym("execute"),Args{V("coffee")});
                V target=rd(callm(night,Sym("spawn_zombie"),Args{V(water?"鸭子普通僵尸":"铁桶僵尸"),V(505),V(water?480:624)}),V(0));
                pvz::setitem(target,V("出场"),V(500));
                callm(test,Sym("ticks"),Args{night,V(1500)});result["success"]=true;
            }catch(const PyError& error){result["success"]=false;result["error"]=error.what();}
            result["last_steps"]=*trail;report["night"].push_back(result);
        }
        std::ofstream output(a.pos.at(0).str(),std::ios::binary);if(!output)throw PyError("OSError","Cannot write units probe");output<<report.dump(2);
        pm_test_pvp_native_units::C_NativeUnits::m_tearDownClass(Args{});
        return V::none();
    });
}
}
