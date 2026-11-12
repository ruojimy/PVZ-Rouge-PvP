// Compare the C++ map generator with extract/golden/maps.json (Python original).
#include "sim/mapgen.h"
#include "data/datastore.h"
#include <cstdio>
#include <fstream>
#include <filesystem>
#include "core/fsutil.h"

int main(int argc, char** argv) {
    using namespace pvz;
    data::set_data_dir(argc > 1 ? argv[1] : "extract/data");
    std::string golden = argc > 2 ? argv[2] : "extract/golden/maps.json";
    std::ifstream f(pvz::u8p(golden), std::ios::binary);
    auto j = nlohmann::json::parse(f);
    int total = 0, bad = 0;
    for (auto& [key, grid] : j.items()) {
        auto bar = key.find('|');
        std::string name = key.substr(0, bar);
        long long seed = std::stoll(key.substr(bar + 1));
        ++total;
        GenGrid g;
        try { g = generate_original_map(name, seed); }
        catch (std::exception& e) { printf("EXC %s: %s\n", key.c_str(), e.what()); ++bad; continue; }
        bool ok = g.size() == grid.size();
        for (size_t y = 0; ok && y < g.size(); ++y)
            for (size_t x = 0; ok && x < g[y].size(); ++x) {
                const auto& c = grid[y][x];
                if (g[y][x].方块 != c[0].get<std::string>() || g[y][x].里方块 != c[1].get<std::string>()) {
                    ok = false;
                    printf("DIFF %s at %zu,%zu: got %s/%s want %s/%s\n", key.c_str(), y, x, g[y][x].方块.c_str(),
                           g[y][x].里方块.c_str(), c[0].get<std::string>().c_str(), c[1].get<std::string>().c_str());
                }
            }
        if (!ok) ++bad;
    }
    printf("maps %d, mismatches %d\n", total, bad);
    return bad ? 1 : 0;
}
