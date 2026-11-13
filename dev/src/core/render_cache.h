#pragma once
#include "core/value.h"
namespace pvz {
// Ordered mapping for the renderer's recipe/scale LRU. The caller owns bounds.
V native_render_cache();
}
