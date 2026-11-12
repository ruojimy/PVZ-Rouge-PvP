"""patch_timing.py <match_probe.cpp>: opt-in MATCH_NO_TRACE=1 skips the per-tick JSON trace (the record
is still built for nothing else), and the report gains sim_seconds, the wall time of the room loop, so
simulation throughput can be measured without trace serialization dominating."""
import sys
from pathlib import Path
p=Path(sys.argv[1]);t=p.read_text(encoding='utf8')
if 'sim_seconds' in t:raise SystemExit('already patched')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a[:70])
    t=t.replace(a,b)
sub("    void write_record(){(*out)<<record().dump(-1,' ',false,J::error_handler_t::replace)<<'\\n';pending_inputs=J::array();calls.clear();}",
    "    const bool no_trace=std::getenv(\"MATCH_NO_TRACE\")!=nullptr;\n"
    "    void write_record(){if(!no_trace)(*out)<<record().dump(-1,' ',false,J::error_handler_t::replace)<<'\\n';pending_inputs=J::array();calls.clear();}")
sub('        try {for(match.current_room=0;match.current_room<ticks;++match.current_room){',
    '        const auto sim_started=std::chrono::steady_clock::now();\n        try {for(match.current_room=0;match.current_room<ticks;++match.current_room){')
sub('        catch(const std::exception& error){failure=error.what();}\n',
    '        catch(const std::exception& error){failure=error.what();}\n'
    '        const double sim_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-sim_started).count();\n')
sub('{"unsupported_operations",match.unsupported},','{"unsupported_operations",match.unsupported},{"sim_seconds",sim_seconds},')
if '#include <chrono>' not in t:t='#include <chrono>\n'+t
p.write_text(t,encoding='utf8');print('ok',p)
