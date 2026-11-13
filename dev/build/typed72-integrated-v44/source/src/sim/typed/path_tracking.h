#pragma once
#include "sim/typed/zombie_motion.h"

namespace pvz::typed72 {
enum class PathMode {follow_hero,attack_plants};
struct NativePathRules {
    std::vector<std::string> targets,producers;
};
class PathTracking {
public:
    PathTracking(TypedBattleState& world,ZombieNavigation& navigation,const NativePathRules& rules)
        :world_(world),navigation_(navigation),rules_(rules){}
    void initialize(Point hero);
    void advance(Point hero,PathMode);
    void begin_tracking_phase(){phase_active_=true;phase_choice_.reset();}
    void end_tracking_phase(){phase_active_=false;phase_choice_.reset();}
    uint64_t target_scans=0,target_candidates=0,target_cache_hits=0;
private:
    TypedBattleState& world_;
    ZombieNavigation& navigation_;
    const NativePathRules& rules_;
    struct PlantChoice {int64_t index=-1;double outputs=0.;};
    bool phase_active_=false;
    std::optional<PlantChoice> phase_choice_;
    void choose_target(PathMode);
};
} // namespace pvz::typed72
