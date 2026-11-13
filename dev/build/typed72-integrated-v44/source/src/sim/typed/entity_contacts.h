#pragma once
#include "sim/typed/zombie_pea.h"
#include "sim/typed/coverage_grid.h"

namespace pvz::typed72 {
// Tables are materialized at match admission. The damage-entity list is
// separate from the lobber list; the patch can extend the former.
struct EntityRegionRules {
    std::vector<std::string> damaging, thrown;
    std::unordered_map<std::string,double> homing_height;
};

class EntityContacts {
public:
    EntityContacts(TypedBattleState& world, ZombiePeaCallbacks& callbacks,
                   const CollisionCatalog& collision, const EntityRegionRules& rules)
        : world_(world), callbacks_(callbacks), collision_(collision), rules_(rules) {}
    // l remains a numeric index throughout the original region. A synchronous
    // damage, knockback or death callback may replace either roster.
    bool strike(size_t l, const std::string& frame_name, double driving);
    void home(size_t l, std::optional<size_t> nearest);
    void freeze_melon(size_t l);
    mutable uint64_t queries=0,candidates=0,full_scan_equivalent=0,index_builds=0,narrow_queries=0,empty_cell_skips=0;
    void invalidate_spatial()const{contact_tick_=-1;}
    size_t occupied_cells()const{return contact_grid_.occupied_cells();}
    size_t spatial_bytes()const{return contact_grid_.storage_bytes();}
private:
    TypedBattleState& world_;
    ZombiePeaCallbacks& callbacks_;
    const CollisionCatalog& collision_;
    const EntityRegionRules& rules_;
    // Per native tick / target view broad phase. Buckets retain original roster
    // indices so the reverse-order narrow phase and simultaneous-hit rules stay intact.
    mutable const TargetRoster* contact_roster_=nullptr;
    mutable const CombatTarget* contact_data_=nullptr;
    mutable size_t contact_count_=0;
    mutable int64_t contact_tick_=-1;
    mutable CoverageGrid contact_grid_;
    mutable std::vector<size_t> contact_heroes_,contact_candidates_;
    bool occupied_contact_cell(size_t l)const;
    void prepare_contacts() const;
    Entity& entity(size_t l) const {return *world_.runtime.entities.list()->at(l);}
    CombatTarget target(size_t z) const {return world_.targets->at(z);}
    ZombieRecordFields& body(const CombatTarget&) const;
    Motion& motion(const CombatTarget&) const;
    bool allows_contact(const Entity&,const CombatTarget&) const;
    std::optional<size_t> find_contact(size_t l) const;
    void set_status(size_t,HeroStatus,double);
    void ice_hit(size_t,double);
    void splat(size_t);
};
} // namespace pvz::typed72
