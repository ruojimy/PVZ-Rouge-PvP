from pathlib import Path
p=Path('cold72_export.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('const auto names=[&](const V& v){J list=J::array();for(const auto& item:py::iter_list(v).items())list.push_back(py_str(item));return list;};',
    'const auto names=[&](const V& v){J list=J::array();if(v.is_dict()){for(const auto& [key,value]:py::items_vec(v))list.push_back(py_str(key));}else for(const auto& item:py::iter_list(v).items())list.push_back(py_str(item));return list;};')
p.write_text(t,encoding='utf8')
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
# Source command_input: only these validated fields enter the audit log.
sub('''                if(error.empty()){J row=J::object();for(auto item=payload.begin();item!=payload.end();++item)if(item.key()!="type")row[item.key()]=item.value();row["event"]="input";row["accepted"]=true;row["kind"]=payload.value("type",std::string{});row["side"]=side;match.log_event(std::move(row));}
''','''                if(error.empty())match.log_event(match.input_record(seat,side,payload));
''')
sub('    J players_json()const{\n','''    J input_record(Seat seat,const std::string& side,const J& payload)const{
        const auto kind=payload.value("type",std::string{});const auto& player=*world.players[seat_index(seat)];
        J row={{"event","input"},{"accepted",true},{"kind",kind},{"side",side},{"seq",payload.at("seq")}};
        if(kind=="move"){row["move"]=player.move;row["jump"]=player.jump_held;}
        else if(kind=="deploy"){
            const auto key=payload.at("card").get<std::string>();row["card"]=key;row["x"]=payload.at("x");row["y"]=payload.at("y");if(payload.contains("facing"))row["facing"]=payload.at("facing");
            const auto* card=catalog.find(key);const auto behavior=card?card->behavior:std::string{};
            if(side=="zombie"&&behavior!="grave")row["grave"]=payload.value("grave",J(nullptr));
            if(behavior=="copy")row["copy"]=payload.value("copy",J(nullptr));
        }
        else if(kind=="command")row["mode"]=(battle.mode==MatchMode::duo?commands.by_seat[seat_index(seat)]:commands.shared)==PathMode::follow_hero?"follow":"attack";
        else if(kind=="rally"){const auto& flag=hero_flags.for_owner(battle.mode,seat);row["point"]=flag?J{{"x",flag->x},{"y",flag->y}}:J(nullptr);}
        else if(kind=="collect")row["resource"]=payload.at("resource");
        else if(kind=="mark")row["target"]="zombie";
        else for(auto item=payload.begin();item!=payload.end();++item)if(item.key()!="type"&&item.key()!="seq")row[item.key()]=item.value();
        return row;
    }
    J players_json()const{
''')
# The audit log opens in the source constructor, before any setup spawn.
sub('        match.log.push_back({{"event","battle_start"},{"map",scenario.value("map",std::string("家院"))},{"seed",seed},{"tick",0},{"time",0}});\n        match.write_record();\n','        match.write_record();\n')
sub('        load_atlas(argv[2],match.battle.runtime.presentation.atlas);\n','        load_atlas(argv[2],match.battle.runtime.presentation.atlas);\n        match.log.push_back({{"event","battle_start"},{"map",scenario.value("map",std::string("家院"))},{"seed",seed},{"tick",0},{"time",0}});\n')
sub('''                else if constexpr(std::is_same_v<T,CoinIncomeEvent>)row=''','''                else if constexpr(std::is_same_v<T,MelonSplashEvent>)row={{"event","melon_splash"},{"x",v.position.x},{"y",v.position.y},{"owner",v.owner?J(seat_name(*v.owner)):J(nullptr)},{"source_entity",v.source?J(*v.source):J(nullptr)}};
                else if constexpr(std::is_same_v<T,CoinIncomeEvent>)row=''')
p.write_text(t,encoding='utf8')
