from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('#include "sim/typed/expansion_combat.h"\n','#include "sim/typed/expansion_combat.h"\n#include "sim/typed/cold_deployment.h"\n#include "sim/typed/command_actions.h"\n')
sub('ColdZombieSecretServices,ColdAdmissionServices,RoomPublicServices {','ColdZombieSecretServices,ColdAdmissionServices,RoomPublicServices,ColdDeploymentServices,NativeCommandServices {')
sub('    std::unordered_map<std::string,std::shared_ptr<const RoomPublicCard>> public_cards;\n','''    ColdDeployment cold_deployment{battle,catalog,deployment,room,published,resources,placement_view,cold_admission,vines,binding,scarecrows,zsecrets,tick_state.native_secrets,*this};
    NativeRoomCommands native_commands{battle,room,room_rules,hero_flags,plant_environment,grave_clock,sight,tick_state.native_secrets,*this};
    // Deployment boundary.
    void terrain_grass(Cell)override{unsupported.push_back("terrain_grass");}
    void deploy_event(ColdDeployEvent e)override{spawn_events.push_back({"deploy",seat_name(e.seat),e.card,e.charge});}
    void flag_event(ColdFlagEvent)override{}
    void select_grave(Seat,const std::string&)override{unsupported.push_back("select_grave");}
    // Native command boundary.
    mutable CommandTargetView target_view;
    const CommandTargetView* published_target(const std::string& id)const override{
        const auto* unit=public_sync.find(id);if(!unit)return nullptr;
        target_view={unit->position,unit->hp,unit->side,unit->original_owner,false,false,false};return &target_view;
    }
    void zombie_teleport(Seat)override{unsupported.push_back("zombie_teleport");}
    bool has_self_destruct(Seat)const override{return false;}
    std::string self_destruct(Seat,const std::string&)override{unsupported.push_back("self_destruct");return "unsupported";}
    void remove_basin(const PlantRef&)override{unsupported.push_back("remove_basin");}
    std::string basin_to_pot(const PlantRef&,Cell,double)override{unsupported.push_back("basin_to_pot");return "unsupported";}
    static std::optional<std::string> text_field(const InputField<std::string>& f){return f.valid()?std::optional<std::string>(f.value):std::nullopt;}
    std::string deploy(Seat seat,const NativeCommand& c)override{
        if(!c.card.valid()||!c.x.valid()||!c.y.valid())return "bad deploy";
        std::optional<double> facing;if(c.facing.valid())facing=double(c.facing.value);
        return cold_deployment.deploy(seat,c.card.value,{c.x.value,c.y.value},text_field(c.grave),text_field(c.copy),facing);
    }
    // Same wrapper order as the verified expansion and garden stages.
    void expansion_before_plants()override{ContentPhaseProbe::expansion_before_plants();garden.before_plants(path_rules.producers);}
    void expansion_after_plants()override{ContentPhaseProbe::expansion_after_plants();garden.after_plants();}
    void finish_expansion_zombie()override{ContentPhaseProbe::finish_expansion_zombie();expansion.finish_zombie();}
    void zombie_gate(size_t i)override{ContentPhaseProbe::zombie_gate(i);expansion.zombie_gate(battle.targets->at(i).unit);}
    void ordinary_damage(size_t i,double facing,double amount)override{expansion.ordinary(i,facing,amount);}
    void add_entity(std::string name,double facing,Motion point)override{
        const auto first=visual.entities.list()->size();const auto captured=world.source();PlantRef plant;
        for(const auto& candidate:*battle.plant_roster)if(captured.get()==&candidate->source){plant=candidate;break;}
        ContentPhaseProbe::add_entity(std::move(name),facing,point);expansion.after_projectile(captured,plant,first,world.source_index);
    }
    std::unordered_map<std::string,std::shared_ptr<const RoomPublicCard>> public_cards;
''')
sub('    std::string native_command(Seat,const NativeCommand& c)override{unsupported.push_back("native command "+std::to_string(int(c.kind)));return "unsupported";}\n','    std::string native_command(Seat seat,const NativeCommand& c)override{return native_commands.apply(seat,c);}\n')
sub('for(const auto& e:*battle.runtime.entities.list())entities.push_back(phase_entity_json(e));','for(const auto& e:*battle.runtime.entities.list())entities.push_back(entity_json(e));')
sub('    static J buckets(const TargetBuckets& value)','''    static J entity_json(const EntityRef& entity){
        J j=phase_entity_json(entity);const auto& e=*entity;J src=source_state(e.source,std::nullopt,e.flight);src.erase("_pvp_instant_attack_text");src.erase("名");j.update(src);
        if(e.source.instant_attack)j["_pvp_instant_attack"]=J::parse(encode_attack_identity(*e.source.instant_attack).dump());
        if(e.flight.torch_visits.present()&&!e.flight.torch_visits.is_null())j["_pvp_torch_visits"]=*e.flight.torch_visits.get();
        write_point(j,"_pvp_torch_previous",e.flight.torch_previous);return j;
    }
    static J buckets(const TargetBuckets& value)''')
sub('if(u.protection.grave)j["_pvp_grave"]=true;','if(u.protection.grave)j["_pvp_grave"]=true;if(u.grenadier.before.present())j["_pvp_content_position_before"]=as_json(u.grenadier.before.get());')
sub('        try {for(match.current_room=0;match.current_room<ticks;++match.current_room)match.scheduler.step();}','''        std::array<int64_t,4> seqs{-1,-1,-1,-1};
        try {for(match.current_room=0;match.current_room<ticks;++match.current_room){
            const auto key=std::to_string(match.current_room);
            if(scenario.contains("inputs")&&scenario.at("inputs").contains(key))for(const auto& raw:scenario.at("inputs").at(key)){
                const auto side=raw.at("side").get<std::string>();const auto seat=parse_seat(side);auto payload=raw;payload.erase("side");payload["seq"]=++seqs[seat_index(seat)];
                const auto error=match.inputs.apply(seat,decode_command(nlohmann::json::parse(payload.dump())));
                match.pending_inputs.push_back({side,payload.value("type",std::string{}),error.empty()?J(nullptr):J(error)});
            }
            match.scheduler.step();
        }}''')
p.write_text(t,encoding='utf8')
p=Path('probes/plants_probe.cpp');t=p.read_bytes().decode('utf8')
a='write(j,"_pvp_max_hp",p.content_state.maximum_hp);'
b='if(p.expansion_clock.delta.present())j["_pvp_clock_delta"]=J::object();write(j,"_pvp_max_hp",p.content_state.maximum_hp);'
assert t.count(a)==1;t=t.replace(a,b);p.write_bytes(t.encode('utf8'))
