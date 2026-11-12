#include "sim/pvp/shim/pm_native_candidates.h"
#include <cstdlib>
namespace pvz::pm_native_candidates {
V f_install(const Args& a) {
    V battle=a.get(0,Sym("battle"),nullptr,"install"),none=V::none();
    V jobs=a.get(1,Sym("jobs"),&none);
    const char* configured=std::getenv("PVP_CANDIDATE_MIN_PAIRS");
    V minimum=configured?py::int_(V(configured)):V(256);
    V scan=new_StarDamageScan(Args{pvz::getattr(pvz::getattr(battle,Sym("patch")),Sym("ns")),jobs,minimum});
    callm(scan,Sym("install"),Args{});
    return V::list({scan});
}
}
