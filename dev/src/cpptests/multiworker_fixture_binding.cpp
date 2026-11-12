// Lazy source-verified binding of the original scenario helper, not an output replay.
#include "cpptests/multiworker_fixture.h"
#include "core/fsutil.h"
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace pvz::cpptests {
static V fixture_attr(Sym name) {
    const char* root=std::getenv("PVZ_TEST_ROOT");
    if(!root || !*root) throw PyError("RuntimeError","Multiworker helper requires an isolated verified fixture");
    std::ifstream input(u8p(std::string(root)+"/tests/multiworker_fixtures.py"),std::ios::binary);
    if(!input) throw PyError("RuntimeError","Missing original multiworker helper fixture");
    std::ostringstream text;text<<input.rdbuf();
    V digest=py::stdlib_call(V("hashlib.sha256"),Args{V::bytes(text.str())});
    if(callm(digest,Sym("hexdigest"),Args{}).str()!="89e66daeacdee3669c108b7298d547ec7b391553990e06816beb5f37b9a06bc6")
        throw PyError("RuntimeError","Original multiworker helper fingerprint mismatch");
    // module_ns installs the generated table after validation and initializes actual constants.
    V module=pm_multiworker_fixtures::module_ns();
    return pvz::getattr(module,name);
}
void install_multiworker_fixture() {
    py::register_module_attrs("multiworker_fixtures",fixture_attr);
    py::register_module("multiworker_fixtures",py::module_ns(V("multiworker_fixtures")));
}
}
