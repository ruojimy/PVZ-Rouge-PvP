// Direct existing V-library JSON/digest entry. No local digest reimplementation.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include <fstream>
#include <iostream>
using namespace pvz;
using J=nlohmann::ordered_json;
namespace {
V decode(const J& value){
    if(value.is_null())return V::none();if(value.is_boolean())return V(value.get<bool>());if(value.is_number())return V(value.get<double>());if(value.is_string())return V(value.get<std::string>());
    if(value.is_array()){V out=V::list();for(const auto& child:value)out.append(decode(child));return out;}
    V out=V::dict();for(const auto& [key,child]:value.items())setitem(out,V(key),decode(child));return out;
}
}
int main(int argc,char** argv){try{
    if(argc!=3)throw std::invalid_argument("usage: replay_v_digest_probe input output");
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);pg::install_pygame();init_pvp_modules();
    std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;
    while(std::getline(input,line))if(!line.empty()){
        const auto document=J::parse(line);J result=J::array();
        for(const auto& item:document.at("payloads")){
            const V value=decode(item);const auto encoded=py::stdlib_call(SV("json.dumps"),Args({value},{{SY("sort_keys"),V(true)},{SY("ensure_ascii"),V(false)},{SY("separators"),V::tuple({SV(","),SV(":")})},{SY("allow_nan"),V(false)}}));
            result.push_back({{"canonical",encoded.str()},{"sha256",pm_catalog::f_digest(Args{value}).str()}});
        }
        output<<result.dump()<<'\n';
    }
    return input.bad()||!output?2:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
