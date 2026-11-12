// Compare build_snapshot with extract/golden/snapshots.json
#include "sim/terrain.h"
#include "data/datastore.h"
#include "core/fsutil.h"
#include <cstdio>
#include <fstream>

int main(int argc, char** argv) {
    using namespace pvz;
    data::set_data_dir("extract/data");
    std::ifstream f(u8p("extract/golden/snapshots.json"), std::ios::binary);
    auto j = nlohmann::json::parse(f);
    int total = 0, bad = 0;
    for (auto& [key, ref] : j.items()) {
        ++total;
        auto a = key.find('|'), b = key.rfind('|');
        std::string name = key.substr(0, a), weather = key.substr(b + 1);
        long long seed = std::stoll(key.substr(a + 1, b - a - 1));
        MapSnapshot s;
        try { s = build_snapshot(name, seed, weather); }
        catch (std::exception& e) {
            if (!ref.contains("error")) { printf("EXC %s %s\n", key.c_str(), e.what()); ++bad; }
            continue;
        }
        bool ok = true;
        for (int y = 0; y < s.rows && ok; ++y)
            for (int x = 0; x < s.cols && ok; ++x) {
                const auto& c = s.tiles[y][x];
                char buf[256];
                snprintf(buf, sizeof buf, "%s/%d%d%d/%s/%s", c.kind.c_str(), c.solid, c.water, c.ladder,
                         c.background.c_str(), c.native.has里 ? "1" : "0");
                if (ref["tiles"][y][x].get<std::string>() != buf) {
                    printf("DIFF %s %d,%d got %s want %s\n", key.c_str(), y, x, buf, ref["tiles"][y][x].get<std::string>().c_str());
                    ok = false;
                }
            }
        auto& sp = ref["spawns"];
        if (sp[0] != s.spawn_plant.x || sp[1] != s.spawn_plant.y || sp[2] != s.spawn_zombie.x || sp[3] != s.spawn_zombie.y) {
            printf("SPAWN %s\n", key.c_str()); ok = false;
        }
        if (ref["changes"].get<int>() != int(s.changes.size()) || ref["waterline"].get<int>() != s.environment.waterline_row ||
            ref["audit"].get<bool>() != audit_snapshot(s)) {
            printf("META %s changes %zu/%d\n", key.c_str(), s.changes.size(), ref["changes"].get<int>()); ok = false;
        }
        if (!ok) ++bad;
    }
    printf("snapshots %d, mismatches %d\n", total, bad);
    return bad ? 1 : 0;
}
