#pragma once
#include "core/value.h"
namespace pvz {
// Ordered mapping for the renderer's recipe/scale LRU. The caller owns bounds.
V native_render_cache();
// Exact structural cache key, with no lossy hash or numeric formatting.
V native_recipe_key(const V& description,const V& area,const V& scale);
}
