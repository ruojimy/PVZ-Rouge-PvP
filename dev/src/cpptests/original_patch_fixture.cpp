// Native equivalent of load_real_patch's compile/exec bootstrap; no assertions are replaced.
#include "cpptests/gen/pm_test_pvp_legacy.h"
#include "sim/pvp/gen/pm_native_runtime.h"
namespace pvz::pm_test_pvp_legacy {
V f_load_real_patch(const Args&) {
    V text=callm(SOURCE,Sym("read_text"),Args({},{{Sym("encoding"),V("utf-8")}}));
    // The product loader verifies the complete original source SHA and executes
    // the compiled original definitions (not a result transcript or a PvP rewrite).
    V ns=pm_native_runtime::f_load_patch(Args{text});
    pvz::setitem(ns,V("__name__"),V("pvz_test_authoritative_patch"));
    return ns;
}
}
