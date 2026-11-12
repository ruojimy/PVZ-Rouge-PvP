// The original helper builds a real authority room and native units. It is not a reference transcript.
#include "cpptests/guest_cost_fixture.h"
#include "core/fsutil.h"
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace pvz::cpptests {
static V guest_cost_attr(Sym name) {
    const char* root=std::getenv("PVZ_TEST_ROOT");
    if(!root || !*root)throw PyError("RuntimeError","Guest cost helper requires an isolated verified fixture");
    std::ifstream input(u8p(std::string(root)+"/tests/probe_pvp_net_guest_cost.py"),std::ios::binary);
    if(!input)throw PyError("RuntimeError","Missing original guest cost helper fixture");
    std::ostringstream source;source<<input.rdbuf();
    V hash=py::stdlib_call(V("hashlib.sha256"),Args{V::bytes(source.str())});
    if(callm(hash,Sym("hexdigest"),Args{}).str()!="b564eaeed83d2ee84186437df0b9d81eb3195efa1a4d2090a5368ca34433a77a")
        throw PyError("RuntimeError","Original guest cost helper fingerprint mismatch");
    return pvz::getattr(pm_probe_pvp_net_guest_cost::module_ns(),name);
}
void install_guest_cost_fixture() {
    py::register_module_attrs("probe_pvp_net_guest_cost",guest_cost_attr);
    py::register_module("probe_pvp_net_guest_cost",py::module_ns(V("probe_pvp_net_guest_cost")));
}
}
