// Port of pvp/maps.py: MapSnapshot / build_snapshot (PvP adaptation of an original map).
#pragma once
#include "core/sym.h"
#include "sim/mapgen.h"
#include <string>
#include <vector>

namespace pvz {

struct TerrainCell {
    Sym kind;            // "方块"
    bool solid = false, water = false, ladder = false;
    Sym background;      // "里方块" ("" when absent)
    GenCell native;      // original generator cell (provenance; seeds the native ditu row)
};

struct TerrainChange { int col, row; Sym before, after; std::string reason; };

struct Environment {
    std::string weather = "clear";   // clear | rain
    int waterline_row = 24;
    bool night = false;
};

struct MapSnapshot {
    std::string map_id;
    int64_t seed = 1;
    int tile_size = 48;
    int rows = 0, cols = 0, width = 0, height = 0;
    std::vector<std::vector<TerrainCell>> tiles;
    struct Spawn { double x, y; } spawn_plant{}, spawn_zombie{};
    std::vector<TerrainChange> changes;
    Environment environment;
    std::string source = "original";

    const TerrainCell& tile_at(int col, int row) const;
    double wrap_x(double x) const;
    double short_dx(double from_x, double to_x) const;
};

// pvp.maps.build_snapshot(bridge, map_id, seed, tile_size=48, adapt=True, weather)
MapSnapshot build_snapshot(const std::string& map_id, int64_t seed, const std::string& weather = "clear",
                           int tile_size = 48, bool adapt = true);

// _cell(raw, empty_blocks)
TerrainCell make_cell(const GenCell& raw, const std::vector<std::string>& empty_blocks);

// audit_snapshot(): spawn/wrap-portal geometry
bool audit_snapshot(const MapSnapshot& s, std::vector<std::string>* issues = nullptr);

// kong from the original game (pass-through blocks)
const std::vector<std::string>& original_kong();

}  // namespace pvz
