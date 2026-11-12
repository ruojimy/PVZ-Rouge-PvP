from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
# Ordered event log with the same record shape as the source _emit.
sub('    std::array<int64_t,4> sequence{-1,-1,-1,-1};\n','''    std::array<int64_t,4> sequence{-1,-1,-1,-1};
    J log=J::array();size_t journal_read=0;
    void log_event(J fields){
        flush_journal();
        fields["tick"]=room.tick;fields["time"]=pvz::py::roundn(world.time,4);log.push_back(std::move(fields));
    }
    static const char* hit_kind(HeroHit h){
        switch(h){case HeroHit::normal:return "normal";case HeroHit::ash:return "ash";case HeroHit::swallow:return "swallow";case HeroHit::content:return "content";case HeroHit::lightning:return "lightning";case HeroHit::spring:return "spring";case HeroHit::grenade:return "grenade";case HeroHit::poison:return "poison";case HeroHit::hook:return "hook";case HeroHit::anchor:return "anchor";case HeroHit::chili:return "chili";case HeroHit::tentacle:return "tentacle";case HeroHit::black_armor:return "black_armor";}
        return "?";
    }
    // The typed journal preserves cross-system order, so drain it before any other emission.
    void flush_journal(){
        auto& events=battle.runtime.events;
        for(;journal_read<events.size();++journal_read){
            J row;
            std::visit([&](const auto& v){using T=std::decay_t<decltype(v)>;
                if constexpr(std::is_same_v<T,HeroDamageEvent>){if(v.type==HeroDamageEvent::Type::damage)row={{"event","damage"},{"target",seat_name(v.seat)},{"amount",v.amount},{"kind",hit_kind(v.hit)},{"source_entity",v.source_id?J(*v.source_id):J(nullptr)},{"native",true}};}
                else if constexpr(std::is_same_v<T,ResourceIncomeEvent>)row={{"event","income"},{"side",seat_name(v.seat)},{"amount",v.amount},{"source",v.source},{"resource_id",v.id}};
                else if constexpr(std::is_same_v<T,HeroHealEvent>)row={{"event","heal"},{"target",seat_name(v.seat)},{"amount",v.amount},{"kind","out_of_combat"}};
                else if constexpr(std::is_same_v<T,CoinIncomeEvent>)row={{"event","coin"},{"side",seat_name(v.seat)},{"amount",v.amount},{"resource_id",v.id}};
                else row={{"event","journal-unmapped"},{"index",int(events[journal_read].index())}};
            },events[journal_read]);
            if(!row.is_null()){row["tick"]=room.tick;row["time"]=pvz::py::roundn(world.time,4);log.push_back(std::move(row));}
        }
    }
''')
sub('void spawn(const ColdSpawnEvent& e)override{spawn_events.push_back({"spawn",e.entity,e.card});}','void spawn(const ColdSpawnEvent& e)override{log_event({{"event","spawn"},{"entity",e.entity},{"card",e.card},{"side",seat_name(e.side)},{"source_entity",e.entity},{"parent_entity",e.parent_entity?J(*e.parent_entity):J(nullptr)},{"parent_attack",e.parent_attack?J::parse(encode_attack_identity(*e.parent_attack).dump()):J(nullptr)},{"native",true}});}')
sub('void deploy_event(ColdDeployEvent e)override{spawn_events.push_back({"deploy",seat_name(e.seat),e.card,e.charge});}','void deploy_event(ColdDeployEvent e)override{log_event({{"event","deploy"},{"side",seat_name(e.seat)},{"card",e.card},{"charge",e.charge},{"entity",e.entity?J(*e.entity):J(nullptr)},{"x",e.position.x},{"y",e.position.y},{"grave",e.grave?J(*e.grave):J(nullptr)},{"facing",e.facing}});}')
sub('void death(const RoomPublicDeath& d)override{spawn_events.push_back({"death",d.entity,d.card});}','void death(const RoomPublicDeath& d)override{log_event({{"event","death"},{"entity",d.entity},{"side",seat_name(d.side)},{"card",d.card}});}')
sub('    void emit(RoomEvent e)override{events.push_back(int(e.index()));}\n','''    void emit(RoomEvent e)override{
        events.push_back(int(e.index()));
        std::visit([&](const auto& v){using T=std::decay_t<decltype(v)>;
            if constexpr(std::is_same_v<T,RoomResult>)log_event({{"event","result"},{"winner",v.winner==RoomWinner::plant?"plant":v.winner==RoomWinner::zombie?"zombie":"draw"},{"reason",v.reason==RoomResultReason::hero_death?"hero_death":v.reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"}});
            else if constexpr(std::is_same_v<T,RoomRallyEvent>)log_event({{"event","rally"},{"side",seat_name(v.seat)},{"point",v.point?J{{"x",v.point->x},{"y",v.point->y}}:J(nullptr)}});
            else if constexpr(std::is_same_v<T,RoomCommandEvent>)log_event({{"event","command"},{"mode",v.mode==PathMode::follow_hero?"follow":"attack"},{"side",seat_name(v.seat)},{"seq",v.sequence}});
            else if constexpr(std::is_same_v<T,RoomDeathmatchEvent>)log_event({{"event","deathmatch"},{"multiplier",v.multiplier}});
            else log_event({{"event","room-unmapped"},{"index",int(e.index())}});
        },e);
    }
''')
# Public player view, read from the existing owners.
sub('    J record() {\n','''    J players_json()const{
        J out=J::object();
        for(const auto seat:tick_state.present){
            const auto i=seat_index(seat);const auto& p=*world.players[i];const auto& rp=room.players[i];const auto& view=published.heroes[i]->visible;
            J cool=J::object();for(const auto& [key,value]:p.cooldowns)cool[key]=value;J spans=J::object();for(const auto& [key,value]:rp.cooldown_spans)spans[key]=value;
            const auto& account=resources.accounts[i];
            out[seat_name(seat)]={{"x",view.position.x},{"y",view.position.y},{"vx",view.velocity.x},{"vy",view.velocity.y},{"h",p.height},{"hp",p.hp},{"max_hp",p.max_hp},{"resource",account.balance},
                {"cooldowns",cool},{"cooldown_spans",spans},{"seq",rp.sequence},{"last_input_tick",rp.last_input_tick},{"marked_until",p.marked_until},{"immune_until",rp.immune_until},{"facing",view.facing},
                {"frozen",view.frozen},{"slowed",view.slowed},{"buttered",view.buttered},{"jumps",view.jumps},{"jump_cap",view.jump_cap},{"grounded",view.grounded},{"poison_level",view.poison},{"jump_held",p.jump_held},
                {"stats",{{"spent",deployment.players[i].spent},{"earned",account.earned},{"hero_damage",p.hero_damage},{"producer_lost",rp.producer_lost}}}};
        }
        return out;
    }
    J record() {
''')
sub('{"g",gl},{"avatars",avatars},','{"g",gl},{"avatars",avatars},{"players",players_json()},')
sub('        J report={{"backend_requested"','''        match.flush_journal();
        if(argc>6){std::ofstream final_out(argv[6],std::ios::binary);J result=nullptr;
            if(match.room.result)result={{"winner",match.room.result->winner==RoomWinner::plant?"plant":match.room.result->winner==RoomWinner::zombie?"zombie":"draw"},{"reason",match.room.result->reason==RoomResultReason::hero_death?"hero_death":match.room.result->reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",match.room.result->tick}};
            final_out<<J{{"result",result},{"tick",match.room.tick},{"log",match.log}}.dump(-1,' ',false,J::error_handler_t::replace);}
        J report={{"backend_requested"''')
sub('if(argc!=6)throw','if(argc!=6&&argc!=7)throw')
sub('''                const auto error=match.inputs.apply(seat,decode_command(nlohmann::json::parse(payload.dump())));\n''','''                const auto error=match.inputs.apply(seat,decode_command(nlohmann::json::parse(payload.dump())));
                if(error.empty()){J row=J::object();for(auto item=payload.begin();item!=payload.end();++item)if(item.key()!="type")row[item.key()]=item.value();row["event"]="input";row["accepted"]=true;row["kind"]=payload.value("type",std::string{});row["side"]=side;match.log_event(std::move(row));}
''')
sub('        match.write_record();\n','        match.log.push_back({{"event","battle_start"},{"map",scenario.value("map",std::string("家院"))},{"seed",seed},{"tick",0},{"time",0}});\n        match.write_record();\n')
p.write_text(t,encoding='utf8')
p=Path('compare_match.py');t=p.read_text(encoding='utf8')
sub("RECORD=ROOT/'build/typed72-ref-recorder-v1/build/Release/ref72_record.exe'","RECORD=ROOT/'build/typed72-ref-recorder-v2/build/Release/ref72_record.exe'\nPLAYER_FIELDS=('x','y','vx','vy','h','hp','max_hp','resource','cooldowns','cooldown_spans','seq','last_input_tick','marked_until','immune_until','facing','frozen','slowed','buttered','jumps','jump_cap','grounded','poison_level','jump_held','stats')")
sub("run=subprocess.run([str(MATCH),str(cold),str(atlas),str(source),str(typed),str(report)]","typed_final=out/'typed.final.json'\n    run=subprocess.run([str(MATCH),str(cold),str(atlas),str(source),str(typed),str(report),str(typed_final)]")
sub("keys=('t','g','avatars','inp','battle','rng')\n            walk({k:x.get(k) for k in keys},{k:y.get(k) for k in keys},'',found)","keys=('t','g','avatars','inp','battle','rng')\n            walk({k:x.get(k) for k in keys},{k:y.get(k) for k in keys},'',found)\n            walk({s:{f:v.get(f) for f in PLAYER_FIELDS} for s,v in (x.get('players') or {}).items()},y.get('players') or {},'.players',found)")
sub("    if summary['identical'] and '--keep'","""    # Settlement and the complete ordered event log.
    final={}
    try:
        rf=json.loads((out/'reference.jsonl.final.json').read_text(encoding='utf8'));tf=json.loads(typed_final.read_text(encoding='utf8'))
        final['result_equal']=rf.get('result')==tf.get('result');final['result']=[rf.get('result'),tf.get('result')];final['tick_equal']=rf.get('tick')==tf.get('tick')
        la,lb=rf.get('log') or [],tf.get('log') or [];found=[];walk(la,lb,'.log',found);final['log_lengths']=[len(la),len(lb)];final['log_differences']=[[f[0],f[1],f[2],f[3]] for f in found[:12]];final['log_difference_count']=len(found)
        import collections
        final['event_counts']=[dict(collections.Counter(e['event'] for e in la)),dict(collections.Counter(e['event'] for e in lb))]
        final['log_equal']=not found
    except Exception as error:final['error']=repr(error)
    summary['final']=final;summary['identical']=summary['identical'] and final.get('log_equal') is True and final.get('result_equal') is True
    if summary['identical'] and '--keep'""")
p.write_text(t,encoding='utf8')
