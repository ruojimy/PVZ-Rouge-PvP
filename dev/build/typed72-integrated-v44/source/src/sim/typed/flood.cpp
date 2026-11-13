#include "core/function_profile.h"
#include "sim/typed/spatial_mode.h"
#include "flood.h"
#include "core/pymath.h"
#include <cmath>
#include <limits>

namespace pvz::typed72 {
FloodTerrain::FloodTerrain(int rows, int cols, std::vector<uint8_t> empty, std::vector<uint8_t> valid,
                           std::vector<uint8_t> water)
    : rows_(rows), cols_(cols), empty_(std::move(empty)), valid_(std::move(valid)), water_(std::move(water)) {
    if (rows <= 0 || cols <= 0 || uint64_t(rows) * uint64_t(cols) != empty_.size() || valid_.size() != size_t(rows))
        throw std::invalid_argument("invalid typed terrain dimensions");
    if (water_.empty()) water_.resize(empty_.size());
    if (water_.size() != empty_.size()) throw std::invalid_argument("invalid typed water dimensions");
}
size_t FloodTerrain::index(int y, int64_t x) const {
    if (y < 0 || y >= rows_) throw std::out_of_range("typed terrain row");
    return size_t(y) * cols_ + wrap(x);
}
bool FloodTerrain::empty(int y, int64_t x) const { return empty_[index(y, x)] != 0; }
bool FloodTerrain::water(int y, int64_t x) const { return water_[index(y, x)] != 0; }
void FloodTerrain::set_empty(int y, int64_t x, bool value) { empty_[index(y, x)] = uint8_t(value); ++revision_; }
void FloodTerrain::set_valid(int y, bool value) {
    if (y < 0 || y >= rows_) throw std::out_of_range("typed terrain row");
    valid_[y] = uint8_t(value); ++revision_;
}

Cell terrain_cell(Point p, double tile) {
    if (!std::isfinite(tile) || tile <= 0) throw std::invalid_argument("invalid tile scale");
    const double x = py::floordiv(p.x, tile), y = py::floordiv(p.y, tile);
    // Conversion is checked before the C++ integral cast (undefined out of range).
    if (!std::isfinite(x) || !std::isfinite(y) || x < -0x1p63 || x >= 0x1p63 ||
        y < std::numeric_limits<int>::min() || y > std::numeric_limits<int>::max())
        throw std::out_of_range("typed flood seed range");
    return {int(y), int64_t(x)};
}
Cell player_flood_seed(Point p, double tile) { return terrain_cell({p.x,p.y-.5*tile},tile); }

template<class Terrain> void advance_flood_impl(const Terrain& map, FloodState& state, const FloodInput& input) {
    ++state.calls;
    if (state.field->size() != size_t(map.rows()) * map.cols()) throw std::invalid_argument("typed flood field dimensions");
    if (state.sign != 1 && state.sign != -1) throw std::invalid_argument("typed flood sign");
    if (state.cooldown > 0) --state.cooldown;
    if (state.cooldown != 0) return;
    state.cooldown = input.plants && !input.has_target ? 20 : 3;
    if (state.queue->empty()) {
        ++state.cycles;
        state.seed_scratch = input.seed;
        if (map.valid_row(input.seed.y)) state.queue->push_back(input.seed);
        state.sign = -state.sign;
    }
    // Native banks retain the old queue object when the global queue is
    // replaced. Reuse a retired buffer only after every saved alias is gone.
    if (state.frontier.use_count()!=1) state.frontier=std::make_shared<std::vector<Cell>>();
    state.queue.swap(state.frontier);
    state.queue->clear();
    ++state.expansions;
    for (Cell point : *state.frontier) {
        if (point.y < 0 || point.y >= map.rows() || point.x == std::numeric_limits<int64_t>::min() ||
            point.x == std::numeric_limits<int64_t>::max()) throw std::out_of_range("typed flood frontier");
        const std::array<Cell, 4> neighbours{{{point.y-1, point.x}, {point.y+1, point.x},
                                             {point.y, point.x-1}, {point.y, point.x+1}}};
        const bool indexed=spatial741_enabled();
        const int base=indexed?map.wrap(point.x):0;
        const int columns[4]={base,base,base?base-1:map.cols()-1,base+1<map.cols()?base+1:0};
        for (int direction = 1; direction <= 4; ++direction) {
            ++state.neighbours;
            const Cell n = neighbours[direction-1];
            if (!map.valid_row(n.y)) continue;
            const int col=indexed?columns[direction-1]:map.wrap(n.x);
            if (!(indexed?map.empty_canonical(n.y,col):map.empty(n.y,col)) || n.y > input.surface) continue;
            int& old = state.field->at(size_t(n.y) * map.cols() + col);
            if (old != 0 && int64_t(state.sign) * old >= 0) continue;
            if (0 < n.y && n.y < 23 && !map.empty(n.y-1, col) && !map.empty(n.y+1, col)) continue;
            state.queue->push_back(n);
            old = direction * state.sign;
        }
    }
    if (!state.frontier->empty()) state.last_scratch = state.frontier->back();
}
void advance_flood(const FloodTerrain& map,FloodState& state,const FloodInput& input){PVP_PROFILE_SCOPE("advance_flood::fixture");advance_flood_impl(map,state,input);}
void advance_flood(const WorldTerrain& map,FloodState& state,const FloodInput& input){PVP_PROFILE_SCOPE("advance_flood::world");advance_flood_impl(map,state,input);}
} // namespace pvz::typed72
