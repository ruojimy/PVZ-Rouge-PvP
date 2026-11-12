#pragma once
#include "sim/typed/ai_observation.h"
#include "sim/typed/command_input.h"
#include "sim/typed/command_gateway.h"

namespace pvz::typed72 {
enum class AiStance {hold,advance,hunt,kite,retreat};
struct AiPlan {
    std::vector<std::string> priority;
    std::vector<std::pair<std::string,int64_t>> quotas;
    AiStance stance=AiStance::hold;
    std::optional<double> target_x;
    double reserve=0.,distance=350.,deploy_ahead=120.,economy_offset=100.,jump_every=0.,teleport_hp=0.;
    std::optional<std::string> save_for;
    bool evade=false,jump_on_block=true,dodge_jump=true,mark=true;
    std::optional<PathMode> command=PathMode::attack_plants;
};
struct AiHeroView {Point position;double hp=0.,max_hp=1.,resource=0.,teleport_ready=0.;int jumps_left=1;std::vector<std::pair<std::string,double>> cooldowns;};
struct AiThreat {double eta_ms;bool from_left;};
struct AiControlFrame {
    double time=0.,width=0.,tile=48.;
    AiHeroView me,enemy;
    bool deathmatch=false,night=false;
    PathMode command=PathMode::follow_hero;
    std::span<const AiUnitView> units,sleeping_plants,empty_supports;
    std::span<const std::string> collectable;
    std::span<const AiThreat> threats;
    const TargetSight& terrain;
};
enum class AiCardBehavior {other,grave,coffee,pot,lily};
struct AiResolvedCard {double cost=0.;AiCardBehavior behavior=AiCardBehavior::other;bool producer=false,mushroom=false;};
struct AiClick {Point point;std::optional<std::string> grave;friend bool operator==(const AiClick& a,const AiClick& b){return a.point.x==b.point.x&&a.point.y==b.point.y&&a.grave==b.grave;}};
struct AiPlacementResult {std::string error;bool placement=false;};
struct AiControlStatus {
    double time=0.;std::optional<std::string> card,setup_for;std::string error;
    AiCardCounts counts;std::vector<std::pair<std::string,std::vector<std::string>>> refusals;
    bool missing_support=false,blocked=false;
};
class AiControlServices {
public:
    virtual ~AiControlServices()=default;
    virtual std::string send(Seat owner,CommandPayload)=0;
    virtual AiResolvedCard resolve(Seat owner,const std::string&)=0;
    virtual std::vector<Point> candidates(int region,Point hero,size_t limit)=0;
    virtual void begin_preview()=0;
    virtual AiPlacementResult placement(Seat owner,const std::string& card,const AiClick&)=0;
};
struct AiControlState {
    double next_deploy=0.,next_jump=0.,mark_at=0.,teleport_at=0.,max_gap=0.;
    uint64_t samples=0;
    std::optional<double> last_sample;
    struct Position {double x,time;bool blocked;};
    std::optional<Position> previous;
    AiControlStatus status;
};
class AiLiveControls {
public:
    AiLiveControls(AiControlState& state,AiControlServices& services):state_(state),services_(services){}
    void step(Seat owner,const AiControlFrame&,const AiPlan&);
private:
    AiControlState& state_;AiControlServices& services_;
    std::vector<AiClick> targets(Seat,const std::string&,const AiResolvedCard&,const AiControlFrame&,const AiPlan&);
};
// AI uses the same validated command application as human/network inputs.
class AiRoomSender {
public:
    explicit AiRoomSender(RoomInputGateway& gateway):gateway_(gateway){}
    int64_t sequence=0;
    std::string send(Seat owner,CommandPayload payload){return gateway_.generated(owner,++sequence,std::move(payload));}
private:RoomInputGateway& gateway_;
};
} // namespace pvz::typed72
