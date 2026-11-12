# Avatar fields written by ZombieSecrets: _pvp_pea_head (lock) and _pvp_base_speedmax (汇流 setdefault).
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
a='J avatars=J::object();for(const auto seat:tick_state.present)avatars[seat_name(seat)]=frame_json(world.hero(seat));'
b='''J avatars=J::object();for(const auto seat:tick_state.present){auto row=frame_json(world.hero(seat));const auto& zs=battle.heroes.hero(seat).secret;
            if(zs.pea_head.present())row["_pvp_pea_head"]=zs.pea_head.get();if(zs.base_speedmax.present())row["_pvp_base_speedmax"]=zs.base_speedmax.is_null()?J(nullptr):J(zs.base_speedmax.get());avatars[seat_name(seat)]=std::move(row);}'''
assert t.count(a)==1;t=t.replace(a,b);p.write_text(t,encoding='utf8');print('ok')
