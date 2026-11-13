#pragma once
#include "sim/typed/entity_region.h"
#include "sim/typed/native_tracking.h"
#include "sim/typed/torch_rules.h"

namespace pvz::typed72 {
class EntityContentGate {
public:
    virtual ~EntityContentGate()=default;
    virtual void entity_gate(const EntityRef&)=0;
};
class EntityPhaseServices : public EntityRenderer {
public:
    virtual bool has_sprite(const std::string&)const=0;
    virtual void release_pending_destination()=0;
};
// The 250 Hz native pass from the pre-projectile index through both owners.
// Later content projectiles, flight culling and particles run after this pass.
class EntityPhase final : private EntityRegionBindings {
public:
    EntityPhase(TypedBattleState& w,EntityRegionEnvironment& environment,const EntityRegionRules& rules,
                EntityContacts& contacts,ProjectileRules& flight,SquashEffects& squash,SquashCallbacks& damage,
                PlantLifecycle& plants,TorchRules& torches,TargetIndexes& indexes,const TargetSight& sight,
                EntityPhaseServices& services):world_(w),torches_(torches),indexes_(indexes),tracking_(w,indexes,sight),
                services_(services),region_(w,environment,rules,contacts,flight,squash,damage,plants,*this){}
    void run();
    std::array<uint64_t,3> tracking_counters()const{return {tracking_.nearest_queries,tracking_.nearest_candidates,tracking_.nearest_full_scan};}
    void bind_content_gate(EntityContentGate& gate){if(content_gate_&&content_gate_!=&gate)throw std::logic_error("entity content gate already bound");content_gate_=&gate;}
    void require_content_gate(bool required=true){content_required_=required;}
private:
    TypedBattleState& world_;
    TorchRules& torches_;
    TargetIndexes& indexes_;
    NativeTracking tracking_;
    EntityPhaseServices& services_;
    EntityRegion region_;
    std::optional<Seat> entry_;
    EntityContentGate* content_gate_=nullptr;
    bool content_required_=false;
    Seat nearest_plant(Point)const;
    void switch_dave(Seat);
    void run_owner(Seat);
    void tracking_gate(size_t)override;
    std::optional<size_t> nearest_target()const override{return indexes_.nearest;}
    EntitySprite sprite(EntitySprite)const;
    void draw(EntityDraw)override;
    void alpha(const EntitySprite&,double)override;
};
} // namespace pvz::typed72
