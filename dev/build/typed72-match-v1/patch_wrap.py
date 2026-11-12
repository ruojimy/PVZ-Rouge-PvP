from pathlib import Path
p=Path('probes/content_phase_probe.cpp');t=p.read_bytes().decode('utf8')
a='phases.add_entity(std::move(name),facing,position,[&](std::string kind,double f,Motion p){ContentControllersProbe::add_entity(std::move(kind),f,p);});'
assert t.count(a)==1
t=t.replace(a,'phases.add_entity(std::move(name),facing,position,[&](std::string kind,double f,Motion p){patched_add_entity(std::move(kind),f,p);});')
nl='\r\n' if '\r\n' in t else '\n'
a='    ContentCombatState combat_state;'+nl;assert t.count(a)==1
t=t.replace(a,a+'    virtual void patched_add_entity(std::string kind,double f,Motion p){ContentControllersProbe::add_entity(std::move(kind),f,p);}'+nl)
p.write_bytes(t.encode('utf8'))
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
a='    // Same wrapper order as the verified expansion and garden stages.\n';assert t.count(a)==1
t=t.replace(a,'''    // Source __pvz_sb_add_entity_wrapper: every native entity birth passes through this.
    void patched_add_entity(std::string kind,double f,Motion position)override{
        const std::string name=kind;ContentPhaseProbe::patched_add_entity(std::move(kind),f,position);
        const auto& mode=world.globals.mode;
        if(mode.present()&&!mode.is_null()&&mode.get()=="我是僵尸"&&!bonus_projectiles.zombie_placed())return;
        const auto list=battle.runtime.entities.list();if(list->empty())return;const auto entity=list->back();
        if(name=="星星")bonus_plants.record_star(entity,f);
        else if(name=="玉米炮"){bonus_projectiles.prepare_cannon(entity);bonus_projectiles.mark_reloading(entity);}
        else if(name=="窝瓜x")squash.patch_entity(entity);
        else if(name=="火")chain.chili.patch_fire(entity);
        bonus_projectiles.patch(entity);
    }
'''+a)
p.write_text(t,encoding='utf8')
