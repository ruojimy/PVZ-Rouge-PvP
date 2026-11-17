// Isolated pacing experiment. Production libraries and normal Application loop;
// only this executable forces a diagnostic scale before each authority update.
#include "pvp742_guest_memory_fixture.h"
#include "ui/gen/pm_performance_probe.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;

int main(int argc, char** argv) {
    if (argc != 3 || !std::getenv("PVP_USERDATA")) return 2;
    try {
        J config; std::ifstream(u8p(argv[1])) >> config;
        const auto output=u8p(argv[2]);
        std::filesystem::create_directories(output.parent_path());
        const bool fixed=config.contains("fixed_scale");
        const double scale=config.value("fixed_scale",1.);
        require(std::isfinite(scale)&&scale>=.10&&scale<=1.,"scale must be 0.10-1.0");
        config["output"]=p8(output);
        config["durable_units"]=true;config["unit_hp"]=1e8;
        config["world_quality"]="native";config["display_filter"]="pixel";
        config["display_budget"]=false;config["detail"]=false;
        require(config.value("units",120)>=1&&config.value("units",120)<=300,"unit bound");
        require(config.value("seconds",60.)>=1&&config.value("seconds",60.)<=600,"duration bound");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");
        py::g_real_clock=true;pg::install_pygame();init_pvp_modules();pm_app::init();pm_performance_probe::init();
        V driver;
        J applied=J::array();
        J counters_before;
        bool caption_set=false;
        V callback=V::func([&](const Args& args){
            if(args.pos.at(1).num()==0)return V::none();
            V app=args.pos.at(0);
            if(!driver.has())driver=pm_performance_probe::new_Driver(Args{py::json_loads(V(config.dump()))});
            driver.call(Args{app,args.pos.at(1)});
            if(getattr(driver,SY("finished")).truthy())return V::none();
            V room=getattr(app,SY("room")),battle=getattr(room,SY("battle"));
            if(!caption_set){callm(pg::display_module(),SY("set_caption"),Args{V(config.value("label",std::string("PvP pacing lab")))});caption_set=true;}
            if(counters_before.is_null()&&getattr(driver,SY("measuring")).truthy())
                counters_before=json(callm(battle,SY("backend_audit"),Args{}));
            // Avoid Room replacing the just-initialized diagnostic policy.
            setattr(room,SY("_paced_battle"),battle);
            V pacing=getattr(room,SY("pacing"));
            if(fixed)setattr(pacing,SY("scale"),V(scale));
            if(getattr(driver,SY("measuring")).truthy())applied.push_back({
                {"room_tick",getattr(battle,SY("tick")).num()},
                {"scale",getattr(pacing,SY("scale")).num()},
                {"target",py::m_get(getattr(app,SY("state")),SV("pressure_target"),V(1.)).num()},
                {"accumulator",getattr(room,SY("accumulator")).num()}});
            return V::none();
        });
        pm_app::f_run(Args({},{{SY("auto_test"),callback}}));
        require(driver.has()&&getattr(driver,SY("finished")).truthy(),"diagnostic stopped before completion");
        J report;std::ifstream(output)>>report;
        report["pacing_lab"]={{"fixed_scale",fixed?J(scale):J(nullptr)},
            {"applied",applied},{"counters_before",counters_before},{"scope","PC production-library Application experiment; headless render completion is not physical display FPS; no human responsiveness acceptance"}};
        std::ofstream(output)<<report.dump(2);
        std::cout<<J{{"completed",true},{"scale",fixed?J(scale):J(nullptr)},
            {"presentation_fps",report["presentation"]["frames_per_second"]},
            {"simulation_wall_ratio",report["simulation_wall_ratio"]}}.dump()<<std::endl;
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
