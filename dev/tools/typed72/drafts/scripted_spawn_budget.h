#pragma once
#include "sim/typed/targets.h"
#include <functional>
#include <list>

namespace pvz::typed72 {
struct ScriptedSpawnKey {
    std::string source,kind;
    double slot=0.;
    friend bool operator==(const ScriptedSpawnKey&,const ScriptedSpawnKey&)=default;
};
struct ScriptedSpawnKeyHash {size_t operator()(const ScriptedSpawnKey&)const noexcept;};
struct ScriptedSpawnRequest {
    ScriptedSpawnKey key;
    Field<int64_t> wave;
    std::function<bool()> create;
};
struct ScriptedSpawnOrigin {
    std::shared_ptr<AttackSource> source;
    Field<std::string> public_id;
    Field<double> facing;
    Field<Motion> position,barrel_position;
};
ScriptedSpawnOrigin scripted_spawn_origin(const ZombieRef&);
class ScriptedSpawnServices {
public:
    virtual ~ScriptedSpawnServices()=default;
    virtual void summon_deferred(const ScriptedSpawnKey&,const Field<int64_t>& wave)=0;
    virtual ZombieRef spawn_dancer(Point,double facing,const ScriptedSpawnOrigin& parent)=0;
};
// Limits are decoded at the cold configuration boundary. A present null
// means the supplied value failed Python's int conversion and uses 40.
struct ScriptedSpawnLimits {Field<int64_t> director,rule;};
class ScriptedSpawnBudget {
public:
    ScriptedSpawnBudget(TypedBattleState& world,ScriptedSpawnServices& services,bool enabled)
        :enabled(enabled),world_(world),services_(services){}
    bool enabled,draining=false;
    uint64_t admitted=0,deferred=0,peak_pending=0;
    ScriptedSpawnLimits limits;
    int limit()const;
    size_t count()const;
    int64_t available()const;
    bool can_spawn(int64_t count=1,const std::shared_ptr<AttackSource>& source={})const;
    size_t pending_count(std::optional<int64_t> wave={})const;
    bool pending_for_source(const AttackSource&,std::optional<std::string_view> kind={})const;
    bool defer(const std::shared_ptr<AttackSource>&,std::string kind,double slot,
               std::function<bool()>);
    void drain();
    void clear();
    const std::list<ScriptedSpawnRequest>& pending()const{return ordered_;}
    static bool live_enemy(const CombatTarget&);
    static void inherit(AttackSource& child,const AttackSource* parent);
    bool hold_dance()const;
    bool hold_spawn()const;
    bool defer_dancer(Point,double facing,int64_t slot);
private:
    TypedBattleState& world_;
    ScriptedSpawnServices& services_;
    std::list<ScriptedSpawnRequest> ordered_;
    std::unordered_map<ScriptedSpawnKey,std::list<ScriptedSpawnRequest>::iterator,ScriptedSpawnKeyHash> index_;
};
} // namespace pvz::typed72
