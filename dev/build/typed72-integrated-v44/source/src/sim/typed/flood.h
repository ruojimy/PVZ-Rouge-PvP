#pragma once
#include "state.h"
#include "sim/typed/terrain.h"
#include <span>

namespace pvz::typed72 {
// Terrain is authoritative typed storage. Changes take effect before the next
// neighbour query; there is no V mirror, cache lifetime, or geometry rebuild.
class FloodTerrain {
public:
    FloodTerrain(int rows, int cols, std::vector<uint8_t> empty, std::vector<uint8_t> valid,
                 std::vector<uint8_t> water = {});
    int rows() const noexcept { return rows_; }
    int cols() const noexcept { return cols_; }
    int wrap(int64_t col) const noexcept { auto r = col % cols_; return int(r < 0 ? r + cols_ : r); }
    bool valid_row(int y) const noexcept { return y >= 0 && y < rows_ && valid_[y]; }
    bool empty(int y, int64_t x) const;
    bool water(int y, int64_t x) const;
    void set_empty(int y, int64_t x, bool value);
    void set_valid(int y, bool value);
    uint64_t revision() const noexcept { return revision_; }
private:
    size_t index(int y, int64_t x) const;
    int rows_, cols_;
    std::vector<uint8_t> empty_, valid_, water_;
    uint64_t revision_ = 0;
};

struct FloodState {
    int cooldown = 0, sign = 1;
    std::shared_ptr<std::vector<int>> field=std::make_shared<std::vector<int>>();
    std::shared_ptr<std::vector<Cell>> queue=std::make_shared<std::vector<Cell>>();
    std::shared_ptr<std::vector<Cell>> frontier=std::make_shared<std::vector<Cell>>();
    std::optional<Cell> seed_scratch, last_scratch;
    uint64_t calls = 0, expansions = 0, neighbours = 0;
};

struct FloodInput {
    bool plants = false, has_target = false;
    Cell seed;
    double surface = 23;
};

// Exact source schedule, signed writes, queue order, raw unwrapped x and narrow
// passage test from modkit/pvp/native_flood.py::advance. No sorting or dedup.
void advance_flood(const FloodTerrain&, FloodState&, const FloodInput&);
void advance_flood(const WorldTerrain&, FloodState&, const FloodInput&);
Cell player_flood_seed(Point position, double tile);
Cell terrain_cell(Point position, double tile);
void advance_particles(CombatStages&, const FloodTerrain&, bool draw, Point shake);
void advance_particles(CombatRuntime&, const WorldTerrain&, bool draw, Point shake, std::optional<int64_t>* source_index=nullptr);
int displace_body(Motion&, double size, const FloodTerrain&, double tile, double plk, bool periodic);
int displace_body(Motion&, double size, const WorldTerrain&, double tile, double plk, bool periodic);
} // namespace pvz::typed72
