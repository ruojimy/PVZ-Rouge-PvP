#pragma once
#include "sim/typed/scripted_spawn_budget.h"
#include <variant>

namespace pvz::typed72 {
class NativeSummonServices {
public:
    virtual ~NativeSummonServices()=default;
    virtual ZombieRef spawn_content(const std::string& name,Point,double facing,const ScriptedSpawnOrigin& parent)=0;
    virtual void content_summoned(const Field<std::string>& source,const std::string& entity,const std::string& card,Seat owner)=0;
};
class NativeSummons {
public:
    NativeSummons(TypedBattleState& world,ScriptedSpawnBudget& budget,NativeSummonServices& services)
        :world_(world),budget_(budget),services_(services){}
    bool summon(ZombieRef source,std::string name,bool thrown=false,double offset=0.,bool defer=true);
private:
    // A running producer keeps its live identity through constructor callbacks.
    // Deferred requests own only the admitted provenance and position snapshot.
    using Source=std::variant<ZombieRef,ScriptedSpawnOrigin>;
    TypedBattleState& world_;
    ScriptedSpawnBudget& budget_;
    NativeSummonServices& services_;
    bool summon_source(const Source&,const std::string& name,bool thrown,double offset,bool defer);
    static std::shared_ptr<AttackSource> metadata(const Source&);
    static ScriptedSpawnOrigin snapshot(const Source&);
    static Motion position(const Source&);
    static Motion barrel_position(const Source&);
    static double facing(const Source&);
};
} // namespace pvz::typed72
