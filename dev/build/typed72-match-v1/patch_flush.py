from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('void native_tick_done()override{++typed_ticks;write_record();}','void native_tick_done()override{++typed_ticks;flush_journal();write_record();}')
sub('            match.scheduler.step();\n','            match.scheduler.step();match.flush_journal();\n')
sub('''            for(const auto& [key,value]:player.at("cooldowns").items())p.cooldowns.emplace_back(key,value.get<double>());\n''','''            for(const auto& [key,value]:player.at("cooldowns").items())p.cooldowns.emplace_back(key,value.get<double>());
            for(const auto& [key,value]:player.at("cooldown_spans").items())room.players[seat_index(seat)].cooldown_spans.emplace_back(key,value.get<double>());
''')
# The source publishes during construction, before scenario `place` moves the avatars.
sub('''        public_sync.sync(tick_state.present,true);\n        const double tile_size=runtime.tile;''','''        public_sync.sync(tick_state.present,true);
        for(const auto seat:tick_state.present){
            const auto& player=cold.at("players").at(seat_name(seat));const Point before{player.at("x"),player.at("y")};
            world.players.at(seat_index(seat))->position=before;published.heroes[seat_index(seat)]->visible.position=before;
        }
        const double tile_size=runtime.tile;''')
p.write_text(t,encoding='utf8')
