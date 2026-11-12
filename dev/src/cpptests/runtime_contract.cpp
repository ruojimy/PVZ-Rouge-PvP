// Test-only probes execute the production container/profiler implementation.
#include "sim/pvp/pvprt.h"
#include "sim/pvp/gen/pm_native_phase_profiler.h"
#include "ui/gen/pm_rendering.h"
#include "cpptests/argument_fixture.h"
#include <nlohmann/json.hpp>
#include <fstream>
namespace pvz::cpptests {
nlohmann::json snapshot_contract(const nlohmann::json& spec);
void install_runtime_contract() {
    py::register_native_hook("test.runtime.report",[](const Args& a){
        using json=nlohmann::json;
        std::ifstream input(a.pos.at(0).str(),std::ios::binary);
        if(!input)throw PyError("OSError","Cannot read runtime inputs");
        json spec=json::parse(input),report;
        auto v=[](const json& value){return py::json_loads(V(value.dump()));};
        auto j=[](const V& value){return json::parse(py::stdlib_call(V("json.dumps"),Args{value}).str());};
        pm_native_argument_fixture::init();
        report["arguments"]=json::array({j(pm_native_argument_fixture::f_run_order(Args{})),j(pm_native_argument_fixture::f_run_duplicate(Args{})),j(pm_native_argument_fixture::f_run_bad_mapping(Args{}))});
        report["sets"]=json::array();
        for(const auto& row:spec.at("sets")){
            V left=py::set_it(v(row.at(0))),right=py::set_it(v(row.at(1)));
            report["sets"].push_back(json::array({left<right,left<=right,left==right,left>=right,left>right}));
        }
        report["deques"]=json::array();
        for(const auto& row:spec.at("deques")){
            json states=json::array();V deque;
            try {
                deque=py::stdlib_call(V("collections.deque"),Args({v(row.at("initial"))},{{Sym("maxlen"),v(row.at("maxlen"))}}));
            }catch(const PyError& error){report["deques"].push_back(json{{"error",error.kind}});continue;}
            for(const auto& action:row.at("actions")){
                json state;std::string op=action.at(0).get<std::string>();V result=V::none();
                try{
                    if(op=="getitem")result=rd(deque,v(action.at(1)));
                    else if(op=="setitem")pvz::setitem(deque,v(action.at(1)),v(action.at(2)));
                    else if(op=="delitem")pvz::delitem(deque,v(action.at(1)));
                    else if(op=="contains")result=V(deque.contains(v(action.at(1))));
                    else if(op=="copy_append") {V copy=callm(deque,Sym("copy"),Args{});callm(copy,Sym("append"),Args{v(action.at(1))});result=py::list_it(copy);}
                    else {std::vector<V> args;for(size_t i=1;i<action.size();++i)args.push_back(v(action.at(i)));result=callm(deque,Sym(op),Args(args));}
                    state["result"]=j(result);
                }catch(const PyError& error){state["error"]=error.kind;}
                state["values"]=j(py::list_it(deque));state["maxlen"]=j(pvz::getattr(deque,Sym("maxlen")));states.push_back(state);
            }
            report["deques"].push_back(states);
        }
        report["profiles"]=json::array();
        pm_native_phase_profiler::init();
        for(const auto& row:spec.at("profiles")){
            V profile=pm_native_phase_profiler::new_PhaseProfiler(Args({},{{Sym("limit"),v(row.at("limit"))},{Sym("rolling"),v(row.at("rolling"))}}));
            for(const auto& sample:row.at("values"))callm(profile,Sym("record"),Args{v(sample.at(0)),v(sample.at(1))});
            report["profiles"].push_back(j(callm(profile,Sym("summary"),Args{})));
        }
        if(spec.contains("ordered_dicts")) {
            report["ordered_dicts"]=json::array();
            for(const auto& test:spec["ordered_dicts"]) {
                V dictionary=py::stdlib_call(V("collections.OrderedDict"),Args{v(test["initial"])});
                json states=json::array();
                for(const auto& action:test["actions"]) {
                    std::string op=action[0].get<std::string>();json state;V result=V::none();
                    try {
                        if(op=="set")dictionary.at(v(action[1]))=v(action[2]);
                        else if(op=="move")result=callm(dictionary,Sym("move_to_end"),Args{v(action[1]),v(action[2])});
                        else if(op=="pop")result=callm(dictionary,Sym("popitem"),Args({},{{Sym("last"),v(action[1])}}));
                        else if(op=="delete")dictionary.erase(v(action[1]));
                        else if(op=="get")result=dictionary.get(v(action[1]),v(action[2]));
                        else if(op=="clear")result=callm(dictionary,Sym("clear"),Args{});
                        else if(op=="copy") {
                            V shallow=py::copy(dictionary),deep=py::deepcopy(dictionary);
                            result=V::tuple({py::items(shallow),py::items(deep),V(pvz::hasattr(shallow,Sym("move_to_end"))),V(pvz::hasattr(deep,Sym("move_to_end")))});
                            callm(shallow,Sym("clear"),Args{});
                        } else throw PyError("ValueError","Unknown ordered mapping probe operation");
                        state["result"]=j(result);
                    } catch(const PyError& error) {state["error"]=error.kind;}
                    state["items"]=j(py::items(dictionary));
                    state["type"]=pvz::getattr(py::type(dictionary),Sym("__name__")).str();
                    state["ordered_method"]=pvz::hasattr(dictionary,Sym("move_to_end"));states.push_back(state);
                }
                report["ordered_dicts"].push_back(states);
            }
        }
        if(spec.contains("snapshot"))report["snapshot"]=snapshot_contract(spec["snapshot"]);
        V renderer=callm(pm_rendering::cls_Renderer(),Sym("__new__"),Args{pm_rendering::cls_Renderer()});
        pvz::setattr(renderer,Sym("text_scale"),V(2));pvz::setattr(renderer,Sym("custom_probe"),V(7));
        V view=py::builtin_call(V("vars"),Args{renderer});
        report["vars"]["initial"]=j(callm(view,Sym("copy"),Args{}));
        pvz::setitem(view,V("text_scale"),V(3));pvz::setattr(renderer,Sym("custom_probe"),V(8));
        report["vars"]["live"]=j(callm(view,Sym("copy"),Args{}));
        pvz::delitem(view,V("text_scale"));report["vars"]["deleted"]=j(callm(view,Sym("copy"),Args{}));
        std::ofstream output(a.pos.at(1).str(),std::ios::binary);if(!output)throw PyError("OSError","Cannot write runtime report");output<<report.dump();
        return V::none();
    });
}
}
