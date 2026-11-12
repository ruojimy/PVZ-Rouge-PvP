#include "sim/typed/ai_observation_builder.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <tuple>

namespace pvz::typed72 {
namespace {
double pct(double hp,double max_hp){return py::roundn(std::clamp(hp/std::max(1.,max_hp),0.,1.),2);}
bool is_support(const std::optional<std::string>& b){return b&&(b=="pot"||b=="lily");}
template<class T,class Less>void cap_sorted(std::vector<T>& values,size_t cap,Less less){std::stable_sort(values.begin(),values.end(),less);if(values.size()>cap)values.resize(cap);}
}
AiObservationBuilder::AiObservationBuilder(Seat side,double width,double height,double tile,bool night)
    :side_(side),width_(width),height_(height),tile_(tile),night_(night){
    if((side!=Seat::plant&&side!=Seat::zombie)||!std::isfinite(width)||width<=0.||!std::isfinite(tile)||tile<=0.)throw std::invalid_argument("invalid AI observation geometry or faction");
}
int AiObservationBuilder::zone(double x)const{return int(py::mod(x,width_)/width_*6.)%6;}
std::array<AiObservedZone,6> AiObservationBuilder::zones(std::span<const AiUnitView> units)const{
    std::array<AiObservedZone,6> out;std::array<double,6> friendly{},enemy{};
    for(const auto& u:units)if(u.hp>0.){
        const auto value=u.card_info.cost.value_or(0.)*std::clamp(u.hp/std::max(1.,u.max_hp),0.,1.);
        (u.side==side_?friendly:enemy)[zone(u.position.x)]+=value;
    }
    for(int i=0;i<6;++i){const double total=friendly[i]+enemy[i];out[i]={i,int64_t(friendly[i]),int64_t(enemy[i]),total?py::roundn((friendly[i]-enemy[i])/total,2):0.};}
    return out;
}
std::vector<AiObservedThreat> AiObservationBuilder::threats(const AiObservationFrame& frame)const{
    std::vector<AiObservedThreat> out;const auto& me=*frame.mine;const double maximum=std::max(1.,me.max_hp);
    for(const auto& shot:frame.shots){
        if(shot.side==side_||std::abs(ai_wrap_delta(shot.position.x,me.position.x,width_))>900.)continue;
        const double rx=me.w*.6+14.+shot.splash*.5,ry=me.h*.5+14.+shot.splash*.5;
        std::optional<double> impact;
        for(int index=1;index<=int(1.2/.04);++index){const double t=index*.04;
            const double x=shot.position.x+shot.velocity.x*t,y=shot.position.y+shot.velocity.y*t+.5*shot.gravity*t*t;
            if(std::abs(ai_wrap_delta(x,me.position.x,width_))<=rx&&std::abs(me.position.y-me.h*.5-y)<=ry){impact=t;break;}}
        if(!impact)continue;
        double severity=std::clamp(shot.damage/maximum,.05,1.);
        if(shot.control)severity=std::clamp(severity+.25,0.,1.);
        if(shot.slow)severity=std::clamp(severity+.1,0.,1.);
        out.push_back({shot.asset.empty()?"projectile":shot.asset,ai_wrap_delta(me.position.x,shot.position.x,width_)<0.,int64_t(*impact*1000.),py::roundn(severity,2),shot.splash!=0.,true});
    }
    for(const auto& unit:frame.units){
        if(unit.side==side_||!unit.mobile||unit.hp<=0.)continue;
        const double offset=ai_wrap_delta(me.position.x,unit.position.x,width_);
        if(std::abs(offset)>tile_*3.||std::abs(unit.position.y-me.position.y)>tile_*1.6)continue;
        const double speed=std::max(20.,unit.velocity.x?std::abs(unit.velocity.x):40.);
        const std::string name=unit.card_info.name&&!unit.card_info.name->empty()?*unit.card_info.name:unit.card.empty()?"melee":unit.card;
        out.push_back({name,offset<0.,int64_t(std::max(0.,std::abs(offset)-tile_*.8)/speed*1000.),py::roundn(std::clamp(unit.card_info.damage/maximum+.1,.1,1.),2),false,false});
    }
    cap_sorted(out,6,[](const auto& a,const auto& b){return std::tuple(-a.severity,a.eta_ms)<std::tuple(-b.severity,b.eta_ms);});return out;
}
std::vector<AiObservedTarget> AiObservationBuilder::plant_targets(const AiObservationFrame& frame,bool supports)const{
    std::vector<AiObservedTarget> out;if(side_!=Seat::plant)return out;
    const auto& hero=*frame.mine;
    for(const auto& unit:frame.units){
        if(unit.side!=side_||unit.hp<=0.)continue;
        const auto behavior=unit.behavior&&!unit.behavior->empty()?*unit.behavior:unit.card_info.behavior;
        if(supports){
            if(behavior!="pot"&&behavior!="lily")continue;
            bool occupied=false;
            for(const auto& other:frame.units)if(&other!=&unit&&other.side==side_&&other.hp>0.&&!is_support(other.behavior)&&
                std::abs(ai_wrap_delta(unit.position.x,other.position.x,width_))<tile_*.5&&std::abs(unit.position.y-tile_-other.position.y)<tile_*.5){occupied=true;break;}
            if(occupied)continue;
        }else if(unit.awake)continue;
        const double dx=ai_wrap_delta(hero.position.x,unit.position.x,width_),dy=unit.position.y-hero.position.y;
        if(std::abs(dx)>480.||dy< -384.||dy>256.)continue;
        out.push_back({unit.position,int64_t(dx),int64_t(dy),unit.position.y-tile_-tile_*.5,zone(unit.position.x),unit.card,unit.card_info.producer});
    }
    cap_sorted(out,8,[](const auto& a,const auto& b){return std::abs(a.dx)<std::abs(b.dx);});return out;
}
AiObservation AiObservationBuilder::build(const AiObservationFrame& frame,int64_t plan,int64_t match,int64_t observation){
    if(!frame.mine||!frame.enemy)throw std::invalid_argument("snapshot has no battle players");
    if(frame.enemy_input_present)throw std::invalid_argument("observation requires a peer-masked snapshot");
    const auto& mine=*frame.mine;const auto& enemy=*frame.enemy;
    AiObservation out;out.match_id=match;out.observation_id=observation;out.tick=frame.tick;out.plan_id=plan;out.time=py::roundn(frame.time,1);out.side=side_;out.night=night_||frame.night;out.width=width_;out.deathmatch=frame.deathmatch;
    double income=0.;if(last_time_&&frame.time>*last_time_)income=std::max(0.,mine.resource-*last_resource_)/(frame.time-*last_time_);
    last_time_=frame.time;last_resource_=mine.resource;out.resource=int64_t(mine.resource);out.income=py::roundn(income,1);
    out.hero={pct(mine.hp,mine.max_hp),int64_t(mine.position.x),int64_t(mine.position.y),int64_t(mine.velocity.x),int64_t(mine.velocity.y),zone(mine.position.x),mine.facing,std::max(int64_t(0),mine.jump_cap-mine.jumps),mine.poison,mine.grounded,mine.frozen,mine.slowed,mine.buttered,py::roundn(std::max(0.,mine.teleport_ready-frame.time),1)};
    out.enemy_hero={pct(enemy.hp,enemy.max_hp),int64_t(ai_wrap_delta(mine.position.x,enemy.position.x,width_)),int64_t(enemy.position.y-mine.position.y),zone(enemy.position.x),enemy.facing,int64_t(enemy.resource)};
    out.threats=threats(frame);for(const auto& threat:out.threats)out.danger=std::max(out.danger,threat.severity*std::clamp(1.2-threat.eta_ms/1000.,.2,1.2));out.danger=py::roundn(out.danger,2);
    out.zones=zones(frame.units);out.sleeping_plants=plant_targets(frame,false);out.empty_supports=plant_targets(frame,true);
    for(const auto& card:frame.cards)if(!card.secret){const double remaining=std::max(0.,card.cooldown_ready-frame.time);const bool affordable=mine.resource>=card.cost;
        out.cards.push_back({card.id,card.name,card.behavior,card.cost,py::roundn(remaining,1),affordable,remaining<=0.&&affordable&&!(frame.deathmatch&&card.producer),card.producer,card.mushroom,card.range});}
    for(const auto& unit:frame.units){
        if(unit.hp<=0.)continue;
        if(unit.side==side_){++out.my_unit_count;if(unit.card_info.producer&&unit.awake)++out.producer_count;}
        else if(unit.side==(side_==Seat::plant?Seat::zombie:Seat::plant))++out.enemy_unit_count;
        const double dx=ai_wrap_delta(mine.position.x,unit.position.x,width_),dy=unit.position.y-mine.position.y;
        if(unit.side!=side_)out.enemy_units.push_back({unit.card,unit.card_info.name,unit.behavior,int64_t(dx),int64_t(dy),zone(unit.position.x),pct(unit.hp,unit.max_hp),unit.mobile});
        if(side_==Seat::zombie&&unit.side==Seat::zombie&&unit.behavior=="grave"&&out.deploy_anchors.size()<8)out.deploy_anchors.push_back({unit.id,zone(unit.position.x),int64_t(unit.position.x),pct(unit.hp,unit.max_hp)});
        if(side_==Seat::plant&&unit.side==Seat::plant&&std::abs(dx)<=480.){
            AiObservedTool tool{unit.id,unit.card,unit.card_info.name,int64_t(dx),int64_t(dy),zone(unit.position.x),pct(unit.hp,unit.max_hp)};
            if(unit.card=="plant:玉米加农炮")out.cannons.push_back(tool);
            if(!unit.mobile&&unit.behavior!="cannon")out.shovel_targets.push_back(std::move(tool));
        }
    }
    cap_sorted(out.enemy_units,8,[](const auto& a,const auto& b){return std::abs(a.dx)<std::abs(b.dx);});
    cap_sorted(out.cannons,6,[](const auto& a,const auto& b){return std::abs(a.dx)<std::abs(b.dx);});
    cap_sorted(out.shovel_targets,6,[](const auto& a,const auto& b){return std::tuple(a.hp_pct,std::abs(a.dx))<std::tuple(b.hp_pct,std::abs(b.dx));});out.cannon_aimed=mine.cannon_aimed;
    std::vector<std::pair<double,AiObservedCollectable>> collectable;
    if(side_==Seat::plant)for(const auto& value:frame.resources){
        if(value.side!=Seat::plant)continue;const double dx=ai_wrap_delta(mine.position.x,value.position.x,width_),dy=value.position.y-mine.position.y;
        if(std::abs(dx)>480.||dy< -384.||dy>256.)continue;
        collectable.push_back({std::abs(dx),{value.id,int64_t(dx),int64_t(value.amount),value.source}});
    }
    cap_sorted(collectable,6,[](const auto& a,const auto& b){return a.first<b.first;});for(auto& value:collectable)out.collectable.push_back(std::move(value.second));
    return out;
}
} // namespace pvz::typed72
