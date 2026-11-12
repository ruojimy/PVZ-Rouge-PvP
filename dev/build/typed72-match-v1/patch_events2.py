from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('    // Cold spawn boundary.\n','''    // Every service event in the same shape as the source _emit call.
    static J text(const Field<std::string>& f){return f.present()&&!f.is_null()?J(f.get()):J(nullptr);}
    void plant70_event(const Plant70Event& v)override{
        ContentPhaseProbe::plant70_event(v);
        if(v.kind==Plant70Event::Kind::tentacle_spawn)log_event({{"event","tentacle_spawn"},{"source",text(v.source)},{"entity",text(v.head)}});
        else if(v.kind==Plant70Event::Kind::tentacle_hit)log_event({{"event","tentacle_hit"},{"source",text(v.source)},{"head",text(v.head)},{"target",text(v.target)}});
        else{J water=J::array();for(const auto& [row,col]:v.water)water.push_back({row,col});log_event({{"event","lettuce_freeze"},{"source",text(v.source)},{"water",water},{"targets",v.targets}});}
    }
    void zombie56_event(const Zombie56Event& v)override{
        ContentPhaseProbe::zombie56_event(v);
        if(v.kind==Zombie56Event::Kind::dance_started)log_event({{"event","dance_started"},{"source",text(v.source)},{"owner",seat_name(v.owner)},{"x",v.position.x},{"y",v.position.y}});
        else log_event({{"event","content_summon"},{"source",text(v.source)},{"entity",text(v.entity)},{"card","zombie:伴舞僵尸"},{"owner",seat_name(v.owner)},{"slot",v.slot?J(*v.slot):J(nullptr)}});
    }
    void zombie64_event(const Zombie64Event& v)override{
        ContentPhaseProbe::zombie64_event(v);
        if(v.kind==Zombie64Event::Kind::belt_placed)log_event({{"event","belt_placed"},{"row",v.cell.y},{"col",v.cell.x},{"entity",text(v.entity)}});
        else if(v.kind==Zombie64Event::Kind::slime_split)log_event({{"event","slime_split"},{"source",text(v.source)},{"card",v.card},{"entities",v.children}});
        else log_event({{"event",v.kind==Zombie64Event::Kind::grab?"redeye_grab":"redeye_throw"},{"source",text(v.source)},{"entity",text(v.entity)}});
    }
    void zombie70_event(const Zombie70Event& v)override{
        ContentPhaseProbe::zombie70_event(v);J row={{"source",text(v.source)}};
        switch(v.kind){
            case Zombie70Event::Kind::reaper_idle:row["event"]="reaper_idle";break;
            case Zombie70Event::Kind::reaper_resumed:row["event"]="reaper_resumed";break;
            case Zombie70Event::Kind::airdrop:row["event"]="airdrop_summon";row["entity"]=text(v.entity);row["owner"]=seat_name(v.owner.get());break;
            case Zombie70Event::Kind::hook_fired:row["event"]="hook_fired";row["target"]=text(v.target);break;
            case Zombie70Event::Kind::bone_thrown:row["event"]="bone_thrown";row["row"]=v.cell.y;row["col"]=v.cell.x;break;
            case Zombie70Event::Kind::grenade_reflected:row["event"]="grenade_reflected";row["umbrella"]=text(v.target);break;
            case Zombie70Event::Kind::projectile_reflected:row["event"]="projectile_reflected";row["kind"]=v.projectile;row["umbrella"]=text(v.target);break;
            case Zombie70Event::Kind::bone_grave:row["event"]="bone_grave";row["entity"]=text(v.entity);break;
            case Zombie70Event::Kind::bone_gravebuster:row["event"]="bone_gravebuster";row["entity"]=text(v.entity);row["grave"]=text(v.target);break;
            case Zombie70Event::Kind::hook_hit:row["event"]="hook_hit";row["target"]=text(v.target);break;
        }
        log_event(std::move(row));
    }
    void grenade_event(const GrenadeEvent& v)override{
        ContentPhaseProbe::grenade_event(v);J row={{"source",text(v.source)}};
        switch(v.kind){
            case GrenadeEvent::Kind::cancelled:row["event"]="grenade_cancelled";break;
            case GrenadeEvent::Kind::no_target:row["event"]="grenade_no_target";break;
            case GrenadeEvent::Kind::thrown:row["event"]="grenade_thrown";row["target"]=text(v.other);break;
            case GrenadeEvent::Kind::reflected:row["event"]="grenade_reflected";row["umbrella"]=text(v.other);break;
            case GrenadeEvent::Kind::explode:row["event"]="grenade_explode";row["row"]=v.cell.y;row["col"]=v.cell.x;row["targets"]=v.targets;row["instant"]=v.instant;break;
        }
        log_event(std::move(row));
    }
    void mortar_event(const MortarPlantEvent& v)override{
        ContentPhaseProbe::mortar_event(v);
        if(v.spring)log_event({{"event","spring_whip"},{"source",text(v.source)},{"targets",v.targets}});
        else log_event({{"event","mortar_volley"},{"source",text(v.source)},{"shots",v.shots},{"targets",v.targets}});
    }
    void reed_event(const ReedEvent& v)override{ContentPhaseProbe::reed_event(v);log_event({{"event","lightning"},{"source",text(v.source)},{"kind",v.overload?"overload":"chain"},{"targets",v.targets}});}
    void september_event(const SeptemberPlantEvent& v)override{
        ContentPhaseProbe::september_event(v);
        if(v.kind==SeptemberPlantEvent::Kind::bloom)log_event({{"event","gold_bloom"},{"source",text(v.source)},{"suns",8},{"amount",v.sun_amount}});
        else log_event({{"event",v.kind==SeptemberPlantEvent::Kind::ghost_activated?"ghost_activated":"ghost_exploded"},{"source",text(v.source)}});
    }
    // Cold spawn boundary.
''')
sub('    void first_soldier_event(ColdFirstSoldierEvent)override{}\n','    void first_soldier_event(ColdFirstSoldierEvent e)override{log_event({{"event","zsecret_first_soldier"},{"grave",e.grave},{"entity",e.entity}});}\n')
sub('    void flag_event(ColdFlagEvent)override{}\n','''    void flag_event(ColdFlagEvent e)override{
        if(e.blocked)log_event({{"event","flag_reinforcement_blocked"},{"grave",e.grave},{"reason","blocked"}});
        else log_event({{"event","flag_reinforcement"},{"grave",e.grave},{"source",e.source},{"entity",e.entity?J(*e.entity):J(nullptr)}});
    }
''')
sub('''            else log_event({{"event","room-unmapped"},{"index",int(e.index())}});\n''','''            else if constexpr(std::is_same_v<T,RoomGiftEvent>)log_event({{"event","gift"},{"side",seat_name(v.seat)},{"to",seat_name(v.to)},{"amount",v.amount}});
            else if constexpr(std::is_same_v<T,RoomSurrenderRequestEvent>)log_event({{"event","surrender_requested"},{"side",seat_name(v.seat)},{"request",v.request}});
            else if constexpr(std::is_same_v<T,RoomSurrenderVoteEvent>)log_event({{"event","surrender_vote"},{"side",seat_name(v.seat)},{"request",v.request},{"accepted",v.accepted}});
            else if constexpr(std::is_same_v<T,RoomFallenEvent>)log_event({{"event","hero_fallen"},{"side",seat_name(v.seat)}});
            else if constexpr(std::is_same_v<T,RoomHelpedEvent>)log_event({{"event","hero_helped"},{"side",seat_name(v.seat)},{"helper",seat_name(v.helper)}});
            else if constexpr(std::is_same_v<T,RoomRevivedEvent>)log_event({{"event","hero_revived"},{"side",seat_name(v.seat)},{"helper",seat_name(v.helper)},{"hp",v.hp}});
            else if constexpr(std::is_same_v<T,RoomSubsidyEvent>)log_event({{"event","ai_subsidy"},{"side",seat_name(v.seat)},{"amount",v.amount}});
            else if constexpr(std::is_same_v<T,RoomSpawnBlockedEvent>)log_event({{"event","spawn_blocked"},{"card",v.card},{"reason","deathmatch_pending_copy"}});
            else log_event({{"event","room-unmapped"},{"index",int(e.index())}});\n''')
# Journal events that carry their own _emit shape.
sub('''                else row={{"event","journal-unmapped"},{"index",int(events[journal_read].index())}};''','''                else if constexpr(std::is_same_v<T,RelicEvent>)row={{"event","zsecret_relic"},{"entity",v.entity?J(*v.entity):J(nullptr)},{"seconds",v.seconds}};
                else if constexpr(std::is_same_v<T,EnvironmentalDamageEvent>)row={{"event","damage"},{"target",seat_name(v.seat)},{"amount",v.amount},{"kind","environment"},{"native",true}};
                else if constexpr(std::is_same_v<T,SturdyEvent>)row={{"event","sturdy"},{"side",seat_name(v.seat)},{"cards",v.cards}};
                else if constexpr(std::is_same_v<T,GraveWokenEvent>)row={{"event","grave_woken"},{"entity",v.entity?J(*v.entity):J(nullptr)},{"cause",v.cause}};
                else row={{"event","journal-unmapped"},{"index",int(events[journal_read].index())}};''')
# The chain's complete writers include hit tables and the smart-ballistic record.
sub('    static J entity_json(const EntityRef& entity){\n        J j=phase_entity_json(entity);','    J entity_json(const EntityRef& entity){\n        J j=phase_entity_json(entity);j.update(pea_state(entity));')
sub('    J record() {\n','    J record() {\n        hit_entity_guard=true;\n')
sub('    J spawn_events=J::array();\n','    J spawn_events=J::array();\n    bool hit_entity_guard=false;\n')
p.write_text(t,encoding='utf8')
