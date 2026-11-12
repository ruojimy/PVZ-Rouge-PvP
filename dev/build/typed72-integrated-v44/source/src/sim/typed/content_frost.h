#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
class ContentFrost {
public:
    explicit ContentFrost(TypedBattleState& world):world_(world){}
    std::vector<CombatTarget> pending;
    void apply();
    bool contains(const CombatTarget& target)const;
    void freeze(const CombatTarget&,double minimum);
    double ice(const CombatTarget&)const;
private:
    TypedBattleState& world_;
};
} // namespace pvz::typed72
