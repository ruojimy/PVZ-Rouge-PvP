// Numeric PvP damage policy. Called before the native death/armor branches.
#pragma once
#include "sim/typed/hero.h"
#include <bitset>

namespace pvz::typed72 {

enum class DamageSecret : size_t { focus, rage, armstrong, basketball_lock, seal, relic, secondhand, king_shield, count };
struct DamageSecrets {
    std::array<std::bitset<size_t(DamageSecret::count)>,4> seats;
    std::bitset<size_t(DamageSecret::count)> team;
    bool enabled = false;
    // Same lock-time derivation as ZombieSecrets.by_seat; subsequent hero
    // aliasing cannot change which player's secret is held.
    void configure(const std::array<std::optional<HeroPlayer>,4>&);
    bool has(DamageSecret s) const { return team.test(size_t(s)); }
    bool seat_has(Seat seat,DamageSecret s) const { return seats.at(seat_index(seat)).test(size_t(s)); }
};

struct UnitProtectionState {
    Field<std::string> card;
    bool hero = false, grave = false;
    Field<double> anchor_until, hurt_tick, crowd_factor, relic_until, basketball;
    Field<double> reaper_hurt;
    bool lock_done = false;
    Field<bool> locked;
};

// Borrowed views point at a unit's authoritative fields. They do not clone a
// zombie, plant or hero into a damage-specific world.
struct DamageTarget {
    double& hp;
    const std::string& hand;
    AttackSource& identity;
    UnitProtectionState& state;
};
struct ProducerPolicy {
    bool producer=false;
    Field<double> period,yield_amount,mature_at,mature_hp,mature_yield;
};

class UnitProtection {
public:
    explicit UnitProtection(HeroCombat& heroes) : events(heroes.events),heroes_(heroes) {}
    DamageSecrets secrets;
    std::unordered_map<std::string,ProducerPolicy> cards;
    std::array<std::optional<std::string>,4> selected_grave;
    int64_t until = 0;
    double producer_factor = 1.;
    bool deathmatch = false;
    std::vector<BattleEvent>& events;

    double amount(DamageTarget, double);
    double multiplier(const DamageTarget&) const;
    double damage_factor(const DamageTarget&) const;
    bool shield_first(const DamageTarget&, double hand_hp) const;
    bool selected(const DamageTarget&) const;
    bool focused(const DamageTarget&) const;
    bool berserk() const;
private:
    HeroCombat& heroes_;
    std::optional<Seat> owner(const AttackSource&) const;
    bool own(const DamageTarget&) const;
    double adjust(DamageTarget,double);
    double relic(DamageTarget,double);
};
} // namespace pvz::typed72
