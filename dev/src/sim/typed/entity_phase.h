#pragma once
#include "sim/typed/entity_region.h"
#include "sim/typed/native_tracking.h"
#include "sim/typed/torch_rules.h"

namespace pvz::typed72 {
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
private:
    TypedBattleState& world_;
    TorchRules& torches_;
    TargetIndexes& indexes_;
    NativeTracking tracking_;
    EntityPhaseServices& services_;
    EntityRegion region_;
    std::optional<Seat> entry_;
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
