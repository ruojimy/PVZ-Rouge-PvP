#include "sim/pvp/hand/solo_campaign77.h"
#include <algorithm>
#include "sim/pvp/hand/pvp76r2_coop.h"
#include <array>
#include <cmath>
#include <random>
namespace pvz::solo77 {
namespace {

const Keys secrets{"石果","胆大","尖刺","压顶","蓝火","地雷","核平","魅惑","雷霆","磁力","黄油","卷心菜","地刺","水兵","光疗","龙蒺藜","小喷","大帝","三向蓝火","豌豆杂交","麻痹","毒镖","毒气","电疗","触手"};
bool has(const Keys& keys,const std::string& key){return std::find(keys.begin(),keys.end(),key)!=keys.end();}
template<class T> void shuffle(std::vector<T>& v,std::mt19937& rng){
    for(size_t n=v.size();n>1;--n)std::swap(v[n-1],v[size_t(rng())%n]);
}
bool defender_secret(const Card& c,const Keys& defenders){
    if(!c.dependency.empty())return has(defenders,c.dependency);
    static const std::map<std::string,Keys> families{
        {"secret:三向蓝火",{"plant:裂荚射手","plant:三向射手","plant:豌豆迫击炮"}},
        {"secret:电疗",{"plant:闪电芦苇","plant:超载芦苇"}},
        {"secret:豌豆杂交",{"plant:豌豆射手","plant:寒冰射手","plant:双发射手","plant:机枪射手","plant:原始豌豆射手","plant:裂荚射手"}}
    };
    const auto f=families.find(c.key);
    return f==families.end()||std::any_of(f->second.begin(),f->second.end(),[&](const auto& key){return has(defenders,key);});
}
bool eligible(const Card& c,const Keys& owned){
    return !has(owned,c.key)&&(c.dependency.empty()||has(owned,c.dependency));
}
}
const Keys& original_maps(){
    static const Keys names{"山地","沙城","家院","要塞","大桥","铁道","遗迹","绿洲","小镇","古堡","木船","大楼"};
    return names;
}
std::string map_for_stage(Keys pool,const std::string& run,int day){
    if(pool.empty()||day<1)throw std::invalid_argument("地图池或关卡无效");
    const size_t index=size_t(day-1);
    std::vector<uint32_t> words(run.begin(),run.end());
    words.push_back(uint32_t(index/pool.size()));
    std::seed_seq seed(words.begin(),words.end());
    std::mt19937 rng(seed);
    shuffle(pool,rng);
    return pool[index%pool.size()];
}
bool rainy_stage(int seed,int stage){
    std::seed_seq sequence{seed,stage,0x5241494e};
    std::mt19937 rng(sequence);
    return (rng()&3u)==0u;
}
void Campaign::draw_map(const Pools& pools){
    Keys available=original_maps();
    if(cooperative)available.insert(available.end(),pools.team_maps.begin(),pools.team_maps.end());
    Keys remaining;
    for(const auto& candidate:available)if(!has(visited_maps,candidate))remaining.push_back(candidate);
    if(remaining.empty()){remaining=std::move(available);visited_maps.clear();}
    std::seed_seq sequence{seed,stage,cooperative?1:0,zombie()?1:0};
    std::mt19937 rng(sequence);
    map=remaining[std::uniform_int_distribution<size_t>(0,remaining.size()-1)(rng)];
    visited_maps.push_back(map);
    rain=zombie()&&!map.starts_with("custom:")&&rainy_stage(seed,stage);
}
int Campaign::slots()const{return std::min(10,4+(stage+1)/2)+slots_bought;}
void Campaign::start(const std::string& id,int value,const Pools& pools,bool shared){
    *this=Campaign{};mode=id;seed=value;cooperative=shared;draw_map(pools);
    owned=zombie()?Keys{"zombie:普通僵尸"}:Keys{"plant:模仿者","plant:向日葵","plant:金盏花","plant:樱桃炸弹","secret:无土栽培"};
    deck=owned;
    if(!zombie())owned.insert(owned.end(),{"plant:花盆","plant:睡莲","plant:咖啡豆"});
    defenders={"plant:豌豆射手","plant:向日葵","plant:金盏花","plant:土豆地雷"};
    if(zombie())defenders.push_back("plant:睡莲");
    stock(pools);
}
std::string Campaign::toggle(const Pools& pools,const std::string& key){
    if(!has(owned,key))return "尚未解锁";
    auto next_deck=deck;
    if(has(next_deck,key))std::erase(next_deck,key);
    else{
        if(int(next_deck.size())>=slots())return "卡槽已满";
        next_deck.push_back(key);
    }
    const auto& cards=zombie()?pools.zombies:pools.plants;
    for(const auto& c:cards)if(has(next_deck,c.key)){
        if(!c.dependency.empty()&&!has(next_deck,c.dependency))return "需要同时携带这张卡的前体";
    }
    deck=std::move(next_deck);return {};
}
void Campaign::stock(const Pools& pools,int price_stage){
    if(!price_stage)price_stage=stage;
    std::vector<uint32_t> words{uint32_t(seed),uint32_t(price_stage)};
    words.insert(words.end(),last_result.begin(),last_result.end());
    std::seed_seq batch(words.begin(),words.end());
    std::mt19937 rng(batch);
    shop.clear();auto list=zombie()?pools.zombies:pools.plants;shuffle(list,rng);
    int units=0,books=0;
    auto add=[&](std::string key,int price){shop.push_back({std::move(key),((price*(price_stage+9)+49)/50)*5,false});};
    for(const auto& c:list)if(eligible(c,owned)&&!has(rewards,c.key)){
        if(c.secret&&books<2&&(!zombie()||pvp76r2::precursor_in_roster(c.key,owned))){++books;add(c.key,250+int(rng()%21)*5);}
        if(!c.secret&&units<3){++units;add(c.key,int(std::round((75+c.cost*1.2)/5.))*5);}
    }
    if(slots_bought<3)add("slot",150*(slots_bought+1));
    if(sun_bought<6)add(zombie()?"brain":"sun",100*(sun_bought+1));
}
void Campaign::grant(const std::string& key){
    if(has(owned,key))return;owned.push_back(key);if(int(deck.size())<slots())deck.push_back(key);
}
std::string Campaign::buy(const std::string& key){
    const auto it=std::find_if(shop.begin(),shop.end(),[&](const auto& o){return o.key==key;});
    if(it==shop.end()||it->sold||has(owned,key))return "该商品已售出";
    if(coins<it->price)return "金币不足";
    if(key=="slot")++slots_bought;else if(key=="sun"||key=="brain")++sun_bought;else grant(key);
    coins-=it->price;it->sold=true;return {};
}
void Campaign::finish(const Pools& pools,const std::string& match,bool win,int pickups,int diamonds){
    if(match.empty()||match==last_result||complete||!rewards.empty())return;
    last_result=match;pickups=std::max(0,pickups);diamonds=std::clamp(diamonds,0,pickups);
    if(zombie())coins+=pickups;
    else {int ordinary=pickups-diamonds+half;coins+=diamonds+ordinary/2;half=ordinary%2;if(win)coins+=(150+20*stage)/2;}
    if(!win){stock(pools);return;}
    clear_difficulty=std::min(clear_difficulty,difficulty);
    if(stage==(zombie()?19:24)){complete=true;stock(pools);return;}
    std::mt19937 rng(uint32_t(seed)*31u+uint32_t(stage));
    if(zombie()){
        Keys choices;for(const auto& key:pools.defenders)if(!has(defenders,key))choices.push_back(key);
        shuffle(choices,rng);if(!choices.empty())defenders.push_back(choices.front());
        choices.clear();
        for(const auto& c:pools.plants)if(c.key.starts_with("secret:")&&has(secrets,c.key.substr(7))&&!has(plant_secrets,c.key)&&defender_secret(c,defenders))choices.push_back(c.key);
        shuffle(choices,rng);if(!choices.empty())plant_secrets.push_back(choices.front());
    }
    const auto& list=zombie()?pools.zombies:pools.plants;
    for(const auto& c:list)if(eligible(c,owned)&&(!zombie()||!c.secret))rewards.push_back(c.key);
    shuffle(rewards,rng);
    if(zombie()&&!has(owned,"zombie:梯子僵尸")){
        auto it=std::find(rewards.begin(),rewards.end(),"zombie:梯子僵尸");if(it!=rewards.end())std::iter_swap(rewards.begin(),it);
    }
    rewards.resize(std::min(rewards.size(),size_t(3)));
    stock(pools,stage+1);
    if(rewards.empty())next(pools);
}
void Campaign::reward(const Pools& pools,const std::string& key){if(has(rewards,key)){
    grant(key);
    for(auto& offer:shop)if(offer.key==key)offer.sold=true;
    rewards.clear();next(pools);
}}
void Campaign::next(const Pools& pools){
    ++stage;
    draw_map(pools);
}
}
