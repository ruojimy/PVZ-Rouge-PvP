#include "cold_admission.h"
#include "core/pymath.h"
namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool named(const Field<std::string>& f,std::string_view value){return f.present()&&!f.is_null()&&f.get()==value;}
bool value(const Field<std::string>& f){return f.present()&&!f.is_null()&&!f.get().empty();}
std::optional<std::string> id(const AttackSource& s){return value(s.id)?std::optional<std::string>(s.id.get()):std::nullopt;}
}
std::vector<std::string> ColdAdmission::team_secrets(Seat team)const{
    std::vector<std::string> result;
    for(Seat seat:seats_for(world_.mode))if(team_of(seat)==team)if(const auto& player=world_.heroes.players[seat_index(seat)])for(const auto& secret:player->secrets)
        if(std::find(result.begin(),result.end(),secret)==result.end())result.push_back(secret);
    return result;
}
ColdRegistrationContext ColdAdmission::context()const{return {state_.acting_seat,budget_.enabled,state_.scripted_wave};}
void ColdAdmission::harden(const PlantRef& plant){const auto secrets=team_secrets(Seat::plant);registration_.health(plant,secrets);registration_.hardening(plant,secrets);}
PlantRef ColdAdmission::native_plant(Cell cell,const std::string& name,double facing){
    const auto key="plant:"+name;
    if(catalog_.find(key)){
        ColdCard card;try{const auto secrets=team_secrets(Seat::plant);card=catalog_.resolve(key,secrets,state_.bans);}catch(const std::invalid_argument&){return {};}
        if(room_.deathmatch&&catalog_.deathmatch_blocked(card)){services_.spawn_blocked(key);return {};}
    }return factory_.plant(cell,name,facing);
}
bool ColdAdmission::imitate(const PlantRef& imitater,Cell cell,double facing){
    // Copy the handle: the caller passes a roster element, and the roster grows below.
    const PlantRef source=imitater;
    if(!source||source->kind!="模仿者"||!value(source->copy_card))return false;
    const auto key=source->copy_card.get();const auto secrets=team_secrets(Seat::plant);
    ColdCard card;try{card=catalog_.resolve(key,secrets,state_.bans,economy_.night);}catch(const std::invalid_argument&){services_.spawn_blocked(key);return true;}
    if(room_.deathmatch&&card.producer){services_.spawn_blocked(card.id);return true;}
    const auto before=world_.plant_roster->size();
    // Admission concerns the copied card; its implementation template may be banned independently.
    (void)factory_.plant(cell,card.native_input_name,facing);
    ColdParent parent;if(value(source->source.id))parent.id=source->source.id.get();
    for(size_t i=before;i<world_.plant_roster->size();++i){
        const auto native=world_.plant_roster->at(i);
        registration_.configure_plant(native,card,secrets);
        registration_.register_unit(native,card,Seat::plant,true,context(),&parent);
        content_.configure(native,card);native->monochrome.set(DeathMarker(0.));
        source->transform_succeeded.set(true);
    }
    return true;
}
ZombieRef ColdAdmission::native_zombie(const std::string& name,Motion& position,double facing,const ColdNativeCallSite& site){
    const bool native=site.kind==ColdNativeCall::zombie_region;ZombieRef carrier;
    if(native&&name=="小鬼僵尸"&&site.index&&*site.index<world_.targets->size()){
        const auto& target=world_.targets->at(*site.index);if(target.unit&&target.unit->body.kind=="巨人僵尸")carrier=target.unit;
    }
    const auto source=(native||(world_.heroes.active&&world_.heroes.active->phase==CombatPhase::summon))?world_.heroes.source():std::shared_ptr<AttackSource>{};
    const auto key="zombie:"+name;
    if(catalog_.find(key)&&!world_.spawn_ban_exempt&&!carrier)try{catalog_.resolve(key,world_.heroes.players[seat_index(Seat::zombie)]->secrets,state_.bans);}catch(const std::invalid_argument&){return {};}
    if(!budget_.can_spawn(1,source)){if(native)throw std::runtime_error("Unguarded native campaign spawn");return {};}
    const auto before=world_.targets->size();auto created=factory_.zombie(name,position,facing);
    if(world_.targets->size()>before){const auto child=world_.targets->back().unit;if(!child)throw std::logic_error("native factory appended a hero proxy");
        if(carrier){inherit_carried_imp_armor(child,carrier);ColdParent parent;parent.id=id(carrier->source);
            registration_.register_unit(child,placement_.unit_card(Seat::zombie,key),Seat::zombie,true,context(),&parent);
        }else if(native&&source){ColdParent parent;parent.id=id(*source);registration_.register_unit(child,placement_.unit_card(Seat::zombie,key),Seat::zombie,true,context(),&parent);}
        if(source)ScriptedSpawnBudget::inherit(child->source,source.get());
    }return created;
}
bool ColdAdmission::inherit_carried_imp_armor(const ZombieRef& child,const ZombieRef& carrier){
    if(!child||!carrier||child==carrier||carrier->body.kind.find("巨人")==std::string::npos||!value(carrier->poison.imp_armor)||!carrier->poison.imp_armor_hp.present()||carrier->poison.imp_armor_hp.is_null()||carrier->poison.imp_armor_hp.get()<=0.)return false;
    const auto armor=carrier->poison.imp_armor.get();child->body.armor=armor=="黑路障"?"路障":armor=="黑铁桶"?"铁桶":armor;child->body.armor_hp=carrier->poison.imp_armor_hp.get();
    if(armor=="黑路障")child->expansion.black_armor.set("黑路障僵尸");else if(armor=="黑铁桶")child->expansion.black_armor.set("黑铁桶僵尸");else child->expansion.black_armor.erase();
    auto& secondhand=carrier->registration.secondhand;
    if(secondhand.present()&&!secondhand.is_null()&&yes(secondhand.get().carried_imp)){
        if(!child->registration.secondhand.present())child->registration.secondhand.set({});child->registration.secondhand.get().head.set(true);
    }
    carrier->poison.imp_armor.set("");carrier->poison.imp_armor_hp.set(0.);if(secondhand.present()&&!secondhand.is_null())secondhand.get().carried_imp.erase();return true;
}
std::optional<ExpansionVariantSetup> ColdAdmission::expansion_setup(const ColdCard& card)const{
    if(!value(card.expansion))return {};const auto& name=card.expansion.get();
    if(name!="黑普通僵尸"&&name!="黑路障僵尸"&&name!="黑铁桶僵尸"&&name!="黑旗帜僵尸"&&name!="黑撑杆僵尸"&&name!="黑橄榄僵尸"&&name!="角斗士巨人")return {};
    std::string armor;
    if(name=="黑路障僵尸")armor="路障";else if(name=="黑铁桶僵尸")armor="铁桶";else if(name=="黑橄榄僵尸"||name=="角斗士巨人")armor="黑橄榄球头盔";
    // Setup is from base definitions, prior to per-holder modifiers.
    const auto& base=catalog_.at(card.base_id);ExpansionVariantSetup setup;setup.name=name;setup.native_template=base.native_input_name;
    setup.hp=base.native_hp.get();setup.armor=armor;setup.armor_hp=base.native_armor_hp.or_missing(0.);
    if(name=="角斗士巨人"){setup.riding=base.riding_armor.get();setup.riding_hp=base.riding_armor_hp.get();}
    return setup;
}
std::optional<std::string> ColdAdmission::spawn(const std::string& key,Seat side,Point position,double facing,bool temporary,const ColdParent* parent,std::optional<AttackIdentity> attack){
    if(key=="plant:抓人草触手")throw std::invalid_argument("抓人草触手只能由存活本体生成");
    auto card=world_.spawn_ban_exempt?placement_.unit_card(side,key):placement_.player_card(side,key);
    if(card.behavior=="grass")throw std::invalid_argument("草坪是地形工具，必须通过合法放置建立原生方块");
    if(room_.deathmatch&&catalog_.deathmatch_blocked(card))return {};
    if(side==Seat::zombie&&card.behavior!="grave"&&!budget_.can_spawn(1,parent?registration_.parent_source(*parent):std::shared_ptr<AttackSource>{}))return {};
    if(key=="zombie:残骸墓碑（非生产）"&&(!parent||parent->card!="zombie:墓碑吞噬者僵尸"))throw std::invalid_argument("残骸墓碑只能由墓碑吞噬者僵尸死亡产生");
    ColdHeroScope hero(world_.heroes,side,native_secrets_);NativeObject object;
    if(card.behavior=="grave"){
        Motion p{position.x,position.y,0.,0.};auto z=factory_.zombie("普通僵尸",p,facing);if(!z)return {};
        bool on_vine=false;
        // The public state intentionally follows the source's last sync boundary.
        for(const auto& entry:world_.native_objects.entries())if(const auto* existing=std::get_if<ZombieRef>(&entry.object)){
            const auto* view=placement_.find(entry.key);if(!view||view->side!=Seat::zombie||view->hp<=0.)continue;
            const auto c=placement_.unit_card(view->original_owner,view->card->id);if(!yes(c.shell))continue;
            const double dx=pvz::py::mod(view->position.x-position.x+placement_.width()/2.,placement_.width())-placement_.width()/2.;
            if(std::abs(dx)<world_.runtime.tile*.5&&std::abs(view->position.y-position.y)<world_.runtime.tile*.5)on_vine=true;
        }
        const bool floating=placement_.cell({position.x,position.y+1.}).water&&!yes(card.shell)&&(named(card.grave_surface,"water")||!on_vine);
        z->native.entry.set(500.);z->body.hp=card.hp.get();z->body.motion.replace({position.x,position.y,0.,0.});z->protection.grave=true;z->registration.floating.set(floating);object=z;
    }else if(side==Seat::plant){
        const Cell cell{int(pvz::py::round0(position.y/world_.runtime.tile))-1,int64_t(position.x/world_.runtime.tile)};
        auto p=value(card.content)||value(card.expansion)?factory_.plant(cell,card.native_input_name,facing):native_plant(cell,card.native_input_name,facing);
        if(!p){services_.sync_terrain();return {};}
        const auto secrets=team_secrets(Seat::plant);registration_.configure_plant(p,card,secrets);object=p;
    }else{
        Motion p{position.x,position.y,0.,0.};auto z=value(card.expansion)||card.native_input_name=="小鬼僵尸"?factory_.zombie(card.native_input_name,p,facing):native_zombie(card.native_input_name,p,facing);
        if(!z)return {};if(card.native_input_name!="飞贼僵尸")z->native.entry.set(400.);if(const auto setup=expansion_setup(card))expansion_.configure(z,*setup);object=z;
    }
    registration_.register_unit(object,card,side,temporary,context(),parent,std::move(attack));
    if(key=="zombie:投篮车僵尸")std::get<ZombieRef>(object)->protection.basketball.set(20.);
    content_.configure(object,card);if(side==Seat::zombie)secrets_.on_spawn(std::get<ZombieRef>(object),card,parent);
    services_.sync_public();const auto uid=std::visit([](const auto& unit){return unit->source.id.get();},object);
    if(!placement_.find(uid))throw std::out_of_range("spawned unit is absent after public synchronization");return uid;
}
bool ColdAdmission::auto_register(const NativeObject& object,Seat side,const std::string& key,bool temporary){
    if(!catalog_.find(key))return false;ColdCard card;try{card=placement_.player_card(side,key);}catch(const std::invalid_argument&){return false;}
    registration_.register_unit(object,card,side,temporary,context());return true;
}
std::shared_ptr<const RoomPublicCard> ColdAdmission::public_card(Seat owner,const std::string& key)const{
    const auto card=placement_.unit_card(owner,key);auto result=std::make_shared<RoomPublicCard>();result->id=card.id;result->name=card.name;result->behavior=card.behavior;result->asset=card.asset;
    result->cost=card.cost;result->damage=card.damage;result->range=card.range;result->producer=card.producer;result->mushroom=yes(card.mushroom);result->flying=yes(card.flying);return result;
}
RoomRegistrationView ColdAdmission::registration_view(const NativeObject& object)const{
    RoomRegistrationView result;
    if(const auto* p=std::get_if<PlantRef>(&object)){result.registered_plant_max_hp=(*p)->content_state.maximum_hp.or_missing(0.);result.plant_armor_max=(*p)->registration.armor_max.or_missing(0.);}
    else{const auto& z=*std::get<ZombieRef>(object);result.zombie_temporary=yes(z.registration.temporary);result.floating=yes(z.registration.floating);result.coop_dormant=yes(z.registration.coop_dormant);result.first_soldier_used=yes(z.registration.first_soldier_used);result.secret_speed=z.patch.speed_factors;}
    return result;
}
} // namespace pvz::typed72
