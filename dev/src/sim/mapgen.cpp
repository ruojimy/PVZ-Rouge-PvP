// Line-by-line port of the original 生成地图 (see extract/original/mapgen.py and the
// disassembly notes in docs/mapgen.md). Variable names follow the original.
#include "sim/mapgen.h"
#include "core/pymath.h"
#include "data/datastore.h"
#include <stdexcept>

namespace pvz {

const char* const MAP_NAMES[12] = {"山地", "沙城", "家院", "要塞", "大桥", "铁道",
                                   "遗迹", "绿洲", "小镇", "古堡", "木船", "大楼"};

namespace {

struct Gen {
    PyRandom rng;
    GenGrid ditu;
    explicit Gen(int64_t seed) : rng(seed) {}
    int64_t 随(int64_t a, int64_t b) { return rng.randint(a, b); }
    GenCell& at(int64_t y, int64_t x) {
        // Python negative indexing
        if (y < 0) y += int64_t(ditu.size());
        auto& row = ditu.at(size_t(y));
        if (x < 0) x += int64_t(row.size());
        return row.at(size_t(x));
    }
    void set(int64_t y, int64_t x, const char* v) { at(y, x).方块 = v; }
    void setin(int64_t y, int64_t x, const std::string& v) { auto& c = at(y, x); c.里方块 = v; c.has里 = true; }
    int64_t W() const { return int64_t(ditu[0].size()); }
    int64_t H() const { return int64_t(ditu.size()); }
};

int64_t fdiv(int64_t a, int64_t b) { return int64_t(py::floordiv(double(a), double(b))); }

void gen_山地(Gen& g) {
    int64_t 起伏y = 22, x = -1, 终x = g.W();
    int64_t 参数 = g.随(10, 20);
    int64_t 连续 = 参数 + g.随(fdiv(-参数, 5), fdiv(参数, 5));
    int64_t 上下 = 0, 真连续 = 0;
    while (true) {
        x += 1;
        if (x == 终x) break;
        连续 -= 1;
        if (连续 <= 0 && 真连续 > 1) {
            连续 = 参数 + g.随(fdiv(-参数, 5), fdiv(参数, 5));
            上下 = 上下 == 0 ? 1 : 0;
        }
        if (g.随(1, 2) == 1) {
            if (上下 == 0) {
                起伏y -= 1;
                if (起伏y < 8) 起伏y = 8; else 真连续 = 0;
            } else {
                起伏y += 1;
                if (起伏y > 22) 起伏y = 22; else 真连续 = 0;
            }
        } else {
            真连续 += 1;
        }
        if (22 - 起伏y > 终x - x) 起伏y = 22 - 终x + x;
        int64_t cao = 1, tu = 1;
        for (int64_t yy = 0; yy < 24 - 起伏y; ++yy) {
            int64_t y = 起伏y + yy;
            const char* zi = "石";
            if (cao > 0) { cao -= 1; zi = "草"; }
            else if (tu > 0) { tu -= 1; zi = "土"; }
            g.set(y, x, zi);
        }
    }
}

void gen_大楼(Gen& g) {
    int64_t lou = 2;
    int64_t chux = fdiv(g.W() - lou * 16, 2);
    int64_t gao = 6, chang = 12;
    for (int64_t x = 0; x < g.W(); ++x) {
        int64_t yy = 20;
        for (int64_t lzx = 0; lzx < g.H() - yy; ++lzx) {
            const char* fk;
            if (lzx == 0) fk = "草";
            else if (lzx == 1) { fk = "土"; if (x >= 20 && x <= 49) fk = "石"; }
            else fk = "石";
            g.set(yy + lzx, x, fk);
        }
    }
    int64_t tongdao = g.随(0, 1);
    for (int64_t xx = 0; xx < 6; ++xx) g.set(20, xx + chux + 12, "墙砖");
    if (tongdao == 0) {
        for (int64_t xx = 0; xx < 6; ++xx) {
            int64_t x = xx + chux + 12;
            for (int64_t yy = 0; yy < gao + 1; ++yy) {
                int64_t y = 20 - gao * 2 + yy;
                if (yy == 0 || yy == gao) g.set(y, x, "墙砖");
                else if (yy == fdiv(gao, 2) || yy == fdiv(gao, 2) + 1) g.setin(y, x, "窗户");
                else g.setin(y, x, "墙砖");
            }
        }
    }
    int64_t yqq;
    if (g.随(1, 2) == 1) {
        yqq = 6;
        if (tongdao == 1) {
            int64_t yy = 20 - 3 * gao;
            for (int64_t lzx = 0; lzx < gao * 3 - gao; ++lzx) g.set(yy + lzx + gao, chux + chang, "梯子块");
        }
    } else {
        yqq = 9;
        if (tongdao == 1) {
            int64_t yy = 20 - 3 * gao;
            for (int64_t lzx = 0; lzx < gao * 3 - gao; ++lzx) g.set(yy + lzx + gao, chux + chang + 5, "梯子块");
        }
    }
    int64_t yq;
    if (tongdao == 1) yq = (yqq == 6) ? 8 : 5;
    else yq = (g.随(1, 2) == 1) ? 4 : 7;
    std::vector<int64_t> 破门位;
    { int64_t a = g.随(2, 3); int64_t b = yq; int64_t c = g.随(11, 12); 破门位 = {a, b, c, yqq}; }
    if (tongdao == 0) { 破门位.push_back(5); 破门位.push_back(8); }
    auto in门 = [&](int64_t v) { for (auto p : 破门位) if (p == v) return true; return false; };
    for (int64_t l = 0; l < lou; ++l) {
        for (int64_t ceng = 0; ceng < 3; ++ceng) {
            int64_t yqx = (g.随(0, 1) == 0) ? 2 : 8;
            int64_t y = 0;
            for (int64_t yy = 0; yy < gao; ++yy) {
                y = 20 - gao + yy - ceng * gao;
                for (int64_t xx = 0; xx < chang; ++xx) {
                    int64_t x = chux + xx;
                    if (yy == 0) g.set(y, x, "墙砖");
                    else if (xx == 0 && (!in门(1 + ceng + l * 6) || yy == 1)) g.set(y, x, "墙砖");
                    else if (xx == chang - 1 && (!in门(4 + ceng + l * 6) || yy == 1)) g.set(y, x, "墙砖");
                    else if (yy == 3 && xx > 1 && xx < chang - 2 && gao > 3) g.setin(y, x, "窗户");
                    else g.setin(y, x, "墙砖");
                    if (ceng != 0) continue;
                    g.set(20, x, "墙砖");
                }
                if (ceng == 2) continue;
                GenCell& c = g.at(y, chux + yqx);
                if (c.方块 != "空") { c.里方块 = c.方块; c.has里 = true; }
                c.方块 = "梯子块";
            }
        }
        chux += chang + 6;
    }
}

void gen_铁道(Gen& g) {
    for (int64_t yy = 0; yy < 8; ++yy) {
        const char* fk = yy == 0 ? "铁路" : "石";
        int64_t y = yy + 16;
        for (int64_t x = 0; x < g.W(); ++x) g.set(y, x, fk);
    }
    for (int64_t lzx = 0; lzx < 6; ++lzx) {
        int64_t yq = (lzx == 5) ? g.随(1, 3) : g.随(1, 4);
        for (int64_t yy = 0; yy < 6; ++yy) {
            int64_t y = 9 + yy;
            for (int64_t xx = 0; xx < 11; ++xx) {
                int64_t x = xx + lzx * 12 + 1;
                if (yy == 0 || (yy <= 2 && (xx == 0 || xx == 10))) g.set(y, x, "车体");
                else if (yy == 5) g.set(y, x, "车底");
                else if (yy == 3 && xx > 1 && xx < 9) g.setin(y, x, "窗户");
                else g.setin(y, x, "车体");
            }
        }
        if (g.随(1, 4) == 1 || lzx == 2) {
            for (int64_t yy = 0; yy < 5; ++yy) {
                int64_t y = 9 + yy;
                if (yy == 0 || g.at(y, lzx * 12 + 6).方块 == "空") g.set(y, lzx * 12 + 6, "梯子块");
                if (yy != 0) continue;
                g.setin(y, lzx * 12 + 6, "车体");
            }
        }
        if (yq == 2) {
            for (int64_t yy = 0; yy < 2; ++yy) {
                int64_t y = 12 + yy;
                for (int64_t xx = 0; xx < 5; ++xx) {
                    int64_t x = xx + lzx * 12 + 4;
                    if (yy == 0 && (xx == 0 || xx == 4)) continue;
                    g.set(y, x, "木箱");
                }
            }
        }
        if (yq == 4) {
            for (int64_t yy = 0; yy < 2; ++yy) {
                int64_t y = 12 + yy;
                for (int64_t xx = 0; xx < 6; ++xx) {
                    if (xx == 5 && yy == 0) continue;
                    g.set(y, xx + lzx * 12 + 1, "木箱");
                }
            }
        }
        if (yq == 3) {
            for (int64_t yy = 0; yy < 2; ++yy) {
                int64_t y = 12 + yy;
                for (int64_t xx = 0; xx < 6; ++xx) {
                    if (xx == 5 && yy == 0) continue;
                    g.set(y, 11 - xx + lzx * 12, "木箱");
                }
            }
        }
        for (int64_t xx = 0; xx < 11; ++xx) {
            int64_t x = xx + lzx * 12 + 1;
            if (xx % 2 != 0) continue;
            g.setin(15, x, "车轮");
        }
        g.set(14, lzx * 12, "车底");
        g.setin(13, lzx * 12, "铁栅栏");
    }
}

void gen_沙城(Gen& g) {
    for (int64_t yy = 0; yy < 4; ++yy) {
        const char* fk = yy == 0 ? "沙板" : "沙石";
        for (int64_t x = 0; x < g.W(); ++x) g.set(yy + 20, x, fk);
    }
    for (int side = 0; side < 2; ++side) {
        for (int64_t yy = 0; yy < 7; ++yy) {
            int64_t x = side == 0 ? 1 + yy : g.W() - 2 - yy;
            int64_t y = 19 - yy;
            if (y < 16) y = 16;
            if (yy == 6) y = 19;
            g.set(y, x, "沙板");
            for (int64_t yyy = 0; yyy < 20 - y; ++yyy) g.set(y + yyy + 1, x, "沙石");
        }
    }
    int64_t chux = 10;
    bool 中楼 = false;
    while (true) {
        int64_t chang = g.随(5, 7);
        if (chang == 6) continue;
        if (chux + chang >= g.W() - 8) {
            chang = 5;
            if (!(chux + chang < g.W() - 8)) break;
        }
        int64_t zuo = g.随(0, 1);
        int64_t you = (zuo == 0) ? g.随(0, 1) : 0;
        int64_t tizi = 0;
        if (zuo == 1 || you == 1) tizi = 1;
        if (!中楼 && chux > 27) { 中楼 = true; tizi = 1; }
        int64_t gao = g.随(3, 5);
        int64_t cengs = g.随(1, 2);
        for (int64_t ceng = 0; ceng < cengs; ++ceng) {
            for (int64_t yy = 0; yy < gao; ++yy) {
                int64_t y = 20 - gao + yy - ceng * gao;
                for (int64_t xx = 0; xx < chang; ++xx) {
                    int64_t x = chux + xx;
                    if (yy == 0) {
                        g.set(y, x, (xx == fdiv(chang, 2) && ceng == 1) ? "沙刻" : "沙砖");
                    } else {
                        bool window = yy == 2 && xx > 0 && xx < chang - 1 && gao > 3;
                        if (!window || (tizi != 0 && ceng <= 0)) g.setin(y, x, "沙墙");
                    }
                    if (ceng != 0) continue;
                    if (zuo == 1 && xx == 0) g.set(y, x, "沙砖");
                    if (you == 1 && xx == chang - 1) g.set(y, x, "沙砖");
                    if (tizi == 1 && xx == fdiv(chang, 2)) { g.set(y, x, "梯子块"); g.setin(y, x, "沙墙"); }
                }
            }
        }
        chux += chang + g.随(1, 3);
    }
}

std::vector<std::string> split_dash(const std::string& s) {
    std::vector<std::string> out;
    size_t a = 0;
    while (true) {
        size_t b = s.find('-', a);
        out.push_back(s.substr(a, b == std::string::npos ? std::string::npos : b - a));
        if (b == std::string::npos) break;
        a = b + 1;
    }
    return out;
}

bool starts_with(const std::string& s, const char* utf8char) { return s.rfind(utf8char, 0) == 0; }

void gen_data(Gen& g, const std::string& mapname) {
    const auto& lits = data::get("_original_literals", "地图数据");
    if (!lits.contains(mapname)) throw std::runtime_error("Original generator requested an uncatalogued external map");
    const auto& xditu = lits[mapname];
    std::vector<std::string> fk;
    if (mapname == "家院") fk = {"空", "石", "里-栅栏", "土", "草", "池砖", "墙砖", "屋瓦", "里-窗户", "里-屋瓦", "里-墙砖", "马路", "梯子块"};
    if (mapname == "古堡") fk = {"空", "石", "土", "草", "石砖", "里-石砖", "里-土", "里-石", "里-堡砖", "隔-石砖1", "", ""};
    if (mapname == "大桥") fk = {"空", "石", "土", "草", "桥砖", "里-石", "里-桥砖", "梯子块", "桥面", "", "", ""};
    if (mapname == "要塞") fk = {"空", "石", "土", "草", "砖1", "里-砖3", "里-窗户", "隔-砖3", "梯子块", "", "", ""};
    if (mapname == "木船") fk = {"空", "沙", "木板", "木头", "里-帆", "里-木板", "里-木头", "梯子块", "空", "", "", ""};
    if (mapname == "小镇") fk = {"空", "水泥", "泥砖", "泥砖", "里-泥砖", "木箱", "里-窗户", "", "", "", ""};
    if (mapname == "遗迹") fk = {"空", "石", "石砖", "石砖", "里-石砖", "堡砖", "里-堡砖", "草", "土", "", ""};
    if (mapname == "绿洲") fk = {"空", "沙石", "石", "桥砖", "里-桥砖", "草", "土", "隔-桥砖", "", "", ""};
    for (size_t y = 0; y < xditu.size(); ++y) {
        for (size_t x = 0; x < xditu[0].size(); ++x) {
            int64_t lzx = xditu[y][x].get<int64_t>();
            bool tizi = false;
            if (lzx < 0) { tizi = true; lzx = -lzx; }
            std::string name = fk.at(size_t(lzx));
            if (name.empty()) throw std::runtime_error("string index out of range");
            GenCell& c = g.at(int64_t(y), int64_t(x));
            if (starts_with(name, "里")) {
                std::string namex = split_dash(name).at(1);
                if (namex == "石砖") {
                    int64_t yq = (g.随(1, 6) == 1) ? g.随(2, 3) : 1;
                    namex += std::to_string(yq);
                }
                c.里方块 = namex; c.has里 = true;
                if (tizi) c.方块 = "梯子块";
            } else {
                if (name == "石砖") {
                    int64_t yq = (g.随(1, 6) == 1) ? g.随(2, 3) : 1;
                    name += std::to_string(yq);
                }
                if (starts_with(name, "隔")) {
                    c.里方块 = split_dash(name).at(1); c.has里 = true;
                    if (c.里方块 == "空") { c.里方块.clear(); c.has里 = false; }
                } else {
                    c.方块 = name;
                }
            }
        }
    }
}

}  // namespace

GenGrid generate_original_map(const std::string& name, int64_t seed) {
    Gen g(seed);
    g.ditu.assign(24, std::vector<GenCell>(72));
    if (name == "山地") gen_山地(g);
    else if (name == "大楼") gen_大楼(g);
    else if (name == "铁道") gen_铁道(g);
    else if (name == "沙城") gen_沙城(g);
    else gen_data(g, name);
    return std::move(g.ditu);
}

}  // namespace pvz
