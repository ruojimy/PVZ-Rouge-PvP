#include "sim/pvp/hand/hero_monitor.h"
#include "sim/pvp/shim/pm_hero_guard.h"
#include <cstdio>
using namespace pvz;
int main() {
    int checks=0,failed=0;
    try {
        V battle=py::new_object(),engine=py::new_object();
        V first=py_dict({{V("玩家位置"),V::list({V(100),V(100)})},{V("玩家血量"),V(100)}});
        V second=py_dict({{V("玩家位置"),V::list({V(900),V(100)})},{V("玩家血量"),V(100)}});
        V states=py_dict({{V("plant"),first},{V("zombie"),second}});
        V globals=py_dict({{V("玩家位置"),first.get(V("玩家位置"))},{V("玩家血量"),V(100)}});
        V fields=py_dict({{V("hero_states"),states},{V("avatars"),py::copy(states)},
                {V("g"),globals},{V("tile"),V(48)},{V("width"),V(1536)},
                {V("tick"),V(0)},{V("engine"),engine},{V("mode"),V("pvp")}});
        for(auto& kv:fields.kv())
            pvz::setattr(battle,kv.first.sym(),kv.second);
        pvz::setattr(engine,Sym("native_tick"),V(0));
        V guard=pm_hero_guard::new_HeroGuard(Args{battle});
        pvz::setattr(battle,Sym("hero_guard"),guard);
        callm(guard,Sym("check"),Args{V("init")});++checks;
        auto reject=[&](const char* kind,auto action) {
            ++checks;auto before=pm_hero_guard::violation_count();bool caught=false;
            try{action();}catch(PyError& e){caught=e.matches("AssertionError") && std::string(e.what()).find(kind)!=std::string::npos;if(!caught)fprintf(stderr,"unexpected: %s\n",e.what());}
            if(!caught || pm_hero_guard::violation_count()!=before+1){++failed;fprintf(stderr,"FAIL negative control %s\n",kind);}
        };
        reject("alias",[&] {
            V old=second.get(V("玩家位置"));second.at(V("玩家位置"))=first.get(V("玩家位置"));
            try{callm(guard,Sym("check"),Args{V("spawn")});}
            catch(...){second.at(V("玩家位置"))=old;throw;}
            second.at(V("玩家位置"))=old;
        });
        reject("jump",[&] {
            pm_hero_guard::TickScope scope(battle);
            pvz::setitem(first.get(V("玩家位置")),V(0),V(500));
        });
        // A move between ticks is an allowed fixture change.
        {pm_hero_guard::TickScope scope(battle);}++checks;
        reject("spawn",[&] {
            pm_hero_guard::SpawnScope scope(battle);globals.at(V("玩家血量"))=V(1);
        });
        {pm_hero_guard::SpawnScope scope(battle);}++checks;
    }catch(const std::exception& e){++failed;fprintf(stderr,"ERROR: %s\n",e.what());}
    printf("HERO GUARD CONFORMANCE: %d checks, %d failures\n",checks,failed);
    return failed?1:0;
}
