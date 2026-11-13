#pragma once
#include "sim/typed/ballistics.h"
#include "sim/typed/entity_contacts.h"

namespace pvz::typed72 {
// Dispatch goes through the installed typed PvP damage chain. Head collisions
// carry their explicit original call-site entity for NativeContent.head_impact.
class BonusImpactServices {
public:
    virtual ~BonusImpactServices() = default;
    virtual void bonus_damage(size_t index, double facing, double amount) = 0;
    virtual void head_damage(const EntityRef&, size_t index, double facing,
                             double amount, bool surface) = 0;
};

class BonusProjectiles {
public:
    BonusProjectiles(TypedBattleState& world, BonusImpactServices& services,
                     const CollisionCatalog& collision, const EntityRegionRules& rules)
        : world_(world), services_(services), collision_(collision), rules_(rules), ballistics_(world) {}
    uint64_t patches = 0, seen_throwers = 0, guide_logs = 0, bonus_hits = 0, cannon_patches = 0;
    uint64_t head_queries=0,head_candidates=0,head_full_scan=0,head_exact_tests=0;
    size_t spatial_bytes()const{return head_grid_.storage_bytes();}
    bool zombie_placed();
    static bool live(const ZombieRecordFields&);
    bool has_live_zombies() const;
    static bool thrown(std::string_view);
    static double base_damage(const EntityRef&);
    void bind_content_ballistics(BallisticComputePolicy& policy){ballistics_.bind_compute_policy(policy);ballistics_.require_compute_policy();}
    void patch(const EntityRef&);
    void reaim(const EntityRef&);
    void guide();
    void velocity_damage(const std::shared_ptr<EntityRoster>& captured_entities,
                         const std::shared_ptr<TargetRoster>& captured_zombies);
    void prepare_cannon(const EntityRef&);
    void fix_cannons();
    void mark_reloading(const EntityRef&);
    void patch_cannons();
    void head_hits();
private:
    TypedBattleState& world_;
    BonusImpactServices& services_;
    const CollisionCatalog& collision_;
    const EntityRegionRules& rules_;
    NativeBallistics ballistics_;
    CoverageGrid head_grid_;
    std::weak_ptr<TargetRoster> board_zombies_;
    std::weak_ptr<PlantRoster> board_plants_;
    bool placed_ = false;
    bool i_zombie() const;
    double head_damage(const EntityRef&) const;
    static bool pierces(const EntityRef&);
    static bool surface(const EntityRef&, const CombatZombie&, const Ellipse&);
};
} // namespace pvz::typed72
