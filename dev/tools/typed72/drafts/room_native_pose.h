#pragma once
#include "sim/typed/hero.h"
namespace pvz::typed72 {
// A detached publication of one avatar at _sync_public, preserving source
// missing/None distinctions. Its nested lists and poison layers never alias
// the live body. Combat continues to own the sole mutable HeroState.
class RoomNativePose {
public:
    void capture(const HeroState&);
    const HeroState& value()const noexcept{return state_;}
private:
    HeroState state_;
};
}
