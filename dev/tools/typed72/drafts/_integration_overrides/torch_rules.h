#pragma once
#include "sim/typed/targets.h"

namespace pvz::typed72 {
class TorchRewards {
public:
    virtual ~TorchRewards()=default;
    virtual void petrified_resource(double amount,Point position)=0;
};
class TorchRules {
public:
    TorchRules(TypedBattleState& world,TorchRewards& rewards):world_(world),rewards_(rewards){}
    // zombie_secrets.torch_range_scale/torch_sleep_scale and the blue petrified fire read 暴怒,
    // not 狂暴 (DamageSecret::rage). Set at the lock from the zombie team secrets.
    bool fury=false;
    void tick();
    void ignite_charmed_peas();
    void zombie_pea(const EntityRef&);
private:
    struct Torch {Point point;std::shared_ptr<AttackSource> source;ZombieRef grave;};
    TypedBattleState& world_;
    TorchRewards& rewards_;
    std::vector<Torch> points() const;
    void convert(const EntityRef&,bool zombie,const std::vector<Torch>*);
    void reward(const ZombieRef&,Point);
};
} // namespace pvz::typed72
