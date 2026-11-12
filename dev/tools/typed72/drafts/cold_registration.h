#pragma once
#include "cold_catalog.h"
#include "sim/typed/scripted_spawn_budget.h"
namespace pvz::typed72 {
struct ColdParent {
    std::optional<std::string> id,card;
    std::shared_ptr<AttackSource> fallback;
};
struct ColdSpawnEvent {
    std::string entity,card;
    Seat side;
    std::optional<std::string> parent_entity;
    std::optional<AttackIdentity> parent_attack;
};
class ColdSpawnEvents {
public:
    virtual ~ColdSpawnEvents()=default;
    virtual void spawn(const ColdSpawnEvent&)=0;
};
struct ColdRegistrationContext {
    std::optional<Seat> acting_seat;
    bool budget_enabled=false;
    std::optional<int64_t> scripted_wave;
};
class ColdRegistration {
public:
    ColdRegistration(TypedBattleState& world,const ColdCatalog& catalog,uint64_t& sequence,ColdSpawnEvents& events)
        :world_(world),catalog_(catalog),sequence_(sequence),events_(events){}
    std::shared_ptr<AttackSource> parent_source(const ColdParent&)const;
    void register_unit(const NativeObject&,const ColdCard&,Seat side,bool temporary,
                       const ColdRegistrationContext&,const ColdParent* parent=nullptr,
                       std::optional<AttackIdentity> parent_attack={});
    void health(const PlantRef&,std::span<const std::string> team_secrets)const;
    void hardening(const PlantRef&,std::span<const std::string> team_secrets)const;
    void configure_plant(const PlantRef&,const ColdCard&,std::span<const std::string> team_secrets)const;
private:
    TypedBattleState& world_;
    const ColdCatalog& catalog_;
    uint64_t& sequence_; // Shared with Resources' r/u ID counter, not native:.
    ColdSpawnEvents& events_;
};
} // namespace pvz::typed72
