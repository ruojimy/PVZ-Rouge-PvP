// Step 3: card feature table for the planner network, exported from the typed ColdCatalog.
//   card_features <day|night> <out.jsonl>
// Line 1 is a header (catalog_hash, rules_hash, field lists). Then one "card" line per catalog
// row, in catalog order, holding ColdCatalog::actual(id, no secrets, night): the card as the
// battle resolves it for that daylight. "catalog_id" is the row's own id; for a derived form
// actual() reports the base card's id in "id" and the form in "resolved_id". Then "variant" lines: for every non-secret card and
// every single secret of its side, the fields that secret changes (ColdCatalog::actual with
// that one secret). Field lists come from the generated cold_card_fields.h, so a catalog field
// added later is exported without touching this file.
// Presentation-only fields (art, descriptions, native_* source values) are left out.
#include "common.h"
#include "sim/typed/cold_catalog.h"
#include <fstream>
#include <iostream>
#include <set>
namespace {
using ainn::J;
using pvz::typed72::ColdCard;
using pvz::typed72::Field;
J number(double v){if(std::isnan(v))return "nan";if(std::isinf(v))return v>0?"inf":"-inf";return v;}
template<class T> J optional(const Field<T>& f){
    if(!f.present()||f.is_null())return nullptr;
    if constexpr(std::is_same_v<T,double>)return number(f.get());else return f.get();
}
bool skipped(const std::string& name){
    static const std::set<std::string> text{"asset","description","native_input_name","native_source","content","content_art","native_description","native_name",
        "native_secret_name","projectile_asset"};
    return text.count(name)||name.rfind("native_",0)==0;
}
J row(const ColdCard& c){
    J r=J::object();
#define STR(n) if(!skipped(#n))r[#n]=c.n;
    PVZ72_COLD_REQUIRED_STRINGS(STR)
#undef STR
#define NUM(n) if(!skipped(#n))r[#n]=number(c.n);
    PVZ72_COLD_REQUIRED_NUMBERS(NUM)
#undef NUM
#define FLAG(n) if(!skipped(#n))r[#n]=c.n;
    PVZ72_COLD_REQUIRED_FLAGS(FLAG)
#undef FLAG
#define OPT(n) if(!skipped(#n))r[#n]=optional(c.n);
    PVZ72_COLD_OPTIONAL_STRINGS(OPT)
    PVZ72_COLD_OPTIONAL_NUMBERS(OPT)
    PVZ72_COLD_OPTIONAL_FLAGS(OPT)
#undef OPT
    // slow is a bool or a number in the source data.
    if(!c.slow.present()||c.slow.is_null())r["slow"]=nullptr;
    else if(const auto* b=std::get_if<bool>(&c.slow.get()))r["slow"]=*b;
    else r["slow"]=number(std::get<double>(c.slow.get()));
    r["targets"]=c.targets.present()&&!c.targets.is_null()?J(c.targets.get()):J(nullptr);
    return r;
}
}
int main(int argc,char** argv){
    try{
        if(argc!=3||(std::string(argv[1])!="day"&&std::string(argv[1])!="night"))throw std::invalid_argument("usage: card_features <day|night> <out.jsonl>");
        const bool night=std::string(argv[1])=="night";
        const pvz::typed72::ColdCatalog catalog;const auto& data=catalog.data();
        std::ofstream out(argv[2],std::ios::binary);if(!out)throw std::runtime_error(std::string("cannot write ")+argv[2]);
        std::vector<std::string> required_numbers,optional_numbers,flags,optional_flags,strings;
#define NUM(n) if(!skipped(#n))required_numbers.push_back(#n);
        PVZ72_COLD_REQUIRED_NUMBERS(NUM)
#undef NUM
#define NUM(n) if(!skipped(#n))optional_numbers.push_back(#n);
        PVZ72_COLD_OPTIONAL_NUMBERS(NUM)
#undef NUM
#define FLAG(n) if(!skipped(#n))flags.push_back(#n);
        PVZ72_COLD_REQUIRED_FLAGS(FLAG)
#undef FLAG
#define FLAG(n) if(!skipped(#n))optional_flags.push_back(#n);
        PVZ72_COLD_OPTIONAL_FLAGS(FLAG)
#undef FLAG
#define STR(n) if(!skipped(#n))strings.push_back(#n);
        PVZ72_COLD_REQUIRED_STRINGS(STR)
        PVZ72_COLD_OPTIONAL_STRINGS(STR)
#undef STR
        std::set<std::string> behaviors,categories;std::vector<std::string> plant_secrets,zombie_secrets;
        for(const auto& c:data.cards){
            behaviors.insert(c.behavior);categories.insert(c.category);
            if(c.category=="secret")(c.side=="plant"?plant_secrets:zombie_secrets).push_back(c.id);
        }
        J replacements=J::array();for(const auto& r:data.replacements)replacements.push_back({{"base",r.base},{"secret",r.secret},{"resolved",r.resolved}});
        out<<J{{"type","header"},{"format","pvz-ai-nn-card-features-1"},{"catalog_hash",data.catalog_hash},{"rules_hash",data.rules_hash},
            {"night",night},{"cards",data.cards.size()},{"source","ColdCatalog::actual(id, secrets, night)"},
            {"required_numbers",required_numbers},{"optional_numbers",optional_numbers},{"required_flags",flags},{"optional_flags",optional_flags},{"strings",strings},
            {"other_fields",{"slow","targets"}},{"behaviors",behaviors},{"categories",categories},{"replacements",replacements}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';
        std::vector<J> base;base.reserve(data.cards.size());
        for(const auto& c:data.cards){
            J r=row(catalog.actual(c.id,{},night));base.push_back(r);
            r["type"]="card";r["catalog_id"]=c.id;out<<r.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';
        }
        size_t variants=0;
        for(size_t i=0;i<data.cards.size();++i){
            const auto& c=data.cards[i];if(c.category=="secret")continue;
            for(const auto& secret:c.side=="plant"?plant_secrets:zombie_secrets){
                const std::vector<std::string> one{secret};
                const J with=row(catalog.actual(c.id,one,night));J changes=J::object();
                for(auto it=with.begin();it!=with.end();++it)if(base[i].at(it.key())!=it.value())changes[it.key()]=it.value();
                if(changes.empty())continue;
                out<<J{{"type","variant"},{"catalog_id",c.id},{"secret",secret},{"changes",changes}}.dump(-1,' ',false,J::error_handler_t::replace)<<'\n';++variants;
            }
        }
        std::cout<<J{{"night",night},{"cards",data.cards.size()},{"variants",variants},{"behaviors",behaviors.size()},{"catalog_hash",data.catalog_hash},{"rules_hash",data.rules_hash}}.dump()<<'\n';
        return out?0:3;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
