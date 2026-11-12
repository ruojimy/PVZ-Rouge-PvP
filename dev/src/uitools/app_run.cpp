// Console launcher for the translated app (development): prints Python-level errors instead of a
// message box and can stop after N frames (app.run(auto_test=N)).
//   app_run [frames]      (0 = run until the window is closed)
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_network.h"
#include "ui/gen/pm_lobby_room.h"
#include <map>
#include "sim/pvp/gen/pm_catalog.h"
#include <fstream>
#include <SDL.h>
#include "data/datastore.h"
#include <cstdio>
#include <cstdlib>
#include <windows.h>
#include <cstdlib>

using namespace pvz;
namespace pvz { void install_crash_handler(); void start_sampler(); void stop_sampler_report(int top); }
#include "core/gil.h"

int main(int argc, char** argv) {
    SDL_SetMainReady();
    install_crash_handler();
    gil::init();   // main thread holds the GIL; network transports run on GIL threads
    data::set_data_dir("extract/data");
    py::g_real_clock = true;
    // isolated save folder: never touch the Python release's %APPDATA%/PVZ-Rouge-PvP67 data
    if (!std::getenv("PVP_USERDATA")) {
        const char* appdata = std::getenv("APPDATA");
        std::string dir = std::string(appdata ? appdata : ".") + "/PVZ-PvP-Native/pvp_userdata";
        _putenv_s("PVP_USERDATA", dir.c_str());
        SetEnvironmentVariableA("PVP_USERDATA", dir.c_str());
    }
    pg::install_pygame();
    int frames = argc > 1 ? std::atoi(argv[1]) : 0;
    try {
        init_pvp_modules();
        pm_app::init();
        // app_run smokedbg -> same driver through a callable, dumping app.smoke when it fails
        if (argc > 1 && std::string(argv[1]) == "smokedbg") {
            auto app_ref = std::make_shared<V>();
            V cb = V::func([app_ref](const Args& a) {
                *app_ref = a.pos.at(0);
                if (a.pos.at(1).num() == 2399) {   // state just before the driver's frame-budget assertion
                    V room = pvz::getattr(*app_ref, Sym("room"), V::none());
                    fprintf(stderr, "VIEW phase=%s status=%s\n", py_str(py::m_get(pvz::getattr(*app_ref, Sym("view")), V("phase"))).c_str(),
                            py_str(py::m_get(pvz::getattr(*app_ref, Sym("view")), V("status"))).c_str());
                    if (!room.is_none()) {
                        for (const char* k : {"phase", "status", "rematch_votes", "members", "connected", "mode"})
                            fprintf(stderr, "ROOM %s=%s\n", k, dump(pvz::getattr(room, Sym(k), V::none())).substr(0, 300).c_str());
                        fprintf(stderr, "ROOM seat_list=%s local_sides=%s\n", dump(callm(room, Sym("seat_list"), Args{})).c_str(),
                                dump(callm(*app_ref, Sym("local_sides"), Args{})).c_str());
                        for (const char* peer : {"host", "guest"}) {
                            V err = callm(room, Sym("command"), Args{V(peer), py_dict({{V("type"), V("rematch")}, {V("swap"), V(false)}, {V("same_deck"), V(false)}, {V("revision"), pvz::getattr(room, Sym("revision"))}})});
                            fprintf(stderr, "ROOM rematch(%s) -> %s\n", peer, py_str(err).c_str());
                        }
                        fprintf(stderr, "ROOM after phase=%s\n", dump(pvz::getattr(room, Sym("phase"))).c_str());
                        fprintf(stderr, "REV room=%s view=%s\n", dump(pvz::getattr(room, Sym("revision"))).c_str(),
                                dump(py::m_get(pvz::getattr(*app_ref, Sym("view")), V("revision"))).c_str());
                    }
                }
                return pm_app::f__smoke_driver(Args{a.pos.at(0), a.pos.at(1)});
            });
            try {
                pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            } catch (PyError& e) {
                fprintf(stderr, "PyError %s\n", e.what());
                if (app_ref->has()) {
                    V rec = pvz::getattr(*app_ref, Sym("smoke"), V::none());
                    V copy = V::dict();
                    if (rec.is_dict()) for (auto& kv : rec.kv()) if (kv.first.str().find("hash") == std::string::npos) copy.at(kv.first) = kv.second;
                    fprintf(stderr, "SMOKE RECORD %s\n", dump(copy).substr(0, 4000).c_str());
                    fprintf(stderr, "VIEW phase=%s\n", py_str(py::m_get(pvz::getattr(*app_ref, Sym("view")), V("phase"))).c_str());
                    V room = pvz::getattr(*app_ref, Sym("room"), V::none());
                    if (!room.is_none()) {
                        for (const char* k : {"phase", "status", "rematch_votes", "members", "connected", "mode"})
                            fprintf(stderr, "ROOM %s=%s\n", k, dump(pvz::getattr(room, Sym(k), V::none())).substr(0, 300).c_str());
                        fprintf(stderr, "ROOM seat_list=%s\n", dump(callm(room, Sym("seat_list"), Args{})).c_str());
                        V err = callm(room, Sym("command"), Args{py_dict({{V("type"), V("rematch")}, {V("swap"), V(false)}, {V("same_deck"), V(false)}}), V("plant")});
                        fprintf(stderr, "ROOM rematch(plant) -> %s\n", py_str(err).c_str());
                    }
                }
                return 2;
            }
            return 0;
        }
        // app_run netpeer host|guest <port> <tokenfile> -> two processes play a networked room over
        // 127.0.0.1: connect, confirm the map, draft through the view (like a player would), reach battle
        if (argc > 4 && std::string(argv[1]) == "netpeer") {
            std::string role = argv[2], tokenfile = argv[4];
            int port = std::atoi(argv[3]);
            std::string mode = argc > 5 ? argv[5] : "duel";   // duel | coop  (role spectate: a third process watching)
            struct St { int attempt = 0; double step = -1; int since = 0; int battle_frames = 0; bool joined = false; int result = 1; std::string last_phase;
                        bool chat_ok = false, surrendered = false; int result_frames = 0; };
            auto st = std::make_shared<St>();
            V cb = V::func([=](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                V state = pvz::getattr(app, Sym("state"));
                bool relay = mode == "relay";   // private room through the public relay (relay.json beside the exe)
                if (relay && role == "host" && fr > 2 && !st->joined) {
                    std::string tok = py_str(py::m_get(state, V("token"), V("")));
                    if (!tok.empty()) { std::ofstream(tokenfile, std::ios::binary) << tok; st->joined = true; fprintf(stderr, "NET host relay room code=%s\n", tok.c_str()); }
                    if (fr % 120 == 0) fprintf(stderr, "NET host relay waiting msg=%s\n", py_str(py::m_get(state, V("message"), V(""))).c_str());
                }
                if (fr == 2 && role == "host" && relay) {
                    state.at(V("network_mode")) = V("relay");
                    state.at(V("room_public")) = V(false);
                    state.at(V("room_name")) = V("native-test");
                    state.at(V("save_replays")) = V(true);
                    fprintf(stderr, "NET host relay endpoint=%s\n", py_str(py::m_get(state, V("relay_endpoint"), V(""))).c_str());
                    callm(app, Sym("create"), Args{});
                }
                if (fr == 2 && role == "host" && !relay) {
                    state.at(V("network_mode")) = V("direct");
                    state.at(V("port")) = V(std::to_string(port));
                    state.at(V("save_replays")) = V(true);
                    callm(app, Sym("create"), Args{});
                    if (mode == "coop") {
                        V err = callm(pvz::getattr(app, Sym("room")), Sym("set_mode"), Args{V("coop")});
                        fprintf(stderr, "NET host set_mode coop -> '%s'\n", py_str(err).c_str());
                    }
                    std::ofstream(tokenfile, std::ios::binary) << py_str(py::m_get(state, V("token"), V("")));
                    fprintf(stderr, "NET host listening token=%s\n", py_str(py::m_get(state, V("token"), V(""))).c_str());
                }
                if ((role == "guest" || role == "spectate") && !st->joined && fr > 2 && fr % 10 == 0) {
                    std::ifstream f(tokenfile, std::ios::binary);
                    std::string tok; if (f) std::getline(f, tok);
                    if (tok.size() >= 4) {
                        state.at(V("network_mode")) = V(relay ? "relay" : "direct");
                        state.at(V("address")) = V("127.0.0.1:" + std::to_string(port));
                        state.at(V("token")) = V(tok);
                        callm(app, Sym("join"), Args({}, {{Sym("spectator"), V(role == "spectate")}}));
                        st->joined = true;
                        fprintf(stderr, "NET guest joining token=%s\n", tok.c_str());
                    }
                }
                V view = pvz::getattr(app, Sym("view"));
                std::string phase = py_str(py::m_get(view, V("phase"), V("")));
                if (phase != st->last_phase) { fprintf(stderr, "NET %s frame=%d t=%u phase=%s msg=%s\n", role.c_str(), fr, SDL_GetTicks(), phase.c_str(), py_str(py::m_get(state, V("message"), V(""))).substr(0, 120).c_str()); st->last_phase = phase; }
                V locals = callm(app, Sym("local_sides"), Args{});
                if (getenv("PVZ_PROFILE") && fr == atoi(getenv("PVZ_PROFILE"))) start_sampler();
                if (getenv("PVZ_PROFILE") && getenv("PVZ_PROF_TO") && fr == atoi(getenv("PVZ_PROF_TO"))) stop_sampler_report(30);
                if (fr == 200 && (phase == "banning")) {
                    std::string ks;
                    for (auto& kv : view.kv()) { std::string k = py_str(kv.first); if (k.find("draft") != std::string::npos || k.find("current") != std::string::npos || k.find("action") != std::string::npos || k.find("stage") != std::string::npos) ks += k + "=" + dump(kv.second).substr(0, 160) + " | "; }
                    fprintf(stderr, "NET %s VIEW %s\n", role.c_str(), ks.c_str());
                }
                if (fr % 300 == 0)
                    fprintf(stderr, "NET %s frame=%d t=%u phase=%s side=%s act=%s remaining=%s locals=%s attempt=%d msg=%s\n", role.c_str(), fr, SDL_GetTicks(), phase.c_str(),
                            dump(py::m_get(view, V("current_side"), V::none())).c_str(), dump(py::m_get(view, V("current_action"), V::none())).substr(0, 120).c_str(),
                            dump(py::m_get(view, V("remaining"), V::none())).c_str(), dump(locals).c_str(), st->attempt,
                            py_str(py::m_get(state, V("message"), V(""))).substr(0, 100).c_str());
                if (phase == "config" && fr % 30 == 0) callm(app, Sym("action"), Args{V::tuple({V("confirm_map")})});
                if ((phase == "banning" || phase == "picking") && fr % 6 == 0) {
                    V side = py::m_get(view, V("current_side"), V::none());
                    V act = py::m_get(view, V("current_action"), V::none());
                    double step = py::m_get(view, V("remaining"), V(0.0)).num();
                    if (step != st->step) { st->step = step; st->attempt = 0; st->since = 0; }
                    if (!side.is_none() && py::in(side, locals)) {
                        if (st->since++ % 2 == 0) {
                            // view: current_side = actor, current_action = the ban category ("plant" / "zombie" / "secret")
                            std::string kind = phase == "banning" ? "ban" : "pick", cat = act.t == V::STR ? act.str() : std::string();
                            V bans = py::m_get(view, V("bans"), V::list());
                            V own = py::m_get(py::m_get(view, V("decks"), V::dict()), side, V::list());
                            std::vector<V> cands;
                            for (auto& kv : pm_catalog::CARDS.kv()) {
                                const V& c = kv.second;
                                std::string cs = py_str(py::m_get(c, V("side"), V(""))), cc = py_str(py::m_get(c, V("category"), V("")));
                                if (py::in(kv.first, bans) || py::in(kv.first, own)) continue;
                                if (kind == "ban" && cat != "secret" && cs == cat && cc != "secret") cands.push_back(kv.first);
                                if (kind == "pick" && py_str(side).rfind(cs, 0) == 0) cands.push_back(kv.first);
                            }
                            V card = (kind == "ban" && cat == "secret") || cands.empty() ? V::none() : cands[size_t(st->attempt) % cands.size()];
                            ++st->attempt;
                            V err = callm(app, Sym("command"), Args{py_dict({{V("type"), V(kind)}, {V("card"), card}}), side});
                            (void)err;
                        }
                    }
                    if (py_str(py::m_get(view, V("draft_stage"), V(""))) == "complete" && fr % 30 == 0)
                        for (auto& s : py::iter_list(locals).items()) callm(app, Sym("command"), Args{py_dict({{V("type"), V("ready")}, {V("ready"), V(true)}}), s});
                }
                if (role == "spectate") {
                    if (phase == "battle" && ++st->battle_frames == 120) {
                        fprintf(stderr, "NET spectate PASS watching battle (received_snapshots=%s spectating=%s)\n", dump(pvz::getattr(app, Sym("received_snapshots"), V(0.0))).c_str(),
                                dump(py::m_get(state, V("spectating"), V::none())).c_str());
                        st->result = 0;
                        pvz::setattr(app, Sym("running"), V(false));
                    }
                    if (fr > 60 * 150) { fprintf(stderr, "NET spectate TIMEOUT phase=%s\n", phase.c_str()); pvz::setattr(app, Sym("running"), V(false)); }
                    return V::none();
                }
                // co-op: team chat from the guest must reach the host's view
                if (mode == "coop" && !phase.empty()) {
                    if (st->chat_ok && fr % 600 == 0) { st->result = 0; pvz::setattr(app, Sym("running"), V(false)); }
                    if (role == "guest" && fr == 200)
                        for (auto& s : py::iter_list(locals).items()) callm(app, Sym("command"), Args{py_dict({{V("type"), V("chat")}, {V("text"), V("native chat check")}}), s});
                    if (!st->chat_ok && dump(view).find("native chat check") != std::string::npos) { st->chat_ok = true; fprintf(stderr, "NET %s CHAT OK frame=%d\n", role.c_str(), fr); }
                }
                // duel: the host surrenders after the battle check; the match result saves a replay, which must replay and verify
                { static const int perf_s = getenv("NETPERF") ? atoi(getenv("NETPERF")) : 0; static uint32_t t0 = 0; static int f0 = 0;
                  if (perf_s && phase == "battle" && st->battle_frames % 300 == 1) { uint32_t now = SDL_GetTicks(); if (t0) {
                      V pb = pvz::getattr(app, Sym("presentation_budget"), V::none());
                      fprintf(stderr, "NETPERF %s battle=%ds fps=%.1f render_ms=%s presented=%s skipped=%s snapshots=%s\n", role.c_str(), st->battle_frames / 60, (st->battle_frames - f0) * 1000.0 / std::max<uint32_t>(1, now - t0),
                          pb.is_none() ? "?" : dump(pvz::getattr(pb, Sym("cost"))).c_str(), pb.is_none() ? "?" : dump(pvz::getattr(pb, Sym("presented"))).c_str(), pb.is_none() ? "?" : dump(pvz::getattr(pb, Sym("skipped"))).c_str(),
                          dump(pvz::getattr(app, Sym("received_snapshots"), V(0.0))).c_str()); }
                      t0 = now; f0 = st->battle_frames; } }
                if (mode == "duel" && role == "host" && phase == "battle" && st->battle_frames == (getenv("NETPERF") ? atoi(getenv("NETPERF")) * 60 : 240) && !st->surrendered) {
                    st->surrendered = true;
                    V err = callm(app, Sym("input"), Args{py::iter_list(locals).idx(0), V("surrender")});
                    fprintf(stderr, "NET host surrender -> '%s'\n", py_str(err).c_str());
                }
                if (mode == "duel" && role == "host" && phase == "result" && st->surrendered && ++st->result_frames == 30) {
                    bool replay_verified = false;
                    std::string saved = py_str(py::m_get(state, V("replay_saved"), V("")));
                    fprintf(stderr, "NET host replay_saved=%s\n", saved.c_str());
                    if (!saved.empty()) {
                        callm(app, Sym("close_room"), Args{});
                        callm(app, Sym("action"), Args{V::tuple({V("replay_open"), V(saved)})});
                        V pb = pvz::getattr(app, Sym("playback"), V::none());
                        if (!pb.is_none()) {
                            callm(pb, Sym("seek"), Args{V(1e9)});   // to the end: the final hash is verified there
                            for (int i = 0; i < 2000 && !pvz::getattr(pb, Sym("target"), V::none()).is_none(); ++i)
                                callm(pb, Sym("update"), Args({V(0.0)}, {{Sym("max_steps"), V(120.0)}, {Sym("budget"), V(1.0)}}));
                            fprintf(stderr, "NET host REPLAY verified=%s error=%s\n", dump(pvz::getattr(pb, Sym("verified"), V::none())).c_str(), dump(pvz::getattr(pb, Sym("error"), V::none())).c_str());
                            replay_verified = pvz::getattr(pb, Sym("verified"), V(false)).truthy() && !pvz::getattr(pb, Sym("error"), V::none()).truthy();
                        } else fprintf(stderr, "NET host REPLAY open failed: %s\n", py_str(py::m_get(state, V("message"), V(""))).c_str());
                    }
                    st->result = replay_verified ? 0 : 1;
                    pvz::setattr(app, Sym("running"), V(false));
                }
                // A duel guest must remain connected until the host has
                // surrendered and sent the result, not race its 240th frame.
                if (mode == "duel" && role == "guest" && phase == "result" && ++st->result_frames == 120) {
                    fprintf(stderr, "NET guest PASS result received (received_snapshots=%s)\n", dump(pvz::getattr(app, Sym("received_snapshots"), V(0.0))).c_str());
                    st->result = 0;
                    pvz::setattr(app, Sym("running"), V(false));
                }
                if (phase == "battle" && ++st->battle_frames == (mode == "duel" ? 100000 : 240)) {
                    fprintf(stderr, "NET %s PASS battle reached (received_snapshots=%s)\n", role.c_str(), dump(pvz::getattr(app, Sym("received_snapshots"), V(0.0))).c_str());
                    st->result = 0;
                    pvz::setattr(app, Sym("running"), V(false));
                }
                if (fr > 60 * 150) { fprintf(stderr, "NET %s TIMEOUT phase=%s\n", role.c_str(), phase.c_str()); pvz::setattr(app, Sym("running"), V(false)); }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return st->result;
        }
        // app_run almanac -> in a local room's draft, right-click every card (opens its almanac page, simple
        // and detailed view) and render; any PyError fails (user report 11-02: right-click crashed in re)
        if (argc > 1 && std::string(argv[1]) == "almanac") {
            auto result = std::make_shared<int>(1);
            V cb = V::func([result](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                if (fr == 2) callm(app, Sym("create"), Args({}, {{Sym("local"), V(true)}}));
                if (fr == 4) callm(app, Sym("action"), Args{V::tuple({V("confirm_map")})});
                if (fr == 8) {
                    int n = 0;
                    for (auto& kv : pm_catalog::CARDS.kv()) {
                        callm(app, Sym("action"), Args({V::tuple({V("card"), kv.first})}, {{Sym("right"), V(true)}}));
                        callm(app, Sym("render"), Args{});
                        callm(app, Sym("action"), Args{V::tuple({V("almanac_detail")})});
                        callm(app, Sym("render"), Args{});
                        callm(app, Sym("action"), Args{V::tuple({V("almanac_detail")})});
                        ++n;
                    }
                    V state = pvz::getattr(app, Sym("state"));
                    fprintf(stderr, "ALMANAC %d cards rendered, screen=%s\n", n, py_str(py::m_get(state, V("screen"), V(""))).c_str());
                    *result = 0;
                    pvz::setattr(app, Sym("running"), V(false));
                }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return *result;
        }
        // app_run retest <cases.json> <out.json> -> run tools/re_cases.py cases through the native re module
        if (argc > 3 && std::string(argv[1]) == "retest") {
            V json = py::stdlib_module(V("json"));
            V cases = callm(json, Sym("loads"), Args{callm(py::path_new(Args{V(std::string(argv[2]))}), Sym("read_text"), Args({}, {{Sym("encoding"), V("utf-8")}}))});
            V re = py::stdlib_module(V("re"));
            std::vector<V> out;
            for (auto& c : py::iter_list(cases).items()) {
                V cs = py::m_get(c, V("case"));
                std::string op = py_str(cs.idx(0));
                V pat = cs.idx(1), text = cs.idx(2), flags = cs.idx(3);
                V res;
                try {
                    Args fl({}, {{Sym("flags"), flags}});
                    if (op == "split") res = callm(re, Sym("split"), Args({pat, text}, {{Sym("flags"), flags}}));
                    else if (op == "findall") {
                        V r = callm(re, Sym("findall"), Args({pat, text}, {{Sym("flags"), flags}}));
                        std::vector<V> o; for (auto& x : py::iter_list(r).items()) o.push_back(x.t == V::TUPLE ? V::list(x.items()) : x);
                        res = V::list(o);
                    } else if (op == "sub") res = callm(re, Sym("sub"), Args({pat, cs.idx(4), text}, {{Sym("flags"), flags}}));
                    else {
                        V m = callm(re, Sym(op), Args({pat, text}, {{Sym("flags"), flags}}));
                        res = m.is_none() ? V::none() : V::list({callm(m, Sym("group"), Args{V(0.0)}), V::list(callm(m, Sym("groups"), Args{}).items()), V::list(callm(m, Sym("span"), Args{}).items())});
                    }
                } catch (PyError& e) { res = V("error: " + e.kind); }
                out.push_back(res);
            }
            callm(py::path_new(Args{V(std::string(argv[3]))}), Sym("write_text"), Args({callm(json, Sym("dumps"), Args({V::list(out)}, {{Sym("ensure_ascii"), V(false)}}))}, {{Sym("encoding"), V("utf-8")}}));
            printf("retest %zu cases\n", out.size());
            return 0;
        }
        // app_run mapedit [shot_dir] -> map editor: new map, paint a blue snow block, save, reload from disk,
        // "use" it, open a local room on it, confirm the map and reach the draft
        if (argc > 1 && std::string(argv[1]) == "mapedit") {
            std::string shots = argc > 2 ? argv[2] : "";
            struct St { int stage = 0; int at = 0; int result = 1; std::string id; };
            auto st = std::make_shared<St>();
            auto shot = [shots](const char* name) {
                if (shots.empty()) return;
                V pygame = py::stdlib_module(V("pygame"));
                V screen = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{});
                callm(pvz::getattr(pygame, Sym("image")), Sym("save"), Args{screen, V(shots + "/" + name + ".png")});
            };
            V cb = V::func([=](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                V state = pvz::getattr(app, Sym("state"));
                auto act = [&](std::initializer_list<V> xs) { callm(app, Sym("action"), Args{V::tuple(std::vector<V>(xs))}); };
                auto say = [&](const std::string& what) { fprintf(stderr, "MAP frame=%d stage=%d screen=%s %s msg=%s\n", fr, st->stage, py_str(py::m_get(state, V("screen"), V(""))).c_str(), what.c_str(), py_str(py::m_get(state, V("message"), V(""))).substr(0, 100).c_str()); };
                auto fail = [&](const std::string& why) { say("FAIL " + why); pvz::setattr(app, Sym("running"), V(false)); };
                if (st->stage == 0 && fr == 10) { act({V("maps_open")}); act({V("maps_new"), V(true)}); st->stage = 1; st->at = fr; say("new map"); }
                else if (st->stage == 1 && fr - st->at == 10) {
                    act({V("mapedit_tool"), V("雪")});
                    act({V("mapedit_color"), V(6.0)});
                    V canvas = py::m_get(state, V("map_canvas"), V::none());
                    if (canvas.is_none()) return fail("no canvas"), V::none();
                    V rect = canvas.idx(0); double cell = canvas.idx(1).num();
                    V pos = V::tuple({V(rect.idx(0).num() + 30.5 * cell), V(rect.idx(1).num() + 18.5 * cell)});
                    callm(app, Sym("map_brush"), Args{pos});
                    V doc = pvz::getattr(pvz::getattr(app, Sym("map_editor")), Sym("document"));
                    std::string cellv = py_str(doc.at(V("grid")).idx(18).idx(30));
                    say("painted grid[18][30]=" + cellv + " color=" + dump(doc.at(V("colors")).idx(18).idx(30)));
                    if (cellv != "雪") return fail("brush did not paint"), V::none();
                    shot("01-editor");
                    state.at(V("map_name")) = V("原生版测试地图");
                    act({V("mapedit_save")});
                    doc = pvz::getattr(pvz::getattr(app, Sym("map_editor")), Sym("document"));
                    st->id = py_str(doc.at(V("id")));
                    V loaded = callm(pvz::getattr(app, Sym("map_store")), Sym("load"), Args{V(st->id)});
                    bool same = py_eq(loaded, doc);
                    say("saved id=" + st->id + " disk roundtrip=" + (same ? "ok" : "MISMATCH"));
                    if (!same) return fail("disk roundtrip"), V::none();
                    act({V("mapedit_use")});
                    say("use");
                    act({V("maps_launch"), V("local")});
                    st->stage = 2; st->at = fr;
                }
                else if (st->stage == 2 && fr - st->at == 20) {
                    V room = pvz::getattr(app, Sym("room"), V::none());
                    if (room.is_none()) return fail("no room"), V::none();
                    std::string mid = py_str(pvz::getattr(room, Sym("map_id")));
                    say("room map_id=" + mid);
                    if (mid != "custom:" + st->id) return fail("room is not on the custom map"), V::none();
                    shot("02-room");
                    act({V("confirm_map")});
                    st->stage = 3; st->at = fr;
                }
                else if (st->stage == 3) {
                    V room = pvz::getattr(app, Sym("room"));
                    std::string phase = py_str(pvz::getattr(room, Sym("phase")));
                    if (phase == "banning") { say("PASS draft on the custom map"); shot("03-draft"); st->result = 0; pvz::setattr(app, Sym("running"), V(false)); }
                    else if (fr - st->at > 600) fail("confirm did not start the draft, phase=" + phase);
                    else if ((fr - st->at) % 30 == 0) act({V("confirm_map")});
                }
                if (fr > 60 * 60) fail("timeout");
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return st->result;
        }
        // app_run cooplobby [shot_dir] -> home "合作闯关" -> coop_entry -> fixed co-op AI room -> campaign -> battle;
        // the AI teammate (plant2) must plant (smoke66._coop_fixed through the lobby entry)
        if (argc > 1 && std::string(argv[1]) == "cooplobby") {
            std::string shots = argc > 2 ? argv[2] : "";
            struct St { int stage = 0; int wait = 0; int result = 1; };
            auto st = std::make_shared<St>();
            auto shot = [shots](const char* name) {
                if (shots.empty()) return;
                V pygame = py::stdlib_module(V("pygame"));
                V screen = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{});
                callm(pvz::getattr(pygame, Sym("image")), Sym("save"), Args{screen, V(shots + "/" + name + ".png")});
            };
            V cb = V::func([=](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                V state = pvz::getattr(app, Sym("state"));
                std::string screen = py_str(py::m_get(state, V("screen"), V("")));
                V room = pvz::getattr(app, Sym("room"), V::none());
                auto say = [&](const char* what) { fprintf(stderr, "COOP frame=%d stage=%d screen=%s %s msg=%s\n", fr, st->stage, screen.c_str(), what, py_str(py::m_get(state, V("message"), V(""))).substr(0, 100).c_str()); };
                if (fr == 5) shot("01-home");
                if (st->stage == 0 && fr == 10) { callm(app, Sym("action"), Args{V::tuple({V("coop_lobby")})}); st->stage = 1; say("coop_lobby"); }
                else if (st->stage == 1 && fr == 20) { shot("02-coop-entry"); say("entry"); callm(app, Sym("action"), Args{V::tuple({V("ai_room"), V("coop")})}); st->stage = 2; }
                else if (st->stage == 2 && !room.is_none() && py::len(pvz::getattr(room, Sym("members"))).num() >= 2) { say("teammate seated"); shot("03-coop-room"); callm(app, Sym("action"), Args{V::tuple({V("pve_open")})}); st->stage = 3; st->wait = fr; }
                else if (st->stage == 3 && fr - st->wait == 20) { shot("04-campaign"); say("pve_open"); callm(app, Sym("action"), Args{V::tuple({V("pve_start")})}); st->stage = 4; }
                else if (st->stage == 4 && !room.is_none() && py_str(pvz::getattr(room, Sym("phase"))) == "battle") { say("battle"); st->stage = 5; st->wait = fr; }
                else if (st->stage == 5) {
                    V snap = callm(pvz::getattr(room, Sym("battle")), Sym("snapshot"), Args({}, {{Sym("include_map"), V(false)}}));
                    V units = py::m_get(snap, V("units"), V::list());
                    if (units.is_dict()) units = callm(units, Sym("values"), Args{});
                    bool planted = false;
                    for (auto& u : py::iter_list(units).items()) if (py_str(py::m_get(u, V("seat"), V(""))) == "plant2" && py_str(py::m_get(u, V("side"), V(""))) == "plant") planted = true;
                    if (planted && fr - st->wait > 60 * 30) { fprintf(stderr, "PURE_TYPED_AUDIT %s\n", dump(callm(pvz::getattr(room, Sym("battle")), Sym("backend_audit"), Args{})).c_str()); say("PASS teammate planted"); shot("05-coop-battle"); st->result = 0; pvz::setattr(app, Sym("running"), V(false)); }
                    else if (fr - st->wait > 60 * 90) { say("FAIL teammate never planted"); pvz::setattr(app, Sym("running"), V(false)); }
                }
                if (fr % 600 == 0) say("tick");
                if (fr > 60 * 300) { say("TIMEOUT"); pvz::setattr(app, Sym("running"), V(false)); }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return st->result;
        }
        // app_run airoom [seconds] -> the lobby's fixed AI room: the host drafts legal cards (room rules), the
        // embedded rival (rv_r22) drafts and plays; the battle runs for N seconds, counting both sides' units
        if (argc > 1 && std::string(argv[1]) == "airoom") {
            int seconds = argc > 2 ? std::atoi(argv[2]) : 60;
            struct St { int battle_frames = 0; std::string last; int result = 1; std::map<std::string, int> peak; };
            auto st = std::make_shared<St>();
            V cb = V::func([=](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                if (fr == 2) pm_lobby_room::f_create(Args{app});
                if (getenv("PVZ_PROFILE") && fr == atoi(getenv("PVZ_PROFILE"))) start_sampler();
                if (getenv("PVZ_PROFILE") && getenv("PVZ_PROF_TO") && fr == atoi(getenv("PVZ_PROF_TO"))) stop_sampler_report(40);
                V room = pvz::getattr(app, Sym("room"), V::none());
                if (room.is_none()) return V::none();
                std::string phase = py_str(pvz::getattr(room, Sym("phase")));
                if (phase != st->last) { fprintf(stderr, "AI frame=%d t=%u phase=%s status=%s\n", fr, SDL_GetTicks(), phase.c_str(), py_str(pvz::getattr(room, Sym("status"), V(""))).substr(0, 100).c_str()); st->last = phase; }
                V host = callm(room, Sym("side_for"), Args{V("host")});
                if (phase == "config" && fr % 20 == 0 && py::len(pvz::getattr(room, Sym("members"))).num() >= 2
                    && !py::m_get(pvz::getattr(room, Sym("confirmed")), host, V(false)).truthy()) {
                    V err = callm(app, Sym("command"), Args{py_dict({{V("type"), V("confirm_map")}, {V("terrain_hash"), pvz::getattr(pvz::getattr(room, Sym("map")), Sym("terrain_hash"))}})});
                    if (fr % 300 == 0) fprintf(stderr, "AI confirm -> '%s' confirmed=%s\n", py_str(err).c_str(), dump(pvz::getattr(room, Sym("confirmed"))).c_str());
                }
                if (phase == "config" && fr % 300 == 0)
                    fprintf(stderr, "AI config members=%s ai_room=%d connected=%s audit_error=%s seats=%s\n", dump(pvz::getattr(room, Sym("members"))).c_str(), int(!pvz::getattr(app, Sym("ai_room"), V::none()).is_none()),
                            dump(pvz::getattr(room, Sym("connected"), V::none())).c_str(), dump(pvz::getattr(room, Sym("audit_error"), V::none())).c_str(),
                            dump(callm(room, Sym("seat_list"), Args{})).c_str());
                if ((phase == "banning" || phase == "picking") && fr % 3 == 0) {
                    V act = callm(room, Sym("_draft_action"), Args{});
                    if (act.is_dict() && py::m_get(act, V("side")) == host) {
                        std::string kind = py_str(py::m_get(act, V("kind")));
                        V card = V::none();
                        if (kind == "ban" && py_str(py::m_get(act, V("category"))) != "secret") {
                            for (auto& kv : pm_catalog::CARDS.kv()) if (!callm(room, Sym("_ban_error"), Args{host, kv.first}).truthy()) { card = kv.first; break; }
                        } else if (kind == "pick") {
                            card = callm(room, Sym("_timeout_pick"), Args{host});
                        }
                        callm(app, Sym("command"), Args{py_dict({{V("type"), V(kind)}, {V("card"), card}}), host});
                    } else if (!act.truthy() && py_str(pvz::getattr(room, Sym("draft_stage"))) == "complete" && fr % 30 == 0)
                        callm(app, Sym("command"), Args{py_dict({{V("type"), V("ready")}, {V("ready"), V(true)}}), host});
                }
                if (phase == "battle") {
                    ++st->battle_frames;
                    if (st->battle_frames % 600 == 0) {
                        V snap = callm(pvz::getattr(room, Sym("battle")), Sym("snapshot"), Args{});
                        std::map<std::string, int> count;
                        for (auto& u : py::iter_list(py::m_get(snap, V("units"), V::list())).items()) count[py_str(py::m_get(u, V("side"), V("?")))]++;
                        std::string line;
                        for (auto& [k, n] : count) { line += k + "=" + std::to_string(n) + " "; st->peak[k] = std::max(st->peak[k], n); }
                        V players = py::m_get(snap, V("players"), V::dict());
                        for (auto& kv : players.kv()) line += py_str(kv.first) + ".resource=" + dump(py::m_get(kv.second, V("resource"), V::none())) + " hp=" + dump(py::m_get(kv.second, V("hp"), V::none())) + " ";
                        fprintf(stderr, "AI battle %ds units: %s\n", st->battle_frames / 60, line.c_str());
                    }
                    if (st->battle_frames >= seconds * 60) {
                        std::string peaks; for (auto& [k, n] : st->peak) peaks += k + "=" + std::to_string(n) + " ";
                        fprintf(stderr, "AI DONE %ds of battle, peak units %s\n", seconds, peaks.c_str());
                        fprintf(stderr, "PURE_TYPED_AUDIT %s\n", dump(callm(pvz::getattr(room, Sym("battle")), Sym("backend_audit"), Args{})).c_str());
                        st->result = 0;
                        pvz::setattr(app, Sym("running"), V(false));
                    }
                }
                if (phase == "result") { fprintf(stderr, "AI RESULT %s\n", dump(pvz::getattr(room, Sym("result"), V::none())).substr(0, 300).c_str()); { V bt = pvz::getattr(room, Sym("battle"), V::none()); if (!bt.is_none()) fprintf(stderr, "PURE_TYPED_AUDIT %s\n", dump(callm(bt, Sym("backend_audit"), Args{})).c_str()); } st->result = 0; pvz::setattr(app, Sym("running"), V(false)); }
                if (fr > 60 * (seconds + 240)) { fprintf(stderr, "AI TIMEOUT phase=%s\n", phase.c_str()); pvz::setattr(app, Sym("running"), V(false)); }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return st->result;
        }
        // app_run bpbench -> time the room's draft legality checks (ban / pick) over every card
        if (argc > 1 && std::string(argv[1]) == "bpbench") {
            V cb = V::func([](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                if (fr == 2) callm(app, Sym("create"), Args({}, {{Sym("local"), V(true)}}));
                if (fr == 4) callm(app, Sym("action"), Args{V::tuple({V("confirm_map")})});
                if (fr == 8) {
                    V room = pvz::getattr(app, Sym("room"));
                    fprintf(stderr, "BP phase=%s\n", py_str(pvz::getattr(room, Sym("phase"))).c_str());
                    V act = callm(room, Sym("_draft_action"), Args{});
                    fprintf(stderr, "BP action=%s\n", dump(act).c_str());
                    V side = py::m_get(act, V("side"));
                    Uint32 t0 = SDL_GetTicks();
                    int legal = 0, n = 0;
                    for (auto& kv : pm_catalog::CARDS.kv()) {
                        V err = callm(room, Sym("_ban_error"), Args{side, kv.first});
                        ++n; if (!err.truthy()) ++legal;
                        if (n == 5) fprintf(stderr, "BP first 5 ban checks: %u ms\n", SDL_GetTicks() - t0);
                    }
                    fprintf(stderr, "BP %d ban checks (%d legal): %u ms\n", n, legal, SDL_GetTicks() - t0);
                    t0 = SDL_GetTicks();
                    V err = callm(room, Sym("_ban_error"), Args{side, V::none()});
                    fprintf(stderr, "BP skip check: %u ms (%s)\n", SDL_GetTicks() - t0, py_str(err).c_str());
                    pvz::setattr(app, Sym("running"), V(false));
                }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return 0;
        }
        // app_run nettest -> ServerTransport + ClientTransport over 127.0.0.1 in one process (GIL threads)
        if (argc > 1 && std::string(argv[1]) == "nettest") {
            V server = pm_network::new_ServerTransport(Args({}, {{Sym("host"), V("127.0.0.1")}, {Sym("port"), V(0.0)}, {Sym("room_code"), V("abc")}}));
            V client;
            int port = 0, got_server = 0, got_client = 0;
            Uint32 start = SDL_GetTicks();
            auto pump = [&](const V& t, const char* who) {
                V evs = callm(t, Sym("poll"), Args{});
                for (auto& e : evs.items()) {
                    std::string type = py_str(py::m_get(e, V("type"), V("")));
                    fprintf(stderr, "[%5u] %s %s\n", SDL_GetTicks() - start, who, dump(e).substr(0, 200).c_str());
                    if (type == "listening") port = int(py::m_get(e, V("port")).num());
                    if (type == "message") (std::string(who) == "server" ? got_server : got_client)++;
                    if (type == "connected" && std::string(who) == "server")
                        callm(t, Sym("send"), Args{py::m_get(e, V("peer_id")), py_dict({{V("hello"), V("from server")}})});
                    if (type == "connected" && std::string(who) == "client")
                        callm(t, Sym("send"), Args{V("server"), py_dict({{V("hello"), V("from client")}})});
                }
            };
            while (SDL_GetTicks() - start < 8000 && !(got_server && got_client)) {
                pump(server, "server");
                if (port && !client.has())
                    client = pm_network::new_ClientTransport(Args({V("127.0.0.1"), V(double(port))}, {{Sym("room_code"), V("abc")}}));
                if (client.has()) pump(client, "client");
                { gil::Release g; SDL_Delay(16); }
            }
            fprintf(stderr, "NETTEST server_got=%d client_got=%d %s\n", got_server, got_client, (got_server && got_client) ? "PASS" : "FAIL");
            if (client.has()) callm(client, Sym("close"), Args{});
            callm(server, Sym("close"), Args{});
            { gil::Release g; SDL_Delay(200); }
            return (got_server && got_client) ? 0 : 1;
        }
        // app_run script <script.json> <outdir> -> generic scripted UI driver for investigations.
        //   {"timeout": frames, "steps": [{"wait": {"frames":N}|{"screen":s}|{"phase":p}|{"room_phase":p}|{"path":"a.b","equals":v},
        //                                  "do": [["action",...], ["state",{..}], ["shot",name], ["log",path...],
        //                                         ["set",path,value], ["call",path,args...], ["room_cmd",peer,{..}], ["stop"]]}]}
        if (argc > 3 && std::string(argv[1]) == "script") {
            V json = py::stdlib_module(V("json"));
            V script = callm(json, Sym("loads"), Args{callm(py::path_new(Args{V(std::string(argv[2]))}), Sym("read_text"), Args({}, {{Sym("encoding"), V("utf-8")}}))});
            std::string outdir = argv[3];
            CreateDirectoryA(outdir.c_str(), nullptr);
            struct St { size_t step = 0; int since = 0; int result = 1; };
            auto st = std::make_shared<St>();
            const int timeout = int(py::m_get(script, V("timeout"), V(60.0 * 600)).num());
            FILE* logf = fopen((outdir + "/log.txt").c_str(), "wb");
            auto say = [logf](const std::string& s) { fprintf(stderr, "%s\n", s.c_str()); if (logf) { fprintf(logf, "%s\n", s.c_str()); fflush(logf); } };
            auto resolve = [](V cur, const std::string& path) -> V {
                size_t p = 0;
                while (p <= path.size() && !path.empty()) {
                    size_t q = path.find('.', p); std::string part = path.substr(p, q == std::string::npos ? std::string::npos : q - p);
                    if (cur.is_dict()) cur = py::m_get(cur, V(part), V::none());
                    else if (cur.is_list() || cur.t == V::TUPLE) cur = cur.idx(std::atoi(part.c_str()));
                    else cur = pvz::getattr(cur, Sym(part), V::none());
                    if (q == std::string::npos) break; p = q + 1;
                }
                return cur;
            };
            V steps = py::m_get(script, V("steps"));
            V cb = V::func([=](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                V state = pvz::getattr(app, Sym("state"));
                auto root = [&](const std::string& path) -> V {
                    if (path.rfind("app", 0) == 0 && (path.size() == 3 || path[3] == '.')) return path.size() == 3 ? app : resolve(app, path.substr(4));
                    return resolve(app, path);
                };
                if (fr > timeout) { say("TIMEOUT at step " + std::to_string(st->step)); pvz::setattr(app, Sym("running"), V(false)); return V::none(); }
                st->since++;
                if (st->step >= size_t(py::len(steps).num())) return V::none();
                V step = steps.idx(int(st->step));
                V wait = py::m_get(step, V("wait"), V::dict());
                bool ready = true;
                if (wait.is_dict()) {
                    V f = py::m_get(wait, V("frames"), V::none()); if (!f.is_none() && st->since < int(f.num())) ready = false;
                    V s = py::m_get(wait, V("screen"), V::none()); if (!s.is_none() && py_str(py::m_get(state, V("screen"), V(""))) != py_str(s)) ready = false;
                    V ph = py::m_get(wait, V("phase"), V::none()); if (!ph.is_none() && py_str(py::m_get(pvz::getattr(app, Sym("view")), V("phase"), V(""))) != py_str(ph)) ready = false;
                    V rp = py::m_get(wait, V("room_phase"), V::none());
                    if (!rp.is_none()) { V room = pvz::getattr(app, Sym("room"), V::none()); if (room.is_none() || py_str(pvz::getattr(room, Sym("phase"), V(""))) != py_str(rp)) ready = false; }
                    V path = py::m_get(wait, V("path"), V::none());
                    if (!path.is_none() && ready) { V got = root(py_str(path)); V eq = py::m_get(wait, V("equals"), V::none()); if (!(dump(got) == dump(eq))) ready = false; }
                }
                if (!ready) return V::none();
                for (auto& cmd : py::iter_list(py::m_get(step, V("do"), V::list())).items()) {
                    std::string op = py_str(cmd.idx(0)); int n = int(py::len(cmd).num());
                    try {
                        if (op == "action") { std::vector<V> xs; for (int i = 1; i < n; ++i) xs.push_back(cmd.idx(i)); V r = callm(app, Sym("action"), Args{V::tuple(xs)}); say("frame " + std::to_string(fr) + " action " + dump(cmd).substr(0, 200) + " -> " + dump(r).substr(0, 200)); }
                        else if (op == "state") { callm(state, Sym("update"), Args{cmd.idx(1)}); }
                        else if (op == "shot") {
                            V pygame = py::stdlib_module(V("pygame"));
                            V screen = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{});
                            callm(pvz::getattr(pygame, Sym("image")), Sym("save"), Args{screen, V(outdir + "/" + py_str(cmd.idx(1)) + ".png")});
                            say("frame " + std::to_string(fr) + " shot " + py_str(cmd.idx(1)));
                        }
                        else if (op == "log") { for (int i = 1; i < n; ++i) { std::string p = py_str(cmd.idx(i)); say("frame " + std::to_string(fr) + " " + p + " = " + dump(root(p)).substr(0, 4000)); } }
                        else if (op == "set") {
                            std::string p = py_str(cmd.idx(1)); size_t dot = p.rfind('.');
                            V owner = dot == std::string::npos ? app : root(p.substr(0, dot)); std::string k = dot == std::string::npos ? p : p.substr(dot + 1);
                            if (owner.is_dict()) wr(owner, V(k)) = cmd.idx(2); else pvz::setattr(owner, Sym(k), cmd.idx(2));
                        }
                        else if (op == "call") {
                            std::string p = py_str(cmd.idx(1)); size_t dot = p.rfind('.');
                            V owner = dot == std::string::npos ? app : root(p.substr(0, dot)); std::string k = dot == std::string::npos ? p : p.substr(dot + 1);
                            std::vector<V> xs; for (int i = 2; i < n; ++i) { V x = cmd.idx(i);
                                if (x.t == V::STR && py_str(x) == "$screen") { V pygame = py::stdlib_module(V("pygame")); x = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{}); }
                                xs.push_back(x); }
                            V r = callm(owner, Sym(k), Args{xs}); say("frame " + std::to_string(fr) + " call " + p + " -> " + dump(r).substr(0, 2000));
                        }
                        else if (op == "room_cmd") { V room = pvz::getattr(app, Sym("room"), V::none()); V r = callm(room, Sym("command"), Args{cmd.idx(1), cmd.idx(2)}); say("frame " + std::to_string(fr) + " room_cmd -> " + dump(r).substr(0, 300)); }
                        else if (op == "find") {   // ["find", path, needle]: occurrences + context snippets of a big value
                            std::string text = dump(root(py_str(cmd.idx(1)))), needle = py_str(cmd.idx(2)); size_t pos = 0; int count = 0; std::string snips;
                            while ((pos = text.find(needle, pos)) != std::string::npos) { if (count < 3) snips += " <<" + text.substr(pos > 300 ? pos - 300 : 0, 700) + ">>"; ++count; pos += needle.size(); }
                            say("frame " + std::to_string(fr) + " find " + needle + " x" + std::to_string(count) + snips);
                        }
                        else if (op == "stop") { st->result = 0; pvz::setattr(app, Sym("running"), V(false)); say("STOP"); }
                    } catch (PyError& e) { say("frame " + std::to_string(fr) + " ERROR in " + dump(cmd).substr(0, 200) + ": " + e.what()); }
                }
                st->step++; st->since = 0;
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            if (logf) fclose(logf);
            return st->result;
        }
        // app_run probe -> after 180 frames print audio / mixer / window state, then quit
        if (argc > 1 && std::string(argv[1]) == "probe") {
            V cb = V::func([](const Args& a) {
                V app = a.pos.at(0);
                int fr = int(a.pos.at(1).num());
                if (fr == 60 || fr == 120) callm(app, Sym("action"), Args{V::tuple({V("fullscreen")})});
                if (fr == 100 || fr == 160) {
                    V pygame = py::stdlib_module(V("pygame"));
                    V surf = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{});
                    fprintf(stderr, "PROBE frame=%d fullscreen=%s surface=%s\n", fr, dump(py::m_get(pvz::getattr(app, Sym("state")), V("fullscreen"))).c_str(),
                            dump(callm(surf, Sym("get_size"), Args{})).c_str());
                }
                if (fr == 180) {
                    V ga = pvz::getattr(app, Sym("game_audio"), V::none());
                    V pygame = py::stdlib_module(V("pygame"));
                    fprintf(stderr, "PROBE mixer=%s\n", dump(callm(pvz::getattr(pygame, Sym("mixer")), Sym("get_init"), Args{})).c_str());
                    if (!ga.is_none()) {
                        fprintf(stderr, "PROBE sounds=%d music=%d track=%s missing=%s\n", int(py::len(pvz::getattr(ga, Sym("files"))).num()),
                                int(py::len(pvz::getattr(ga, Sym("music_files"))).num()), dump(pvz::getattr(ga, Sym("track"), V::none())).c_str(),
                                dump(pvz::getattr(ga, Sym("missing"))).c_str());
                        fprintf(stderr, "PROBE music_busy=%s\n", dump(callm(pvz::getattr(pvz::getattr(pygame, Sym("mixer")), Sym("music")), Sym("get_busy"), Args{})).c_str());
                    }
                    V st = pvz::getattr(app, Sym("state"));
                    for (const char* k : {"sound", "music_volume", "fullscreen", "window_size"})
                        fprintf(stderr, "PROBE state.%s=%s\n", k, dump(py::m_get(st, V(k), V::none())).c_str());
                    pvz::setattr(app, Sym("running"), V(false));
                }
                return V::none();
            });
            pm_app::f_run(Args({}, {{Sym("auto_test"), cb}}));
            return 0;
        }
        // app_run evidence <report.json> -> smoke with screenshots per stage + replay / fixed AI room checks
        if (argc > 2 && std::string(argv[1]) == "evidence") {
            V report = pm_app::f_run(Args({}, {{Sym("auto_test"), V(std::string(argv[2]))}}));
            printf("app.run returned: %s\n", py_str(report).substr(0, 600).c_str());
            return 0;
        }
        // app_run smoke  -> python's scripted smoke driver (home/config/draft/battle/result/rematch)
        V report = argc > 1 && std::string(argv[1]) == "smoke" ? pm_app::f_run(Args({}, {{Sym("auto_test"), V("smoke")}}))
                 : frames > 0 ? pm_app::f_run(Args({}, {{Sym("auto_test"), V(double(frames))}})) : pm_app::f_run(Args{});
        printf("app.run returned: %s\n", py_str(report).c_str());
        if (argc > 2) {   // app_run <frames> <screenshot.png>
            V pygame = py::stdlib_module(V("pygame"));
            V screen = callm(pvz::getattr(pygame, Sym("display")), Sym("get_surface"), Args{});
            callm(pvz::getattr(pygame, Sym("image")), Sym("save"), Args{screen, V(std::string(argv[2]))});
            printf("screenshot %s\n", argv[2]);
        }
    } catch (PyError& e) {
        fprintf(stderr, "PyError %s\n", e.what());
        return 2;
    }
    return 0;
}
