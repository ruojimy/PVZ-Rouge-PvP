#include "sim/typed/ai_team_support.h"
#include "core/pymath.h"
#include <algorithm>
#include <array>
#include <cmath>
namespace pvz::typed72 {
std::string_view ai_support_state_name(AiSupportState s){static constexpr std::array names{"home","return","assist","rescue"};return names.at(size_t(s));}
std::string_view ai_support_reason_name(AiSupportReason r){static constexpr std::array names{"no_mate","mate_unavailable","health","local_danger","home_danger","projectile","enemy_hero","no_ready_response","reserve","unguarded_home","economy","too_far","vertical_route","cleared","overwhelming","body_guarded","route","time_limit","cooldown","mate_pressure"};return names.at(size_t(r));}
double AiTeamSupport::power(const AiUnitView& u){
    if(u.card_info.producer||u.behavior=="pot"||u.behavior=="lily"||u.behavior=="grave")return 0.;
    return (u.card_info.cost.value_or(25.)+25.)*std::max(.2,std::min(1.,u.hp/std::max(1.,u.max_hp)));
}
AiSupportDecision AiTeamSupport::finish(const AiSupportFrame& c,Point home,AiSupportReason reason){
    if(state_.active)state_.cooldown_until=c.time+8.;
    const bool returning=state_.active||(state_.last&&state_.last->state==AiSupportState::return_home);
    state_.active=false;state_.quiet_since.reset();
    const auto value=AiSupportDecision{returning&&std::abs(ai_wrap_delta(c.me.position.x,home.x,c.width))>c.tile?AiSupportState::return_home:AiSupportState::home,reason,home.x,0.,{}, {}};
    state_.last=value;return value;
}
std::optional<AiSupportDecision> AiTeamSupport::decide(const AiSupportFrame& c,Point home){
    if(c.mode!=AiTeamMode::duo&&c.mode!=AiTeamMode::coop){state_.active=false;state_.last.reset();return {};}
    const auto done=[&](AiSupportReason reason)->std::optional<AiSupportDecision>{return finish(c,home,reason);};
    const auto distance=[&](Point a,Point b){return std::hypot(ai_wrap_delta(a.x,b.x,c.width),a.y-b.y);};
    if(!c.mate||c.mate->absent)return done(AiSupportReason::no_mate);
    const auto& mate=*c.mate;
    if(mate.hp<=0.&&!c.mate_fallen)return done(AiSupportReason::mate_unavailable);
    if(c.me.hp/std::max(1.,c.me.max_hp)<(state_.active?.55:.70))return done(AiSupportReason::health);
    std::vector<const AiUnitView*> dangerous;
    for(const auto& u:c.enemy)if(u.hp>0.&&power(u)!=0.)dangerous.push_back(&u);
    for(const auto* u:dangerous)if(distance(c.me.position,u->position)<=3.*c.tile)return done(AiSupportReason::local_danger);
    for(const auto* u:dangerous)if(distance(home,u->position)<=5.*c.tile)return done(AiSupportReason::home_danger);
    for(const auto& t:c.threats)if(t.projectile&&t.eta_ms<700)return done(AiSupportReason::projectile);
    for(const auto& hero:c.enemy_heroes)if(!hero.absent&&hero.hp>0.&&(distance(c.me.position,hero.position)<5.*c.tile||distance(home,hero.position)<6.*c.tile))return done(AiSupportReason::enemy_hero);
    std::optional<double> cheapest;double support_cost=0.;
    static constexpr std::array non_combat{"pot","lily","coffee","grave","produce","gold_bloom","lantern","support"};
    for(const auto& card:c.deck){
        if(card.id.starts_with("secret:")||card.id.starts_with("zsecret:"))continue;
        if(card.behavior=="pot"||card.behavior=="lily")support_cost=std::max(support_cost,card.cost);
        else if(!card.producer&&std::find(non_combat.begin(),non_combat.end(),card.behavior)==non_combat.end()&&card.ready)cheapest=cheapest?std::min(*cheapest,card.cost):card.cost;
    }
    if(!cheapest)return done(AiSupportReason::no_ready_response);
    const double response=std::max(25.,*cheapest+support_cost),reserve=std::max(75.,response*1.5);
    if(c.me.resource<reserve+response)return done(AiSupportReason::reserve);
    double own_power=0.;bool producer=false;
    for(const auto& u:c.own)if(u.seat.value_or(c.side)==c.seat&&distance(home,u.position)<=8.*c.tile){own_power+=power(u);producer=producer||u.card_info.producer;}
    if(own_power<75.)return done(AiSupportReason::unguarded_home);
    if(!c.deathmatch&&!producer)return done(AiSupportReason::economy);
    if(distance(home,mate.position)>20.*c.tile)return done(AiSupportReason::too_far);
    if(std::abs(mate.position.y-c.me.position.y)>6.*c.tile)return done(AiSupportReason::vertical_route);
    double strength=0.,allied=0.;
    for(const auto* u:dangerous)if(distance(mate.position,u->position)<=7.*c.tile)strength+=power(*u);
    for(const auto& u:c.own)if(distance(mate.position,u.position)<6.*c.tile)allied+=power(u);
    const bool needs_help=c.mate_fallen||(strength>=75.&&(strength>allied*.8||mate.hp<.65*mate.max_hp));
    if(!needs_help){
        if(state_.active){if(!state_.quiet_since)state_.quiet_since=c.time;if(c.time-*state_.quiet_since<2.)return state_.last;}
        return done(AiSupportReason::cleared);
    }
    state_.quiet_since.reset();
    if(strength>allied+2.5*(c.me.resource-reserve))return done(AiSupportReason::overwhelming);
    if(c.mate_fallen)for(const auto* u:dangerous)if(distance(mate.position,u->position)<4.*c.tile)return done(AiSupportReason::body_guarded);
    const int direction=ai_wrap_delta(mate.position.x,home.x,c.width)>=0.?1:-1;
    const double post=c.mate_fallen?mate.position.x:py::mod(mate.position.x+direction*4.*c.tile,c.width),delta=ai_wrap_delta(c.me.position.x,post,c.width);
    for(const auto* u:dangerous){const double dx=ai_wrap_delta(c.me.position.x,u->position.x,c.width);
        if(dx>=std::min(0.,delta)-c.tile&&dx<=std::max(0.,delta)+c.tile&&std::abs(u->position.y-c.me.position.y)<3.*c.tile)return done(AiSupportReason::route);}
    if(state_.active&&c.time>=state_.until)return done(AiSupportReason::time_limit);
    if(!state_.active){if(c.time<state_.cooldown_until)return done(AiSupportReason::cooldown);state_.active=true;state_.until=c.time+12.;}
    const Seat real_mate=c.side==Seat::plant?(c.seat==Seat::plant2?Seat::plant:Seat::plant2):(c.seat==Seat::zombie2?Seat::zombie:Seat::zombie2);
    state_.last=AiSupportDecision{c.mate_fallen?AiSupportState::rescue:AiSupportState::assist,AiSupportReason::mate_pressure,post,reserve,real_mate,mate.position};return state_.last;
}
} // namespace pvz::typed72
