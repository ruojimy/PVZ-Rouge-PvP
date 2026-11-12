#pragma once
#include "sim/typed/ai_field.h"
#include "sim/typed/ai_controls.h"
#include "sim/typed/ai_team_support.h"
#include <unordered_map>
namespace pvz::typed72 {
struct AiTacticalFrame {
    Seat side=Seat::plant,owner=Seat::plant;AiTeamMode mode=AiTeamMode::duel;
    const AiPublicHero& me;const AiPublicHero& foe;
    const TargetSight& terrain;const AiField& field;
    std::span<const std::vector<uint8_t>> ladders;
    std::span<const AiUnitView> units;
    std::span<const AiObservedThreat> threats;
    double time=0.,width=3456.,tile=48.;bool night=false,deathmatch=false;
};
class AiTacticalServices {
public:
    virtual ~AiTacticalServices()=default;
    virtual std::string send(Seat,CommandPayload)=0;
    virtual const AiDeckCardView& card(const std::string&)=0;
    virtual AiPlacementResult preview(Seat,const std::string&,Point,const std::optional<std::string>&)=0;
    virtual void reset_preview()=0;
};
class AiTacticalContext {
public:
    AiTacticalContext(const AiTacticalFrame&,AiTacticalServices&);
    const AiTacticalFrame& frame;AiTacticalServices& services;
    std::vector<const AiUnitView*> living,own,enemy;
    double dx(double x)const{return ai_wrap_delta(frame.me.position.x,x,frame.width);}
    bool ready(const std::string&,double reserve=0.);
    const std::vector<AiFieldSpot>& spots(bool free=true);
    static bool in_view(Point hero,Point target,double width);
private:
    std::array<std::optional<std::vector<AiFieldSpot>>,2> cached_spots_;
};
struct AiTacticalState {
    double next_deploy=0.,next_jump=0.,detour_until=0.,ladder_backoff_until=0.;
    bool jump_down=false,blocked=false,recovering=false;
    std::optional<std::pair<double,double>> last_position;
    std::optional<double> stuck_since,hold_refuge_until;
    std::unordered_map<std::string,double> failed,log;
    struct LadderRoute {size_t column=0;double x=0.,goal_y=0.;bool up=false;double until=0.,progress_at=0.,y=0.;bool engaged=false;};
    std::optional<LadderRoute> ladder_route;
};
// Shared actual Controller v6 movement/deploy machinery, used by r19/r22.
class AiTacticalBase {
public:
    explicit AiTacticalBase(AiTacticalState& state):state_(state){}
    int drive(AiTacticalContext&,double target_x,bool jump_wish=false,double tolerance=20.);
    std::string try_deploy(AiTacticalContext&,const std::string&,Point,std::optional<std::string> grave={},int facing=1);
    std::optional<int> ladder_drive(AiTacticalContext&,double post,double goal_y,std::optional<AiSupportReason> reason={});
private:AiTacticalState& state_;
};
} // namespace pvz::typed72
