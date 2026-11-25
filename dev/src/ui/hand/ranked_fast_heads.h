#pragma once

#include "sim/pvp/pvprt.h"
#include "core/resource_paths.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <limits>
#include <nlohmann/json.hpp>
#include <optional>

namespace pvz::ranked_fast_heads {
using Json=nlohmann::json;
constexpr size_t hidden=96;

struct Dense {
    std::vector<std::vector<float>> weights;
    std::vector<float> bias;
    Dense(const Json& source,size_t inputs,size_t outputs)
        :weights(source.at("weights").get<decltype(weights)>()),bias(source.at("bias").get<decltype(bias)>()){
        if(weights.size()!=outputs||bias.size()!=outputs||
           std::any_of(weights.begin(),weights.end(),[&](const auto& row){return row.size()!=inputs;}))
            throw std::invalid_argument("incompatible ranked draft layer");
    }
    float row(size_t index,const float* values)const{
        float result=bias[index];
        for(size_t i=0;i<weights[index].size();++i)result+=weights[index][i]*values[i];
        return result;
    }
};

inline float gelu(float x){return .5f*x*(1.f+std::erf(x*.7071067811865475f));}

struct Head {
    std::vector<std::array<float,hidden>> cards;
    std::vector<double> prior;
    std::vector<bool> coverage;
    Dense context,score,output;
    Head(const Json& source,size_t count):cards(source.at("cards").get<decltype(cards)>()),
        prior(source.at("prior").get<decltype(prior)>()),coverage(source.at("coverage").get<decltype(coverage)>()),
        context(source.at("context"),4*hidden+11,hidden),score(source.at("score"),2*hidden,hidden),
        output(source.at("output"),hidden,1){
        if(cards.size()!=count+1||prior.size()!=count||coverage.size()!=count)
            throw std::invalid_argument("incompatible ranked draft vocabulary");
    }
};

struct Bundle {
    std::string build;
    std::vector<std::string> keys,sides;
    Head plant,zombie;
    explicit Bundle(const Json& source):build(source.at("build").get<std::string>()),keys(source.at("keys").get<decltype(keys)>()),
        sides(source.at("sides").get<decltype(sides)>()),plant(source.at("plant"),keys.size()),
        zombie(source.at("zombie"),keys.size()){
        if(source.at("format")!="pvz-ranked-fast-draft-1"||keys.empty()||sides.size()!=keys.size()||
            !std::is_sorted(keys.begin(),keys.end()))
            throw std::invalid_argument("incompatible ranked draft bundle");
    }
    size_t id(const std::string& key)const{
        const auto found=std::lower_bound(keys.begin(),keys.end(),key);
        if(found==keys.end()||*found!=key)throw std::invalid_argument("unknown ranked card");
        return size_t(found-keys.begin());
    }
};

inline const std::optional<Bundle>& configured(){
    static const auto loaded=[]()->std::optional<Bundle>{
        const char* path=std::getenv("PVZ_RANKED_FAST_HEADS");
        const auto source=path&&*path?std::filesystem::u8path(path):
            native_workspace()/"extract"/"data"/"pvp"/"ai"/"ranked-fast-heads.json";
        std::ifstream file(source,std::ios::binary);
        if(!file)return {};
        try{return Bundle(Json::parse(file));}catch(const std::exception&){return {};}
    }();
    return loaded;
}

inline std::optional<V> rank(const Bundle& model,const std::string& side,const std::string& stage,bool ban,
                             const V& mine,const V& enemy,const V& bans,std::vector<size_t> offers,bool pass){
    const auto& head=side=="plant"?model.plant:model.zombie;
    const auto none=model.keys.size();
    if(offers.empty())return pass?std::optional<V>(V::none()):std::nullopt;
    std::stable_sort(offers.begin(),offers.end(),[&](size_t a,size_t b){return head.prior[a]>head.prior[b];});
    auto candidates=offers;
    if(candidates.size()>24)candidates.resize(24);
    std::sort(offers.begin(),offers.end());
    for(const auto i:offers)
        if(head.coverage[i]&&std::find(candidates.begin(),candidates.end(),i)==candidates.end())candidates.push_back(i);
    if(pass)candidates.push_back(none);

    std::array<float,4*hidden+11> input{};
    const auto add=[&](size_t group,size_t id){
        for(size_t i=0;i<hidden;++i)input[group*hidden+i]+=head.cards[id][i];
    };
    for(size_t group=0;group<3;++group){
        const auto& list=group==0?mine:group==1?enemy:bans;
        for(const auto& key:list.items()){
            if(!key.truthy())continue;
            const auto name=py_str(key);
            const auto it=std::lower_bound(model.keys.begin(),model.keys.end(),name);
            if(it==model.keys.end()||*it!=name)continue; // Test-only and workshop cards have no trained embedding.
            const size_t id=size_t(it-model.keys.begin());
            add(group==2&&model.sides[id]!=side?3:group,id);
        }
    }
    const std::array<float,11> flags{float(stage=="opening_ban"),float(stage=="opening_pick"),float(stage=="second_ban"),
        float(stage=="final_pick"),float(!ban),float(ban),float(side=="plant"),float(side=="zombie"),
        float(mine.len())/7.f,float(enemy.len())/7.f,float(bans.len())/16.f};
    std::copy(flags.begin(),flags.end(),input.begin()+4*hidden);
    std::array<float,2*hidden> pair;
    for(size_t i=0;i<hidden;++i)pair[i]=gelu(head.context.row(i,input.data()));
    std::array<float,hidden> features;
    auto best=candidates.front();
    float best_value=-std::numeric_limits<float>::infinity();
    for(const auto id:candidates){
        std::copy(head.cards[id].begin(),head.cards[id].end(),pair.begin()+hidden);
        for(size_t i=0;i<hidden;++i)features[i]=gelu(head.score.row(i,pair.data()));
        const float score=head.output.row(0,features.data());
        if(score>best_value){best=id;best_value=score;}
    }
    return best==none?V::none():V(model.keys[best]);
}

inline std::optional<V> choose(const V& room,const V& action){
    const auto& model=configured();
    if(!model)return {};
    const auto rules=getattr(room,Sym("rules"));
    const auto mode=py_str(getattr(room,Sym("mode")));
    if((mode!="duel"&&mode!="duo")||py_str(rd(rules,V("build")))!=model->build)return {};
    const auto side=rd(action,V("side"));
    const auto actor=py::m_get(action,V("seat"),side);
    const auto foe=side==V("plant")?V("zombie"):V("plant");
    auto decks=getattr(room,Sym("decks")), bans=getattr(room,Sym("bans"));
    if(mode=="duo"){
        auto scoped=callm(room,Sym("advisor_view"),Args{actor});
        decks=rd(scoped,V("decks"));
    }
    const bool ban=rd(action,V("kind"))==V("ban");
    const auto category=py_str(rd(action,V("category")));
    const auto target=py_str(py::m_get(action,V("target"),V(category)));
    const auto check=Sym(ban?"_ban_error":"_pick_error");
    std::vector<size_t> offers;
    for(size_t i=0;i<model->keys.size();++i){
        const auto& key=model->keys[i];
        if(model->sides[i]!=target||(ban&&((category=="secret")!=(key.starts_with("secret:")||key.starts_with("zsecret:")))))continue;
        if(!callm(room,check,Args{side,V(key),actor}).truthy())offers.push_back(i);
    }
    const bool pass=ban&&!callm(room,check,Args{side,V::none(),actor}).truthy();
    return rank(*model,py_str(side),py_str(rd(action,V("stage"))),ban,rd(decks,side),rd(decks,foe),bans,std::move(offers),pass);
}

// Candidate rows are supplied by the active mode after dependency, terrain, slot and opening-resource checks.
inline V recommendation(const V& side,const V& mine,const V& enemy,const V& public_bans,const V& rows,const V& preferred){
    const auto& model=configured();
    if(!model)return V::none();
    std::vector<size_t> offers,preferred_offers;
    for(const auto& row:rows.items()){
        const auto key=row.idx(1);const auto name=py_str(key);
        const auto it=std::lower_bound(model->keys.begin(),model->keys.end(),name);
        if(it==model->keys.end()||*it!=name)continue;
        const auto i=size_t(it-model->keys.begin());offers.push_back(i);
        if(preferred.truthy()&&py::in(key,preferred))preferred_offers.push_back(i);
    }
    if(!preferred_offers.empty())offers=std::move(preferred_offers);
    std::sort(offers.begin(),offers.end());
    const auto card=rank(*model,py_str(side),mine.len()<3?"opening_pick":"final_pick",false,
                         mine,enemy,public_bans,std::move(offers),false);
    if(card)for(const auto& row:rows.items())if(row.idx(1)==*card)return row;
    return V::none();
}
}
