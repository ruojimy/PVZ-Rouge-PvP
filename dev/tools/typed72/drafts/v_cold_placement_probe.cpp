// Exact retained V/hand NativePlacementRules, including its compiled raw query.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_placement.h"
#include "sim/pvp/gen/pm_native_runtime.h"
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
namespace {
V decode(const J& x){
    if(x.is_null())return V::none();if(x.is_boolean())return V(x.get<bool>());if(x.is_number())return V(x.get<double>());
    if(x.is_string())return V(x.get<std::string>());if(x.is_array()){V r=V::list();for(const auto& v:x)r.append(decode(v));return r;}
    V r=V::dict();for(const auto& p:x.items())setitem(r,V(p.key()),decode(p.value()));return r;
}
J evaluate(const J& input,const V& patch){
    J tiles=J::array();for(const auto& row:input.at("grid")){J line=J::array();for(const auto& cell:row)line.push_back({{"kind",cell.value("方块",std::string("空"))},{"native",cell}});tiles.push_back(line);}
    const V terrain=decode(J{{"tiles",tiles},{"source",input.value("source",std::string{})}});
    const V state=decode(J{{"version",1},{"plants",input.value("plants",J::array())},{"secrets",input.value("secrets",J::array())},
        {"empty_blocks",input.at("empty_blocks")},{"spike_cost",input.value("spike_cost",100.)}});
    const auto object=pm_native_placement::new_NativePlacementRules(Args{V::none(),terrain,state,patch});
    auto* rules=as<pm_native_placement::C_NativePlacementRules>(object);
    J values=J::array();
    for(const auto& query:input.at("queries")){
        const V row=decode(query.at("row")),col=decode(query.at("col"));const auto op=query.value("op",std::string("accepts"));
        try{
            V result;
            if(op=="accepts")result=rules->m_accepts(Args{decode(query.at("name")),row,col});
            else if(op=="dense_error")result=rules->m_dense_error(Args{decode(query.at("name")),row,col});
            else if(op=="shell")result=rules->m_shell_cell(Args{row,col,V(query.value("vine",false))});
            else if(op=="idle")result=rules->m_idle_cell(Args{row,col});
            else if(op=="grass")result=rules->m_grass_cell(Args{row,col});
            else if(op=="water")result=rules->m__water(Args{row,col});
            else throw std::invalid_argument("Unknown query");
            values.push_back({{"ok",true},{"value",result.is_str()?J(result.str()):J(result.truthy())}});
        }catch(const PyError& error){values.push_back({{"ok",false},{"kind",error.kind}});}
    }
    return values;
}
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("usage: v_cold_placement_probe inputs output");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);
        pg::install_pygame();init_pvp_modules();const V patch=pm_native_runtime::f_load_patch(Args{});
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;
        if(!input||!output)throw std::runtime_error("Input/output open failed");
        while(std::getline(input,line))if(!line.empty())output<<evaluate(J::parse(line),patch).dump()<<'\n';
        if(input.bad())throw std::runtime_error("Input read failed");output.close();if(!output)throw std::runtime_error("Output write failed");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
