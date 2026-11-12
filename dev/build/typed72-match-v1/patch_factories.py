from pathlib import Path
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('    // Cold spawn boundary.\n','''    // Child units: every source path is b.spawn(card,'zombie',x,y,facing,True,parent=...)
    // or _register(...), i.e. the real cold admission, never a fixture id.
    static ColdParent parent_of(const ScriptedSpawnOrigin& o){
        ColdParent p;if(o.public_id.present()&&!o.public_id.is_null())p.id=o.public_id.get();else if(o.source&&o.source->id.present()&&!o.source->id.is_null())p.id=o.source->id.get();
        p.fallback=o.source;return p;
    }
    ZombieRef spawned_zombie(const std::optional<std::string>& id)const{
        if(!id)return {};const auto object=battle.native_objects.get(*id);if(!object)return {};const auto* z=std::get_if<ZombieRef>(&*object);return z?*z:ZombieRef{};
    }
    ZombieRef admit_child(const std::string& card,Point point,double facing,const ScriptedSpawnOrigin& origin){
        const auto parent=parent_of(origin);return spawned_zombie(cold_admission.spawn(card,Seat::zombie,point,facing,true,&parent));
    }
    ZombieRef spawn_zombie56(const std::string& card,Point point,double facing,const ScriptedSpawnOrigin& parent)override{return admit_child(card,point,facing,parent);}
    ZombieRef spawn_content(const std::string& name,Point point,double facing,const ScriptedSpawnOrigin& parent)override{return admit_child("zombie:"+name,point,facing,parent);}
    ZombieRef spawn_airdrop(Point point,double facing,const ScriptedSpawnOrigin& source)override{return admit_child("zombie:路障僵尸",point,facing,source);}
    ZombieRef spawn_dancer(Point point,double facing,const ScriptedSpawnOrigin& parent)override{return admit_child("zombie:伴舞僵尸",point,facing,parent);}
    std::optional<SpawnedContentZombie> spawn_slime(const std::string& name,Point point,double facing,const SlimeSpawnParent& parent)override{
        const auto p=parent_of(parent.origin);const auto id=cold_admission.spawn("zombie:"+name,Seat::zombie,point,facing,true,&p);
        const auto unit=spawned_zombie(id);if(!unit)return std::nullopt;return SpawnedContentZombie{*id,unit};
    }
    std::optional<std::string> spawn_echo_crow(Point point,double facing,const std::string& scarecrow)override{
        ColdParent p;p.id=scarecrow;return cold_admission.spawn("zombie:乌鸦",Seat::zombie,point,facing,true,&p);
    }
    // native_barrels: b._register(orphan,b._unit_card('zombie','zombie:滚桶僵尸'),'zombie',True,parent={'id':...})
    void register_barrel(const ZombieRef& unit,const Field<std::string>& parent)override{
        ColdParent p;if(parent.present()&&!parent.is_null())p.id=parent.get();
        cold_registration.register_unit(unit,placement_view.unit_card(Seat::zombie,"zombie:滚桶僵尸"),Seat::zombie,true,cold_admission.context(),&p);
    }
    // NativeBattle.spawn_remnant: native body from the grave factory, then the 残骸墓碑 card.
    ZombieRef spawn_bone_grave(Cell cell,const BoneSource& source)override{
        const double tile=battle.runtime.tile;const auto card=placement_view.unit_card(Seat::zombie,"zombie:残骸墓碑（非生产）");
        Motion position{(cell.x+.5)*tile,(cell.y+1.)*tile,0.,0.};const auto native=factory.zombie("普通僵尸",position,source.direction);if(!native)return {};
        native->native.entry.set(500.);native->body.hp=card.hp.get();native->body.motion.replace({(cell.x+.5)*tile,(cell.y+1.)*tile,0.,0.});native->protection.grave=true;
        ColdParent p;if(source.metadata&&source.metadata->id.present()&&!source.metadata->id.is_null())p.id=source.metadata->id.get();
        cold_registration.register_unit(native,card,Seat::zombie,true,cold_admission.context(),source.metadata?&p:nullptr);return native;
    }
    PlantRef spawn_bone_gravebuster(Cell cell,double facing,const Field<std::string>& parent)override{
        const auto plant=factory.plant(cell,"墓碑吞噬者",facing);if(!plant)return {};
        ColdParent p;if(parent.present()&&!parent.is_null())p.id=parent.get();
        cold_registration.register_unit(plant,catalog.actual("plant:墓碑吞噬者"),Seat::plant,true,cold_admission.context(),&p);return plant;
    }
    // Native region summons pass the installed admission gate (_install_admission).
    void summon_zombie(std::string name,Motion p,double facing)override{
        ColdNativeCallSite site{ColdNativeCall::zombie_region,{}};cold_admission.native_zombie(name,p,facing,site);
    }
    // Cold spawn boundary.
''')
p.write_text(t,encoding='utf8')
