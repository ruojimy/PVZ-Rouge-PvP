#pragma once
#include "sim/typed/grenadiers.h"
#include "sim/typed/scripted_spawn_budget.h"
#include "sim/typed/sweet_taunts.h"
#include <unordered_set>

namespace pvz::typed72 {
struct SpawnedContentZombie {std::string id;ZombieRef unit;};
struct SlimeSpawnParent {ScriptedSpawnOrigin origin;Field<bool> sticky;};
struct Zombie64Event {
    enum class Kind { grab,throw_unit,slime_split,belt_placed } kind;
    Field<std::string> source,entity;
    std::string card;
    std::vector<std::string> children;
    Cell cell;
};
class ContentZombie64Services {
public:
    virtual ~ContentZombie64Services()=default;
    virtual void alias_art(const std::string& original,const std::string& replacement)=0;
    virtual void draw_zombie(const ZombieRef&)=0;
    virtual std::optional<SpawnedContentZombie> spawn_slime(const std::string&,Point,double,const SlimeSpawnParent& parent)=0;
    virtual void zombie64_event(const Zombie64Event&)=0;
    virtual void publish_terrain()=0;
};
class ContentZombies64 {
public:
    ContentZombies64(TypedBattleState& world,SweetTaunts& taunts,Grenadiers& grenadiers,
                     ScriptedSpawnBudget& budget,const TargetSight& published,ContentZombie64Services& services)
        :world_(world),taunts_(taunts),grenadiers_(grenadiers),budget_(budget),published_(published),services_(services){}
    std::unordered_set<int64_t> belt_keys;
    bool configure(const ZombieRef&,std::string_view,double hp,bool observed_max_hp);
    void gate(const ZombieRef&);
    void finish(const ZombieRef&,bool alive);
    bool on_belt(const ZombieRef&)const;
    void tag_belt(std::string_view,Point);
    ZombieRef throwable(const ZombieRef&)const;
    void redeye(const ZombieRef&);
    void landed();
    void split(const ZombieRef&);
    void launch_slime(const ZombieRef&,const ScriptedSpawnOrigin&,bool sticky,double direction,bool far);
    bool deferred_slime(const ScriptedSpawnOrigin&,std::string name,bool sticky,double direction,bool far);
private:
    TypedBattleState& world_;
    SweetTaunts& taunts_;
    Grenadiers& grenadiers_;
    ScriptedSpawnBudget& budget_;
    const TargetSight& published_;
    ContentZombie64Services& services_;
    bool solid(Point)const;
    static std::string_view hand_kind(const CombatZombie&);
};
} // namespace pvz::typed72
