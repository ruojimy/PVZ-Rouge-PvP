"""Opt-in MATCH_DEBUG_TICKS=t0:t1: add dbg.seat_tracking (per-seat 人洪水/植洪水 grids and
cooldowns from the authoritative SeatPathTracking bank) to those records, matching the
ref72_record v3 debug block. Without the variable records are unchanged."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'record_base' in t:raise SystemExit('already patched')
a='    J record() {\n'
assert t.count(a)==1
t=t.replace(a,'''    std::pair<int64_t,int64_t> debug_window=[]{const char* s=std::getenv("MATCH_DEBUG_TICKS");long long a=-1,b=-2;if(!s||std::sscanf(s,"%lld:%lld",&a,&b)!=2){a=-1;b=-2;}return std::pair<int64_t,int64_t>{a,b};}();
    J record() {
        J out=record_base();const auto tick=out.at("t").get<int64_t>();
        if(tick<debug_window.first||tick>debug_window.second)return out;
        const auto rows=size_t(battle.terrain.rows()),cols=size_t(battle.terrain.cols());
        const auto grid=[&](const std::shared_ptr<std::vector<int>>& f){J g=J::array();if(!f)return J(nullptr);for(size_t r=0;r<rows;++r){J line=J::array();for(size_t c=0;c<cols;++c)line.push_back((*f)[r*cols+c]);g.push_back(line);}return g;};
        J seats=J::object();
        for(size_t i=0;i<path_banks.seats().size();++i){
            const auto& s=path_banks.seats()[i];if(!s)continue;
            seats[seat_name(Seat(i))]={{"人洪水",grid(s->flood[0].field)},{"植洪水",grid(s->flood[1].field)},{"人洪水cd",s->flood[0].cooldown},{"植洪水cd",s->flood[1].cooldown},
                {"人洪水覆盖",s->flood[0].sign},{"植洪水覆盖",s->flood[1].sign},{"目标位置",J::array({s->chase.goal.y,s->chase.goal.x})},{"目标植物",s->chase.target},{"输出植物数",s->chase.output},{"paoku",s->chase.running},{"先别追植",s->hold},
                {"wjx",s->wjx.present()&&!s->wjx.is_null()?J(s->wjx.get()):J(nullptr)},{"wjy",s->wjy.present()&&!s->wjy.is_null()?J(s->wjy.get()):J(nullptr)}};
        }
        J rallies=J::object();
        for(size_t i=0;i<path_banks.rally_seats().size();++i){const auto& r=path_banks.rally_seats()[i];if(!r)continue;
            rallies[seat_name(Seat(i))]={{"洪水0",grid(r->path.chase.fields[0])},{"洪水1",grid(r->path.chase.fields[1])},{"人洪水",grid(r->path.flood[0].field)},{"goal",r->goal?J::array({r->goal->x,r->goal->y}):J(nullptr)}};}
        out["dbg_rally"]={{"seats",rallies},{"base",bool(path_banks.rally_base())}};
        out["dbg_chart_active"]=chart.active();
        {const auto& h=battle.heroes.hero(Seat::zombie);const auto& px=battle.heroes.cached_proxy(Seat::zombie).position;
         out["dbg_hero_x"]={{"frame",h.frame.position.get()->x},{"proxy",px?J(px->x):J(nullptr)},{"same_motion",px.get()==h.frame.position.get().get()},{"globals",battle.heroes.globals.position.present()?J(battle.heroes.globals.position.get()->x):J(nullptr)}};}
        out["dbg"]={{"seat_tracking",seats},{"selected",path_banks.selected_seat()?J(seat_name(*path_banks.selected_seat())):J(nullptr)}};
        return out;
    }
    J record_base() {
''')
p.write_text(t,encoding='utf8');print('ok')
