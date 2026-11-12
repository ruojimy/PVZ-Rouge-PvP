// JSON belongs only to this verification boundary, never to the catalog model.
#include "cold_catalog.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
using J=nlohmann::json;
namespace {
template<class T>void optional(J& out,const char* key,const Field<T>& field){
    if(field.present()){if(field.is_null())out[key]=nullptr;else out[key]=field.get();}
}
J encoded(const ColdCard& card){J result=J::object();
#define REQUIRED(n) result[#n]=card.n;
    PVZ72_COLD_REQUIRED_STRINGS(REQUIRED)
    PVZ72_COLD_REQUIRED_NUMBERS(REQUIRED)
    PVZ72_COLD_REQUIRED_FLAGS(REQUIRED)
#undef REQUIRED
#define OPTIONAL(n) optional(result,#n,card.n);
    PVZ72_COLD_OPTIONAL_STRINGS(OPTIONAL)
    PVZ72_COLD_OPTIONAL_NUMBERS(OPTIONAL)
    PVZ72_COLD_OPTIONAL_FLAGS(OPTIONAL)
#undef OPTIONAL
    optional(result,"targets",card.targets);optional(result,"native_secret_names",card.native_secret_names);
    if(card.slow.present()){if(card.slow.is_null())result["slow"]=nullptr;else std::visit([&](auto value){result["slow"]=value;},card.slow.get());}
    return result;
}
J evaluate(const ColdCatalog& catalog,const J& request){
    const auto key=request.at("key").get<std::string>();
    const auto secrets=request.value("secrets",std::vector<std::string>{}),bans=request.value("bans",std::vector<std::string>{});
    const auto night=request.value("night",false);const auto op=request.value("op",std::string("actual"));
    try {
        J value;
        if(op=="actual")value=encoded(catalog.actual(key,secrets,night));
        else if(op=="resolve")value=encoded(catalog.resolve(key,secrets,bans,night));
        else if(op=="allowed")value=catalog.allowed(key,bans,request.value("for_spawn",false),secrets);
        else if(op=="native_secrets")value=catalog.native_secrets(secrets,bans);
        else if(op=="player")value=encoded(catalog.player_card(key,secrets,bans,night,request.value("last_copy_card",std::string{})));
        else if(op=="unit")value=encoded(catalog.unit_card(key,secrets,bans,night,request.value("last_copy_card",std::string{})));
        else throw std::logic_error("Unknown operation");
        return {{"ok",true},{"value",value}};
    }catch(const std::invalid_argument& error){return {{"ok",false},{"error",std::string("ValueError: ")+error.what()}};}
    catch(const std::out_of_range& error){return {{"ok",false},{"error",std::string("KeyError: ")+error.what()}};}
}
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("usage: cold_catalog_probe inputs output");
        ColdCatalog catalog;std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("Input/output open failed");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<evaluate(catalog,J::parse(line)).dump()<<'\n';
        if(input.bad())throw std::runtime_error("Input read failed");output.close();if(!output)throw std::runtime_error("Output write failed");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
