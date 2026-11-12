// Port of the original 生成地图(name) (pvzrouge.pyc), run as PvP's NativeBridge
// runs it: 随 = random.Random(seed).randint.
#pragma once
#include "core/pyrandom.h"
#include <string>
#include <vector>

namespace pvz {

struct GenCell {
    std::string 方块 = "空";
    std::string 里方块;
    bool has里 = false;
};
using GenGrid = std::vector<std::vector<GenCell>>;   // [24][72]

// The 12 original map names in PvP order.
extern const char* const MAP_NAMES[12];

// Throws std::runtime_error for an unknown map.
GenGrid generate_original_map(const std::string& name, int64_t seed);

}  // namespace pvz
