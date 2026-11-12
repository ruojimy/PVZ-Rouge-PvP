"""Opt-in MATCH_GATE_TICKS=t0:t1 (+ MATCH_GATE_LOG=path): after each zombie/plant gate chain, the
match RNG digest, matching ref72_record v3's REF_GATE_TICKS "rd" field, so the unit whose turn
advanced the RNG a different number of times can be found. No effect without the variables."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'gate_rng_log' in t:raise SystemExit('already patched')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a)
    t=t.replace(a,b)
sub('''    void zombie_gate(size_t i)override{
        if(const auto& unit=battle.targets->at(i).unit)path_banks.select_rally(*unit);
        ContentPhaseProbe::zombie_gate(i);expansion.zombie_gate(battle.targets->at(i).unit);
    }
''','''    std::pair<int64_t,int64_t> gate_window=[]{const char* s=std::getenv("MATCH_GATE_TICKS");long long a=-1,b=-2;if(!s||std::sscanf(s,"%lld:%lld",&a,&b)!=2){a=-1;b=-2;}return std::pair<int64_t,int64_t>{a,b};}();
    std::unique_ptr<std::ofstream> gate_rng_log=[]{const char* s=std::getenv("MATCH_GATE_LOG");return s?std::make_unique<std::ofstream>(s,std::ios::binary):std::unique_ptr<std::ofstream>{};}();
    void gate_rng(const char* hook,size_t index){
        const auto tick=battle.heroes.tick;if(!gate_rng_log||tick<gate_window.first||tick>gate_window.second)return;
        *gate_rng_log<<"{\\"t\\":"<<tick<<",\\"hook\\":\\""<<hook<<"\\",\\"l\\":"<<index<<",\\"rd\\":"<<hex_digest(battle.runtime.rng).dump()<<"}\\n";gate_rng_log->flush();
    }
    void zombie_gate(size_t i)override{
        if(const auto& unit=battle.targets->at(i).unit)path_banks.select_rally(*unit);
        ContentPhaseProbe::zombie_gate(i);expansion.zombie_gate(battle.targets->at(i).unit);
        gate_rng("zombie",i);
    }
''')
sub('        if(owned)sun_source_start={sun_start,plant->source.seat.value_or(Seat::plant)};\n',
    '        if(owned)sun_source_start={sun_start,plant->source.seat.value_or(Seat::plant)};\n        gate_rng("plant",i);\n')
p.write_text(t,encoding='utf8');print('ok')
