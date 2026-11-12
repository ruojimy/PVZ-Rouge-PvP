"""Translate the two original legacy scenario input helpers; no reference results."""
import ast
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pvp2cpp as g

ROOT = Path(__file__).resolve().parents[1]
SOURCE = g.TESTS/'legacy_pvp_simulation.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
functions = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('flat_map','battle')]
assert len(functions)==2
imports = ast.parse('from .catalog import RULES\nfrom .simulation import Battle\n').body
module = ast.Module(body=imports+functions,type_ignores=[])
ast.fix_missing_locations(module)
g.MODULES['legacy_pvp_simulation'] = g.ModuleInfo('legacy_pvp_simulation',module)
g.GEN_UI[0] = False
gen = g.Gen('legacy_pvp_simulation')
header, cpp = gen.run()
assert not gen.todo, gen.todo
digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
cpp = cpp.replace('#include "sim/pvp/gen/pm_legacy_pvp_simulation.h"','#include "cpptests/legacy_fixture.h"')
cpp = cpp.replace('from modkit/pvp/legacy_pvp_simulation.py','from tests/legacy_pvp_simulation.py (test stimulus only)')
cpp += r'''
#include "pg/pg.h"
#include "core/fsutil.h"
#include <cstdlib>
#include <fstream>
#include <sstream>
namespace pvz::cpptests {
static void verify_legacy_input_source() {
    const char* root = std::getenv("PVZ_TEST_ROOT");
    if (!root) throw PyError("RuntimeError", "Legacy scenario helper requires the isolated verified fixture");
    std::ifstream file(u8p(std::string(root) + "/tests/legacy_pvp_simulation.py"), std::ios::binary);
    if (!file) throw PyError("RuntimeError", "Missing original legacy test helper fixture");
    std::ostringstream text; text << file.rdbuf();
    V hash = py::stdlib_call(V("hashlib.sha256"), Args{V::bytes(text.str())});
    if (callm(hash, Sym("hexdigest"), Args{}).str() != "@DIGEST@")
        throw PyError("RuntimeError", "Original legacy scenario helper fingerprint mismatch");
}
void install_legacy_fixture() {
    V module = pg::new_module("legacy_pvp_simulation");
    pg::module_of(module)->fn("flat_map", [](const Args& a) {
        verify_legacy_input_source(); pm_legacy_pvp_simulation::init();
        return pm_legacy_pvp_simulation::f_flat_map(a);
    });
    pg::module_of(module)->fn("battle", [](const Args& a) {
        verify_legacy_input_source(); pm_legacy_pvp_simulation::init();
        return pm_legacy_pvp_simulation::f_battle(a);
    });
    py::register_module("legacy_pvp_simulation", module);
}
}
'''.replace('@DIGEST@',digest)
(ROOT/'src/cpptests/legacy_fixture.h').write_text(header,encoding='utf-8')
(ROOT/'src/cpptests/legacy_fixture.cpp').write_text(cpp,encoding='utf-8')
provenance = dict(role='native test stimulus, not a Python oracle',source=str(SOURCE),source_sha256=digest,
    functions=[dict(name=n.name,line=n.lineno,ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest()) for n in functions],
    generator_sha256=hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),translation_todo=gen.todo)
(ROOT/'extract/schema/legacy-scenario-fixture.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
print('Translated original scenario input helpers:',[n.name for n in functions])
