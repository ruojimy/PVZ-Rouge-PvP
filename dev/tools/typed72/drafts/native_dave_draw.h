#pragma once
// pvp native_animation.draw_dave (V: src/sim/pvp/hand/runtime.cpp f_draw_dave) with the original
// dave_draw region (src/sim/gen/physics.cpp region_dave_draw). The hurt counter itself is
// advanced by NativeTick's dave_state; this draws the layers and applies the hurt alpha.
#include "sim/typed/native_canvas.h"
#include "sim/typed/hero.h"
#include <functional>
namespace pvz::typed72 {
struct DaveDraw {
    const HeroState& hero;
    const HeroFrame& globals;      // values the avatar does not carry (xx, yy, dushu)
    double tile=48.;
    int64_t native_tick=0;
    std::optional<int> hurt_alpha;  // NativeTickState::dave_hurt_alpha for this seat
    bool materialize=true;
};
// unsupported(name) is told about layers not ported yet (poison tint).
void draw_dave(NativeCanvas&,const DaveDraw&,const std::function<void(const std::string&)>& unsupported);
} // namespace pvz::typed72
