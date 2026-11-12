#include "cold_placement_rules.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz::typed72;using J=nlohmann::json;
namespace {
template<class T>void field(Field<T>& target,const J& source,const char* key){if(source.contains(key)){if(source[key].is_null())target.set_null();else target.set(source[key].get<T>());}}
J evaluate(const J& input){
    WorldTerrain map;map.empty_blocks=input.at("empty_blocks").get<std::vector<std::string>>();
    for(const auto& row:input.at("grid")){std::vector<TileRef> line;
        for(const auto& raw:row){auto tile=std::make_shared<TerrainCell>();field(tile->block,raw,"方块");field(tile->plant,raw,"植物");line.push_back(tile);}map.grid.push_back(line);
    }
    std::vector<ColdPlacementPlant> plants;
    for(const auto& p:input.value("plants",J::array()))plants.push_back({p.at("植物").get<std::string>(),{p.at("坐标")[0].get<int>(),p.at("坐标")[1].get<int64_t>()},p.contains("睡觉")&&!p["睡觉"].is_null()&&p["睡觉"].get<bool>(),p.value("basin",false),p.value("vine",false),p.value("air",false),p.contains("睡觉")});
    const auto secrets=input.value("secrets",std::vector<std::string>{});
    ColdPlacementRules rules(map,plants,secrets,input.value("source",std::string{}),input.value("spike_cost",100.));
    J values=J::array();
    for(const auto& query:input.at("queries")){
        const int row=query.at("row").get<int>();const auto col=query.at("col").get<int64_t>();const auto op=query.value("op",std::string("accepts"));
        try{
            J result;
            if(op=="accepts")result=rules.accepts(query.at("name").get<std::string>(),row,col);
            else if(op=="dense_error")result=rules.dense_error(query.at("name").get<std::string>(),row,col);
            else if(op=="shell")result=rules.shell_cell(row,col,query.value("vine",false));
            else if(op=="idle")result=rules.idle_cell(row,col);
            else if(op=="grass")result=rules.grass_cell(row,col);
            else if(op=="water")result=rules.water(row,col);
            else throw std::logic_error("Unknown query");
            values.push_back({{"ok",true},{"value",result}});
        }catch(const std::out_of_range&){values.push_back({{"ok",false},{"kind","IndexError"}});}
    }return values;
}
}
int main(int argc,char** argv){
    try{if(argc!=3)throw std::invalid_argument("usage: cold_placement_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;
        if(!input||!output)throw std::runtime_error("Input/output open failed");
        while(std::getline(input,line))if(!line.empty())output<<evaluate(J::parse(line)).dump()<<'\n';
        if(input.bad())throw std::runtime_error("Input read failed");output.close();if(!output)throw std::runtime_error("Output write failed");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
