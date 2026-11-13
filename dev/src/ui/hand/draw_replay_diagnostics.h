#pragma once
#include <cstdint>
namespace pvz::pg {
struct ReplayAssetCacheStats {
    uint64_t entries=0,bytes=0,dynamic_entries=0,dynamic_bytes=0;
    uint64_t max_width=0,max_height=0;
};
// Read-only diagnostics, under the V runtime GIL. Never part of match state.
ReplayAssetCacheStats replay_asset_cache_stats();
}
