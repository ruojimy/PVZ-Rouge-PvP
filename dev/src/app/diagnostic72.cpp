#include "app/diagnostic72.h"
#include "pg/pg.h"
#include "pg/render_stats.h"
#include "core/fsutil.h"
#include "core/alloc.h"
#include "data/datastore.h"
#include "ui/gen/pm_performance_probe.h"
#include "ui/gen/pm_performance_window.h"
#include "sim/pvp/gen/pm_catalog.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace pvz {
namespace {
void diagnostic_env(const char* name,const char* value){
    if(SDL_setenv(name,value,1)!=0)throw std::runtime_error("Cannot set diagnostic SDL environment");
#ifdef _WIN32
    // SDL's DLL CRT can own a different environ table from this executable.
    // Engine switches use std::getenv, so update and verify our CRT as well.
    if(_putenv_s(name,value)!=0)throw std::runtime_error("Cannot set diagnostic CRT environment");
#else
    if(::setenv(name,value,1)!=0)throw std::runtime_error("Cannot set diagnostic environment");
#endif
    const char* effective=std::getenv(name);
    if(!effective||std::strcmp(effective,value)!=0)throw std::runtime_error("Diagnostic environment was not applied");
}
V value72(const nlohmann::json& j) {
    if(j.is_null())return V::none();if(j.is_boolean())return V(j.get<bool>());
    if(j.is_number())return V(j.get<double>());if(j.is_string())return V(j.get<std::string>());
    if(j.is_array()){V out=V::list();for(const auto& v:j)out.append(value72(v));return out;}
    V out=V::dict();for(const auto& item:j.items())out.at(V(item.key()))=value72(item.value());return out;
}
}
int run_diagnostic72(const std::string& raw) {
    using json=nlohmann::json;namespace fs=std::filesystem;
    if(raw.size()>32768)throw std::runtime_error("Diagnostic config too large");
    json config=json::parse(raw);
    if(!config.is_object())throw std::runtime_error("Diagnostic config must be an object");
    // Explicit per-process diagnostic controls, shared by PC and Android.
    if(config.value("function_profile",false))diagnostic_env("PVP741_PROFILE","1");
    if(config.contains("engine_options"))for(const auto& [name,value]:config["engine_options"].items()){
        if(name!="PVP742_FRAME"&&name!="PVP742_RECIPE_KEY"&&name!="PVP742_WALL_CLOCK"&&name!="PVP742_LAZY_CANVAS"&&name!="PVP742_INPUT_REFRESH"&&name!="PVP742_TARGETING")throw std::runtime_error("Unknown diagnostic engine option");
        if(!value.is_boolean())throw std::runtime_error("Diagnostic engine option must be boolean");
        diagnostic_env(name.c_str(),value.get<bool>()?"1":"0");
    }
    auto scenario=config.value("scenario",std::string("ordinary"));
    if(scenario!="ordinary" && scenario!="mixed" && scenario!="barrage" && scenario!="grabber")throw std::runtime_error("Unknown diagnostic scene");
    int units=config.value("units",20);double warm=config.value("warmup_seconds",5.),seconds=config.value("seconds",30.);
    if(units<1 || units>300 || !std::isfinite(warm) || !std::isfinite(seconds) || warm<0 || warm>60 || seconds<1 || seconds>600)
        throw std::runtime_error("Diagnostic bounds invalid");
    fs::path folder=fs::current_path()/"reports";
#ifdef __ANDROID__
    auto external=SDL_AndroidGetExternalStoragePath();if(!external)throw std::runtime_error("Report storage unavailable");
    folder=u8p(external)/"reports";
#endif
    fs::create_directories(folder);
    auto stamp=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    auto output=folder/("PVP72-"+std::to_string(stamp)+".json");
    config["output"]=p8(output);config["export_download"]=false;config["scenario"]=scenario;config["units"]=units;
    config["warmup_seconds"]=warm;config["seconds"]=seconds;
    pg::reset_render_stats72();
    pm_performance_probe::f_run(Args{value72(config)});
    std::ifstream input(output,std::ios::binary);if(!input)throw std::runtime_error("Diagnostic did not create a report");
    json report=json::parse(input);input.close();
    if(!report.value("completed",false))throw std::runtime_error("Diagnostic did not complete");
    auto counters=pg::render_stats72();
    const auto allocator=native_small_allocator_stats();
    const char* stats_enabled=std::getenv("PVZ72_RENDER_STATS");
    report["native72"]={{"build",data::get("__init__","BUILD")},{"rules_hash",pm_catalog::f_rules_hash(Args{}).str()},
        {"catalog_hash",pm_catalog::f_catalog_hash(Args{}).str()},{"report_path",p8(output)},
        {"render_stats_enabled",stats_enabled && *stats_enabled=='1'},
        {"surface_allocations",counters.surface_allocations},{"allocated_bytes",counters.allocated_bytes},
        {"blits",counters.blits},{"blit_pixels",counters.blit_pixels},{"direct_scales",counters.direct_scales},
        {"avoided_copy_bytes",counters.avoided_copy_bytes},
        {"small_allocator",{{"slab_bytes",allocator.slab_bytes},{"slab_count",allocator.slab_count},
            {"cross_thread_frees",allocator.cross_thread_frees},{"central_reused_blocks",allocator.central_reused_blocks},
            {"central_blocks",allocator.central_blocks},{"thread_cache_flushes",allocator.thread_cache_flushes},{"legacy",allocator.legacy}}},
        {"memory",json::parse(dump(pm_performance_window::f_process_memory(Args{})))}};
    std::ofstream result(output,std::ios::binary|std::ios::trunc);result<<report.dump(2);result.close();
    if(result.fail())throw std::runtime_error("Cannot finish diagnostic report");
    SDL_Log("PVP72_DIAGNOSTIC_COMPLETE %s",p8(output).c_str());
    printf("PVP72_DIAGNOSTIC_COMPLETE %s\n",p8(output).c_str());return 0;
}
}
