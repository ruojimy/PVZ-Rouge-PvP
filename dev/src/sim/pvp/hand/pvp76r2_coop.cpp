#include "sim/pvp/hand/pvp76r2_coop.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_pve.h"
#include <algorithm>
#include <cmath>
#include <set>
namespace pvz::pvp76r2 {
namespace {
struct Entry {const char* key;std::vector<const char*> precursors;};
// Order is part of the deterministic schedule; append only.
const std::vector<Entry>& table(){
    static const std::vector<Entry> t{
        {"zsecret:专注啃咬",{"zombie:普通僵尸"}},
        {"zsecret:二手",{"zombie:路障僵尸","zombie:铁桶僵尸","zombie:钢门普通僵尸","zombie:铁桶钢门僵尸","zombie:梯子僵尸","zombie:传送带僵尸"}},
        {"zsecret:僵王出品",{"zombie:路障僵尸","zombie:铁桶僵尸","zombie:钢门普通僵尸","zombie:铁桶钢门僵尸","zombie:梯子僵尸","zombie:传送带僵尸","zombie:报纸僵尸"}},
        {"zsecret:大运！小子",{"zombie:雪橇车僵尸","zombie:滚桶僵尸","zombie:投篮车僵尸","zombie:小鬼炮"}},
        {"zsecret:阿姆斯特朗",{"zombie:报纸僵尸"}},
        {"zsecret:立棍！小子",{"zombie:撑杆跳僵尸","zombie:黑撑杆僵尸"}},
        {"zsecret:散弹攻击",{"zombie:机枪僵尸"}},
        {"zsecret:坤坤",{"zombie:投篮车僵尸"}},
        {"zsecret:狂野舞步",{"zombie:舞王僵尸"}},
        {"zsecret:三五成群",{"zombie:普通僵尸","zombie:鸭子普通僵尸","zombie:黑普通僵尸"}},
        {"zsecret:不可撼动",{"zombie:巨人僵尸","zombie:红眼巨人","zombie:角斗士巨人"}},
        {"zsecret:体育生",{"zombie:撑杆跳僵尸","zombie:橄榄球僵尸","zombie:黑撑杆僵尸","zombie:黑橄榄僵尸"}},
        {"zsecret:斩首行动",{"zombie:雪人僵尸"}},
        {"zsecret:沉默",{"zombie:黑路障僵尸","zombie:黑铁桶僵尸"}},
        {"zsecret:暴怒",{"zombie:石化火炬"}},
        {"zsecret:船锚",{"zombie:钩索僵尸"}},
        {"zsecret:手雷",{"zombie:掷弹兵僵尸"}},
        {"zsecret:空输",{"zombie:飞贼僵尸"}},
        {"zsecret:黏糊糊",{"zombie:史莱姆僵尸"}},
        {"zsecret:萝卜伞",{"zombie:萝卜伞僵尸"}},
        {"zsecret:守卫",{"zombie:盾卫僵尸"}},
    };
    return t;
}
const Entry* find(const std::string& key){for(const auto& e:table())if(key==e.key)return &e;return nullptr;}
bool card_exists(const std::string& key){
    pm_catalog::init();
    const V card=py::m_get(pm_catalog::CARDS,V(key),V::none());
    return card.is_dict()&&py::m_get(card,V("selectable"),V(true)).truthy();
}
std::set<std::string> pool(int64_t day){
    pm_catalog::init();pm_pve::init();  // module globals (TIERS, CARDS) before the first call
    std::set<std::string> out;
    // Keep the list alive: a range-for over items() of a temporary would dangle.
    const V entries=py::iter_list(pm_pve::f_zombie_pool(Args{V(double(day)),V::none(),V(true)}));
    for(size_t i=0;i<entries.len();++i)out.insert(py_str(py::as_seq(entries.idx(int64_t(i))).idx(0)));
    return out;
}
uint64_t fnv(const std::string& text){uint64_t h=1469598103934665603ull;for(unsigned char c:text){h^=c;h*=1099511628211ull;}return h;}
int64_t whole(const V& v,int64_t fallback){if(v.is_none())return fallback;const double d=v.num();return std::isfinite(d)?int64_t(std::floor(d)):fallback;}
}
const std::vector<std::string>& coop_secret_keys(){
    static const std::vector<std::string> keys=[]{std::vector<std::string> k;for(const auto& e:table())k.push_back(e.key);return k;}();
    return keys;
}
bool coop_secret_allowed(const std::string& key){return find(key)!=nullptr;}
bool precursor_in_pool(const std::string& key,int64_t day){
    const auto* e=find(key);if(!e||!card_exists(key))return false;const auto today=pool(day);
    return std::any_of(e->precursors.begin(),e->precursors.end(),[&](const char* p){return today.count(p)>0;});
}
V coop_zombie_secrets(const V& run_id,const V& from_day,const V& day){
    V out=V::list();if(run_id.is_none()||from_day.is_none())return out;  // no counting start: none yet
    const std::string run=py_str(run_id);const int64_t first=std::max<int64_t>(1,whole(from_day,1)),now=whole(day,1);
    std::vector<std::string> owned;
    for(int64_t cleared=first;cleared<now&&owned.size()<table().size();++cleared){
        const auto next=pool(cleared+1);std::vector<std::string> eligible;
        for(const auto& e:table()){
            if(std::find(owned.begin(),owned.end(),e.key)!=owned.end()||!card_exists(e.key))continue;
            if(std::any_of(e.precursors.begin(),e.precursors.end(),[&](const char* p){return next.count(p)>0;}))eligible.push_back(e.key);
        }
        if(eligible.empty())continue;
        owned.push_back(eligible[size_t(fnv(run+":"+std::to_string(cleared))%eligible.size())]);
    }
    for(const auto& k:owned)out.append(V(k));
    return out;
}
V coop_secret_line(const V& pve){
    pm_catalog::init();
    const V list=pve.is_dict()?py::m_get(pve,V("coop_zombie_secrets"),V::list()):V::list();
    std::string names;int64_t count=0;
    const V keys=py::iter_list(list);
    for(size_t i=0;i<keys.len();++i){const V key=keys.idx(int64_t(i));
        const V card=py::m_get(pm_catalog::CARDS,key,V::none());if(!card.is_dict())continue;
        if(count++)names+="、";names+=py_str(py::m_get(card,V("name"),key));
    }
    return V(count?"僵尸秘籍（"+std::to_string(count)+"）："+names:std::string("僵尸秘籍：尚无（每通关一天加入一个）"));
}
V coop_battle_secrets(const V& pve){
    if(!pve.is_dict())return V::list();
    return coop_zombie_secrets(py::m_get(pve,V("coop_run_id"),V::none()),py::m_get(pve,V("coop_zombie_from"),V::none()),py::m_get(pve,V("day"),V::none()));
}
}
