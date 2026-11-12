#pragma once
#include "sim/typed/content_queries.h"

namespace pvz::typed72 {
struct ReedBolt {int64_t tick;std::string content;std::vector<Point> points;};
struct ReedEvent {
    Field<std::string> source;
    bool overload=false;
    std::vector<std::string> targets;
};
class ReedPlantServices {
public:
    virtual ~ReedPlantServices()=default;
    virtual void reed_event(const ReedEvent&)=0;
};
class ReedPlants {
public:
    ReedPlants(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,ReedPlantServices& services)
        :world_(world),queries_(queries),targets_(targets),services_(services){}
    bool electrotherapy=false;
    std::vector<ReedBolt> bolts;
    bool configure(const PlantRef&,std::string_view);
    std::vector<ContentTarget> enemies(const PlantRef&);
    std::optional<double> in_cone(const PlantRef&,const ContentTarget&)const;
    std::optional<ContentTarget> select(const PlantRef&);
    void advance(const PlantRef&);
    void strike(const PlantRef&,const ContentTarget&,double amount,bool direct=false);
    void lightning(const PlantRef&,const ContentTarget&);
    std::vector<ContentTarget> contacts(const PlantRef&,const ContentTarget&);
    void overload(const PlantRef&,const ContentTarget&);
    void add_bolt(const PlantRef&,std::span<const ContentTarget>);
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    ReedPlantServices& services_;
    double hp(const ContentTarget&,double fallback)const;
    void emit(const PlantRef&,bool overload,std::span<const ContentTarget>);
};
} // namespace pvz::typed72
