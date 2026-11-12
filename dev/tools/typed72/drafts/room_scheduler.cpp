#include "sim/typed/room_scheduler.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <limits>

namespace pvz::typed72 {
namespace {
bool team_mode(MatchMode m){return m==MatchMode::duo||m==MatchMode::coop;}
bool scripted(MatchMode m){return m==MatchMode::pve||m==MatchMode::coop;}
double deathmatch_factor(double seconds){return seconds<=12.?.5:seconds<=48.?2./3.:.75;}
}
RoomScheduler::RoomScheduler(TypedBattleState& w,RoomState& s,const RoomRules& r,NativeTickState& ns,
        NativeTick& n,HeroRecovery& h,Economy& e,Resources& resources,RoomServices& services)
    :world_(w),state_(s),rules_(r),native_state_(ns),native_(n),recovery_(h),economy_(e),
     resources_(resources),services_(services){
    if(r.tick_rate<=0)throw std::invalid_argument("non-positive room tick rate");
    if(s.native_phase<0||s.native_phase>=r.tick_rate)throw std::invalid_argument("invalid room native phase");
}
void RoomScheduler::clear_input(Seat side){
    auto& p=world_.heroes.players.at(seat_index(side)).value();
    p.move=0;p.jump_held=false;p.jump_presses=0;
    // The explicit press-reporting capability persists across disconnects.
}
void RoomScheduler::begin_deathmatch(){
    state_.deathmatch=true;world_.protection.deathmatch=true;native_state_.production.deathmatch=true;
    const auto time=world_.heroes.time;
    for(size_t i=0;i<world_.heroes.players.size();++i){
        if(!world_.heroes.players[i])continue;
        auto& p=*world_.heroes.players[i];auto& spans=state_.players[i].cooldown_spans;
        for(auto& [key,ready]:p.cooldowns){
            const auto factor=deathmatch_factor(services_.card_cooldown(Seat(i),key));
            ready=time+std::max(0.,ready-time)*factor;
            const auto it=std::find_if(spans.begin(),spans.end(),[&](const auto& item){return item.first==key;});
            if(it!=spans.end())it->second*=factor;
        }
    }
    // Snapshot the roster: emitting an event can synchronously observe or
    // register births, just as list(self.g["植物"]) isolates this traversal.
    const auto plants=*world_.plant_roster;
    for(const auto& p:plants){
        if(p->kind!="模仿者"||!p->imitation.present()||p->imitation.is_null()||p->imitation.get().empty())continue;
        const auto key=p->copy_card.or_missing("plant:"+p->imitation.get());
        const auto producer=services_.copied_card_is_producer(key);
        if(!producer||*producer){p->hp.set(0.);services_.emit(RoomSpawnBlockedEvent{key});}
    }
    services_.emit(RoomDeathmatchEvent{rules_.production_multiplier});
}
void RoomScheduler::publish_heroes(){
    // Deliberately retain the public room boundary used by targeting. These
    // are published observations; simulation HP/position stay in HeroState.
    for(size_t i=0;i<world_.heroes.heroes.size();++i){
        const auto& h=world_.heroes.heroes[i];if(!h)continue;
        auto& p=world_.heroes.players.at(i).value();const auto& m=*h->frame.position.get();
        p.position={m.x,m.y};p.hp=h->frame.hp.get();
    }
}
void RoomScheduler::subsidy(){
    const auto due=int64_t(py::floordiv(world_.heroes.time,8.));
    while(state_.ai_subsidy_paid<due){
        ++state_.ai_subsidy_paid;
        const auto amount=world_.mode==MatchMode::duo?25.:std::min(200.,25.*std::pow(2.,py::floordiv(state_.ai_subsidy_paid*8.,40.)));
        for(const auto seat:state_.ai_subsidy_seats){
            if(!world_.heroes.players.at(seat_index(seat)))continue;
            auto& account=resources_.accounts.at(seat_index(seat));account.balance+=amount;account.earned+=amount;
            services_.emit(RoomSubsidyEvent{seat,amount});
        }
    }
}
bool RoomScheduler::touching(const HeroState& a,const HeroState& b)const{
    const auto& p=*a.frame.position.get();const auto& q=*b.frame.position.get();const auto tile=world_.runtime.tile;
    return std::abs(wrap_delta(p.x,q.x,world_.world_width.get()))<=tile*.9&&std::abs(p.y-q.y)<=tile*1.6;
}
void RoomScheduler::revive(Seat seat,Seat helper){
    auto& h=world_.heroes.heroes.at(seat_index(seat)).value();
    const double hp=py::roundn(h.max_hp.get()*.5,1);
    h.frame.hp.set(hp);h.frame.down.set(0.);h.frame.recovery.set(0.);h.frame.hurt.set(0.);
    h.previous_hp.set(hp);h.last_damage.set(world_.heroes.tick/250.);
    const auto& source=*world_.heroes.heroes.at(seat_index(helper))->frame.position.get();
    *h.frame.position.get()={source.x,source.y,0.,0.};
    state_.revive[seat_index(seat)]=0.;state_.down_since[seat_index(seat)].reset();
    state_.players[seat_index(seat)].immune_until=world_.heroes.time+2.;
    services_.emit(RoomRevivedEvent{seat,helper,hp});publish_heroes();services_.sync_public(true);
}
void RoomScheduler::finish_result(){
    if(!state_.result)return;
    if(scripted(world_.mode)){state_.result->coins=resources_.coins;state_.result->fallen=state_.fallen_count;}
    services_.emit(*state_.result);
}
void RoomScheduler::team_step(double elapsed){
    const auto seats=seats_for(world_.mode);
    if(team_mode(world_.mode)){
        for(const auto seat:seats){
            auto& avatar=world_.heroes.heroes.at(seat_index(seat)).value();std::optional<Seat> helper;
            for(const auto mate:seats){
                if(mate==seat||team_of(mate)!=team_of(seat)||world_.heroes.players.at(seat_index(mate))->hp<=0.)continue;
                const auto& other=world_.heroes.heroes.at(seat_index(mate)).value();
                if(other.frame.down.or_missing(0.)<=0.&&touching(avatar,other)){helper=mate;break;}
            }
            auto& progress=state_.revive[seat_index(seat)];
            if(avatar.frame.hp.get()<=0.){
                auto& down=state_.down_since[seat_index(seat)];
                if(!down){down=world_.heroes.time;++state_.fallen_count;services_.emit(RoomFallenEvent{seat});}
                progress=helper?progress+elapsed:0.;
                if(progress+1e-9>=4.)revive(seat,helper.value());
            }else{
                progress=0.;
                if(helper&&avatar.frame.down.or_missing(0.)>0.&&avatar.frame.recovery.or_missing(0.)<2000.){
                    avatar.frame.recovery.set(2000.);services_.emit(RoomHelpedEvent{seat,*helper});
                }
            }
        }
        publish_heroes();services_.sync_public(false);
    }
    if(state_.director)services_.director_step();
    if(state_.result)return;
    std::array<bool,2> standing{};
    for(const auto seat:seats)if(world_.heroes.players.at(seat_index(seat))->hp>0.)standing[team_of(seat)==Seat::plant?0:1]=true;
    if(scripted(world_.mode)){
        if(!standing[0])state_.result=RoomResult{RoomWinner::zombie,RoomResultReason::hero_death,state_.tick};
        else if(state_.director&&services_.director_cleared())state_.result=RoomResult{RoomWinner::plant,RoomResultReason::waves_cleared,state_.tick};
    }else if(!standing[0]||!standing[1]){
        state_.result=RoomResult{!standing[0]&&!standing[1]?RoomWinner::draw:!standing[0]?RoomWinner::zombie:RoomWinner::plant,
                                RoomResultReason::hero_death,state_.tick};
    }
    finish_result();
}
void RoomScheduler::step(int64_t steps){
    for(int64_t unused=0;unused<steps;++unused){
        if(state_.result||!state_.audit_error.empty())return;
        state_.defer_capture=state_.capture_demand&&(unused<steps-1||state_.capture_intermediate);
        services_.capture_deferred(state_.defer_capture);++state_.capture_frames;state_.capture_deferred+=state_.defer_capture;
        ++state_.tick;world_.heroes.time=state_.tick*rules_.dt();
        if(state_.director&&state_.director_cycle)services_.cycle_step();
        if(!state_.deathmatch&&world_.heroes.time>=rules_.deathmatch_seconds)begin_deathmatch();
        for(size_t i=0;i<world_.heroes.players.size();++i)if(world_.heroes.players[i]&&state_.tick-state_.players[i].last_input_tick>int64_t(rules_.tick_rate)*2)clear_input(Seat(i));
        const int64_t phase=int64_t(state_.native_phase)+250,count=phase/rules_.tick_rate;
        state_.native_phase=int(phase%rules_.tick_rate);
        const auto started=services_.monotonic_seconds();
        for(int64_t index=0;index<count;++index)native_.run(index==count-1);
        if(count){
            const auto ratio=(services_.monotonic_seconds()-started)/(count/250.);
            state_.native_cost_ratio=state_.native_cost_ratio?*state_.native_cost_ratio*(1.-.08)+ratio*.08:ratio;
        }
        const auto elapsed=count/250.;auto recovery_rules=rules_.recovery;recovery_rules.deathmatch=state_.deathmatch;
        recovery_.advance(native_state_.present,elapsed,recovery_rules);
        publish_heroes();services_.sync_public(true);economy_.advance(native_state_.present,rules_.dt(),rules_.economy);
        if(!state_.ai_subsidy_seats.empty())subsidy();
        if(state_.zombie_secrets)services_.zombie_secrets_step(elapsed);
        if(world_.mode!=MatchMode::duel)team_step(elapsed);
        else{
            std::vector<Seat> dead;for(size_t i=0;i<world_.heroes.players.size();++i)if(world_.heroes.players[i]&&world_.heroes.players[i]->hp<=0.)dead.push_back(Seat(i));
            if(!dead.empty()){
                state_.result=RoomResult{dead.size()==2?RoomWinner::draw:dead.front()==Seat::plant?RoomWinner::zombie:RoomWinner::plant,
                                        RoomResultReason::hero_death,state_.tick};finish_result();
            }
        }
    }
    state_.defer_capture=false;services_.capture_deferred(false);
}
double AdaptiveRoomPacing::sample(double cost,double simulated){
    if(simulated<=0.)return scale;
    const auto current=std::max(0.,cost)/simulated,alpha=std::min(1.,simulated/.5);
    ratio=observed==0.?current:ratio+(current-ratio)*alpha;observed+=simulated;
    over=ratio>.9?over+simulated:0.;under=ratio*scale<.58?under+simulated:0.;
    if(observed>=1.&&over>=.35){scale=std::max(.1,std::min(scale,.75/std::max(.001,ratio)));over=0.;}
    else if(under>=1.5){scale=std::min(1.,scale+.1);under=0.;}
    return scale;
}
int RoomWallClock::credit(double dt,double room_dt){
    if(!std::isfinite(dt)||dt<0.||dt>2.)return 0;
    if(!std::isfinite(room_dt)||room_dt<=0.)throw std::invalid_argument("invalid room dt");
    accumulator+=dt*pacing.scale;return int(std::min(12.,std::trunc((accumulator+1e-9)/room_dt)));
}
void RoomWallClock::consume(int count,double room_dt,double spent){
    accumulator-=count*room_dt;pacing.sample(spent,count*room_dt);
}
} // namespace pvz::typed72
