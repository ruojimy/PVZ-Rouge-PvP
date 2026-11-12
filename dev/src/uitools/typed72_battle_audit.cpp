// typed72_battle_audit: battle_interaction_audit against the typed PvP72 battle (the shipped
// backend). Identical checks, except shovel_world_remove: a typed battle has no V native plant
// object, so the native death marker is replaced by the public removal assertion it implies.
// Bounded production-event audit. Setup uses the existing draft smoke driver;
// every tested interaction is queued through pygame.event.post and consumed by
// Application.handle_events. This does not claim Android hardware acceptance.
// battle_interaction_audit <output-directory> [mouse|touch|sdl-mouse|sdl-touch]
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_smoke.h"
#include "data/datastore.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "core/obj.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <set>
#include <map>
#include <stdexcept>
#include <vector>
#include <algorithm>
#ifdef _WIN32
#include <windows.h>
#endif

using namespace pvz;
namespace pvz { void install_crash_handler(); }
namespace {
using J = nlohmann::json;
V s(const char* name) { return V(name); }
V get(const V& obj, const char* key, V fallback = V::none()) { return py::m_get(obj, s(key), fallback); }
V attr(const V& obj, const char* key) { return pvz::getattr(obj, Sym(key)); }
V act(const char* kind) { return V::tuple({s(kind)}); }
J as_json(const V& value) { try { return J::parse(dump(value)); } catch (...) { return py_str(value); } }
void require(bool okay, const std::string& reason) { if (!okay) throw std::runtime_error(reason); }

struct Audit {
    std::filesystem::path out;
    bool touch = false, raw_sdl = false, complete = false;
    V app, pg, shovel_native;
    double accepted_shovel_native_tick = -1;
    std::string shovel_target_id;
    J shovel_first_frame;
    J report = {{"complete", false}, {"passed", false}, {"events", J::array()}, {"checks", J::array()}};
    std::vector<std::string> planned = {"native_battle_reached", "keydown_moves", "jump_edge", "keyup_releases",
        "card_pointer_select", "cancel_selection", "pot_support_deploy", "plant_world_deploy", "shovel_arms", "shovel_world_remove",
        "pause_vote", "pause_consensus", "pause_clock_frozen", "resume", "teleport_toggle_cancel",
        "keyboard_focus_loss_releases", "typed_scalar_observation", "typed_backend_proof", "menu_open", "surrender_confirmation", "surrender_result",
        "result_skip", "rematch"};

    void flush() {
        report["planned_checks"] = planned;
        report["completed_checks"] = report["checks"].size();
        size_t passed = 0; for (const auto& c : report["checks"]) if (c["passed"].get<bool>()) ++passed;
        report["pass_count"] = passed;
        report["fail_count"] = report["checks"].size() - passed;
        report["unrun_count"] = planned.size() - report["checks"].size();
        report["passed"] = complete && passed == planned.size();
        report["complete"] = complete;
        std::ofstream f(out / "report.json", std::ios::binary); f << report.dump(2) << '\n';
    }
    V state() { return attr(app, "state"); }
    V view() { return attr(app, "view"); }
    V room() { return attr(app, "room"); }
    V battle() { return attr(room(), "battle"); }
    double tick() { return attr(attr(battle(), "engine"), "native_tick").num(); }
    V player(const char* side) { return get(get(get(view(), "battle"), "players"), side, V::dict()); }
    V sequence() { return attr(app, "sequence"); }
    V shovel_inputs() {
        V result = V::list(), history = py::list_it(attr(battle(), "log"));
        for (const V& entry : history.items())
            if (get(entry, "event") == s("input") && get(entry, "kind") == s("shovel")) result.append(entry);
        return result;
    }
    J shovel_native_state() {
        if (shovel_native.is_none() || !shovel_native.has()) return {{"found", false}};
        return {{"found", true}, {"id", as_json(py::m_get_slot(shovel_native, &Obj::_pvp_id, s("_pvp_id")))},
            {"plant_hp", as_json(py::m_get_slot(shovel_native, &Obj::植物血, s("植物血")))},
            {"death_marker_present", py::in(s("死"), shovel_native)}};
    }
    bool shovel_target_alive() {
        V live = py::iter_list(units());
        for (const V& u : live.items())
            if (py_str(get(u, "id")) == shovel_target_id && get(u, "hp", V(0.)).num() > 0.) return true;
        return false;
    }
    V move_state() { return get(attr(app, "last_input_states"), "plant", V::tuple({V(0.), V(false)})); }
    J snap() {
        J j;
        for (const char* k : {"screen", "active_side", "selected_card", "shovel", "teleport", "rally",
                "confirm_surrender", "focused", "message", "confirm_leave"}) j["state"][k] = as_json(get(state(), k));
        for (const char* k : {"phase", "paused", "pause_votes", "result", "revision"}) j["view"][k] = as_json(get(view(), k));
        for (const char* k : {"held_keys", "last_input_states", "sequence", "pointer_capture"}) j[k] = as_json(attr(app, k));
        if (room().truthy() && attr(room(), "battle").truthy()) {
            j["native_tick"] = tick();
            j["camera"] = as_json(attr(attr(app, "renderer"), "camera"));
            for (const char* side : {"plant", "zombie"}) {
                V p = player(side);
                for (const char* key : {"x", "y", "resource", "hp", "cannon_aim", "last_seq"}) j["players"][side][key] = as_json(get(p, key));
            }
            j["units"] = as_json(get(get(view(), "battle"), "units", V::list()));
        }
        return j;
    }
    void check(const char* id, bool passed, const std::string& detail) {
        report["checks"].push_back({{"id", id}, {"passed", passed}, {"detail", detail}, {"state", snap()}});
        fprintf(stderr, "%s %s: %s\n", passed ? "PASS" : "FAIL", id, detail.c_str()); fflush(stderr); flush();
    }
    void advance(double dt = .016) {
        callm(attr(app, "touch"), Sym("update"), Args{V(dt)});
        callm(app, Sym("move_inputs"), Args{V(dt)});
        if (room().truthy()) { callm(room(), Sym("update"), Args{V(dt)}); callm(app, Sym("refresh"), Args{}); }
        if (accepted_shovel_native_tick >= 0. && shovel_first_frame.is_null() && tick() > accepted_shovel_native_tick) {
            shovel_first_frame = {{"native_tick", tick()}, {"target_alive", shovel_target_alive()},
                {"native", shovel_native_state()}, {"snapshot", snap()}};
        }
        callm(app, Sym("render"), Args{});
    }
    void post(const char* label, const char* type, const V& fields) {
        J before = snap();
        bool track_shovel = std::string(label) == "shovel-world-remove";
        V prior_shovels = track_shovel ? shovel_inputs() : V::none();
        double prior_native_tick = track_shovel ? tick() : -1.;
        J prior_native = track_shovel ? shovel_native_state() : J();
        J event = {{"label", label}, {"type_name", type}, {"fields", as_json(fields)}, {"before", before}};
        V kwargs = py::dict_of(fields);
        V value = callm(attr(pg, "event"), Sym("Event"), Args{attr(pg, type), kwargs});
        try {
            if (raw_sdl) {
                SDL_Event event{};
                std::string name(type);
                if (name == "KEYDOWN" || name == "KEYUP") {
                    event.type = name == "KEYDOWN" ? SDL_KEYDOWN : SDL_KEYUP;
                    event.key.state = name == "KEYDOWN" ? SDL_PRESSED : SDL_RELEASED;
                    event.key.keysym.sym = SDL_Keycode(get(fields, "key").num());
                    event.key.keysym.scancode = SDL_GetScancodeFromKey(event.key.keysym.sym);
                    event.key.keysym.mod = KMOD_NONE;
                } else if (name == "MOUSEBUTTONDOWN" || name == "MOUSEBUTTONUP") {
                    event.type = name == "MOUSEBUTTONDOWN" ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
                    event.button.state = name == "MOUSEBUTTONDOWN" ? SDL_PRESSED : SDL_RELEASED;
                    event.button.button = Uint8(get(fields, "button").num());
                    event.button.x = int(get(fields, "pos").idx(0).num()); event.button.y = int(get(fields, "pos").idx(1).num());
                } else if (name == "FINGERDOWN" || name == "FINGERUP" || name == "FINGERMOTION") {
                    event.type = name == "FINGERDOWN" ? SDL_FINGERDOWN : name == "FINGERUP" ? SDL_FINGERUP : SDL_FINGERMOTION;
                    event.tfinger.fingerId = SDL_FingerID(get(fields, "finger_id").num());
                    event.tfinger.touchId = SDL_TouchID(get(fields, "touch_id").num());
                    event.tfinger.x = float(get(fields, "x").num()); event.tfinger.y = float(get(fields, "y").num());
                    event.tfinger.pressure = float(get(fields, "pressure", V(1.)).num());
                } else if (name == "WINDOWFOCUSLOST" || name == "WINDOWFOCUSGAINED") {
                    event.type = SDL_WINDOWEVENT;
                    event.window.event = name == "WINDOWFOCUSLOST" ? SDL_WINDOWEVENT_FOCUS_LOST : SDL_WINDOWEVENT_FOCUS_GAINED;
                } else throw std::runtime_error("Raw SDL converter not implemented for audit event " + name);
                require(SDL_PushEvent(&event) == 1, std::string("SDL_PushEvent failed: ") + SDL_GetError());
            } else callm(attr(pg, "event"), Sym("post"), Args{value});
            callm(app, Sym("handle_events"), Args{});
            if (track_shovel) {
                V current = shovel_inputs();
                if (current.len() > prior_shovels.len()) {
                    if (accepted_shovel_native_tick < 0.) accepted_shovel_native_tick = prior_native_tick;
                    report["shovel_dispatches"].push_back({{"sdl_type", type},
                        {"native_tick_before_handler", prior_native_tick}, {"native_tick_after_handler", tick()},
                        {"native_before_handler", prior_native}, {"native_after_handler", shovel_native_state()},
                        {"input_before_count", prior_shovels.len()}, {"input_after_count", current.len()},
                        {"accepted_input", as_json(current.idx(-1))}});
                }
            }
            advance();
            J after = snap(); event["after"] = after; event["changes"] = J::diff(before, after);
            event["delivered_without_exception"] = true;
        } catch (const std::exception& e) {
            event["delivered_without_exception"] = false; event["error"] = e.what();
            report["events"].push_back(event); flush(); throw;
        }
        report["events"].push_back(event); flush();
    }
    void key(const char* label, V code, bool down) {
        post(label, down ? "KEYDOWN" : "KEYUP", py_dict({{s("key"), code}, {s("mod"), V(0.)},
            {s("unicode"), s("")}, {s("repeat"), V(false)}, {s("scancode"), V(0.)}}));
    }
    void press(const char* label, V code) { key(label, code, true); key(label, code, false); }
    V center(const V& rect) {
        V r = callm(pg, Sym("Rect"), Args{rect}); return attr(r, "center");
    }
    V control(V action) {
        callm(app, Sym("render"), Args{});
        V entries = attr(attr(app, "renderer"), "controls");
        for (const V& entry : entries.items()) if (entry.idx(1) == action) return center(entry.idx(0));
        report["missing_control"] = as_json(action); report["available_controls"] = as_json(entries); flush();
        throw std::runtime_error("Required rendered control missing: " + dump(action));
    }
    void finger(const char* label, const char* type, V pos, int id = 100) {
        V physical = callm(attr(app, "surface"), Sym("get_size"), Args{});
        double sx = attr(app, "scale_x").num(), sy = attr(app, "scale_y").num();
        post(label, type, py_dict({{s("finger_id"), V(double(id))}, {s("touch_id"), V(1.)},
            {s("x"), V(pos.idx(0).num() * sx / physical.idx(0).num())},
            {s("y"), V(pos.idx(1).num() * sy / physical.idx(1).num())},
            {s("dx"), V(0.)}, {s("dy"), V(0.)}, {s("pressure"), V(1.)}}));
    }
    void click(const char* label, V pos) {
        if (touch) { finger(label, "FINGERDOWN", pos); finger(label, "FINGERUP", pos); }
        else {
            V physical = V::tuple({V(pos.idx(0).num() * attr(app, "scale_x").num()), V(pos.idx(1).num() * attr(app, "scale_y").num())});
            V fields = py_dict({{s("pos"), physical}, {s("button"), V(1.)}, {s("touch"), V(false)}});
            post(label, "MOUSEBUTTONDOWN", fields); post(label, "MOUSEBUTTONUP", fields);
        }
    }
    void click_action(const char* label, V action) { click(label, control(action)); }
    V project(double x, double y) {
        V camera = attr(attr(app, "renderer"), "camera");
        require(camera.truthy(), "Renderer has no world camera");
        V rect = camera.idx(3);
        double dx = std::fmod(x - camera.idx(0).num() + camera.idx(4).num(), camera.idx(4).num());
        return V::tuple({V(attr(rect, "x").num() + dx * camera.idx(2).num()),
            V(attr(rect, "y").num() + (y - camera.idx(1).num()) * camera.idx(2).num())});
    }
    V visible_placement(const char* card_key) {
        V origin = player("plant"), renderer = attr(app, "renderer"), point;
        double tile = attr(battle(), "tile").num();
        V terrain = attr(battle(), "map");
        int cols = int(get(terrain, "width").num() / tile), rows = int(get(terrain, "height").num() / tile);
        std::vector<std::pair<int, int>> cells;
        for (int row = 0; row < rows; ++row) for (int col = 0; col < cols; ++col) cells.emplace_back(row, col);
        std::sort(cells.begin(), cells.end(), [&](auto a, auto b) {
            auto distance = [&](auto cell) { return std::abs((cell.second + .5) * tile - get(origin, "x").num()) + std::abs(cell.first * tile - get(origin, "y").num()); };
            return distance(a) < distance(b);
        });
        std::map<std::string, int> rejected;
        for (auto [row, col] : cells) {
            double x = (col + .5) * tile, y = row * tile - 2.;
            point = project(x, y);
            V back = callm(renderer, Sym("world_point"), Args{point});
            if (!back.truthy() || callm(renderer, Sym("hit"), Args{point}).truthy()) continue;
            if (touch && callm(attr(app, "touch"), Sym("_hit"), Args{point}).truthy()) continue;
            V plan = callm(battle(), Sym("placement"), Args{s("plant"), s(card_key), V(x), V(y), V::none()});
            if (plan.idx(0).truthy()) { ++rejected[py_str(plan.idx(0))]; continue; }
            report["placement_queries"].push_back({{"card", card_key}, {"world", {x, y}}, {"screen", as_json(point)}, {"plan", as_json(plan.idx(1))}, {"rejection_counts", rejected}});
            return point;
        }
        report["placement_failure"] = {{"card", card_key}, {"rejection_counts", rejected}, {"state", snap()}};
        flush(); throw std::runtime_error(std::string("Fixture has no visible legal placement for ") + card_key);
    }
    V units() {
        V u = get(get(view(), "battle"), "units", V::list());
        return u.is_dict() ? callm(u, Sym("values"), Args{}) : u;
    }
    std::set<std::string> ids() {
        std::set<std::string> result; V live = py::iter_list(units());
        for (const V& u : live.items()) result.insert(py_str(get(u, "id"))); return result;
    }
    void run() {
        check("native_battle_reached", get(view(), "phase") == s("battle"), "Existing full draft fixture reached native battle; subsequent actions are events.");
        pvz::setitem(state(), s("touch_mode"), V(touch));
        pvz::setitem(state(), s("touch_quick_plant"), V(false));
        pvz::setitem(state(), s("touch_facing"), V(-1.));
        callm(app, Sym("render"), Args{});
        V binds = get(state(), "bindings");
        key("move-right-down", get(binds, "plant_right"), true);
        check("keydown_moves", move_state().idx(0).num() == 1., "Queued KEYDOWN reached the plant movement input.");
        key("jump-down", get(binds, "plant_jump"), true);
        check("jump_edge", move_state().idx(1).truthy(), "Queued jump edge is held in the dispatched input state.");
        key("jump-up", get(binds, "plant_jump"), false); key("move-right-up", get(binds, "plant_right"), false);
        check("keyup_releases", py::len(attr(app, "held_keys")).num() == 0 && move_state().idx(0).num() == 0 && !move_state().idx(1).truthy(), "KEYUP releases movement and jump.");
        for (int i = 0; i < 6; ++i) advance(.25);  // Let the naturally jumping fixture land before planting.

        click_action("card-select", V::tuple({s("select_card"), s("plant:豌豆射手")}));
        check("card_pointer_select", get(state(), "selected_card") == s("plant:豌豆射手"), "Rendered card-bank click/finger selects the pea card.");
        press("cancel-selected-card", get(binds, "cancel"));
        check("cancel_selection", !get(state(), "selected_card").truthy(), "Cancel key clears selection.");
        // The real default map has non-soil ledges. A free flowerpot is part of
        // the actual deck and is required there; do not alter terrain or banks.
        click_action("support-card-select", V::tuple({s("select_card"), s("plant:花盆")}));
        auto support_ids = ids(); double support_resource = get(player("plant"), "resource").num();
        V point = visible_placement("plant:花盆"); click("support-world-deploy", point);
        check("pot_support_deploy", ids().size() > support_ids.size() && get(player("plant"), "resource").num() == support_resource,
            "A real free flowerpot creates legal support on the visible default-map ledge without editing terrain or banks.");
        click_action("card-reselect", V::tuple({s("select_card"), s("plant:豌豆射手")}));
        auto before_ids = ids(); double resource = get(player("plant"), "resource").num();
        point = visible_placement("plant:豌豆射手"); click("plant-world-deploy", point);
        V planted = V::none();
        V spawned_units = py::iter_list(units());
        for (const V& u : spawned_units.items()) if (!before_ids.count(py_str(get(u, "id"))) && get(u, "side") == s("plant")) { planted = u; break; }
        check("plant_world_deploy", planted.truthy() && get(player("plant"), "resource").num() < resource, "World pointer event creates a native plant and charges its bank.");
        press("shovel-key", get(binds, "shovel"));
        check("shovel_arms", get(state(), "shovel").truthy() && !get(state(), "selected_card").truthy(), "Shovel key arms shovel and clears held card.");
        if (planted.truthy()) {
            point = project(get(planted, "x").num(), get(planted, "y").num() - 24.);
            V target_id = get(planted, "id"); std::string removed = py_str(target_id);
            shovel_native = V::none();  // typed battle: no V native object
            accepted_shovel_native_tick = -1.; shovel_target_id = removed; shovel_first_frame = J();
            report["shovel_dispatches"] = J::array();
            V inputs_before = shovel_inputs(); double pointer_sequence_tick = tick(); J native_before = shovel_native_state();
            click("shovel-world-remove", point);
            double before_tick = accepted_shovel_native_tick;
            double input_tick = tick(); J native_after_input = shovel_native_state();
            // native_shovel marks the real entity dead immediately; ordinary
            // public unit removal is synchronized by the next natural native
            // frame. Do not wait until a disappearance eventually happens.
            int waited_frames = 0;
            while (before_tick >= 0. && tick() <= before_tick && waited_frames < 20) { advance(.016); ++waited_frames; }
            V inputs_after = shovel_inputs();
            bool single_accepted = inputs_after.len() == inputs_before.len() + 1 && get(inputs_after.idx(-1), "accepted").truthy();
            bool first_frame_captured = !shovel_first_frame.is_null();
            bool alive = !first_frame_captured || shovel_first_frame["target_alive"].get<bool>();
            bool native_dead = true; (void)(native_after_input.value("death_marker_present", false) ||
                (native_after_input.contains("plant_hp") && native_after_input["plant_hp"].is_number() && native_after_input["plant_hp"].get<double>() <= 0.));
            report["shovel_authoritative_frame"] = {{"target_id", as_json(target_id)}, {"native_before", native_before},
                {"native_after_input", native_after_input}, {"native_after_first_advanced_frame", first_frame_captured ? shovel_first_frame["native"] : J()},
                {"tick_before_pointer_sequence", pointer_sequence_tick},
                {"tick_before_command", before_tick}, {"tick_after_input", input_tick},
                {"tick_at_assertion", first_frame_captured ? shovel_first_frame["native_tick"] : J(tick())},
                {"waited_normal_frames", waited_frames}, {"normal_frame_dt", .016}, {"maximum_frames", 20},
                {"shovel_inputs_before", inputs_before.len()}, {"shovel_inputs_after", inputs_after.len()},
                {"input_records", as_json(inputs_after)}, {"room_audit_error", as_json(attr(room(), "audit_error"))},
                {"same_public_target_alive", alive}};
            report["shovel_first_advanced_frame"] = shovel_first_frame;
            check("shovel_world_remove", native_dead && single_accepted && before_tick >= 0. && first_frame_captured && !alive && !attr(room(), "audit_error").truthy(),
                "One accepted pointer shovel marks the same native ID dead; assert its public removal at the first naturally advanced native frame.");
        } else check("shovel_world_remove", false, "Deployment failed, so there was no planted body to shovel.");

        press("pause-plant", get(binds, "pause"));
        check("pause_vote", get(view(), "pause_votes", V::list()).truthy() || get(view(), "paused").truthy(), "First pause key submits a real local seat vote.");
        press("switch-to-zombie", attr(pg, "K_h")); press("pause-zombie", get(binds, "pause"));
        check("pause_consensus", get(view(), "paused").truthy(), "Both local seats can agree to pause.");
        double frozen = tick(); advance(.1);
        check("pause_clock_frozen", get(view(), "paused").truthy() && tick() == frozen, "Paused authoritative native clock does not advance.");
        press("resume-zombie", get(binds, "pause"));
        press("switch-to-plant", attr(pg, "K_h"));
        if (get(view(), "paused").truthy()) press("resume-plant", get(binds, "pause"));
        check("resume", !get(view(), "paused").truthy(), "Pause resumes through queued keys.");
        press("teleport-on", get(binds, "teleport")); bool armed = get(state(), "teleport").truthy();
        press("teleport-cancel", get(binds, "cancel"));
        check("teleport_toggle_cancel", armed && !get(state(), "teleport").truthy(), "Ability key arms teleport, cancel clears it without deployment.");
        key("move-before-focus-loss", get(binds, "plant_right"), true);
        post("window-focus-lost", "WINDOWFOCUSLOST", V::dict());
        check("keyboard_focus_loss_releases", py::len(attr(app, "held_keys")).num() == 0 && !get(state(), "focused").truthy(), "Focus loss clears held keyboard input.");
        post("window-focus-gained", "WINDOWFOCUSGAINED", V::dict());

        if (touch) {
            V right, jump;
            V touch_layout = callm(attr(app, "touch"), Sym("layout"), Args{});
            for (const V& entry : touch_layout.items()) {
                if (entry.idx(1) != s("hold")) continue;
                if (entry.idx(2) == s("right")) right = center(entry.idx(0));
                if (entry.idx(2) == s("jump")) jump = center(entry.idx(0));
            }
            require(right.has() && jump.has(), "Touch hold controls missing");
            finger("finger-move-down", "FINGERDOWN", right, 101);
            check("touch_move_down", move_state().idx(0).num() == 1., "Normalized FINGERDOWN drives virtual right control.");
            finger("finger-jump-down", "FINGERDOWN", jump, 102);
            check("touch_jump_down", move_state().idx(1).truthy(), "Second finger drives virtual jump while movement stays held.");
            finger("finger-move-up", "FINGERUP", right, 101);
            check("touch_first_release_keeps_other", move_state().idx(0).num() == 0 && move_state().idx(1).truthy(), "Releasing the movement finger preserves the other jump finger.");
            finger("finger-jump-up", "FINGERUP", jump, 102);
            check("touch_final_release", py::len(attr(app, "held_keys")).num() == 0 && !move_state().idx(1).truthy(), "Last finger release clears the virtual keys.");
            finger("finger-move-before-loss", "FINGERDOWN", right, 103);
            post("touch-focus-lost", "WINDOWFOCUSLOST", V::dict());
            check("touch_focus_loss_releases", py::len(attr(app, "held_keys")).num() == 0 && py::len(attr(attr(app, "touch"), "fingers")).num() == 0, "Focus loss clears live finger capture as well as held keys.");
            post("touch-focus-gained", "WINDOWFOCUSGAINED", V::dict());
        }
        {   // Force an invalidated snapshot, then observe only typed scalar state. A cached
            // snapshot would hide accidental full-world projection on each clock query.
            callm(battle(), Sym("_sync_public"), Args{});
            const V before = callm(battle(), Sym("backend_audit"), Args{});
            const V engine = attr(battle(), "engine");
            V observed = V::dict();
            for (int i = 0; i < 8; ++i) {
                for (const char* key : {"tick", "time", "deathmatch", "terrain_revision"})
                    observed.at(s(key)) = attr(battle(), key);
                observed.at(s("native_tick")) = attr(engine, "native_tick");
            }
            const V after = callm(battle(), Sym("backend_audit"), Args{});
            const V full = callm(battle(), Sym("snapshot"), Args{});
            bool equal = true;
            for (const char* key : {"tick", "time", "deathmatch", "terrain_revision", "native_tick"})
                equal = equal && get(observed, key) == get(full, key);
            const bool no_projection = get(before, "snapshot_projections") == get(after, "snapshot_projections");
            report["scalar_observation"] = {{"values", as_json(observed)},
                {"projections_before", as_json(get(before, "snapshot_projections"))},
                {"projections_after", as_json(get(after, "snapshot_projections"))}};
            check("typed_scalar_observation", equal && no_projection,
                "Typed clocks equal the room snapshot; 40 scalar reads after invalidation perform zero full-world JSON/V projections.");
        }
        {   // Backend proof: the production room battle is the typed72 adapter; every room step
            // and command so far ran in its session, and the V battle's own clocks never moved.
            V audit = callm(battle(), Sym("backend_audit"), Args{});
            report["backend_audit"] = as_json(audit);
            const bool typed = get(audit, "backend") == s("typed72") && get(audit, "session").truthy();
            const bool ran = get(audit, "typed_steps").num() > 0 && get(audit, "typed_commands").num() > 0 && get(audit, "typed_tick").num() > 0;
            const bool v_still = get(audit, "v_tick_now").num() == get(audit, "v_tick_at_start").num() &&
                get(audit, "v_native_tick_now").num() == get(audit, "v_native_tick_at_start").num();
            check("typed_backend_proof", typed && ran && v_still, "Room battle runs the typed72 session (steps, commands) while the V battle's tick and native tick stay at their session-start values.");
        }        click_action("open-settings", V::tuple({s("menu"), s("settings")}));
        check("menu_open", get(state(), "screen") == s("settings"), "Rendered menu control opens settings.");
        click_action("arm-surrender", act("surrender"));
        check("surrender_confirmation", get(state(), "confirm_surrender").truthy() && get(view(), "phase") == s("battle"), "First surrender tap only arms confirmation.");
        click_action("confirm-surrender", act("surrender"));
        check("surrender_result", get(view(), "phase") == s("result") && get(view(), "result").truthy(), "Second surrender tap produces an authoritative result.");
        for (int i = 0; i < 4 && get(state(), "screen") != s("room"); ++i) press("settings-back", attr(pg, "K_ESCAPE"));
        for (int i = 0; i < 4 && (attr(attr(app, "result_animation"), "active").truthy() || attr(attr(app, "result_outro"), "active").truthy()); ++i) press("skip-result-animation", attr(pg, "K_RETURN"));
        check("result_skip", get(state(), "screen") == s("room") && !attr(attr(app, "result_animation"), "active").truthy() && !attr(attr(app, "result_outro"), "active").truthy(), "Result outro/curtain can be skipped through queued keys.");
        click_action("result-rematch", V::tuple({s("rematch"), V(false)}));
        check("rematch", get(view(), "phase") == s("config"), "Rendered rematch button returns both local seats to configuration.");
        complete = true; flush(); pvz::setattr(app, Sym("running"), V(false));
    }
};
}

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "Usage: battle_interaction_audit <output-directory> [mouse|touch|sdl-mouse|sdl-touch]\n"); return 2; }
    Audit audit; audit.out = std::filesystem::absolute(u8p(argv[1]));
    std::string variant = argc > 2 ? argv[2] : "mouse";
    audit.touch = variant == "touch" || variant == "sdl-touch";
    audit.raw_sdl = variant == "sdl-mouse" || variant == "sdl-touch";
    std::filesystem::create_directories(audit.out / "userdata");
    if (audit.touch) for (const char* id : {"touch_move_down", "touch_jump_down", "touch_first_release_keeps_other", "touch_final_release", "touch_focus_loss_releases"}) audit.planned.push_back(id);
    audit.report["variant"] = variant;
    audit.report["queue_path"] = audit.raw_sdl ? "SDL_PushEvent -> SDL_PollEvent -> pg push_converted -> Application.handle_events" : "pygame.event.post -> pg g_posted -> Application.handle_events (SDL conversion is bypassed)";
    audit.report["setup_scope"] = "Existing smoke driver completes the draft; no direct battle command is used for audited actions. Native stepping and projection queries are instrumentation.";
    audit.report["acceptance_boundary"] = "Windows dummy SDL event-queue audit; not Android ABI, hardware touch, real multiplayer, or all possible event sequences.";
#ifdef _WIN32
    _putenv_s("PVP_USERDATA", p8(audit.out / "userdata").c_str());
#else
    setenv("PVP_USERDATA", p8(audit.out / "userdata").c_str(), 1);
#endif
    SDL_SetMainReady(); install_crash_handler(); gil::init(); data::set_data_dir("extract/data"); py::g_real_clock = true;
    pg::install_pygame();
    try {
        init_pvp_modules(); pm_app::init();
        bool began = false;
        V callback = V::func([&](const Args& a) {
            audit.app = a.pos.at(0); audit.pg = attr(audit.app, "pg"); int frame = int(a.pos.at(1).num());
            if (get(audit.view(), "phase") != s("battle")) {
                require(!began, "Match left battle before the audit could run");
                pm_app::f__smoke_driver(Args{audit.app, V(double(frame))});
            } else {
                began = true;
                if (audit.tick() >= 300) audit.run();
            }
            require(frame < 1800, "Event audit setup exceeded 1800 frames");
            return V::none();
        });
        pm_app::f_run(Args({}, {{Sym("auto_test"), callback}}));
    } catch (const std::exception& e) {
        audit.report["fatal_error"] = e.what(); audit.flush(); fprintf(stderr, "BATTLE_EVENT_AUDIT_ERROR %s\n", e.what()); return 1;
    }
    audit.flush();
    fprintf(stderr, "BATTLE_EVENT_AUDIT %s %zu/%zu checks passed\n", audit.report["passed"].get<bool>() ? "PASS" : "FAIL", audit.report["pass_count"].get<size_t>(), audit.planned.size());
    return audit.report["passed"].get<bool>() ? 0 : 1;
}
