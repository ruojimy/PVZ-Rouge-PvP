#pragma once
#include "core/value.h"
namespace pvz {
// Ordered mapping for the renderer's recipe/scale LRU. The caller owns bounds.
V native_render_cache();
// Exact structural cache key, with no lossy hash or numeric formatting.
V native_recipe_key(const V& description,const V& area,const V& scale);
// PvP75 replay-cache normalisation for pure transform chains (asset / crop / flip / scale /
// rotate). In such chains every intermediate surface alpha is copied, never baked into pixels,
// and DrawReplay.surface sets the outermost alpha last, so the pixels do not depend on any alpha:
// the returned copy carries alpha 255 throughout and `alpha` receives the outer value to set on the
// cached surface at blit time (hurt flashes then share one cached image). Rotation angles are
// rounded to 1/4 degree (a sub-pixel change on unit art) so a walking unit's continuously varying
// limb angles reuse cached rotations. Returns the input unchanged (applied=false) for any other
// chain, or when PVP75_REPLAY_NORMALIZE=0.
V native_replay_normalize(const V& description,V& alpha,bool& applied);
// PvP75 replay recipe cache bounds: 64 MiB / 1536 entries (was 32 MiB / 512, full in ordinary
// fights once split head/body/armour art is cached). PVP75_REPLAY_CACHE_MB / _ENTRIES override.
double native_replay_cache_bytes();
// Rotation step of the normalisation (default 0.25 degrees, PVP75_REPLAY_ANGLE_STEP; 0 = exact).
double native_replay_angle_step();
// Exact-angle scope for replay-vs-direct-pygame pixel parity checks (restores the step on exit).
struct ReplayExactAngles {double previous;ReplayExactAngles();~ReplayExactAngles();};
double native_replay_cache_entries();
}
