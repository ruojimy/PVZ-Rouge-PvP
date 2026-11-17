// Explicit, bounded physical-device fixture. Uses production Application, Room,
// Driver and transport; owns only isolated PVP_USERDATA. Never used by launcher.
#include "pvp742_guest_memory_fixture.h"
#include "ui/gen/pm_performance_probe.h"
#include "ui/gen/pm_relay.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;
using Clock = std::chrono::steady_clock;

int main(int argc, char** argv) {
    if (argc != 3 || !std::getenv("PVP_USERDATA")) return 2;
    const std::filesystem::path out = u8p(argv[2]);
    std::filesystem::create_directories(out);
    J config; std::ifstream(u8p(argv[1])) >> config;
    const auto started = Clock::now();
    J events = J::array();
    int index = 0;
    V driver;
    bool connected = false, ready_written = false;
    try {
        require(config.at("scenes").is_array() && !config["scenes"].empty() && config["scenes"].size() <= 4, "1-4 scenes required");
        for (const auto& scene : config["scenes"]) {
            const auto name = scene.at("scenario").get<std::string>();
            require(name=="ordinary" || name=="mixed" || name=="barrage" || name=="grabber", "unsupported scene");
            require(scene.at("units").get<int>()>=1 && scene.at("units").get<int>()<=300, "unit bound");
            require(scene.at("seconds").get<double>()>=1 && scene.at("seconds").get<double>()<=90, "duration bound");
        }
        SDL_SetMainReady(); gil::init(); data::set_data_dir("extract/data");
        py::g_real_clock = true; pg::install_pygame(); init_pvp_modules();
        pm_app::init(); pm_performance_probe::init();
        V callback = V::func([&](const Args& args) {
            V app = args.pos.at(0), state = getattr(app,SY("state"));
            const int frame = int(args.pos.at(1).num());
            const double elapsed = std::chrono::duration<double>(Clock::now()-started).count();
            if (frame == 0) return V::none();
            if (frame == 1) {
                setitem(state,SV("network_mode"),V(config.value("mode","direct")));
                setitem(state,SV("port"),V(config.value("port",24617)));
                setitem(state,SV("room_public"),V(false));
                setitem(state,SV("room_name"),SV("private physical-device fixture"));
                setitem(state,SV("relay_endpoint"),V(config.value("endpoint","")));
                setitem(state,SV("allow_spectators"),V(false));
                callm(app,SY("create"),Args{V(false)});
            }
            V room=getattr(app,SY("room")), transport=getattr(app,SY("transport"));
            require(!room.is_none() && !transport.is_none(), "host creation failed");
            if (!ready_written) {
                V token=py::m_get(state,SV("token"));
                if (config.value("mode","direct")=="relay") token=getattr(transport,SY("code"));
                if (token.has() && !token.is_none() && !py_str(token).empty()) {
                    std::ofstream(out/"ready.json") << J{{"mode",config.value("mode","direct")},{"port",config.value("port",24617)},{"code",py_str(token)},{"private",true}}.dump(2);
                    ready_written=true;
                }
            }
            if (!connected && getattr(room,SY("members")).len() >= 2) {
                connected=true; events.push_back({{"event","physical_peer_joined"},{"elapsed",elapsed}});
            }
            if (!connected) {
                require(elapsed < 240, "physical peer did not join within 240 seconds");
                return V::none();
            }
            if (!driver.has()) {
                if (index >= int(config["scenes"].size())) {setattr(app,SY("running"),V(false));return V::none();}
                J scene=config["scenes"][index];
                require(scene["units"].get<int>()>=1 && scene["units"].get<int>()<=300,"unit bound");
                require(scene["seconds"].get<double>()>=1 && scene["seconds"].get<double>()<=90,"duration bound");
                scene["output"]=p8(out/("scene-"+std::to_string(index)+".json"));
                scene["warmup_seconds"]=5;scene["interactive_input"]=true;
                scene["durable_units"]=true;scene["unit_hp"]=1e8;
                scene["world_quality"]="native";scene["display_filter"]="pixel";
                scene["display_budget"]=true;scene["detail"]=false;
                scene["prime_tentacles"]=scene["scenario"]=="grabber";
                V old_create=getattr(app,SY("create"));
                // Driver normally creates a local room. Keep the already joined
                // real network room and replace only its diagnostic battle.
                setattr(app,SY("create"),V::func([](const Args&){return V::none();}));
                driver=pm_performance_probe::new_Driver(Args{py::json_loads(V(scene.dump()))});
                try { callm(driver,SY("setup"),Args{app}); }
                catch (...) { setattr(app,SY("create"),old_create);throw; }
                setattr(app,SY("create"),old_create);
                V fixture=getattr(driver,SY("fixture"));
                setitem(fixture,SV("network"),V(config.value("mode","direct")));
                setitem(fixture,SV("harness_scope"),SV("isolated fixture executable linked to production libraries; phone is released APK"));
                setitem(fixture,SV("scene_index"),V(index));
                // Driver's primed-tentacle note assumes local neutral inputs.
                // This fixture deliberately keeps the physical guest's input.
                setitem(fixture,SV("input"),SV("Live physical guest input and heartbeats; not deterministic A/B. Tentacle growth may be primed before timing."));
                callm(app,SY("invalidate_snapshots"),Args{});
                events.push_back({{"event","scene_started"},{"index",index},{"elapsed",elapsed},{"scenario",scene["scenario"]}});
            }
            driver.call(Args{app,args.pos.at(1)});
            if (getattr(driver,SY("finished")).truthy()) {
                events.push_back({{"event","scene_completed"},{"index",index},{"elapsed",elapsed}});
                ++index;driver=V();setattr(app,SY("running"),V(index<int(config["scenes"].size())));
            }
            std::ofstream(out/"events.json") << events.dump(2);
            return V::none();
        });
        pm_app::f_run(Args({},{{SY("auto_test"),callback}}));
        std::ofstream(out/"completion.json") << J{{"completed",index==int(config["scenes"].size())},{"scenes_completed",index},{"events",events}}.dump(2);
        return index==int(config["scenes"].size())?0:1;
    } catch (const std::exception& error) {
        std::ofstream(out/"failure.json") << J{{"error",error.what()},{"scenes_completed",index},{"events",events}}.dump(2);
        std::cerr << error.what() << '\n'; return 1;
    }
}
