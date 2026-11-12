// taco_icon_audit <output-directory>: production cold-cache pixels and timing.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_ui_pvp67_assets.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <chrono>
#include <cstdio>
#include <fstream>

using namespace pvz;
int main(int argc,char**argv) {
    if(argc!=2)return 2;
    try {
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");
        pg::install_pygame();init_pvp_modules();pm_ui_pvp67_assets::init();
        V pygame=py::stdlib_module(SV("pygame"));callm(pygame,SY("init"),Args{});
        callm(getattr(pygame,SY("display")),SY("set_mode"),Args{V::tuple({V(1),V(1)})});
        auto folder=u8p(argv[1]);std::filesystem::create_directories(folder);
        auto start=std::chrono::steady_clock::now();
        V icon=pm_ui_pvp67_assets::f_taco(Args{pygame});
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        V image=getattr(pygame,SY("image")),size=callm(icon,SY("get_size"),Args{});
        V rgba=callm(image,SY("tobytes"),Args{icon,SV("RGBA")});
        std::string raw=py::bytes_data(rgba);
        std::string hash=callm(py::stdlib_call(SV("hashlib.sha256"),Args{rgba}),SY("hexdigest"),Args{}).str();
        callm(image,SY("save"),Args{icon,V(p8(folder/"taco-native.png"))});
        std::ofstream pixels(folder/"taco-native.rgba",std::ios::binary);pixels.write(raw.data(),raw.size());pixels.close();
        nlohmann::json report={{"width",int(size.idx(0).num())},{"height",int(size.idx(1).num())},
            {"rgba_bytes",raw.size()},{"rgba_sha256",hash},{"cold_seconds",seconds},
            {"function","pm_ui_pvp67_assets::f_taco"}};
        std::ofstream output(folder/"taco-native.json",std::ios::binary);output<<report.dump(2);output.close();
        printf("%s\n",report.dump().c_str());return pixels.fail() || output.fail()?1:0;
    }catch(const std::exception& e){fprintf(stderr,"FAIL %s\n",e.what());return 1;}
}
