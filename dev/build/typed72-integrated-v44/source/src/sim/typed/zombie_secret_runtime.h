#pragma once
#include "sim/typed/cold_zombie_secrets.h"
#include "sim/typed/hero_phase.h"
#include "sim/typed/plant_death_rules.h"
#include "sim/typed/resources.h"
#include "sim/typed/zombie_pea.h"
#include <map>
namespace pvz::typed72 {
// One event in the shape of the source ZombieSecrets._emit call.
struct ZombieSecretEvent {
    std::string name;
    std::optional<Seat> side;
    std::optional<std::string> entity,card,item,slot,wearer;
    double amount=0.;
    int64_t count=0;
};
class ZombieSecretRuntimeServices {
public:
    virtual ~ZombieSecretRuntimeServices()=default;
    // g["伤害僵尸"](index,facing,amount) over the current (full) roster.
    virtual void damage_zombie(size_t index,double facing,double amount)=0;
    // b.spawn(card,"zombie",x,y,facing,True) with _acting_seat set, nullopt when banned.
    virtual std::optional<std::string> spawn_zombie(const std::string& card,Point,double facing,Seat acting)=0;
    virtual void secret_event(const ZombieSecretEvent&)=0;
};
struct ZombieSecretPickup {
    std::string id,slot,name,kind;
    double hp=0.,until=0.;
    Point position;
    const CombatZombie* dropper=nullptr;
    std::optional<std::string> black;
};
// zombie_secrets.ZombieSecrets runtime: the 30 Hz step and its state hooks.
// Spawn-time, damage-factor, last-stand and pressure rules already have their
// typed owners (ColdZombieSecrets, UnitProtection, HeroCombat, HeroPhase).
class ZombieSecretRuntime {
public:
    ZombieSecretRuntime(TypedBattleState& world,ColdZombieSecrets& secrets,const RallyPoints& rally,PlantDeathState& deaths,
        Resources& resources,ZombiePeas& peas,ZombieSecretRuntimeServices& services)
        :world_(world),secrets_(secrets),rally_(rally),deaths_(deaths),resources_(resources),peas_(peas),services_(services){}
    std::vector<Seat> present;
    std::vector<ZombieSecretPickup> pickups;
    // ZombieSecrets.effects: the 玉米卷 throw shown for .8 s (public snapshot only).
    struct Effect {std::string kind;Seat seat;std::string target;double x=0.,y=0.,tx=0.,ty=0.,born=0.,until=0.;};
    std::vector<Effect> effects;
    uint64_t pickup_serial=0;
    void lock();
    void step(double dt);
    void on_armor_break(const ZombieRef&,ArmorSlot,const std::string& name,double top);
    void on_unit_gone(const NativeObject&);
private:
    TypedBattleState& world_;ColdZombieSecrets& secrets_;const RallyPoints& rally_;PlantDeathState& deaths_;
    Resources& resources_;ZombiePeas& peas_;ZombieSecretRuntimeServices& services_;
    std::map<std::string,double> clock_;
    bool tick(const std::string& key,double dt,double period);
    bool zombie(const CombatZombie&)const;
    bool own(const ZombieRef&)const;
    double distance(double ax,double ay,double bx,double by)const;
    std::vector<Seat> holders(std::string_view)const;
    std::optional<Point> hero_spot(Seat)const;
    bool berserk()const;
    void crowd();void steady_giants();void slow_charmed();void rally_dave_speed();
    void heal(Seat);void taco(Seat);void fast_shots();void basket_lock();void pole_smash();void smash(const ZombieRef&);
    void relic_expiry();void convert();void take_pickups();
    bool wearer(const CombatZombie&,const ZombieSecretPickup&)const;
    bool riding_wearer(const ZombieRef&,const ZombieSecretPickup&)const;
    void pay(Seat,double amount,Point,const std::string& reason);
};
} // namespace pvz::typed72
