#pragma once
#include "sim/typed/native_tracking.h"
#include <set>

namespace pvz::typed72 {
using ScarecrowCells=std::set<std::pair<int,int64_t>>;
class ScarecrowServices {
public:
    virtual ~ScarecrowServices()=default;
    virtual std::optional<std::string> spawn_echo_crow(Point,double facing,const std::string& parent)=0;
    virtual void crow_echo_event(const std::string& source,const Field<std::string>& scarecrow,const std::string& child)=0;
};
class Scarecrows {
public:
    Scarecrows(TypedBattleState& world,const TargetSight& published,ScarecrowServices& services)
        :world_(world),published_(published),services_(services){}
    bool configure(const ZombieRef&,std::string_view,double hp);
    std::vector<ZombieRef> living()const;
    ScarecrowCells aura_cells()const;
    static double slow_factor(const PlantRef&,const ScarecrowCells&);
    ZombieRef grave_goal(const ZombieRef&)const;
    void advance(const ZombieRef&,double factor);
    std::optional<std::string> crow_echo(Point,const std::string& id);
private:
    TypedBattleState& world_;
    const TargetSight& published_;
    ScarecrowServices& services_;
    bool solid(Point)const;
};
} // namespace pvz::typed72
