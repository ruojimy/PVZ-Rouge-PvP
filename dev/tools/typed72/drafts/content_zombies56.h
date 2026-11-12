#pragma once
#include "sim/typed/scripted_spawn_budget.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct Zombie56Event {
    enum class Kind {dance_started,summon} kind;
    Field<std::string> source,entity;
    Seat owner=Seat::zombie;
    Point position;
    std::optional<double> slot;
};
class ContentZombie56Services {
public:
    virtual ~ContentZombie56Services()=default;
    virtual void alias_art(const std::string&,const std::string&)=0;
    virtual ZombieRef spawn_zombie56(const std::string& card,Point,double facing,const ScriptedSpawnOrigin& parent)=0;
    virtual void zombie56_event(const Zombie56Event&)=0;
};
class ContentZombies56 {
public:
    ContentZombies56(TypedBattleState& world,ScriptedSpawnBudget& budget,const TargetSight& published,
                     const bool& wild_secret,ContentZombie56Services& services)
        :world_(world),budget_(budget),published_(published),wild_secret_(wild_secret),services_(services){}
    bool configure(const ZombieRef&,std::string_view name,double native_hp,bool observed_max_hp);
    void before_tick();
    void gate(const ZombieRef&);
    void finish(const ZombieRef&);
    std::vector<ZombieRef> children(const ZombieRef&,bool wild=false)const;
    void release(const ZombieRef&);
    ZombieRef leader_for(const ZombieRef&);
    void anchor(const ZombieRef& child,const ZombieRef& leader,bool after_motion=false);
    void fill_group(const ZombieRef&);
    void spawn_squad(const ZombieRef&);
    bool deferred_dancer(const ScriptedSpawnOrigin&,double slot,bool wild);
    bool deferred_sled(const ScriptedSpawnOrigin&,double slot);
    static bool alive(const ZombieRef&);
private:
    TypedBattleState& world_;
    ScriptedSpawnBudget& budget_;
    const TargetSight& published_;
    const bool& wild_secret_;
    ContentZombie56Services& services_;
    bool solid(Point)const;
    bool wild(const ZombieRef&)const;
    ZombieRef lookup(const Field<std::string>&)const;
    void started(const ZombieRef&,Seat);
    void summoned(const Field<std::string>& source,const ZombieRef&,Seat,std::optional<double> slot);
};
} // namespace pvz::typed72
