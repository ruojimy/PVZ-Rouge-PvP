#include "sim/typed/ai_tactical_base.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <tuple>
namespace pvz::typed72 {
namespace {
template<class T>InputField<T> value(T v){return {InputFieldState::value,std::move(v)};}
std::string prefix(std::string_view text,size_t count){size_t i=0,n=0;for(;i<text.size();++i)if((static_cast<unsigned char>(text[i])&0xc0)!=0x80&&n++==count)break;return std::string(text.substr(0,i));}
}
AiTacticalContext::AiTacticalContext(const AiTacticalFrame& f,AiTacticalServices& s):frame(f),services(s){
    for(const auto& u:f.units)if(u.hp>0.){living.push_back(&u);(u.side==f.side?own:enemy).push_back(&u);}
}
bool AiTacticalContext::in_view(Point hero,Point point,double width){const auto y=point.y-hero.y;return std::abs(ai_wrap_delta(hero.x,point.x,width))<=472.&&y>=-376.&&y<=248.;}
bool AiTacticalContext::ready(const std::string& key,double reserve){const auto& card=services.card(key);return card.cooldown_ready<=frame.time&&!(frame.deathmatch&&card.producer)&&frame.me.resource>=card.cost+reserve;}
const std::vector<AiFieldSpot>& AiTacticalContext::spots(bool free){
    auto& cached=cached_spots_[free?1:0];if(cached)return *cached;cached.emplace();auto& out=*cached;
    for(int zone=0;zone<6;++zone)for(const auto& point:frame.field.candidates(zone,frame.me.position.x,frame.me.position.y,40)){
        if(!in_view(frame.me.position,point.point,frame.width))continue;
        if(free){bool occupied=false;for(const auto* u:living)if(!u->mobile&&u->behavior!="pot"&&u->behavior!="lily"&&std::abs(ai_wrap_delta(point.point.x,u->position.x,frame.width))<frame.tile*.6&&std::abs(u->position.y-point.point.y)<frame.tile*1.1){occupied=true;break;}if(occupied)continue;}
        out.push_back(point);
    }return out;
}
int AiTacticalBase::drive(AiTacticalContext& c,double target_x,bool jump_wish,double tolerance){
    const auto& f=c.frame;const double delta=ai_wrap_delta(f.me.position.x,target_x,f.width),t=f.time;int move=std::abs(delta)<=tolerance?0:delta>=0.?1:-1;
    if(move&&std::abs(delta)>900.){
        if(state_.blocked){if(!state_.stuck_since||!*state_.stuck_since)state_.stuck_since=t;if(t-*state_.stuck_since>2.5){state_.detour_until=t+10.;state_.stuck_since.reset();}}
        else state_.stuck_since.reset();if(t<state_.detour_until)move=-move;
    }else state_.stuck_since.reset();
    if(!state_.last_position||t-state_.last_position->second>=.35){state_.blocked=move&&state_.last_position&&std::abs(ai_wrap_delta(state_.last_position->first,f.me.position.x,f.width))<8.;state_.last_position=std::pair(f.me.position.x,t);}
    bool wall=false;if(move){const auto row=int64_t(py::floordiv(f.me.position.y-24.,f.tile));const auto column=size_t(py::floordiv(py::mod(f.me.position.x+move*36.,f.width),f.tile));if(row>=0&&size_t(row)<f.terrain.solid.size())wall=f.terrain.solid[size_t(row)].at(column)!=0;}
    const bool want=jump_wish||(move&&(wall||state_.blocked));bool jump=false;
    if(state_.jump_down)state_.jump_down=false;else if(want&&t>=state_.next_jump){jump=true;state_.jump_down=true;state_.next_jump=t+.3;}
    c.services.send(f.owner,MoveCommand{value(int64_t(move)),value(jump),jump});return move;
}
std::string AiTacticalBase::try_deploy(AiTacticalContext& c,const std::string& key,Point point,std::optional<std::string> grave,int facing){
    const auto& f=c.frame;const auto memo=key+"|"+std::to_string(int64_t(py::floordiv(point.x,8.)))+"|"+std::to_string(int64_t(py::floordiv(point.y,8.)))+"|"+grave.value_or("None");
    if(const auto it=state_.failed.find(memo);it!=state_.failed.end()&&it->second>f.time)return "memo";
    const auto preview=c.services.preview(f.owner,key,point,grave);
    if(!preview.error.empty()||!preview.placement){state_.failed[memo]=f.time+3.;const auto colon=key.find(':');if(colon==std::string::npos)throw std::out_of_range("AI card has no faction prefix");const auto next=key.find(':',colon+1);const auto name=key.substr(colon+1,next==std::string::npos?next:next-colon-1);++state_.log["fail:"+name+":"+prefix(preview.error.empty()?"none":preview.error,12)];return preview.error.empty()?"no placement":preview.error;}
    NativeCommand command{NativeCommandKind::deploy};command.card=value(key);command.x=value(point.x);command.y=value(point.y);command.facing=value(int64_t(facing));command.grave=grave?value(*grave):InputField<std::string>{InputFieldState::null,{}};
    const auto error=c.services.send(f.owner,std::move(command));if(error.empty()){++state_.log["deploy:"+key];c.services.reset_preview();}return error;
}
std::optional<int> AiTacticalBase::ladder_drive(AiTacticalContext& c,double post,double goal_y,std::optional<AiSupportReason> reason){
    const auto& f=c.frame;if(f.mode!=AiTeamMode::coop&&f.mode!=AiTeamMode::duo&&f.mode!=AiTeamMode::pve)return {};
    bool danger=f.deathmatch||state_.recovering||(state_.hold_refuge_until&&f.time<*state_.hold_refuge_until)||f.me.hp<.4*std::max(1.,f.me.max_hp)||reason==AiSupportReason::local_danger||reason==AiSupportReason::projectile||reason==AiSupportReason::enemy_hero||reason==AiSupportReason::health;
    for(const auto& t:f.threats)if(t.projectile&&t.eta_ms<350)danger=true;
    for(const auto* u:c.enemy)if(u->mobile&&std::abs(ai_wrap_delta(f.me.position.x,u->position.x,f.width))<2.*f.tile&&std::abs(u->position.y-f.me.position.y)<2.*f.tile)danger=true;
    if(danger){state_.ladder_route.reset();return {};}
    auto& route=state_.ladder_route;
    if(route&&route->engaged&&std::abs(goal_y-f.me.position.y)<=f.tile*.8&&std::abs(route->goal_y-f.me.position.y)>f.tile*.8)goal_y=route->goal_y;
    const double dy=goal_y-f.me.position.y;
    if(route&&(std::abs(route->goal_y-goal_y)>f.tile*.5||f.time>route->until))route.reset();
    if(route&&(route->up?dy>=-f.tile*.08:dy<=f.tile*.08)){route.reset();return {};}
    if(!route&&std::abs(dy)<=f.tile*.8)return {};if(f.time<state_.ladder_backoff_until)return {};
    const auto& tiles=f.terrain.solid;const auto rows=tiles.size();if(!rows||tiles.front().empty())return {};const auto columns=tiles.front().size();
    const auto first=size_t(std::clamp(int64_t(py::floordiv(std::min(f.me.position.y,goal_y)+2.,f.tile)),int64_t(0),int64_t(rows-1)));
    const auto last=size_t(std::clamp(int64_t(py::floordiv(std::max(f.me.position.y,goal_y)-2.,f.tile)),int64_t(0),int64_t(rows-1)));
    const auto ladder=[&](size_t column){for(size_t row=first;row<=last;++row)if(tiles.at(row).at(column)||row>=f.ladders.size()||column>=f.ladders[row].size()||!f.ladders[row][column])return false;return true;};
    if(!route){
        std::optional<std::tuple<double,size_t,double>> best;
        for(size_t col=0;col<columns;++col){const double x=(col+.5)*f.tile,dx=std::abs(ai_wrap_delta(f.me.position.x,x,f.width));if(dx>9.*f.tile||!ladder(col))continue;
            bool threatened=false;for(const auto* u:c.enemy)if(u->mobile&&std::abs(ai_wrap_delta(x,u->position.x,f.width))<2.*f.tile&&u->position.y>std::min(f.me.position.y,goal_y)-f.tile&&u->position.y<std::max(f.me.position.y,goal_y)+f.tile){threatened=true;break;}if(threatened)continue;
            auto candidate=std::tuple(dx+.15*std::abs(ai_wrap_delta(x,post,f.width)),col,x);if(!best||candidate<*best)best=candidate;
        }
        if(!best)return {};route=AiTacticalState::LadderRoute{std::get<1>(*best),std::get<2>(*best),goal_y,dy<0.,f.time+12.,f.time,f.me.position.y,false};++state_.log[route->up?"route:ladder_up":"route:ladder_down"];
    }else if(!ladder(route->column)){route.reset();return {};}
    const double dx=ai_wrap_delta(f.me.position.x,route->x,f.width);const bool on_column=size_t(py::mod(py::floordiv(f.me.position.x,f.tile),double(columns)))==route->column;if(on_column)route->engaged=true;
    if(!on_column||std::abs(dx)>f.tile*.23){route->progress_at=f.time;if(route->engaged){state_.jump_down=false;const int move=dx>0.?1:-1;c.services.send(f.owner,MoveCommand{value(int64_t(move)),value(route->up),false});return move;}return drive(c,route->x,false,f.tile*.14);}
    if(std::abs(f.me.position.y-route->y)>f.tile*.2){route->progress_at=f.time;route->y=f.me.position.y;}
    else if(f.time-route->progress_at>2.){route.reset();state_.ladder_backoff_until=f.time+2.;return {};}
    state_.jump_down=false;c.services.send(f.owner,MoveCommand{value(int64_t(0)),value(route->up),false});return 0;
}
} // namespace pvz::typed72
