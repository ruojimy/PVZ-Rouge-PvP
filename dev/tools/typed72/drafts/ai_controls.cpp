#include "sim/typed/ai_controls.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
template<class T>InputField<T> value(T v){return {InputFieldState::value,std::move(v)};}
template<class T>double lookup(const std::vector<std::pair<std::string,T>>& pairs,const std::string& key,double fallback){const auto i=std::find_if(pairs.begin(),pairs.end(),[&](const auto& p){return p.first==key;});return i==pairs.end()?fallback:double(i->second);}
bool solid(const TargetSight& map,Point p,double tile,double width){const auto row=py::floordiv(p.y,tile);if(row<0.||row>=map.solid.size())return false;const auto& cells=map.solid.at(size_t(row));return cells.at(size_t(py::floordiv(py::mod(p.x,width),tile)))!=0;}
}
std::vector<AiClick> AiLiveControls::targets(Seat side,const std::string& key,const AiResolvedCard& card,const AiControlFrame& f,const AiPlan& plan){
    std::vector<AiClick> points;const auto dx=ai_wrap_delta(f.me.position.x,f.enemy.position.x,f.width);
    const auto in_view=[&](const AiUnitView& u){return std::abs(ai_wrap_delta(f.me.position.x,u.position.x,f.width))<=480.&&u.position.y-f.me.position.y>=-384.&&u.position.y-f.me.position.y<=256.;};
    if(side==Seat::zombie&&card.behavior!=AiCardBehavior::grave){
        for(const auto& u:f.units)if(u.hp>0.&&u.side==side&&u.grave&&in_view(u))points.push_back({{u.position.x,u.position.y-24.},u.id});
        const auto desired=py::mod(f.me.position.x+(dx>=0.?1.:-1.)*plan.deploy_ahead,f.width);
        std::stable_sort(points.begin(),points.end(),[&](const auto& a,const auto& b){return std::abs(ai_wrap_delta(desired,a.point.x,f.width))+std::abs(a.point.y-f.me.position.y)<std::abs(ai_wrap_delta(desired,b.point.x,f.width))+std::abs(b.point.y-f.me.position.y);});return points;
    }
    if(card.behavior==AiCardBehavior::coffee){for(const auto& u:f.sleeping_plants)points.push_back({{u.position.x,u.position.y-24.},{}});return points;}
    if(key=="plant:墓碑吞噬者"){
        for(const auto& u:f.units)if(u.hp>0.&&u.side!=side&&u.grave&&in_view(u))points.push_back({{u.position.x,u.position.y-24.},{}});return points;
    }
    const auto ahead=card.producer?-plan.economy_offset:plan.deploy_ahead;
    const auto desired=py::mod(f.me.position.x+(dx>=0.?1.:-1.)*ahead,f.width);
    std::vector<AiClick> floor;
    for(int z=0;z<6;++z)for(const auto p:services_.candidates(z,f.me.position,24))floor.push_back({p,{}});
    if(card.behavior!=AiCardBehavior::pot&&card.behavior!=AiCardBehavior::lily)for(const auto& u:f.empty_supports)points.push_back({{u.position.x,u.plant_y},{}});
    const auto rank=[&](const AiClick& p){return std::abs(ai_wrap_delta(desired,p.point.x,f.width))+std::abs(p.point.y-f.me.position.y)*1.3;};
    const auto compare=[&](const auto& a,const auto& b){return rank(a)<rank(b);};
    std::stable_sort(points.begin(),points.end(),compare);std::stable_sort(floor.begin(),floor.end(),compare);points.insert(points.end(),floor.begin(),floor.end());
    std::vector<AiClick> distinct;for(const auto& p:points)if(std::find(distinct.begin(),distinct.end(),p)==distinct.end()){distinct.push_back(p);if(distinct.size()==48)break;}return distinct;
}
void AiLiveControls::step(Seat owner,const AiControlFrame& f,const AiPlan& plan){
    const auto side=team_of(owner);const auto t=f.time;const auto& me=f.me;const auto& enemy=f.enemy;
    ++state_.samples;if(state_.last_sample)state_.max_gap=std::max(state_.max_gap,t-*state_.last_sample);state_.last_sample=t;
    const auto dx=ai_wrap_delta(me.position.x,enemy.position.x,f.width);auto target=py::mod(plan.target_x.value_or(me.position.x),f.width);
    if(plan.stance==AiStance::hunt||plan.stance==AiStance::kite||plan.stance==AiStance::retreat){const auto gap=plan.stance==AiStance::retreat?std::max(600.,plan.distance):plan.distance;target=py::mod(enemy.position.x-(dx>=0.?1.:-1.)*gap,f.width);}
    const auto delta=ai_wrap_delta(me.position.x,target,f.width);int move=std::abs(delta)>24.?(delta>0.?1:-1):0;
    const auto previous=state_.previous.value_or(AiControlState::Position{me.position.x,t,false});bool blocked=previous.blocked;
    if(t-previous.time>=.4){blocked=move&&std::abs(ai_wrap_delta(previous.x,me.position.x,f.width))<10.;state_.previous=AiControlState::Position{me.position.x,t,blocked};}
    else if(!state_.previous)state_.previous=previous;
    const bool wall=move&&solid(f.terrain,{me.position.x+move*36.,me.position.y-24.},f.tile,f.width);
    const auto threat=std::find_if(f.threats.begin(),f.threats.end(),[](const auto& x){return x.eta_ms<300.;});
    const bool evade=plan.evade&&threat!=f.threats.end();if(evade)move=threat->from_left?1:-1;
    const bool jumping=(plan.jump_on_block&&(wall||blocked))||(evade&&plan.dodge_jump)||(plan.jump_every>0.&&move);
    const bool jump=jumping&&me.jumps_left>0&&t>=state_.next_jump;if(jump)state_.next_jump=t+(plan.jump_every!=0.?std::max(.25,plan.jump_every):.32);
    services_.send(owner,MoveCommand{value(int64_t(move)),value(jump),jump});
    if(side==Seat::plant){
        for(const auto& id:f.collectable)services_.send(owner,CollectCommand{value(id)});
        if(plan.mark&&std::abs(dx)<350.&&std::abs(enemy.position.y-me.position.y)<220.&&t>=state_.mark_at){services_.send(owner,MarkCommand{});state_.mark_at=t+1.;}
    }else if(!plan.command||*plan.command!=f.command)services_.send(owner,ToggleCommand{});
    if(me.hp/std::max(1.,me.max_hp)<plan.teleport_hp&&t>=me.teleport_ready&&t>=state_.teleport_at){
        std::vector<const AiUnitView*> anchors;for(const auto& u:f.units)if(u.hp>0.&&u.side==side&&(side==Seat::plant||u.grave))anchors.push_back(&u);
        std::stable_sort(anchors.begin(),anchors.end(),[&](auto a,auto b){return std::abs(ai_wrap_delta(a->position.x,enemy.position.x,f.width))>std::abs(ai_wrap_delta(b->position.x,enemy.position.x,f.width));});
        for(size_t i=0;i<std::min<size_t>(4,anchors.size());++i){NativeCommand c{NativeCommandKind::teleport};c.target=value(anchors[i]->id);if(services_.send(owner,std::move(c)).empty()){state_.teleport_at=t+1.;return;}}
        state_.teleport_at=t+1.;
    }
    if(t<state_.next_deploy)return;state_.next_deploy=t+.2;
    const auto counts=ai_own_counts(f.units,side);bool preview=false;
    std::vector<std::pair<std::string,AiResolvedCard>> pending,supports;std::vector<std::pair<std::string,std::vector<std::string>>> refusals;
    for(const auto& key:plan.priority){
        const auto card=services_.resolve(owner,key);
        if(lookup(counts,key,0.)>=lookup(plan.quotas,key,999.))continue;
        if(card.behavior==AiCardBehavior::pot||card.behavior==AiCardBehavior::lily){supports.emplace_back(key,card);continue;}
        if(f.deathmatch&&card.producer)continue;if(lookup(me.cooldowns,key,0.)>t)continue;
        auto reserve=std::max(0.,plan.reserve);
        if(plan.save_for&&*plan.save_for!=key&&lookup(counts,*plan.save_for,0.)<lookup(plan.quotas,*plan.save_for,999.))reserve=std::max(reserve,services_.resolve(owner,*plan.save_for).cost);
        if(me.resource<card.cost+reserve)continue;
        if(card.mushroom&&!f.night){if(std::find(plan.priority.begin(),plan.priority.end(),"plant:咖啡豆")==plan.priority.end()||!f.sleeping_plants.empty())continue;if(me.resource<card.cost+services_.resolve(owner,"plant:咖啡豆").cost+reserve)continue;}
        if(card.behavior==AiCardBehavior::coffee&&f.sleeping_plants.empty())continue;
        pending.emplace_back(key,card);std::vector<std::string> reasons;
        if(!preview){services_.begin_preview();preview=true;}
        for(const auto& click:targets(side,key,card,f,plan)){
            const auto p=services_.placement(owner,key,click);
            if(!p.error.empty()||!p.placement){if(!p.error.empty()&&std::find(reasons.begin(),reasons.end(),p.error)==reasons.end())reasons.push_back(p.error);continue;}
            NativeCommand c{NativeCommandKind::deploy};c.card=value(key);c.x=value(click.point.x);c.y=value(click.point.y);c.facing=value(int64_t(dx>=0.?1:-1));if(click.grave)c.grave=value(*click.grave);else c.grave.state=InputFieldState::null;
            const auto error=services_.send(owner,std::move(c));state_.status={t,key,{},error,counts};if(error.empty())return;
        }
        if(reasons.empty())reasons.push_back("no candidate in view");if(reasons.size()>2)reasons.resize(2);refusals.emplace_back(key,std::move(reasons));
    }
    if(side==Seat::plant&&!pending.empty()&&f.empty_supports.size()<2){
        for(const auto& [key,card]:supports){
            if(lookup(me.cooldowns,key,0.)>t||me.resource<card.cost)continue;
            for(const auto& click:targets(side,key,card,f,plan)){
                const auto p=services_.placement(owner,key,click);if(!p.error.empty()||!p.placement)continue;
                NativeCommand c{NativeCommandKind::deploy};c.card=value(key);c.x=value(click.point.x);c.y=value(click.point.y);c.facing=value(int64_t(dx>=0.?1:-1));c.grave.state=InputFieldState::null;
                const auto error=services_.send(owner,std::move(c));state_.status={t,key,pending.front().first,error,counts};if(error.empty())return;
            }
        }
    }
    state_.status={t,{},{},{},counts,std::move(refusals),side==Seat::plant&&!pending.empty()&&supports.empty(),blocked};
}
} // namespace pvz::typed72
