// Typed NativeTargets dispatch. The required raw patch chain is injected as
// a typed C++ interface; there is no default or old-runtime fallback.
#pragma once
#include "sim/typed/pve_director_state.h"
#include "sim/typed/zombie_secret_state.h"
#include "sim/typed/cold_factory_state.h"
#include "sim/typed/cold_registration_state.h"
#include "sim/typed/expansion_combat_state.h"
#include "sim/typed/protection.h"
#include "sim/typed/plant.h"
#include "sim/typed/terrain.h"
#include "sim/typed/native_registry.h"
#include "sim/typed/wind_state.h"
#include "sim/typed/fume_state.h"
#include "sim/typed/grenadier_state.h"
#include "sim/typed/content_zombie64_state.h"
#include "sim/typed/content_zombie_state.h"
#include "sim/typed/content_zombie56_state.h"
#include "sim/typed/content_zombie70_state.h"
#include <span>
#include <unordered_set>

namespace pvz::typed72 {
struct ZombiePatchState {
    Field<bool> plant_zombie,chili_exploded,doom_exploded,gravebuster_done;
    Field<bool> duck;
    Field<std::string> plant_name;
    Field<double> observed_max_hp,plant_max_hp,knockback;
    Field<double> fire_animation,aim_angle,chili_row_hint,doom_life_ticks,doom_life_time;
    Field<double> shoot,blover_cooldown,blover_wind_tick,lantern_cooldown;
    Field<double> umbrella_cooldown,magnet_cooldown;
    Field<bool> umbrella_secret,umbrella_initialized;
    Field<bool> squash_used,no_attack;
    Field<double> bite_plant;
    Field<Point> miner_rally;
    std::vector<std::pair<std::string,double>> speed_factors;
    Field<double> shotgun_volley;
    Field<double> torch_sleep_until,torch_brain;
    Field<double> shooting_cooldown,burst_left,burst_cooldown,jump_assist_cooldown;
    Field<double> fume_cooldown,fume_attack_angle,fume_damage_done,fume_bubble_tick;
    // Legacy True is a kind-dependent resistance, distinct from numeric 1.
    bool knockback_is_boolean=false;
};
struct CombatZombie {
    PveZombieState pve;
    ZombieSecretUnitState secret;
    ColdFactoryZombieState factory;
    ColdZombieRegistrationState registration;
    ExpansionCombatState expansion;
    RecordId identity;
    Zombie body;
    AttackSource source;
    UnitProtectionState protection;
    ZombiePatchState patch;
    ZombieNativeState native;
    GrenadierState grenadier;
    ContentZombie64State content64;
    ContentZombieState content;
    ContentZombie56State content56;
    ContentZombie70State content70;
    ZombiePoisonState poison;
    bool orphan_barrel=false;
    Field<std::shared_ptr<Motion>> barrel_position;
    Field<Point> head_point;
    Field<Point> anchor;
    Field<double> armor_max,hand_max;
    Field<double> max_hp,born;
    Field<double> base_speed,walk_speed,hop_clock;
    Field<bool> flight;
    Field<bool> mature,produced;
    Field<bool> producer,permanently_awake;
    Field<double> idle,production_rate;
    Field<std::string> taunted_by;
    Field<std::vector<ChiliAttackKey>> chili_ash_hits;
    CombatZombie(){source.bind_zombie_kind(body.kind);}
    CombatZombie(const CombatZombie&)=delete;
    CombatZombie& operator=(const CombatZombie&)=delete;
    DamageTarget damage_target(){return {body.hp,body.hand,source,protection};}
};
using ZombieRef=std::shared_ptr<CombatZombie>;
inline std::shared_ptr<AttackSource> source_ref(const ZombieRef& unit){unit->source.unit.bind(unit);return {unit,&unit->source};}

struct CombatTarget {
    ZombieRef unit;
    Seat hero=Seat::zombie;
    static CombatTarget zombie(ZombieRef unit){if(!unit)throw std::invalid_argument("null combat unit");return {std::move(unit),Seat::zombie};}
    static CombatTarget player(Seat side){return {{},side};}
    bool is_hero() const noexcept{return !unit;}
    friend bool operator==(const CombatTarget& a,const CombatTarget& b){return a.unit==b.unit&&(a.unit||a.hero==b.hero);}
};
using TargetRoster=std::vector<CombatTarget>;

// full_targets restores the original LIST identity even when the body replaces
// it, removing only inserted objects and retaining removals/new summons.
class FullTargetsScope {
public:
    FullTargetsScope(std::shared_ptr<TargetRoster>& roster,std::optional<std::span<const CombatTarget>> extras,std::shared_ptr<TargetRoster> original={});
    ~FullTargetsScope() noexcept;
    FullTargetsScope(const FullTargetsScope&)=delete;
    FullTargetsScope& operator=(const FullTargetsScope&)=delete;
    void close();
private:
    std::shared_ptr<TargetRoster>* current_=nullptr;
    std::shared_ptr<TargetRoster> original_;
    TargetRoster inserted_;
};

struct HitResult {
    enum class Kind { none,boolean,hero_amount } kind=Kind::none;
    double value=0;
    static HitResult flag(bool value){return {Kind::boolean,value?1.:0.};}
    static HitResult hero(double amount){return {Kind::hero_amount,amount};}
};
enum class ArmorSlot { head,hand };
class RawDamageChain {
public:
    virtual ~RawDamageChain()=default;
    virtual HitResult ordinary(const ZombieRef&,double facing,double amount)=0;
    virtual HitResult surface(const ZombieRef&,double facing,double amount)=0;
    virtual HitResult ash(const ZombieRef&)=0;
    virtual void armor_broken(const ZombieRef&,ArmorSlot,const std::string& kind,double maximum)=0;
};

class TargetDamage {
public:
    TargetDamage(HeroCombat& heroes,UnitProtection& protection,RawDamageChain& raw)
        :heroes_(heroes),protection_(protection),raw_(raw){}
    // These flags correspond to whether NativeBattle installed the respective
    // exact secret hook. A production world derives them from its locked deck.
    bool watch_armor=false,shield_first=false,adjust_amount=true;
    // Capture the target reference before callbacks can replace the roster
    // containing the caller's CombatTarget element.
    HitResult ordinary(CombatTarget,double facing,double amount);
    HitResult surface(CombatTarget,double facing,double amount);
    HitResult ash(CombatTarget);
    bool has_packet(const ZombieRef& target) const{return packets_.contains(target.get());}
private:
    enum class Callback { ordinary,surface };
    HeroCombat& heroes_;
    UnitProtection& protection_;
    RawDamageChain& raw_;
    std::unordered_set<const CombatZombie*> packets_;
    void record_melon(const CombatTarget&);
    HitResult unit_damage(Callback,const ZombieRef&,double,double);
    HitResult shielded(Callback,const ZombieRef&,double,double);
};

// The new world owns each unit's body/metadata once. Shared references retain
// an already-selected unit during nested deaths even after roster removal.
// There is deliberately no step()/legacy conversion until the full driver is
// implemented; this type is not a selectable production battle backend yet.
struct TypedBattleState : EntityBirthObserver {
    using UnitId=Store<ZombieRef>::Id;
    explicit TypedBattleState(int64_t seed=1):runtime(seed),room_rng(seed),heroes(runtime),protection(heroes){runtime.birth_observer=this;}
    TypedBattleState(const TypedBattleState&)=delete;
    TypedBattleState& operator=(const TypedBattleState&)=delete;
    CombatRuntime runtime;
    PyRandom room_rng;
    HeroCombat heroes;
    UnitProtection protection;
    Store<ZombieRef> units;
    Store<PlantRef> plants;
    std::shared_ptr<PlantRoster> plant_roster=std::make_shared<PlantRoster>();
    WorldTerrain terrain;
    PlantCatalog plant_catalog;
    PlantPlacementState placement;
    NativeObjectRegistry native_objects;
    WindEnvironment wind_environment;
    ContentProjectiles content_projectiles;
    FumeState fume;
    BallisticHistory ballistics;
    ZombiePeaWorld zombie_peas;
    bool dense_planting=false;
    // The live match installs NativePlantZombies. A component oracle can
    // explicitly stop at the underlying bonus patch to compare that layer.
    bool native_plant_zombies_installed=true;
    const std::vector<Cell>* pea_shell_cells=nullptr;
    Field<double> world_width,world_height;
    MatchMode mode=MatchMode::duel;
    TargetRoster omitted_targets();
    std::vector<ZombieRef> suspended_graves;
    int spawn_ban_exempt=0;
    double native_time=0.;
    std::shared_ptr<TargetRoster> targets=std::make_shared<TargetRoster>();
    void entity_born(const EntityRef& entity)override {
        if(heroes.active)heroes.tag_entity(source_ref(entity),&entity->motion.get(),entity->flight,heroes.owner(),heroes.source());
    }
    UnitId add_zombie(ZombieRef unit){
        if(!unit)throw std::invalid_argument("null world unit");
        if(!unit->identity.value)unit->identity=runtime.identities.assign();
        targets->push_back(CombatTarget::zombie(unit));
        try{return units.emplace(std::move(unit));}
        catch(...){targets->pop_back();throw;}
    }
    Store<PlantRef>::Id add_plant(PlantRef plant){
        if(!plant)throw std::invalid_argument("null world plant");
        if(!plant->identity.value)plant->identity=runtime.identities.assign();
        plant_roster->push_back(plant);
        try{return plants.emplace(std::move(plant));}
        catch(...){plant_roster->pop_back();throw;}
    }
    void erase_plant_at(size_t index){
        const auto plant=plant_roster->at(index);
        if(std::count(plant_roster->begin(),plant_roster->end(),plant)==1){
            const auto& order=plants.order();
            const auto found=std::find_if(order.begin(),order.end(),[&](auto id){return plants.at(id)==plant;});
            if(found!=order.end())plants.erase(*found);
        }
        plant_roster->erase(plant_roster->begin()+index);
    }
    bool remove_zombie(UnitId id){auto* unit=units.find(id);if(!unit)return false;const auto retained=*unit;std::erase_if(*targets,[&](const CombatTarget& t){return t.unit==retained;});return units.erase(id);}
    void erase_mobile_at(size_t index){
        const auto unit=targets->at(index).unit;
        if(!unit)throw std::logic_error("mobile phase cannot erase a hero");
        // A repeated list entry must continue to resolve the same object.
        const auto duplicate=std::count_if(targets->begin(),targets->end(),[&](const auto& t){return t.unit==unit;})>1;
        if(!duplicate){
            const auto& order=units.order();
            const auto it=std::find_if(order.begin(),order.end(),[&](auto id){return units.at(id)==unit;});
            if(it!=order.end())units.erase(*it);
        }
        targets->erase(targets->begin()+index);
    }
};

// Native callbacks resolve the current record by the live roster and index,
// including when a gate substitutes a list or enters a nested damage scope.
class LiveBattleSources {
public:
    explicit LiveBattleSources(TypedBattleState& world):heroes_(world.heroes),previous_(std::exchange(heroes_.live_world,&world)){}
    ~LiveBattleSources(){heroes_.live_world=previous_;}
    LiveBattleSources(const LiveBattleSources&)=delete;
private:
    HeroCombat& heroes_;
    const TypedBattleState* previous_;
};
} // namespace pvz::typed72
