// Source-verified frozen full-scan algorithm for the unchanged differential tests.
#include "cpptests/dart_reference_fixture.h"
#include "core/fsutil.h"
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace pvz::cpptests {
static V dart_fixture_attr(Sym name) {
    const char* root=std::getenv("PVZ_TEST_ROOT");
    if(!root || !*root)throw PyError("RuntimeError","Dart reference requires an isolated verified fixture");
    std::ifstream input(u8p(std::string(root)+"/tests/fixtures_dart_reference67.py"),std::ios::binary);
    if(!input)throw PyError("RuntimeError","Missing original frozen dart reference fixture");
    std::ostringstream source;source<<input.rdbuf();
    V hash=py::stdlib_call(V("hashlib.sha256"),Args{V::bytes(source.str())});
    if(callm(hash,Sym("hexdigest"),Args{}).str()!="d914a896ce7a9ae0fe30d361ddad58672602683e17d28d90f0b8221e9d89bb0b")
        throw PyError("RuntimeError","Original frozen dart reference fingerprint mismatch");
    return pvz::getattr(pm_fixtures_dart_reference67::module_ns(),name);
}
void install_dart_reference_fixture() {
    py::register_module_attrs("fixtures_dart_reference67",dart_fixture_attr);
    py::register_module("fixtures_dart_reference67",py::module_ns(V("fixtures_dart_reference67")));
}
}
