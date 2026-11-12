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
private:
    TypedBattleState& world_;
    ZombieNavigation& navigation_;
    const NativePathRules& rules_;
    void choose_target(PathMode);
};
} // namespace pvz::typed72
