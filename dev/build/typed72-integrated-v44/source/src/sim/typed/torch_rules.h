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
    void begin_pea_batch(){if(batch_depth_++==0)batch_ready_=false;}
    void end_pea_batch(){--batch_depth_;}
    void invalidate_pea_batch(){batch_ready_=false;}
    mutable uint64_t roster_scans=0,roster_candidates=0,batch_reuses=0;
private:
    struct Torch {Point point;std::shared_ptr<AttackSource> source;ZombieRef grave;};
    TypedBattleState& world_;
    TorchRewards& rewards_;
    int batch_depth_=0;
    mutable bool batch_ready_=false;
    mutable const PlantRoster* plants_=nullptr;mutable const PlantRef* plant_data_=nullptr;
    mutable const TargetRoster* zombies_=nullptr;mutable const CombatTarget* zombie_data_=nullptr;
    mutable size_t plant_count_=0,zombie_count_=0;
    mutable std::vector<PlantRef> batch_plants_;
    mutable std::vector<ZombieRef> batch_graves_;
    std::vector<Torch> points() const;
    void convert(const EntityRef&,bool zombie,const std::vector<Torch>*);
    void reward(const ZombieRef&,Point);
};
} // namespace pvz::typed72
