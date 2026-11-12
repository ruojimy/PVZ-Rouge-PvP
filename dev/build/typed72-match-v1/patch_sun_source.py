"""native_battle.py:243-252 owned_plant_gate (installed only with more than one plant seat, outermost
around the content and tracking plant gates) and :2412 _finish_sun_source: every native sun a plant's
turn creates belongs to that plant's seat. Economy::sun_owner already reads NativeSun::producer;
the match chain left finish_sun_source as a recording fixture and never set the producer."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'sun_source_start' in t:raise SystemExit('already patched')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a)
    t=t.replace(a,b)
sub('''    void plant_gate(size_t i)override{
        const auto plant=battle.plant_roster->at(i);
''','''    // owned_plant_gate / _finish_sun_source: (first new loose sun, seat) of the plant now running.
    std::optional<std::pair<size_t,Seat>> sun_source_start;
    bool multi_plant_seats()const{return std::count_if(seated_seats.begin(),seated_seats.end(),[](Seat s){return team_of(s)==Seat::plant;})>1;}
    void finish_sun_source()override{
        if(!sun_source_start)return;
        const auto [start,seat]=*sun_source_start;
        for(size_t k=start;k<world_region.loose_suns.size();++k)world_region.loose_suns[k]->producer=seat;
        sun_source_start.reset();
    }
    void plant_gate(size_t i)override{
        const bool owned=multi_plant_seats();
        if(owned)finish_sun_source();
        const size_t sun_start=world_region.loose_suns.size();
        const auto plant=battle.plant_roster->at(i);
''')
CATTAIL='香蒲'
sub('        if(plant->kind=="'+CATTAIL+'")chart.tracking_index(source);\n        ContentPhaseProbe::plant_gate(i);\n    }\n',
    '        if(plant->kind=="'+CATTAIL+'")chart.tracking_index(source);\n        ContentPhaseProbe::plant_gate(i);\n'
    '        // Reached only when the inner gates return normally, as in the source wrapper.\n'
    '        if(owned)sun_source_start={sun_start,plant->source.seat.value_or(Seat::plant)};\n    }\n')
p.write_text(t,encoding='utf8');print('ok')
