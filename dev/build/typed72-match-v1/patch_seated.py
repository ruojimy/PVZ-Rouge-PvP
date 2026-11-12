"""simulation.Battle: players (and NativeBattle avatars/hero_states) exist for every seat,
ordered ("plant","zombie")+others; the "zombie" seat is a faction anchor even when it is
not in `present` (coop/pve: a dormant record). `commands`/`rally_points` exist only in duo."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b,n=1):
    global t
    assert t.count(a)==n,(t.count(a),a)
    t=t.replace(a,b)
if 'seated_seats' in t:raise SystemExit('already patched')
# Every seat with a player record, in simulation.Battle order.
sub('present=tick_state.present;\n','''present=tick_state.present;
        seated_seats.clear();for(const auto& [name,row]:cold.at("players").items())seated_seats.push_back(parse_seat(name));
        std::stable_sort(seated_seats.begin(),seated_seats.end(),[](Seat a,Seat b){const auto rank=[](Seat s){return s==Seat::plant?0:s==Seat::zombie?1:2+int(seat_index(s));};return rank(a)<rank(b);});
''')
sub('        for(const auto seat:tick_state.present) {\n            const auto& player=cold.at("players").at(seat_name(seat));const auto& avatar=cold.at("avatars").at(seat_name(seat));',
    '        for(const auto seat:seated_seats) {\n            const auto& player=cold.at("players").at(seat_name(seat));const auto& avatar=cold.at("avatars").at(seat_name(seat));')
sub('        for(const auto seat:tick_state.present){\n            auto& d=deployment.players[seat_index(seat)];',
    '        for(const auto seat:seated_seats){\n            auto& d=deployment.players[seat_index(seat)];')
sub('        for(const auto seat:tick_state.present){\n            const auto& player=cold.at("players").at(seat_name(seat));const Point before{',
    '        for(const auto seat:seated_seats){\n            const auto& player=cold.at("players").at(seat_name(seat));const Point before{')
sub('        for(const auto seat:tick_state.present){\n            const auto i=seat_index(seat);const auto& p=*world.players[i];',
    '        for(const auto seat:seated_seats){\n            const auto i=seat_index(seat);const auto& p=*world.players[i];')
sub('J avatars=J::object();for(const auto seat:tick_state.present){','J avatars=J::object();for(const auto seat:seated_seats){')
sub('{"commands",seat_commands()}','{"commands",battle.mode==MatchMode::duo?seat_commands():J(nullptr)}')
sub('{"rally_points",seat_rallies()}','{"rally_points",battle.mode==MatchMode::duo?seat_rallies():J(nullptr)}')
sub('    ColdCatalog catalog;\n','    ColdCatalog catalog;\n    std::vector<Seat> seated_seats;  // every player record; tick_state.present stays the acting set\n')
p.write_text(t,encoding='utf8');print('ok')
# NativeBattle._sync_public iterates self.avatars (every seat).
t=p.read_text(encoding='utf8');n=t.count('public_sync.sync(tick_state.present,');assert n==4,n
t=t.replace('public_sync.sync(tick_state.present,','public_sync.sync(seated_seats,');p.write_text(t,encoding='utf8');print('sync',n)
