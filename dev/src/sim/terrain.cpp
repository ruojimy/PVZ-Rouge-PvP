#include "sim/terrain.h"
#include "core/pymath.h"
#include "data/datastore.h"
#include <algorithm>
#include <cstdlib>
#include <map>
#include <stdexcept>

namespace pvz {

const std::vector<std::string>& original_kong() {
    static std::vector<std::string> k = [] {
        std::vector<std::string> v;
        for (auto& s : data::get("_original_literals", "kong")) v.push_back(s.get<std::string>());
        return v;
    }();
    return k;
}

static bool ends_with(const std::string& s, const std::string& suf) {
    return s.size() >= suf.size() && s.compare(s.size() - suf.size(), suf.size(), suf) == 0;
}

TerrainCell make_cell(const GenCell& raw, const std::vector<std::string>& empty_blocks) {
    TerrainCell c;
    const std::string& kind = raw.方块;
    bool water = kind == "水" || kind == "海水" || kind == "池水" || ends_with(kind, "水");
    bool ladder = kind == "梯子块" || kind == "梯子" || kind == "扶梯";
    bool in_empty = std::find(empty_blocks.begin(), empty_blocks.end(), kind) != empty_blocks.end();
    c.kind = Sym(kind);
    c.water = water;
    c.ladder = ladder;
    c.solid = !in_empty && !water && !ladder && kind != "" && kind != "空";
    c.background = Sym(raw.has里 ? raw.里方块 : std::string());
    c.native = raw;
    return c;
}

const TerrainCell& MapSnapshot::tile_at(int col, int row) const {
    static TerrainCell above = [] { TerrainCell c; c.kind = Sym("空"); return c; }();
    static TerrainCell below = [] { TerrainCell c; c.kind = Sym("边界"); c.solid = true; return c; }();
    if (row < 0) return above;
    if (row >= rows) return below;
    int m = ((col % cols) + cols) % cols;
    return tiles[size_t(row)][size_t(m)];
}

double MapSnapshot::wrap_x(double x) const { return py::mod(x, double(width)); }
double MapSnapshot::short_dx(double from_x, double to_x) const {
    return py::mod(to_x - from_x + width / 2.0, double(width)) - width / 2.0;
}

namespace {
using Tiles = std::vector<std::vector<TerrainCell>>;

bool standable(const Tiles& t, int col, int feet) {
    return feet >= 2 && feet < int(t.size()) && t[feet][col].solid && !t[feet - 1][col].solid &&
           !t[feet - 2][col].solid && !t[feet - 1][col].water;
}
int first_floor(const Tiles& t, int col) {
    for (int row = 2; row < int(t.size()); ++row) if (standable(t, col, row)) return row;
    return -1;
}
bool protected_support(const Tiles& t, int row, int col) {
    const auto& c = t[row][col];
    return c.water || c.ladder || (row + 1 < int(t.size()) && t[row + 1][col].ladder);
}
int safe_floor(const Tiles& t, int preferred, const std::vector<int>& columns) {
    std::vector<int> rows;
    for (int r = 2; r < int(t.size()); ++r) rows.push_back(r);
    std::stable_sort(rows.begin(), rows.end(), [&](int a, int b) {
        int da = std::abs(a - preferred), db = std::abs(b - preferred);
        return da != db ? da < db : a < b;
    });
    for (int row : rows) {
        bool ok = true;
        for (int col : columns)
            if (protected_support(t, row, col) || t[row - 1][col].water) { ok = false; break; }
        if (ok) return row;
    }
    throw std::runtime_error("无法在保护水域与梯子的前提下设置出生点");
}
void set_cell(Tiles& t, int row, int col, const char* kind, std::vector<TerrainChange>& changes,
              const std::string& reason) {
    const TerrainCell existing = t[row][col];
    if (reason.rfind("horizontal_wrap_", 0) == 0 || reason.rfind("plant_spawn_", 0) == 0) {
        if (existing.water || existing.ladder) return;
        if (std::string(kind) != "空" && protected_support(t, row, col)) return;
    }
    if (existing.kind == Sym(kind) && !existing.water) return;
    changes.push_back({col, row, existing.kind, Sym(kind), reason});
    GenCell raw;
    raw.方块 = kind;
    raw.里方块 = existing.background.str();
    raw.has里 = true;   // _cell({"方块": kind, "里方块": background}) always carries the key
    t[row][col] = make_cell(raw, {"空", "梯子块"});
}
}  // namespace

MapSnapshot build_snapshot(const std::string& map_id, int64_t seed, const std::string& weather, int tile_size,
                           bool adapt) {
    static const std::map<std::string, int> DEFAULT_WATERLINES = {{"家院", 20}, {"大桥", 20}, {"绿洲", 20}, {"木船", 20}};
    static const std::map<std::string, int> RAIN_WATERLINES = {{"家院", 13}, {"大桥", 18}, {"绿洲", 18},
                                                               {"木船", 20}, {"遗迹", 14}, {"小镇", 17},
                                                               {"要塞", 18}, {"古堡", 14}, {"大楼", 14}};
    bool known = false;
    for (auto n : MAP_NAMES) if (map_id == n) known = true;
    if (!known) throw std::runtime_error("Map is not in the verified original catalogue: " + map_id);
    GenGrid original = generate_original_map(map_id, seed);
    const auto& empty = original_kong();
    MapSnapshot s;
    s.map_id = map_id;
    s.seed = seed;
    s.tile_size = tile_size;
    Tiles& tiles = s.tiles;
    for (auto& row : original) {
        tiles.emplace_back();
        for (auto& c : row) tiles.back().push_back(make_cell(c, empty));
    }
    int rows = int(tiles.size()), cols = int(tiles[0].size());
    if (weather != "clear" && weather != "rain") throw std::runtime_error("天气设置无效");
    const auto& wl = weather == "rain" ? RAIN_WATERLINES : DEFAULT_WATERLINES;
    int waterline = wl.count(map_id) ? wl.at(map_id) : rows;
    if (weather == "rain" && map_id == "山地") {
        int highest = -1;
        for (int y = 0; y < rows && highest < 0; ++y)
            for (auto& c : tiles[y]) if (c.solid) { highest = y; break; }
        waterline = int(py::floordiv(highest + 24, 2));
    }
    s.environment.weather = weather;
    s.environment.waterline_row = waterline;
    for (int row = waterline; row < rows; ++row) {
        for (int col = 0; col < cols; ++col) {
            if (row == waterline && row > 2 && tiles[row - 1][col].kind == Sym("梯子块") &&
                tiles[row - 2][col].kind != Sym("梯子块"))
                set_cell(tiles, row - 1, col, "空", s.changes, "native_waterline_ladder_trim");
            if (tiles[row][col].kind == Sym("空") || tiles[row][col].kind == Sym("梯子块")) {
                GenCell original_cell = tiles[row][col].native;
                set_cell(tiles, row, col, "水", s.changes, "native_clear_water");
                tiles[row][col].native = original_cell;
            }
        }
    }
    int center_col = cols / 2, edge_col = 1;
    int center_floor = first_floor(tiles, center_col);
    int edge_floor = first_floor(tiles, edge_col);
    if (center_floor < 0) center_floor = rows - 3;
    if (edge_floor < 0) {
        int f2 = first_floor(tiles, 2);
        edge_floor = f2 > 0 ? f2 : center_floor;   // `or` treats row 0 as falsy; floors are >= 2
    }
    if (adapt) {
        center_floor = safe_floor(tiles, center_floor, {center_col});
        edge_floor = safe_floor(tiles, edge_floor, {0, 1, cols - 2, cols - 1});
        for (int col : {0, 1, cols - 2, cols - 1}) {
            for (int row : {edge_floor - 2, edge_floor - 1}) set_cell(tiles, row, col, "空", s.changes, "horizontal_wrap_portal");
            set_cell(tiles, edge_floor, col, "石", s.changes, "horizontal_wrap_support");
        }
        for (int col : {center_col - 1, center_col, center_col + 1}) {
            for (int row : {center_floor - 2, center_floor - 1}) set_cell(tiles, row, col, "空", s.changes, "plant_spawn_headroom");
            if (!tiles[center_floor][col].solid) set_cell(tiles, center_floor, col, "石", s.changes, "plant_spawn_support");
        }
    } else if (!standable(tiles, center_col, center_floor) || !standable(tiles, edge_col, edge_floor)) {
        throw std::runtime_error("Original map requires a recorded PvP spawn adaptation");
    }
    s.spawn_plant = {(center_col + 0.5) * tile_size, double(center_floor) * tile_size};
    s.spawn_zombie = {(edge_col + 0.5) * tile_size, double(edge_floor) * tile_size};
    s.rows = rows;
    s.cols = cols;
    s.width = cols * tile_size;
    s.height = rows * tile_size;
    return s;
}

bool audit_snapshot(const MapSnapshot& s, std::vector<std::string>* issues) {
    std::vector<std::string> out;
    auto check = [&](const char* faction, const MapSnapshot::Spawn& sp) {
        int col = int(py::mod(py::floordiv(sp.x, s.tile_size), s.cols));
        int row = int(py::floordiv(sp.y, s.tile_size));
        if (!standable(s.tiles, col, row)) out.push_back(std::string(faction) + "_spawn_obstructed");
    };
    check("plant", s.spawn_plant);
    check("zombie", s.spawn_zombie);
    int row = int(py::floordiv(s.spawn_zombie.y, s.tile_size));
    for (int col : {0, s.cols - 1})
        if (!standable(s.tiles, col, row)) { out.push_back("wrap_portal_obstructed"); break; }
    if (issues) *issues = out;
    return out.empty();
}

}  // namespace pvz
