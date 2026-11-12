#pragma once
// Owned cold data admitted by the typed session. This header deliberately has no
// dependency on V, PyObj, Args or the legacy battle runtime: only the exporter
// knows how the outer application constructed these values.
#include <nlohmann/json.hpp>
#include <array>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
namespace pvz::typed72app {
struct ColdPixels {int width=0,height=0;std::vector<std::array<uint8_t,4>> rgba;};
struct ColdExport {
    nlohmann::json cold;
    std::vector<std::pair<std::string,ColdPixels>> atlas;  // 图集 order
    nlohmann::json draw_atlas;                           // {world, ui, world_before}
};
} // namespace pvz::typed72app
