#include "sim/typed/hero_recovery.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
bool has(const HeroPlayer& p,std::string_view secret){return std::find(p.secrets.begin(),p.secrets.end(),secret)!=p.secrets.end();}
}
void HeroRecovery::water_damage(std::span<const Seat> seats,double elapsed,bool deathmatch){
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    for(const auto side:seats){
        auto& a=world_.heroes.hero(side);const auto& p=*a.frame.position.get();bool wet=false;
        if(deathmatch)for(const double dx:{-tile*.2,0.,tile*.2})for(const double dy:{.1,-tile*.5,-tile*1.2})
            if(map_.water_at({p.x+dx,p.y+dy},tile,width))wet=true;
        double progress=wet?a.water_damage_clock.or_missing(0.)+elapsed:0.;
        auto& hp=a.frame.hp.get();
        if(wet && hp>0. && progress+1e-9>=1.){
            const double amount=std::trunc(progress+1e-9);progress-=amount;hp=std::max(0.,hp-amount);
            world_.runtime.events.emplace_back(EnvironmentalDamageEvent{side,amount});
        }
        a.water_damage_clock.set(progress);
    }
}
void HeroRecovery::masochist(Seat side){
    auto& h=world_.heroes;auto& a=h.hero(side);const auto hp=a.frame.hp.get();const auto before=a.previous_hp.or_missing(hp);
    const auto& p=h.players.at(seat_index(side)).value();
    const bool team=world_.mode==MatchMode::duo || world_.mode==MatchMode::coop;
    if(!has(p,"secret:抖M") || hp>=before || (team && hp<=0.) || h.time<a.masochist_ready.or_missing(0.))return;
    a.masochist_ready.set(h.time+3.);
    const auto id=resources_.create(side,h.time<120.?15.:25.,p.position,"masochist");
    resources_.remove_motion(id);resources_.collect(id);
}
void HeroRecovery::sturdy(Seat side){
    auto& h=world_.heroes;auto& a=h.hero(side);auto& p=h.players.at(seat_index(side)).value();
    const bool down=a.frame.down.or_missing(0.)>0. && a.frame.hp.or_missing(0.)>0.;
    if(!down){a.sturdy_down.erase();return;}
    if(!has(p,"secret:强健") || a.sturdy_down.or_missing(false))return;
    a.sturdy_down.set(true);std::vector<std::string> cut;
    for(auto& [key,ready]:p.cooldowns){
        const auto remaining=ready-h.time;
        if(remaining>0.){ready=h.time+remaining*(1.-.5);cut.push_back(key);}
    }
    std::sort(cut.begin(),cut.end());h.events.emplace_back(SturdyEvent{side,std::move(cut)});
}
void HeroRecovery::regenerate(double elapsed,const HeroRecoveryRules& rules){
    auto& heroes=world_.heroes;const double now=heroes.tick/250.;
    for(size_t i=0;i<heroes.heroes.size();++i){
        if(!heroes.contains(Seat(i)))continue;
        auto& a=heroes.hero(Seat(i));auto& hp=a.frame.hp.get();const auto maximum=a.max_hp.get();
        if(hp<a.previous_hp.get()){a.last_damage.set(now);a.regen_progress.set(0.);}
        const auto quiet=now-a.last_damage.get();
        if(0.<hp && hp<maximum && quiet>=rules.delay){
            const auto eligible=std::max(0.,std::min(elapsed,quiet-rules.delay));
            auto& progress=a.regen_progress.get();progress+=eligible;
            if(progress+1e-9>=rules.interval){
                if(rules.interval==0.)throw std::domain_error("zero native regeneration interval");
                const double count=std::trunc((progress+1e-9)/rules.interval);
                progress-=count*rules.interval;const auto healed=std::min(maximum-hp,count*rules.amount);
                hp+=healed;heroes.events.emplace_back(HeroHealEvent{Seat(i),healed});
            }
        }else a.regen_progress.set(0.);
        a.previous_hp.set(hp);
    }
    heroes.sync_proxies();
}
void HeroRecovery::advance(std::span<const Seat> present,double elapsed,const HeroRecoveryRules& rules){
    water_damage(present,elapsed,rules.deathmatch);
    for(const auto side:seats_for(world_.mode))if(team_of(side)==Seat::plant)masochist(side);
    for(const auto side:seats_for(world_.mode))if(team_of(side)==Seat::plant)sturdy(side);
    regenerate(elapsed,rules);
}
} // namespace pvz::typed72
