#pragma once
#include <nlohmann/json.hpp>
#include <map>
#include <string>
#include <vector>
namespace pvz::solo77 {
using Keys=std::vector<std::string>;
struct Card {std::string key,dependency;bool secret=false;int cost=0;};
struct Pools {std::vector<Card> plants,zombies;Keys defenders,random_plants,random_zombies;};
const Pools& campaign_pools();
struct Offer {std::string key;int price=0;bool sold=false;};
NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(Offer,key,price,sold)
struct Campaign {
    std::string mode,map,last_result;
    int seed=1,stage=1,coins=0,half=0,slots_bought=0,sun_bought=0,attempt=0;
    bool complete=false;
    Keys owned,deck,defenders,plant_secrets,rewards;
    std::vector<Offer> shop;
    bool zombie()const{return mode=="izombie";}
    int slots()const;
    void start(const std::string& mode,int seed,const Pools&);
    void stock(const Pools&,int price_stage=0);
    void finish(const Pools&,const std::string& match,bool win,int pickups,int diamonds);
    void reward(const Pools&,const std::string&);
    void next(const Pools&);
    std::string buy(const std::string&);
    void grant(const std::string&);
    std::string toggle(const Pools&,const std::string&);
};
NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(Campaign,mode,map,last_result,seed,stage,coins,half,slots_bought,sun_bought,attempt,complete,owned,deck,defenders,plant_secrets,rewards,shop)
}
