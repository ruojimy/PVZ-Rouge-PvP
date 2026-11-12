#define PVZ72_CONTENT_CONTROLLERS_PROBE_EMBEDDED
#include "content_controllers_probe.cpp"
#include "sim/typed/native_content_phase.h"
#include "sim/typed/content_damage.h"
#include "sim/typed/barrel_crush.h"
#include "sim/typed/bonus_scan.h"
#include "sim/typed/content_ballistics.h"
#include "sim/typed/content_particles.h"
#include "sim/typed/content_admission.h"
namespace {
struct ContentPhaseProbe : ContentControllersProbe,ContentPlant70Services,ContentLanternEvents,DartPresentation,
        ContentPhasePresentation,BarrelProjectileServices,SeptemberPlantServices,ReedPlantServices,MortarPlantServices,BonusPlantServices {
    ContentCombatState combat_state;
    virtual void patched_add_entity(std::string kind,double f,Motion p){ContentControllersProbe::add_entity(std::move(kind),f,p);}
    virtual std::string tentacle_id(size_t n){return "tentacle:"+std::to_string(n);}
    virtual HitResult content_lower_hit(size_t i,double f,double a){return lower.actual.hit(i,f,a);}
    ContentBallistics content_ballistics{battle};
    ContentParticles content_particles{battle};
    bool full_content=false,content_damage_enabled=false,full_bonus=false,gas_secret=false,hardening=false,phototherapy=false;
    std::vector<std::string> custom_plants,aquatic_cards;
    ContentFrost frost{battle};
    struct ObservedLower final:ContentDamageLower {
        ContentPhaseProbe& p;ContentTargetDamageLower actual;
        explicit ObservedLower(ContentPhaseProbe& probe):p(probe),actual(p.battle,p.chain.damage,p.chain.patch){}
        HitResult hit(size_t i,double f,double a)override {
            p.calls.push_back({"pea_damage",i,f,a});p.before("pea_damage");const auto result=p.content_lower_hit(i,f,a);p.after("pea_damage");return result;
        }
        HitResult surface_hit(size_t i,double f,double a)override {
            p.calls.push_back({"pea_surface",i,f,a});p.before("pea_surface");const auto saved=p.surface_index;p.surface_index=i;
            HitResult result;try{result=actual.surface_hit(i,f,a);}catch(...){p.surface_index=saved;throw;}p.surface_index=saved;p.after("pea_surface");return result;
        }
        HitResult ash(size_t i)override{return actual.ash(i);}
        void knock(size_t i,double a)override {
            p.calls.push_back({"pea_knockback",i,a});p.before("pea_knockback");actual.knock(i,a);p.after("pea_knockback");
        }
        std::optional<double> player_damage(double amount)override {
            // HeroCombat is the installed lower wrapper. The earlier pea
            // fixture observer has already been replaced at this boundary.
            return actual.player_damage(amount);
        }
    } lower{*this};
    NativeContentDamage content_damage{battle,combat_state,lower,barrels,*this,poison,frost,flight,collision,gas_secret};
    ContentPlants70 plants70{battle,queries,target_dispatch,frost,*this,aquatic_cards};
    ContentVines vines{battle,resources,tick_state.production,hardening};
    ContentLantern content_lantern{battle,queries,target_dispatch,plants70,*this,phototherapy};
    ContentDarts darts{battle,queries,target_dispatch,poison,collision,*this,tick_state.drawing};
    MortarPlants mortars{battle,queries,target_dispatch,*this};
    ReedPlants reeds{battle,queries,target_dispatch,*this};
    SeptemberPlants september_plants{battle,world_region,queries,target_dispatch,collision,*this};
    BarrelProjectiles barrel_shots{battle,combat_state,flight,*this};
    NativeBarrelCrush barrel_crush{battle,zombies,static_cast<ZombieActionServices&>(static_cast<WorldRulesProbe&>(*this))};
    NativeContentPhases phases{battle,{target_dispatch,plants70,mortars,content64,zombies56,zombies70,flying,barrels,barrel_shots,darts,
        grenadiers,sea,frost,content_lantern,vines,september_plants,reeds},custom_plants,tick_state.drawing,*this};
    struct ObservedGate final : EntityContentGate {
        ContentPhaseProbe& probe;
        explicit ObservedGate(ContentPhaseProbe& value):probe(value){}
        void entity_gate(const EntityRef& entity)override {
            // The lower expansion alias callback is entered once, even if
            // its atlas lacks the requested image. EntityPhase performs the
            // actual suffix aliases internally; preserve the call observation.
            if(entity->art_name.present()&&!entity->art_name.is_null()&&!entity->art_name.get().empty())
                // Observation only (non-virtual): EntityPhase's source_art already aliases
                // kind->art_name per gate and clears it at the next gate, as _tracking_gate's
                // source_gate(None) restore does. A virtual call here reached the native
                // frame canvas and left 豌豆->原始豌豆弹 aliased for later entities.
                probe.ContentControllersProbe::alias_art(entity->kind,entity->art_name.get());
            probe.phases.entity_gate(entity);
        }
    } observed_gate{*this};
    BonusProjectiles bonus_projectiles{battle,content_damage,collision,rules};
    BonusPlants bonus_plants{battle,chart,squash,content_damage,*this};
    BonusScan bonus_scan{battle,{bonus_plants,bonus_projectiles,chain,shooting,lantern,peas,fume,squash}};
    ContentAdmission admission{battle,{carts,plants70,zombies70,mortars,content64,taunts,reeds,scarecrows,vines,zombies56,flying,september_plants,barrels},combat_rules.black_variants};
    J phase_events=J::array(),phase_draws=J::array();
    bool phase_seen=false;
    explicit ContentPhaseProbe(int64_t seed,double width,double splash):ContentControllersProbe(seed,width,splash){}
    void ordinary(size_t i,double f,double a)override {if(content_damage_enabled)content_damage.hit(i,f,a);else ContentControllersProbe::ordinary(i,f,a);}
    void surface(size_t i,double f,double a)override {if(content_damage_enabled)content_damage.surface_hit(i,f,a);else ContentControllersProbe::surface(i,f,a);}
    void ordinary_damage(size_t i,double f,double a)override {if(content_damage_enabled)content_damage.hit(i,f,a);else ContentControllersProbe::ordinary_damage(i,f,a);}
    std::optional<bool> surface_damage(size_t i,double f,double a)override {
        if(!content_damage_enabled)return ContentControllersProbe::surface_damage(i,f,a);
        const auto value=content_damage.surface_hit(i,f,a);return value.kind!=HitResult::Kind::none&&value.value!=0.;
    }
    HitResult ordinary(const ZombieRef& unit,double f,double a)override {
        if(content_damage_enabled)return content_damage.hit(size_t(chain.zombie_index(unit)),f,a);
        return PeaProbe::ordinary(unit,f,a);
    }
    void knockback(size_t i,double amount)override {if(content_damage_enabled)content_damage.knockback(i,amount);else ContentControllersProbe::knockback(i,amount);}
    void ash_zombie(size_t i)override {if(content_damage_enabled)content_damage.freeze_hit(i);else ContentControllersProbe::ash_zombie(i);}
    void damage_zombie(size_t i,double f,double a)override{ordinary_damage(i,f,a);}
    void surface_zombie(size_t i,double f,double a)override{surface_damage(i,f,a);}
    void player_damage(double amount)override {if(content_damage_enabled)content_damage.player_damage(amount);else ContentControllersProbe::player_damage(amount);}
    void damage_player(double amount)override {if(content_damage_enabled)content_damage.player_damage(amount);else ContentControllersProbe::damage_player(amount);}
    std::optional<TargetRoster> extra_targets()override{return ContentControllersProbe::extra_targets();}
    void plant_gate(size_t i)override{ContentControllersProbe::plant_gate(i);if(full_content)phases.plant_gate(battle.plant_roster->at(i));}
    void add_entity(std::string name,double facing,Motion position)override {
        if(!full_content){ContentControllersProbe::add_entity(std::move(name),facing,position);return;}
        phases.add_entity(std::move(name),facing,position,[&](std::string kind,double f,Motion p){patched_add_entity(std::move(kind),f,p);});
    }
    void stored_add_entity(std::string name,double facing,Motion p)override{ContentControllersProbe::add_entity(std::move(name),facing,p);}
    void prepare_star_atlas()override{phase_events.push_back({"bonus_star_assets"});}
    bool prepare_blue_pea_atlas()override{phase_events.push_back({"bonus_blue_assets"});return true;}
    void content_before_tick()override{ContentControllersProbe::content_before_tick();if(full_content)phases.before_tick();}
    void content_projectiles()override{ContentControllersProbe::content_projectiles();if(full_content)phases.projectiles();}
    void content_after_plants()override{ContentControllersProbe::content_after_plants();if(full_content)phases.after_plants();}
    void before_native_tick(double now)override{ContentControllersProbe::before_native_tick(now);if(full_bonus)bonus_scan.before(now);}
    void after_native_tick(double now)override{ContentControllersProbe::after_native_tick(now);if(full_bonus)bonus_scan.after(now,avatar_order());}
    void reconcile_barrels()override{ContentControllersProbe::reconcile_barrels();if(full_content)barrels.reconcile();}
    void break_poisoned_barrel(const ZombieRef& unit)override{ContentControllersProbe::break_poisoned_barrel(unit);if(full_content)barrels.break_barrel(unit);}
    void detach_poisoned_barrel(const ZombieRef& unit)override{ContentControllersProbe::detach_poisoned_barrel(unit);if(full_content)barrels.detach(unit);}
    void crush_barrel_plant(const ZombieRef& unit,const PlantRef& plant)override{if(full_content)barrel_crush.crush(unit,plant);else ContentControllersProbe::crush_barrel_plant(unit,plant);}
    PlantRef spawn_tentacle_native(Cell cell,double facing)override {
        const auto plant=plant_original(battle,cell,"坚果",facing);all_plants.push_back(plant);return plant;
    }
    void register_tentacle(const PlantRef& plant,const Field<std::string>& parent)override {
        const auto id=tentacle_id(all_plants.size());plant->source.id.set(id);plant->source.owner.set("plant");
        plant->protection.card.set("plant:抓人草触手");battle.native_objects.set(id,plant);phase_events.push_back({"register_tentacle",id,nullable(parent)});
    }
    void plant70_event(const Plant70Event& value)override {
        if(value.kind==Plant70Event::Kind::tentacle_spawn)phase_events.push_back({"tentacle_spawn",nullable(value.source),nullable(value.head)});
        else if(value.kind==Plant70Event::Kind::tentacle_hit)phase_events.push_back({"tentacle_hit",nullable(value.source),nullable(value.head),nullable(value.target)});
        else {J water=J::array();for(const auto& [row,col]:value.water)water.push_back({row,col});phase_events.push_back({"lettuce_freeze",nullable(value.source),water,value.targets});}
        before("phase_event");after("phase_event");
    }
    void sync_terrain()override{phase_events.push_back({"sync_terrain"});}
    void tentacle_knock(size_t index,double amount)override{knockback(index,amount);}
    void lantern_wake(const Field<std::string>& id,const std::vector<Field<std::string>>& targets)override{J found=J::array();for(const auto& target:targets)found.push_back(nullable(target));phase_events.push_back({"lantern_wake",nullable(id),found});}
    void lantern_burn(const Field<std::string>& id,size_t hits)override{phase_events.push_back({"lantern_burn",nullable(id),hits});}
    void september_event(const SeptemberPlantEvent& value)override{phase_events.push_back({"september",int(value.kind),nullable(value.source),value.sun_amount});}
    void reed_event(const ReedEvent& value)override{phase_events.push_back({"reed",nullable(value.source),value.overload,value.targets});}
    void mortar_event(const MortarPlantEvent& value)override{phase_events.push_back({"mortar",nullable(value.source),value.spring,value.shots,value.targets});}
    void spring_knockback(size_t i,double amount)override{knockback(i,amount);}
    void draw_dart(const EntityRef& entity,Point point,double angle)override{phase_draws.push_back({"dart",entity_index(entity),{point.x,point.y},angle});}
    void draw_mortar_projectile(const EntityRef& entity,double angle,const std::optional<Point>& trail,std::string_view tail)override {
        phase_draws.push_back({"mortar",entity_index(entity),angle,trail?J::array({trail->x,trail->y}):J(nullptr),tail});
    }
    void draw_ghost_effect(const GhostBlast& value)override{phase_draws.push_back({"ghost",value.tick,{value.point.x,value.point.y}});}
    void draw_reed_effect(const ReedBolt& value)override{phase_draws.push_back({"reed",value.tick,value.content});}
    void draw_spring_effect(const SpringSwipe& value)override{phase_draws.push_back({"spring",value.tick,{value.point.x,value.point.y},value.angle});}
    void draw_grenade_effect(const GrenadeBlast& value)override{phase_draws.push_back({"grenade",value.tick,{value.point.x,value.point.y},value.instant});}
    void draw_grenade_projectile(const GrenadeRef& shot,double angle,double alpha)override{phase_draws.push_back({"grenade_projectile",{shot->motion.x,shot->motion.y},angle,alpha});}
    void draw_hook_rope(Point point)override{phase_draws.push_back({"hook_rope",{point.x,point.y}});}
    void draw_zombie_projectile(const ContentProjectileRef& shot,std::string_view sprite,double angle,double alpha)override{phase_draws.push_back({"zombie_projectile",sprite,{shot->motion.x,shot->motion.y},angle,alpha});}
    void draw_lettuce_flash(const LettuceFlash& flash)override{J cells=J::array();for(const auto& [row,col]:flash.water)cells.push_back({row,col});phase_draws.push_back({"lettuce",flash.tick,cells,{flash.point.x,flash.point.y}});}
    void draw_zombie70_effects()override{ContentControllersProbe::draw_zombie70_effects();if(full_content)phases.draw_zombie70_effects();}
    void restore_content_art()override{battle.runtime.presentation.source_art.clear();}
    void alias_content_art(const std::string& old,const std::string& name)override{alias_art(old,name);}
    bool has_content_sprite(const std::string& name)const override{return has_sprite(name);}
    static void phase_entity_fields(Entity& e,const J& f) {
        read_shot_fields(e,f);read(f,"_pvp_source_entity",e.source.source_entity);read(f,"_pvp_id",e.source.id);read(f,"_pvp_plant_kind",e.source.plant_kind);
        read(f,"_pvp_melon_splash",e.source.melon_splash);read(f,"_pvp_area_damage",e.source.area_damage);read(f,"_pvp_fire_color",e.source.fire_color);
        read(f,"__pvz_sb_zombie_pea_fire",e.source.zombie_fire);
        read(f,"_pvp_mortar",e.mortar.mortar);read(f,"_pvp_mortar_bonus_done",e.mortar.bonus_done);read(f,"_pvp_mortar_speed",e.mortar.speed);
        read(f,"_pvp_multi_red",e.mortar.multi_red);read(f,"三向蓝火弹",e.mortar.tripea_blue);read(f,"__pvz_sb_charmed_plant_zombie_pea",e.pea.charmed_pea);
        auto& s=e.content_state;read(f,"_pvp_barrel_contact",s.barrel_contact);read(f,"_pvp_content_ready",s.ready);read(f,"_pvp_dart",s.dart);
        read(f,"_pvp_return",s.returning);read(f,"_pvp_turned",s.turned);read(f,"_pvp_distance",s.distance);read(f,"_pvp_speed",s.speed);read(f,"_pvp_launch_direction",s.launch_direction);
        if(f.contains("_pvp_leg_hits"))s.leg_hits.set(f.at("_pvp_leg_hits").get<std::vector<std::string>>());
        if(f.contains("_pvp_primal_knock_hits"))s.primal_knock_hits.set(f.at("_pvp_primal_knock_hits").get<std::vector<std::string>>());
    }
    static J phase_entity_json(const EntityRef& entity) {
        const auto& e=*entity;const auto& s=e.content_state;J result={{"名",e.kind},{"位置",as_json(e.motion.get())},{"方向",e.facing}};
        write(result,"_pvp_content_ready",s.ready);write(result,"_pvp_dart",s.dart);write(result,"_pvp_return",s.returning);write(result,"_pvp_turned",s.turned);
        write(result,"_pvp_distance",s.distance);write(result,"_pvp_speed",s.speed);write(result,"_pvp_launch_direction",s.launch_direction);write(result,"_pvp_leg_hits",s.leg_hits);
        write(result,"_pvp_primal_knock_hits",s.primal_knock_hits);write(result,"_pvp_barrel_contact",s.barrel_contact);write(result,"_pvp_art_name",e.art_name);
        write(result,"_pvp_content",e.source.content);write(result,"_pvp_plant_kind",e.source.plant_kind);write(result,"_pvp_mortar_bonus_done",e.mortar.bonus_done);
        write(result,"上次制导",e.bonus.last_guide);write(result,"制导次数",e.bonus.guide_count);return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="phase_setup") {
            phase_seen=true;full_content=op.value("installed",false);content_damage_enabled=op.value("damage",true);full_bonus=op.value("bonus",false);
            installed=full_content;gas_secret=op.value("gas",false);hardening=op.value("hardening",false);phototherapy=op.value("phototherapy",false);
            custom_plants=op.value("custom",std::vector<std::string>{});aquatic_cards=op.value("aquatic",std::vector<std::string>{});
            if(content_damage_enabled){chain.chili.bind_impacts(content_damage);chain.chili.require_installed_impacts();}
            bonus_projectiles.bind_content_ballistics(content_ballistics);squash.ballistics.bind_compute_policy(content_ballistics);squash.ballistics.require_compute_policy();
            battle.runtime.bind_particles(content_particles);battle.runtime.require_particles();
            if(full_content){owner_phase.bind_content_gate(observed_gate);owner_phase.require_content_gate();}
        }else if(name=="phase_entity") {
            add_entity(op.at("name"),op.value("facing",1.),motion(op.at("position")));phase_entity_fields(*births.back(),op.value("fields",J::object()));
        }else if(name=="phase_admit") {
            const auto& values=op.at("card");ColdCard card;card.id=values.at("id");read(values,"content",card.content);read(values,"hp",card.hp);read(values,"native_hp",card.native_hp);
            if(op.contains("plant"))admission.configure(plant_ref(op.at("plant").get<size_t>()),card);else admission.configure(units.at(op.at("unit").get<size_t>()),card);
        }else if(name=="phase_reaim") {
            battle.native_time=op.at("now");bonus_projectiles.reaim(births.at(op.at("entity").get<size_t>()));
        }else if(name=="phase_particles") {
            if(op.at("source_index").is_null())world.source_index.reset();else world.source_index=op.at("source_index").get<int64_t>();
            battle.runtime.emit_particles(op.at("name"),point(op.at("point")),op.at("count"));
        }else if(name=="phase_entity_fields")phase_entity_fields(*births.at(op.at("entity").get<size_t>()),op.at("fields"));
        else if(name=="phase_prepare_dart")ContentDarts::prepare(births.at(op.at("entity").get<size_t>()));
        else if(name=="phase_darts_separate")darts.separate();
        else if(name=="phase_darts_step")darts.projectiles();
        else if(name=="phase_before")phases.before_tick();
        else if(name=="phase_projectiles")phases.projectiles();
        else if(name=="phase_after")phases.after_plants();
        else if(name=="phase_frost")frost.apply();
        else if(name=="phase_vines")vines.tick();
        else if(name=="phase_lantern")content_lantern.pulses();
        else if(name=="phase_plants70_before")plants70.before_tick();
        else if(name=="phase_plant_tick")plants70.plant_tick(plant_ref(op.at("plant").get<size_t>()));
        else if(name=="phase_configure") {
            const auto plant=plant_ref(op.at("plant").get<size_t>());const auto content=op.at("name").get<std::string>();
            result=plants70.configure(plant,content,op.value("hp",6.))||vines.configure(plant,content);
        }else if(name=="phase_plant_fields") {
            auto& p=*plant_ref(op.at("plant").get<size_t>());const auto& f=op.at("fields");auto& s=p.content70;auto& c=p.content_state;
            read(f,"_pvp_id",p.source.id);read(f,"_pvp_owner",p.source.owner);read(f,"_pvp_content",p.source.content);read(f,"植物血",p.hp);read(f,"睡觉",p.sleep);
            read(f,"冰冻",p.ice);read(f,"黄油",p.butter);read(f,"眩晕",p.stun);read(f,"路灯",p.lamp);read_death(f,"死",p.dead);read(f,"_pvp_crushed",p.crushed);
            read(f,"_pvp70_clock",s.clock);read(f,"_pvp_head_clock",s.head_clock);read(f,"_pvp_head_age",s.head_age);read(f,"_pvp_head_phase",s.head_phase);read(f,"_pvp_head_target",s.head_target);
            read(f,"_pvp_was_asleep",s.was_asleep);read(f,"_pvp_interval",c.interval);read(f,"_pvp_vine_clock",c.vine_clock);read(f,"_pvp_vine_produced",c.vine_produced);read(f,"_pvp_lantern_timer",c.lantern_timer);
            read_point(f,"_pvp_head_point",p.head_point);read_point(f,"_pvp_head_goal",s.head_goal);read_point(f,"_pvp_head_start",s.head_start);
        }else if(name=="phase_player") {
            const auto unit=op.contains("unit")?units.at(op.at("unit").get<size_t>()):ZombieRef{};
            const auto source=unit?source_ref(unit):source_ref(births.at(op.at("entity").get<size_t>()));
            const auto owner=world.owner(source).value();const auto target=parse_seat(op.at("target").get<std::string>());
            HeroContext scope(world,{target,owner,unit?CombatPhase::zombies:CombatPhase::entities,source,{}});
            const auto value=content_damage.player_damage(op.at("amount"),unit,op.value("native_bite",false));if(value)result=*value;
        }else if(name=="phase_hit") {
            const auto e=births.at(op.at("entity").get<size_t>());const auto owner=world.owner(source_ref(e)).value();
            HeroContext scope(world,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::entities,source_ref(e),{}});
            const size_t index=op.at("target");const auto kind=op.value("kind",std::string("ordinary"));HitResult hit;
            if(kind=="surface")hit=content_damage.surface_hit(index,e->facing,op.at("amount"));
            else if(kind=="ash")hit=content_damage.freeze_hit(index);
            else if(kind=="head")hit=content_damage.head_impact(e,index,e->facing,op.at("amount"),op.value("surface",false));
            else if(kind=="knock")content_damage.knockback(index,op.at("amount"));
            else hit=content_damage.hit(index,e->facing,op.at("amount"));
            if(hit.kind!=HitResult::Kind::none)result=hit.kind==HitResult::Kind::boolean?J(hit.value!=0.):J(hit.value);
        }else return ContentControllersProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        ContentControllersProbe::extra_snapshot(row);if(!phase_seen)return;
        J entities=J::array(),plant_records=J::array(),pending=J::array(),frozen=J::array();for(const auto& e:births)entities.push_back(phase_entity_json(e));
        auto merge_entities=[&](const char* key,const EntityRoster& roster){for(size_t i=0;i<roster.size();++i)row[key][i].update(phase_entity_json(roster[i]));};
        merge_entities("effect_births",births);merge_entities("entities",*battle.runtime.entities.list());merge_entities("legacy_peas",*battle.zombie_peas.legacy);
        for(const auto& e:*darts.pending)pending.push_back(entity_index(e));for(const auto& t:frost.pending)frozen.push_back(label(t));
        for(const auto& p:all_plants) {
            const auto& s=p->content70;const auto& c=p->content_state;J item={{"植物",p->kind},{"坐标",{p->cell.y,p->cell.x}}};
            write(item,"植物血",p->hp);write(item,"_pvp_content",p->source.content);write(item,"_pvp_id",p->source.id);write(item,"睡觉",p->sleep);
            write(item,"_pvp70_clock",s.clock);write(item,"_pvp_head_clock",s.head_clock);write(item,"_pvp_head_age",s.head_age);write(item,"_pvp_head_phase",s.head_phase);write(item,"_pvp_parent",s.parent);
            write(item,"_pvp_head_target",s.head_target);write(item,"_pvp_head_color",s.head_color);write(item,"_pvp_head_gone",s.head_gone);write(item,"_pvp_head_crushed",s.head_crushed);write(item,"_pvp_basin_removed",s.basin_removed);
            write(item,"_pvp_head_hits",s.head_hits);write(item,"_pvp_heads",s.heads);write(item,"_pvp_was_asleep",s.was_asleep);
            for(const auto& [key,point]:std::initializer_list<std::pair<const char*,const Field<Point>*>>{{"_pvp_head_point",&p->head_point},{"_pvp_head_goal",&s.head_goal},{"_pvp_head_start",&s.head_start},{"_pvp_head_aim",&s.head_aim}})
                if(point->present())item[key]={point->get().x,point->get().y};
            write(item,"_pvp_interval",c.interval);write(item,"_pvp_before_shot",c.before_shot);write(item,"_pvp_before_cd",c.before_cd);write(item,"_pvp_vine_clock",c.vine_clock);write(item,"_pvp_vine_produced",c.vine_produced);
            write(item,"_pvp_awake_forever",c.awake_forever);write(item,"_pvp_lantern_timer",c.lantern_timer);
            write(item,"_pvp_max_hp",c.maximum_hp);write(item,"_pvp_hardening_form",c.hardening_form);
            write(item,"_pvp_content_age",p->content_age);write(item,"_pvp_attack_clock",p->attack_clock);
            write(item,"冰冻",p->ice);write(item,"黄油",p->butter);write(item,"眩晕",p->stun);write(item,"灰烬",p->ash);
            if(s.basin_terrain.present()){auto saved=tile_state(s.basin_terrain.get());write(saved,"_pvp_basin",s.basin_terrain.get()->basin);item["_pvp_basin_terrain"]=saved;}
            row["all_plants"][plant_records.size()].update(item);
            for(size_t i=0;i<battle.plant_roster->size();++i)if(battle.plant_roster->at(i)==p)row["plants"][i].update(item);
            plant_records.push_back(item);
        }
        for(size_t y=0;y<battle.terrain.grid.size();++y)for(size_t x=0;x<battle.terrain.grid[y].size();++x)write(row["terrain"][y][x],"_pvp_basin",battle.terrain.grid[y][x]->basin);
        for(size_t i=0;i<PlantProbe::held.size();++i)write(row["held_tiles"][i],"_pvp_basin",PlantProbe::held[i]->basin);
        J cold_hits=J::array();for(const auto& unit:units) {
            const auto& field=unit->body.content_target.ice_chili_hits;if(!field.present()){cold_hits.push_back(nullptr);continue;}
            auto keys=field.get();std::sort(keys.begin(),keys.end());J values=J::array();for(const auto& key:keys)values.push_back(key?J(*key):J(nullptr));cold_hits.push_back(values);
        }
        row["content_phase"]={{"entities",entities},{"plants",plant_records},{"darts",pending},{"frost",frozen},{"depth",combat_state.damage_depth},{"events",phase_events},{"draws",phase_draws},{"cold_hits",cold_hits}};
    }
};
J run_content_phase(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");ContentPhaseProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    NativeBirthScope births_scope(probe.battle.runtime,static_cast<PlantRegionServices&>(probe));
    probe.operations(input.at("operations"));return probe.states;
}
void verify_source_links() {
    const auto require=[](bool valid){if(!valid)throw std::logic_error("source weak binding contract");};
    auto entity=std::make_shared<Entity>("豌豆",1.,Motion{});auto entity_source=source_ref(entity);
    require(entity_source->entity.lock()==entity);AttackSource copied=*entity_source;require(!copied.entity.lock());
    AttackSource moved=std::move(copied);require(!moved.entity.lock());
    entity_source->entity=entity_source->entity;require(entity_source->entity.lock()==entity);
    entity_source->entity=std::move(entity_source->entity);require(entity_source->entity.lock()==entity);
    auto unit=std::make_shared<CombatZombie>();unit->body.kind="source-before";auto unit_source=source_ref(unit);
    require(unit_source->unit.lock()==unit);AttackSource snapshot=*unit_source;require(!snapshot.unit.lock());
    unit->body.kind="source-after";require(snapshot.zombie_name()=="source-before");
    unit_source->unit=unit_source->unit;require(unit_source->unit.lock()==unit);
    unit_source->unit=std::move(unit_source->unit);require(unit_source->unit.lock()==unit);
    std::weak_ptr<CombatZombie> lifetime=unit;unit.reset();require(!lifetime.expired());unit_source.reset();
    require(lifetime.expired()&&snapshot.zombie_name()=="source-before");
    auto destination=std::make_shared<CombatZombie>();source_ref(destination);destination->source=snapshot;
    require(!destination->source.unit.lock());require(source_ref(destination)->unit.lock()==destination);
}
}
int main(int argc,char** argv) {
    try {verify_source_links();if(argc!=3)throw std::invalid_argument("usage: content_phase72_probe inputs output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("phase fixture streams");std::string line;while(std::getline(input,line))if(!line.empty())output<<run_content_phase(J::parse(line)).dump()<<'\n';return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
