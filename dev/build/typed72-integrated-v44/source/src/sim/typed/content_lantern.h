#pragma once
#include "sim/typed/content_plants70.h"
namespace pvz::typed72 {
class ContentLanternEvents {
public:
    virtual ~ContentLanternEvents()=default;
    virtual void lantern_wake(const Field<std::string>&,const std::vector<Field<std::string>>&)=0;
    virtual void lantern_burn(const Field<std::string>&,size_t hits)=0;
};
class ContentLantern {
public:
    ContentLantern(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,
        ContentPlants70& plants70,ContentLanternEvents& events,const bool& phototherapy)
        :world_(world),queries_(queries),targets_(targets),plants70_(plants70),events_(events),phototherapy_(phototherapy){}
    void pulses();
    void burn(const PlantRef&);
private:
    TypedBattleState& world_;ContentQueries& queries_;ContentTargets& targets_;
    ContentPlants70& plants70_;ContentLanternEvents& events_;const bool& phototherapy_;
};
} // namespace pvz::typed72
