#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_team_maps.h"
#include "sim/pvp/gen/pm_pve.h"
#include "sim/pvp/gen/pm_teams.h"
#include "sim/pvp/gen/pm_coop_cycle.h"
#include "sim/pvp/gen/pm_coop_progress.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/hand/graphics.h"
#include "data/datastore.h"
#include <map>

namespace pvz {

// NativeBattle with a per-native-tick recording hook (python: wrapping _step_original)
struct RecBattle : pm_native_battle::C_NativeBattle {
    std::function<void()> hook;
    V m__step_original(const Args& A) override {
        V r = pm_native_battle::C_NativeBattle::m__step_original(A);
        if (hook) hook();
        return r;
    }
};

void register_hand_hooks();
void register_runtime_hooks();
void init_pvp_modules() {
    static bool done = false;
    if (done) return;
    done = true;
    register_hand_hooks();
    register_runtime_hooks();
    gfx::load_atlas_index(data::data_dir() + "/../assets/index.json");
    pm_native_battle::init();
    pm_pve::init();
    pm_teams::init();
    pm_coop_cycle::init();
    pm_coop_progress::init();
}

static V jv(const nlohmann::json& j) {
    if (j.is_null()) return V::none();
    if (j.is_boolean()) return V(j.get<bool>());
    if (j.is_number()) return V(j.get<double>());
    if (j.is_string()) return V(j.get<std::string>());
    if (j.is_array()) { std::vector<V> it; for (auto& x : j) it.push_back(jv(x)); return V::list(it); }
    V d = V::dict();
    for (auto& [k, v] : j.items()) d.at(V(k)) = jv(v);
    return d;
}

static const nlohmann::json DEFAULT_DECKS = {
    {"plant", {"plant:豌豆射手", "plant:向日葵", "plant:火炬树桩", "secret:猫尾", "secret:蓝火"}},
    {"zombie", {"zombie:普通僵尸", "zombie:脑光墓碑"}}};

BattleHandle battle_from_scenario(const nlohmann::json& sc) {
    init_pvp_modules();
    BattleHandle h;
    h.bridge = pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
    std::string map = sc.value("map", std::string("家院"));
    double seed = sc.value("seed", 1.0);
    std::string weather = sc.value("weather", std::string("clear"));
    // "team_map": <bundled extended map id> builds the co-op/2v2 extended map exactly as the room does
    // (team_maps.bundled_snapshot); otherwise an original map by name.
    V terrain = sc.contains("team_map") ? pm_team_maps::f_bundled_snapshot(Args{V(sc["team_map"].get<std::string>())})
                                         : pm_maps::f_build_snapshot(Args({h.bridge, V(map), V(seed)}, {{Sym("weather"), V(weather)}}));
    if (sc.value("night", false)) {
        // Night is part of the snapshot's environment and checksum (MapSnapshot.terrain_hash):
        // rebuild through from_dict so NativeBattle accepts it, exactly like a room set to 黑夜.
        V d = callm(terrain, Sym("to_dict"), Args{});
        setitem(py::m_get(d, V("environment")), V("night"), V(true));
        callm(d, Sym("pop"), Args{V("terrain_hash"), V::none()});
        terrain = callm(pm_maps::cls_MapSnapshot(), Sym("from_dict"), Args{d});
    }
    V decks = jv(sc.contains("decks") && !sc["decks"].is_null() ? sc["decks"] : DEFAULT_DECKS);
    std::string mode = sc.value("mode", std::string("duel"));
    V rules = py::copy(pm_catalog::RULES);
    V director = V::none();
    if (sc.value("campaign_deck", false)) {
        // PvE / co-op: the campaign's opening deck and its rules (same as tools/oracle_record.py)
        V deck = callm(pm_pve::new_Campaign(Args{}), Sym("battle_deck"), Args{});
        rules = pm_pve::f_pve_rules(Args{rules, deck});
        decks = V::dict();
        decks.at(V("plant")) = deck;
        decks.at(V("zombie")) = V::list();
        if (mode == "coop") decks.at(V("plant2")) = py::copy(deck);
    }
    if (sc.contains("rules"))
        for (auto& [k, v] : sc["rules"].items()) rules.at(V(k)) = jv(v);
    if (sc.contains("director")) {
        auto& d = sc["director"];
        director = pm_pve::new_WaveDirector(Args({V(d.value("day", 1.0))}, {{Sym("seed"), V(d.value("seed", 1.0))}, {Sym("coop"), V(mode == "coop")}}));
        // Diagnostic: begin at a later wave (its predecessor has no members, so it counts as cleared).
        if (d.contains("start_wave")) pvz::setattr(director, Sym("next_wave"), V(d["start_wave"].get<double>()));
    }
    // A linked pixel backend must start with its real pygame facade: asset
    // loading precedes NativeBattle's recording-namespace installation, just
    // as it does for application-created battles. Pure metadata tools retain
    // their recording facade when no pixel backend is installed.
    V pg = py::has_native_hook("graphics.materialize_image")
        ? py::stdlib_module(V("pygame")) : gfx::make_pygame();
    {
        auto p = std::make_shared<RecBattle>();
        h.battle = V::inst(p);
        pm_native_battle::initcv_NativeBattle(p.get());
        p->m___init__(Args({terrain, decks}, {{Sym("rules"), rules}, {Sym("bridge"), h.bridge}, {Sym("pygame"), pg}, {Sym("seed"), V(seed)},
                                              {Sym("mode"), V(mode)}, {Sym("director"), director}}));
    }
    V b = h.battle;
    if (sc.value("clear_cooldowns", false))
        for (auto& kv : py::items_vec(pvz::getattr(b, Sym("players")))) callm(rd(kv.second, V("cooldowns")), Sym("clear"), Args{});
    if (sc.contains("place")) {
        double t = pvz::getattr(b, Sym("tile")).num();
        for (auto& [seat, cr] : sc["place"].items()) {
            V pos = rd(rd(pvz::getattr(b, Sym("hero_states")), V(seat)), V("玩家位置"));
            py::set_slice(pos, V::none(), V::none(), V::list({V(cr[0].get<double>() * t), V(cr[1].get<double>() * t), V(0.0), V(0.0)}));
        }
    }
    if (sc.value("durable_heroes", false)) {
        V avatars = pvz::getattr(b, Sym("avatars")), players = pvz::getattr(b, Sym("players"));
        for (V tmp1_ = py::items(avatars); auto& kv : tmp1_.items()) {
            V av = kv.idx(1);
            setitem(av, V("玩家血量"), V(1e6)); setitem(av, V("_pvp_max_hp"), V(1e6)); setitem(av, V("_pvp_previous_hp"), V(1e6));
            V p = rd(players, kv.idx(0));
            setitem(p, V("hp"), V(1e6)); setitem(p, V("max_hp"), V(1e6));
        }
    }
    double tile = pvz::getattr(b, Sym("tile")).num();
    if (sc.contains("setup")) {
        for (auto& op : sc["setup"]) {
            std::string kind = op.value("op", std::string());
            if (kind == "plant") {
                callm(b, Sym("spawn"), Args{V("plant:" + op["name"].get<std::string>()), V("plant"),
                                            V((op["col"].get<double>() + .5) * tile), V(op["row"].get<double>() * tile),
                                            V(op.value("facing", 1.0))});
            } else if (kind == "zombie") {
                callm(b, Sym("spawn"), Args{V("zombie:" + op["name"].get<std::string>()), V("zombie"),
                                            V(op["x_tiles"].get<double>() * tile), V(op["row"].get<double>() * tile),
                                            V(op.value("facing", -1.0))});
            } else if (kind == "spawn") {
                try {
                    callm(b, Sym("spawn"), Args{V(op["card"].get<std::string>()), V(op["side"].get<std::string>()),
                                                V(op["x"].get<double>()), V(op["y"].get<double>()), V(op.value("facing", 1.0))});
                } catch (PyError& e) {
                    if (!e.matches("ValueError")) throw;   // same tolerance as tools/oracle_record.py
                }
            } else if (kind == "command") {
                pvz::setattr(b, Sym("command"), jv(op["value"]));
            }
        }
    }
    return h;
}

static const char* GKEYS[] = {"植物", "僵尸", "实体", "粒子", "阳光球", "收集阳光", "同横尸", "同竖尸", "冻水", "水波",
                              "目标植物", "目标位置", "人洪水cd", "植洪水cd", "人洪水覆盖", "植洪水覆盖", "梯子cd", "_pvp_water_ice"};

static std::string g_pending_inputs;   // "[side,type,err],..." applied since the last record
static std::vector<std::string> g_extra_g;   // scenario "extra_g": more globals to record
static std::vector<std::string> g_extra_battle;   // scenario "extra_battle": more battle attributes

static void dump_record(BattleHandle& h, int rt, std::ostream& out) {
    V b = h.battle;
    V g = pvz::getattr(b, Sym("g"));
    Match& G = match_of(g);
    std::string s = "{\"t\":";
    s += py_str(pvz::getattr(pvz::getattr(b, Sym("engine")), Sym("native_tick")));
    s += ",\"rt\":" + std::to_string(rt) + ",\"g\":{";
    bool first = true;
    std::vector<std::string> keys(std::begin(GKEYS), std::end(GKEYS));
    keys.insert(keys.end(), g_extra_g.begin(), g_extra_g.end());
    for (auto& k : keys) {
        if (!first) s += ",";
        first = false;
        const V* v = G.find_global(V(k));
        s += "\"" + k + "\":" + ((v && v->has()) ? dump(*v) : "null");
    }
    s += "},\"avatars\":{";
    first = true;
    for (V tmp2_ = py::items(pvz::getattr(b, Sym("avatars"))); auto& kv : tmp2_.items()) {
        if (!first) s += ",";
        first = false;
        s += "\"" + py_str(kv.idx(0)) + "\":" + dump(kv.idx(1));
    }
    s += "},\"players\":{";
    first = true;
    for (V tmp3_ = py::items(pvz::getattr(b, Sym("players"))); auto& kv : tmp3_.items()) {
        if (!first) s += ",";
        first = false;
        V p = kv.idx(1);
        V sub = V::dict();
        for (auto& e : p.kv()) if (e.first != V("deck") && e.first != V("secrets")) sub.at(e.first) = e.second;
        s += "\"" + py_str(kv.idx(0)) + "\":" + dump(sub);
    }
    s += "},\"inp\":[" + g_pending_inputs + "],\"battle\":{";
    first = true;
    std::vector<std::string> bkeys = {"tick", "command", "commands", "rally_point", "rally_points", "result", "deathmatch"};
    bkeys.insert(bkeys.end(), g_extra_battle.begin(), g_extra_battle.end());
    for (auto& k : bkeys) {
        if (!first) s += ",";
        first = false;
        s += "\"" + k + "\":" + dump(pvz::getattr(b, Sym(k), V::none()));
    }
    s += "}}\n";
    g_pending_inputs.clear();
    out << s;
}

// Records after every native tick by stepping the room tick's native ticks ourselves is not
// possible without editing the translated step(); instead NativeBattle exposes the per-native
// hook `_pvp_record_native` (see hand/record_hook.cpp) that this runner installs.
void battle_record_jsonl(BattleHandle& h, const nlohmann::json& sc, std::ostream& out) {
    V b = h.battle;
    int rt = 0;
    auto* rb = as<RecBattle>(b);
    g_extra_g.clear();
    if (sc.contains("extra_g")) for (auto& k : sc["extra_g"]) g_extra_g.push_back(k.get<std::string>());
    g_extra_battle.clear();
    if (sc.contains("extra_battle")) for (auto& k : sc["extra_battle"]) g_extra_battle.push_back(k.get<std::string>());
    rb->hook = [&h, &rt, &out]() { dump_record(h, rt, out); };
    dump_record(h, 0, out);
    int n = sc.value("room_ticks", 30);
    std::map<std::string, int> seqs;
    for (rt = 0; rt < n; ++rt) {
        auto key = std::to_string(rt);
        if (sc.contains("inputs") && sc["inputs"].contains(key)) {
            for (auto& cmd : sc["inputs"][key]) {
                std::string side = cmd["side"].get<std::string>();
                int seq = seqs.count(side) ? seqs[side] + 1 : 0;
                seqs[side] = seq;
                nlohmann::json payload = cmd;
                payload.erase("side");
                payload["seq"] = seq;
                V pv = jv(payload);
                // placeholders for runtime ids (same rule as tools/oracle_record.py resolve())
                for (auto& kvp : pv.kv()) {
                    if (kvp.second == V("$grave")) {
                        V found = V::none();
                        for (auto& u : py::items_vec(pvz::getattr(b, Sym("units")))) {
                            V unit = u.second;
                            if (unit.get(V("behavior"), V::none()) == V("grave") && unit.get(V("hp"), V(0.0)).num() > 0 &&
                                unit.get(V("side"), V::none()) == V("zombie"))
                                found = rd(unit, V("id"));
                        }
                        kvp.second = found;
                    } else if (kvp.second == V("$sun")) {
                        V found = V::none();
                        for (auto& r : py::items_vec(pvz::getattr(b, Sym("resources"))))
                            if (r.second.get(V("side"), V::none()) == V(side)) { found = r.first; break; }
                        kvp.second = found;
                    }
                }
                V err = callm(b, Sym("command_input"), Args{V(side), pv});
                if (!g_pending_inputs.empty()) g_pending_inputs += ",";
                g_pending_inputs += "[" + dump(V(side)) + "," + dump(jv(payload.value("type", nlohmann::json()))) + "," + dump(err) + "]";
            }
        }
        callm(b, Sym("step"), Args{});
    }
    rb->hook = nullptr;
}

}  // namespace pvz
