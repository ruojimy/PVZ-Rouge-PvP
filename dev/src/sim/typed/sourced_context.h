#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
enum class SourcedCall { regular,spawn,player_hit };
// NativeCombatPatch.bind_targets' exact full-context path. The caller invokes
// its typed body synchronously, then finish(). An exception restores the hero
// context but does not run post-body launch tagging or spawn retagging.
class SourcedContext {
public:
    SourcedContext(TypedBattleState&,std::shared_ptr<AttackSource>,CombatPhase,SourcedCall=SourcedCall::regular);
    SourcedContext(const SourcedContext&)=delete;
    SourcedContext& operator=(const SourcedContext&)=delete;
    void finish();
    static std::shared_ptr<AttackSource> resolve_source(TypedBattleState&,std::shared_ptr<AttackSource>);
    static Seat source_owner(const AttackSource&);
    Seat owner()const{return owner_;}
    const std::shared_ptr<AttackSource>& source()const{return source_;}
private:
    TypedBattleState& world_;
    std::shared_ptr<AttackSource> source_;
    Seat owner_=Seat::zombie;
    SourcedCall call_;
    std::unordered_set<uint64_t> previous_entities_;
    std::optional<HeroContext> context_;
    bool was_launching_=false,finished_=false;
};
} // namespace pvz::typed72
