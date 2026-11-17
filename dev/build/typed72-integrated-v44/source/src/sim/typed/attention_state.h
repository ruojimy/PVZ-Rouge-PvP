#pragma once
#include <algorithm>
#include <map>
#include <string>
namespace pvz::typed72 {
// Opt-in per-unit targeting policy. Times use the simulation clock in seconds.
struct AttentionState {
    int hits=0;double seconds=0.;
    std::string last;int consecutive=0;
    std::map<std::string,double> marked;
    bool enabled()const{return hits>0&&seconds>0.;}
    bool contains(const std::string& id,double now)const{auto i=marked.find(id);return enabled()&&i!=marked.end()&&i->second>now;}
    void damage(const std::string& id,double amount,double now){
        if(!enabled()||id.empty()||amount<=0.)return;
        std::erase_if(marked,[&](const auto& p){return p.second<=now;});
        if(last!=id){last=id;consecutive=0;}++consecutive;
        if(consecutive>=hits){marked[id]=now+seconds;last.clear();consecutive=0;}
    }
};
}
