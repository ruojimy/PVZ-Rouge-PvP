#pragma once
#include "sim/typed/world_regions.h"
#include <list>
#include <unordered_map>

namespace pvz::typed72 {
struct MatchResource {
    std::string id;
    Seat side=Seat::plant;
    double amount=0.,born=0.;
    Point position;
    std::string source;
    Field<bool> shared;
    Field<std::string> coin;
};
struct ResourceMotion {std::string id;NativeSun sun;};
struct ResourceAccount {double balance=0.,earned=0.;Field<double> coins;};
class Resources {
public:
    Resources(TypedBattleState& world,WorldRegions& regions,uint64_t& sequence)
        :world_(world),regions_(regions),sequence_(sequence){}
    std::array<ResourceAccount,4> accounts;
    double coins=0.;
    const std::list<MatchResource>& records()const{return records_;}
    const std::list<ResourceMotion>& motions()const{return motions_;}
    MatchResource* find(const std::string& id);
    NativeSun* motion(const std::string& id);
    std::string create(Seat,double,Point,std::string source);
    void admit(MatchResource); // Validated save/room boundary preserves order.
    void set_motion(std::string,NativeSun);
    void remove_motion(const std::string&);
    void expire(const std::string&);
    void collect(const std::string&,std::optional<Seat> collector={});
    std::string drop_coin(double,Point,std::string kind);
    bool auto_shared_sky(const std::string&);
    std::optional<Seat> shared_collector(const MatchResource&)const;
    void settle(double lifetime);
    void advance_suns();
    void merge_suns();
private:
    TypedBattleState& world_;
    WorldRegions& regions_;
    uint64_t& sequence_;
    std::list<MatchResource> records_;
    std::unordered_map<std::string,std::list<MatchResource>::iterator> index_;
    std::list<ResourceMotion> motions_;
    std::unordered_map<std::string,std::list<ResourceMotion>::iterator> motion_index_;
    void income(const MatchResource&,Seat,double,bool shared_auto=false);
    bool touching(const MatchResource&,const HeroPlayer&)const;
};
} // namespace pvz::typed72
