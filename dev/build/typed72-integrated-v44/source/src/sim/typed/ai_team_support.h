#pragma once
#include "sim/typed/ai_observation_builder.h"
namespace pvz::typed72 {
enum class AiTeamMode {duel,duo,coop,pve};
enum class AiSupportState {home,return_home,assist,rescue};
enum class AiSupportReason {no_mate,mate_unavailable,health,local_danger,home_danger,projectile,enemy_hero,no_ready_response,reserve,unguarded_home,economy,too_far,vertical_route,cleared,overwhelming,body_guarded,route,time_limit,cooldown,mate_pressure};
std::string_view ai_support_state_name(AiSupportState);
std::string_view ai_support_reason_name(AiSupportReason);
struct AiSupportDecision {AiSupportState state=AiSupportState::home;AiSupportReason reason=AiSupportReason::cleared;double post=0.,reserve=0.;std::optional<Seat> mate;Point mate_position;};
struct AiSupportCard {std::string id,behavior;double cost=0.;bool producer=false,ready=false;};
struct AiSupportFrame {
    AiTeamMode mode=AiTeamMode::duel;Seat side=Seat::plant,seat=Seat::plant;
    const AiPublicHero& me;
    const AiPublicHero* mate=nullptr;
    std::span<const AiPublicHero> enemy_heroes;
    std::span<const AiUnitView> own,enemy;
    std::span<const AiObservedThreat> threats;
    std::span<const AiSupportCard> deck;
    double time=0.,width=3456.,tile=48.;bool deathmatch=false,mate_fallen=false;
};
struct AiTeamSupportState {bool active=false;double until=0.,cooldown_until=0.;std::optional<double> quiet_since;std::optional<AiSupportDecision> last;};
class AiTeamSupport {
public:
    explicit AiTeamSupport(AiTeamSupportState& state):state_(state){}
    std::optional<AiSupportDecision> decide(const AiSupportFrame&,Point home);
    static double power(const AiUnitView&);
private:
    AiTeamSupportState& state_;
    AiSupportDecision finish(const AiSupportFrame&,Point,AiSupportReason);
};
} // namespace pvz::typed72
