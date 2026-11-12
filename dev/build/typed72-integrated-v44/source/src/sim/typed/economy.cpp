#include "sim/typed/economy.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <cmath>
#include <limits>
#include <tuple>

namespace pvz::typed72 {
namespace {
bool contains(std::span<const Seat> seats,Seat seat){return std::find(seats.begin(),seats.end(),seat)!=seats.end();}
bool truth(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
}
Seat Economy::sun_owner(NativeSun& sun,std::span<const Seat> present)const{
    const auto owner=std::exchange(sun.producer,{});
    if(owner && contains(present,*owner))return *owner;
    PlantRef best;
    std::pair<double,std::string> best_key;
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    for(const auto& p:*world_.plant_roster){
        if(std::find(producers_.begin(),producers_.end(),p->kind)==producers_.end())continue;
        const double x=(p->cell.x+.5)*tile,y=(p->cell.y+.5)*tile;
        const auto key=std::pair{std::hypot(wrap_delta(sun.motion.x,x,width),sun.motion.y-y),p->source.id.or_missing(std::string{})};
        if(!best || key<best_key){best=p;best_key=key;}
    }
    if(best && best->source.seat && contains(present,*best->source.seat))return *best->source.seat;
    return Seat::plant;
}
std::optional<double> Economy::death_sun_amount(const NativeSun& sun){
    if(sun.size!=0.)return {};
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    for(auto it=state_.death_points.begin();it!=state_.death_points.end();++it){
        if(std::abs(wrap_delta(it->x,sun.motion.x,width))<=tile && std::abs(it->y-sun.motion.y)<=tile*1.5){
            state_.death_points.erase(it);return 25.;
        }
    }
    return {};
}
void Economy::loose_suns(std::span<const Seat> present,bool multi_plant){
    for(const auto& sun:native_.loose_suns){
        auto amount=std::exchange(sun->bloom_amount,{});
        if(!amount)amount=death_sun_amount(*sun);
        const auto owner=multi_plant?sun_owner(*sun,present):Seat::plant;
        const auto p=sun->motion;
        const auto id=resources_.create(owner,amount.value_or(sun->size==0.?15.:25.),{p.x,p.y},"native_producer");
        resources_.set_motion(id,*sun);
    }
    native_.loose_suns.clear();
}
double Economy::day_payments(int64_t previous,int64_t now,double interval){
    if(!state_.subsidy)return std::max(0.,py::floordiv(double(now),interval)-py::floordiv(double(previous),interval));
    const bool occupied=std::any_of(world_.targets->begin(),world_.targets->end(),[&](const CombatTarget& target){
        if(target.is_hero())return false;
        const auto& u=*target.unit;
        return !u.protection.grave && !u.orphan_barrel && !u.source.plant.present() && u.body.hp>0. &&
               u.source.content.or_missing(std::string{})!="抓人草触手" && world_.heroes.owner(source_ref(target.unit))==Seat::zombie;
    });
    state_.subsidy_phase+=(now-previous)*(occupied?1.:2.);
    const double count=py::floordiv(state_.subsidy_phase,interval);
    state_.subsidy_phase=py::mod(state_.subsidy_phase,interval);
    return std::trunc(count);
}
void Economy::sky(double elapsed,const EconomyRules& rules,bool multi_plant){
    state_.sky_progress=state_.night?0.:state_.sky_progress+elapsed;
    if(state_.night || state_.sky_progress+1e-9<state_.sky_interval)return;
    state_.sky_progress=std::max(0.,state_.sky_progress-state_.sky_interval);
    const auto width=world_.world_width.get(),tile=world_.runtime.tile;
    const auto x=world_.room_rng.uniform(0.,width);double floor=world_.world_height.get();
    const auto col=size_t(std::floor(py::mod(x,width)/tile));
    for(size_t row=0;row<map_.solid.size();++row){
        const auto& cells=map_.solid[row];if(cells.empty())throw std::logic_error("empty published sky row");
        if(cells.at(col%cells.size())){floor=row*tile;break;}
    }
    const auto y=std::max(0.,std::min(world_.heroes.players[seat_index(Seat::plant)]->position.y-80.,floor-tile));
    const auto id=resources_.create(Seat::plant,rules.sky_amount,{x,y},"sky");
    if(multi_plant)resources_.find(id)->shared.set(true);
}
void Economy::graves(){
    for(const auto& entry:world_.native_objects.entries()){
        const auto* pointer=std::get_if<ZombieRef>(&entry.object);
        if(!pointer)continue;
        auto& u=**pointer;
        if(!u.protection.grave || u.body.hp<=0.)continue;
        const auto& card=world_.protection.policy(Seat::zombie,u.protection.card.get());
        if(!card.producer)continue;
        const auto age=world_.heroes.time-u.born.or_missing(0.);
        const bool mature=age>=card.mature_at.or_missing(std::numeric_limits<double>::infinity());
        if(mature && card.mature_hp.present() && !card.mature_hp.is_null() && card.mature_hp.get()!=0. && !truth(u.mature)){
            u.body.hp*=2.;u.max_hp.set(card.mature_hp.get());u.mature.set(true);
        }
        auto& progress=state_.grave_progress[entry.key];
        const auto period=truth(u.produced)?card.period.get():6.;
        if(progress+1e-9>=period){
            progress=std::max(0.,progress-period);u.produced.set(true);
            const auto amount=mature?card.mature_yield.or_missing(card.yield_amount.get()):card.yield_amount.get();
            const auto& p=u.body.motion.get();
            resources_.create(u.source.seat.value_or(Seat::zombie),amount,{p.x,p.y},entry.key);
        }
    }
}
void Economy::advance(std::span<const Seat> present,double elapsed,const EconomyRules& rules){
    const auto seats=seats_for(world_.mode);
    const bool multi_plant=std::count_if(seats.begin(),seats.end(),[](Seat s){return team_of(s)==Seat::plant;})>1;
    resources_.merge_suns();loose_suns(present,multi_plant);
    const auto previous=state_.previous_tick,now=world_.heroes.tick;state_.previous_tick=now;
    if(!state_.night){
        const auto interval=std::max(1.,py::round0(rules.day_interval*250.));
        const auto count=day_payments(previous,now,interval);
        for(double i=0.;i<count;++i)for(const auto side:seats){
            if(team_of(side)!=Seat::zombie)continue;
            resources_.create(side,rules.day_amount,world_.heroes.players[seat_index(side)]->position,"day_income");
        }
    }
    sky(elapsed,rules,multi_plant);graves();resources_.settle(rules.sun_lifetime);
}
void Economy::plant_production(const ProductionRules& rules){
    for(const auto& p:*world_.plant_roster){
        if(p->sleep.present() || std::find(producers_.begin(),producers_.end(),p->kind)==producers_.end())continue;
        const auto& card=world_.protection.policy(Seat::plant,"plant:"+p->kind);
        const auto hp=p->hp.or_missing(0.);
        if(!p->rest_hp.present() || p->rest_hp.is_null() || hp<p->rest_hp.get())p->rest_since.set(double(world_.heroes.tick));
        p->rest_hp.set(hp);
        const auto quiet=(world_.heroes.tick-p->rest_since.get())/250.;
        const auto ramp=(quiet-rules.rest_seconds)/std::max(1e-9,rules.ramp_seconds);
        const auto rest=1.+rules.rest_bonus*std::min(1.,std::max(0.,ramp));
        const auto aura=p->aura_factor.or_missing(1.);
        if(aura==0.)throw std::domain_error("zero producer aura interval");
        auto due=p->sun_due.or_missing(1500.)-(rules.deathmatch?rules.multiplier:1.)*rest/aura;
        p->sun.set(1000000.);
        if(due<=125. && (!p->burst.present() || p->burst.is_null() || p->burst.get()==0.))p->burst.set(1.);
        if(due<=1e-7){p->burst.set(124.);due+=card.period.get()*250.;}
        else if(p->burst.present() && !p->burst.is_null() && p->burst.get()==124.)p->burst.set(123.);
        p->sun_due.set(due);
    }
}
} // namespace pvz::typed72
