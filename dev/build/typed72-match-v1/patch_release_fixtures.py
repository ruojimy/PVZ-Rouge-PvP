"""Opt-in MATCH_RELEASE_FIXTURES=1: after every native tick drop the probe chain's fixture containers
(units/births references, recorder logs), so no fixture extends a unit's or entity's lifetime. Running
the full scenario set with and without it shows whether fixture retention affects the simulation."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'release_fixtures' in t:raise SystemExit('already patched')
a='    void native_tick_done()override{++typed_ticks;flush_journal();write_record();}'
assert t.count(a)==1
t=t.replace(a,'''    const bool release_fixtures=std::getenv("MATCH_RELEASE_FIXTURES")!=nullptr;
    void native_tick_done()override{++typed_ticks;flush_journal();write_record();
        if(release_fixtures){units.clear();births.clear();render_log=J::array();calls=J::array();}}''')
p.write_text(t,encoding='utf8');print('ok')
