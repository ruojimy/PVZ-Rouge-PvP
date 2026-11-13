// Bake late-added sprite variants with the game's own original monochrome function.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "sim/pvp/hand/original_namespace.h"
#include "sim/pvp/pvprt.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
namespace pvz {V fn_换黑白(Match&,const Args&);}
using namespace pvz;using J=nlohmann::json;
int main(int argc,char**argv){if(argc!=2)return 2;SDL_SetMainReady();gil::init();pg::install_pygame();V pg=py::stdlib_module(SV("pygame"));callm(getattr(pg,SY("display")),SY("set_mode"),Args{V::tuple({V(16),V(16)})});std::ifstream in("extract/assets/index.json");J index=J::parse(in);auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out/"_png");auto world=std::make_unique<Match>();world->pygame=pg;int i=0;for(const char* key:{"三向射手","三向射手根","三向射手头","水"}){auto e=index["图集"][key];const auto file=std::filesystem::path("extract/assets/_png")/u8p(e[0].get<std::string>());V raw=callm(callm(getattr(pg,SY("image")),SY("load"),Args{V(p8(file))}),SY("convert_alpha"),Args{});V gray=fn_换黑白(*world,Args{raw});std::string name="pvp73-gray-"+std::to_string(++i)+".png";callm(getattr(pg,SY("image")),SY("save"),Args{gray,V(p8(out/"_png"/name))});index["图集"][std::string(key)+"-黑白"]={name,e[1],e[2]};}std::ofstream(out/"index.json")<<index.dump(1,' ',false);return 0;}
