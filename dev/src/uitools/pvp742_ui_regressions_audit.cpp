// Exercise the production card compositor and result screen with isolated data.
#include "ui/hand/texture74_internal.h"
#include "ui/hand/seat_view.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_rendering.h"
#include "ui/gen/pm_native_style.h"
#include "sim/pvp/gen/pm_teams.h"
#include "sim/pvp/battle_api.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "data/datastore.h"
#include <fstream>
#include <iostream>
#include <set>
#include <algorithm>

using namespace pvz;
namespace tx = pvz::texture74;
using J = nlohmann::json;
static void require(bool ok, const std::string& message) { if (!ok) throw std::runtime_error(message); }
static V value(const J& j) { return py::json_loads(V(j.dump())); }

struct CaptureRenderer : pm_rendering::C_Renderer {
    std::vector<std::string> lines;
    V m_text(const Args& a) override {
        const auto text = py_str(a.get(0, SY("text"), nullptr));
        if (lines.empty() || lines.back() != text) lines.push_back(text);
        return C_Renderer::m_text(a);
    }
};

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    const auto out = std::filesystem::absolute(u8p(argv[1]));
    std::filesystem::create_directories(out);
    env_set_u8("PVP_USERDATA", p8(out / "userdata"));
    SDL_SetMainReady(); gil::init(); data::set_data_dir("extract/data");
    pg::install_pygame(); init_pvp_modules();
    V pg = pg::pygame_module();
    V screen = callm(pg::display_module(), SY("set_mode"), Args{V::tuple({V(1280), V(720)})});
    auto battle = battle_from_scenario({{"seed", 742}});
    V app = pm_app::new_Application(Args{pg, screen, battle.bridge});
    auto capture = std::make_shared<CaptureRenderer>();
    pm_rendering::initcv_Renderer(capture.get());
    V renderer = V::inst(capture);
    capture->m___init__(Args{pg, screen, battle.bridge});
    J checks = J::array(); int failures = 0;
    auto test = [&](const std::string& name, auto run) {
        J row = {{"name", name}};
        try { row["evidence"] = run(); row["passed"] = true; }
        catch (const std::exception& e) { row["passed"] = false; row["error"] = e.what(); ++failures; }
        checks.push_back(row); std::cerr << row.dump() << '\n';
    };
    test("rage_uses_world_stump_and_blue_flame", [&]() -> J {
        V actual = callm(renderer, SY("artwork"), Args{SV("石化火炬-蓝火")});
        require(!actual.is_none(), "rage artwork fell back to a solid placeholder");
        V expected = pg::new_surface(128, 128, true);
        V art = pm_native_style::new_NativeArt(Args{pg, battle.bridge, getattr(renderer, SY("asset_dir"))});
        callm(art, SY("grave"), Args({expected, SV("石化火炬-蓝火"), V(64), V(120), V(80)}, {{SY("blue"), V(true)}}));
        const auto pixels = tx::pixels(actual);
        require(pixels == tx::pixels(expected), "card composition differs from the production grave renderer");
        std::set<uint32_t> colors; size_t opaque = 0, transparent = 0;
        for (const auto p : pixels) if ((p & 255) != 0) { ++opaque; colors.insert(p); } else ++transparent;
        require(opaque > 100 && transparent > 100 && colors.size() > 10, "rage art is an empty / solid block");
        V red = callm(renderer, SY("artwork"), Args{SV("石化火炬")});
        require(tx::pixels(red) != pixels, "rage did not replace the red flame");
        callm(pg::image_module(), SY("save"), Args{actual, V(p8(out / "rage-artwork.png"))});
        return {{"colors", colors.size()}, {"visible_pixels", opaque}, {"transparent_pixels", transparent}, {"matches_world_compositor", true}};
    });
    test("rage_workshop_original_matches_card_icon", [&]() -> J {
        tx::load_inventory();
        const auto* resource = tx::resource("icon:石化火炬-蓝火");
        require(resource, "rage icon missing from workshop catalog");
        require(std::find(resource->cards.begin(), resource->cards.end(), "zsecret:暴怒") != resource->cards.end(), "rage card is not linked to its editable icon");
        V icon = pg::new_surface(128, 128, true);
        setattr(renderer, SY("screen"), icon);
        callm(renderer, SY("icon"), Args{SV("石化火炬-蓝火"), V::tuple({V(0), V(0), V(128), V(128)})});
        require(tx::pixels(icon) == tx::pixels(tx::original(*resource)), "workshop still contains the stale baked fallback (run pvp74_texture_audit bake)");
        setattr(renderer, SY("screen"), screen);
        callm(pg::image_module(), SY("save"), Args{icon, V(p8(out / "rage-card-icon.png"))});
        return {{"resource", resource->key}, {"file", resource->file}, {"matches_live_card_icon", true}};
    });

    const J authority = {{"players", {
        {"plant", {{"hp", 31}, {"stats", {{"earned", 111}, {"spent", 25}, {"coins", 12}}}}},
        {"plant2", {{"hp", 17}, {"stats", {{"earned", 777}, {"spent", 350}, {"coins", 28}}}}},
        {"zombie", {{"hp", 43}, {"stats", {{"earned", 999}}}}},
        {"zombie2", {{"hp", 29}, {"stats", {{"earned", 888}}}}}
    }}};
    for (const char* seat : {"plant", "plant2", "zombie", "zombie2"}) {
        test(std::string("authority_seat_lookup_") + seat, [&]() -> J {
            const V source = value(authority);
            const V projected = pm_teams::f_local_perspective(Args{source, V(seat)});
            const auto untouched = dump(projected);
            for (const char* id : {"plant", "plant2", "zombie", "zombie2"})
                require(J::parse(dump(seat_view::player_for_authority_seat(projected, V(id)))) == authority["players"][id], std::string("wrong statistics for ") + id);
            require(dump(projected) == untouched && J::parse(dump(source)) == authority, "lookup changed battle / replay state");
            return {{"local_seat", seat}, {"authority_ids_preserved", true}, {"snapshot_unchanged", true}};
        });
    }
    for (const char* seat : {"plant", "plant2"}) {
        test(std::string("coop_result_names_and_stats_") + seat, [&]() -> J {
            J view = {{"mode", "coop"}, {"seats", {"plant", "plant2"}}, {"members", {{"host", "plant"}, {"guest", "plant2"}}},
                {"player_profiles", {{"host", {{"name", "HOST_111"}}}, {"guest", {{"name", "GUEST_777"}}}}},
                {"result", {{"winner", "plant"}, {"pve_day", 9}, {"coins", 40}}}};
            view["battle"] = J::parse(dump(pm_teams::f_local_perspective(Args{value(authority), V(seat)})));
            const V snapshot = value(view); const auto before = dump(snapshot);
            setattr(app, SY("mode"), SV("guest")); // Avoid loading a campaign; the result rows are shared.
            setattr(renderer, SY("screen"), screen); capture->lines.clear();
            callm(app, SY("draw_pve_result"), Args{renderer, snapshot});
            const auto& lines = capture->lines;
            for (const auto& expected : std::vector<std::vector<std::string>>{
                {"HOST_111", "阳光收入 111 · 消费 25", "拾币 6 · 剩余生命 31"},
                {"GUEST_777", "阳光收入 777 · 消费 350", "拾币 14 · 剩余生命 17"}}) {
                const auto found = std::find(lines.begin(), lines.end(), expected[0]);
                require(found != lines.end() && std::distance(found, lines.end()) >= 3, "result player row absent");
                require(found[1] == expected[1] && found[2] == expected[2], "result name / income / coins / HP belong to different seats");
            }
            require(dump(snapshot) == before, "result rendering mutated the snapshot");
            callm(pg::image_module(), SY("save"), Args{screen, V(p8(out / (std::string("coop-result-") + seat + ".png")))});
            return {{"rows", lines}, {"seat_name_stats_matched", true}, {"snapshot_unchanged", true}};
        });
    }
    std::ofstream(out / "summary.json") << J{{"passed", failures == 0}, {"failures", failures}, {"checks", checks}}.dump(2);
    callm(app, SY("close"), Args{});
    return failures ? 1 : 0;
}
