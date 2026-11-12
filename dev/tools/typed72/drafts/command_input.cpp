#include "sim/typed/command_input.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>

namespace pvz::typed72 {
namespace {
bool is_team(MatchMode mode){return mode==MatchMode::duo||mode==MatchMode::coop;}
bool present(MatchMode mode,Seat seat){const auto s=seats_for(mode);return std::find(s.begin(),s.end(),seat)!=s.end();}
std::vector<Seat> teammates(MatchMode mode,Seat seat){std::vector<Seat> out;for(const auto s:seats_for(mode))if(s!=seat&&team_of(s)==team_of(seat))out.push_back(s);return out;}
}
void RoomCommands::clear(Seat seat,bool record){
    auto& p=world_.heroes.players.at(seat_index(seat)).value();p.move=0;p.jump_held=false;p.jump_presses=0;
    if(record)services_.input_cleared(state_.tick,seat);
}
std::string RoomCommands::apply(Seat seat,const CommandAttempt& attempt){
    std::string error=state_.audit_error.empty()?dispatch(seat,attempt):state_.audit_error;
    if(error.empty())services_.input_accepted(state_.tick,world_.heroes.time,seat,attempt);
    services_.input_attempt(state_.tick,seat,attempt,error);return error;
}
std::string RoomCommands::dispatch(Seat seat,const CommandAttempt& a){
    if(seat_index(seat)>=world_.heroes.players.size()||!world_.heroes.players[seat_index(seat)]||!a.dictionary)return "输入格式错误";
    if(!a.sequence.valid()||a.sequence.value<0||a.sequence.value>int64_t(1ULL<<53))return "序号错误";
    auto& p=world_.heroes.players[seat_index(seat)].value();auto& input=state_.players[seat_index(seat)];
    if(a.sequence.value<=input.sequence)return "旧输入";
    input.sequence=a.sequence.value;input.last_input_tick=state_.tick;
    if(state_.result)return "对局已结束";
    if(const auto* c=std::get_if<MoveCommand>(&a.payload)){
        if((!c->move.absent()&&!c->move.valid())||(c->move.valid()&&(c->move.value< -1||c->move.value>1)))return "方向无效";
        if(!c->jump.absent()&&!c->jump.valid())return "跳跃状态无效";
        const auto before=p.jump_held;p.move=c->move.absent()?0:int(c->move.value);p.jump_held=c->jump.absent()?false:c->jump.value;
        if(c->edge){input.press_reported=true;p.jump_presses=std::min<uint64_t>(3,p.jump_presses+1);}
        else if(p.jump_held&&!before&&!input.press_reported)p.jump_presses=std::min<uint64_t>(3,p.jump_presses+1);
        return {};
    }
    if(const auto* c=std::get_if<NativeCommand>(&a.payload)){
        if(c->kind==NativeCommandKind::deploy&&!c->facing.absent()&&(!c->facing.valid()||(c->facing.value!=-1&&c->facing.value!=1)))return "部署方向无效";
        return services_.native_command(seat,*c);
    }
    if(const auto* c=std::get_if<RallyCommand>(&a.payload)){
        if(team_of(seat)!=Seat::zombie)return "只有僵尸方可召集";
        std::optional<Point> point;
        if(!c->clear){
            if(!c->x.valid()||!c->y.valid()||!std::isfinite(c->x.value)||!std::isfinite(c->y.value)||c->x.value<0.||c->x.value>=world_.world_width.get()||c->y.value<0.||c->y.value>=world_.world_height.get())return "召集点坐标无效";
            point=Point{(std::trunc(py::floordiv(c->x.value,world_.runtime.tile))+.5)*world_.runtime.tile,
                        (std::trunc(py::floordiv(c->y.value,world_.runtime.tile))+.5)*world_.runtime.tile};
        }
        if(world_.mode==MatchMode::duo)rally_.by_seat[seat_index(seat)]=point;
        if(seat==Seat::zombie||world_.mode!=MatchMode::duo)rally_.shared=point;
        services_.emit(RoomRallyEvent{seat,rally_.for_owner(world_.mode,seat)});return {};
    }
    if(std::holds_alternative<ToggleCommand>(a.payload)){
        if(team_of(seat)!=Seat::zombie)return "只有僵尸方可指挥";
        if(world_.mode!=MatchMode::duo&&rally_.shared){rally_.shared.reset();services_.emit(RoomRallyEvent{seat,{}});return {};}
        const auto mode=commands_.for_owner(world_.mode,seat)==PathMode::follow_hero?PathMode::attack_plants:PathMode::follow_hero;
        if(world_.mode==MatchMode::duo)commands_.by_seat[seat_index(seat)]=mode;
        if(seat==Seat::zombie||world_.mode!=MatchMode::duo)commands_.shared=mode;
        services_.emit(RoomCommandEvent{seat,mode,a.sequence.value});return {};
    }
    if(const auto* c=std::get_if<CollectCommand>(&a.payload)){
        if(team_of(seat)!=Seat::plant)return "脑光由系统自动收集";
        if(!c->resource.valid())return "资源编号无效";
        const auto* resource=resources_.find(c->resource.value);
        const bool shared=resource&&resource->shared.present()&&!resource->shared.is_null()&&resource->shared.get()&&team_of(resource->side)==Seat::plant;
        if(!resource||(resource->side!=seat&&!shared))return "资源已收集或不存在";
        if(is_team(world_.mode)&&p.hp<=0.)return "戴夫已阵亡，等待队友复活";
        if(world_.heroes.time<input.collect_locked_until){
            char value[64];std::snprintf(value,sizeof(value),"%.1f",input.collect_locked_until-world_.heroes.time);
            return std::string("黄金蓓蕾放置后")+value+"秒内只能由戴夫肉身拾取阳光";
        }
        resources_.collect(c->resource.value,shared?std::optional<Seat>(seat):std::nullopt);return {};
    }
    if(std::holds_alternative<MarkCommand>(a.payload)){
        if(team_of(seat)!=Seat::plant)return "只有植物方可标记";
        auto& target=world_.heroes.players[seat_index(Seat::zombie)].value();
        const auto dx=wrap_delta(p.position.x,target.position.x,world_.world_width.get());
        const auto dy=(p.position.y-p.height/2.)-(target.position.y-target.height/2.);
        if(std::hypot(dx,dy)>rules_.hero_lock_range||!services_.mark_line_of_sight(seat,Seat::zombie))return "目标超出标记范围或被地形遮挡";
        target.marked_until=world_.heroes.time+rules_.mark_seconds;return {};
    }
    if(const auto* c=std::get_if<SurrenderCommand>(&a.payload))return surrender(seat,*c);
    if(const auto* c=std::get_if<GiftCommand>(&a.payload)){
        const auto mates=teammates(world_.mode,seat);if(mates.empty())return "没有可资助的队友";
        if(!c->amount.valid()||c->amount.value<=0)return "资助数量无效";
        if(c->amount.value>100)return "单次最多资助 100";
        if(world_.mode==MatchMode::duo&&world_.heroes.time<input.gift_ready_at)return "资助冷却中";
        auto& payer=resources_.accounts[seat_index(seat)];if(payer.balance<c->amount.value)return "资源不足";
        auto mate=mates.front();auto distance=std::abs(world_.heroes.players[seat_index(mate)]->position.x-p.position.x);
        for(const auto candidate:mates){const auto d=std::abs(world_.heroes.players[seat_index(candidate)]->position.x-p.position.x);if(d<distance){mate=candidate;distance=d;}}
        auto& receiver=resources_.accounts[seat_index(mate)];payer.balance-=c->amount.value;receiver.balance+=c->amount.value;receiver.earned+=c->amount.value;
        input.gift_ready_at=world_.heroes.time+(world_.mode==MatchMode::duo?12.:0.);
        services_.emit(RoomGiftEvent{seat,mate,c->amount.value});return {};
    }
    return "未知战斗命令";
}
std::string RoomCommands::surrender(Seat seat,const SurrenderCommand& c){
    if(!present(world_.mode,seat))return "观众不能投降";
    const auto mates=teammates(world_.mode,seat);const auto team=team_of(seat);
    if(!mates.empty()){
        auto& request=state_.surrender_requests[team==Seat::plant?0:1];
        if(request&&world_.heroes.time>=request->expires)request.reset();
        if(c.action==SurrenderAction::request){
            if(request)return "已有投降请求，请队友选择同意或拒绝";
            request=RoomSurrenderRequest{++state_.surrender_serial,seat,world_.heroes.time+20.};
            services_.emit(RoomSurrenderRequestEvent{seat,request->id});return {};
        }
        if(!request||!c.request.valid()||c.request.value!=request->id)return "投降请求已失效";
        if(c.action==SurrenderAction::cancel){if(request->seat!=seat)return "只有发起人可以撤回";}
        else if(request->seat==seat)return "请等待队友确认";
        const auto id=request->id;request.reset();services_.emit(RoomSurrenderVoteEvent{seat,id,c.action==SurrenderAction::accept});
        if(c.action!=SurrenderAction::accept)return {};
    }else if(c.action!=SurrenderAction::request)return "当前没有队友投降请求";
    state_.result=RoomResult{team==Seat::plant?RoomWinner::zombie:RoomWinner::plant,RoomResultReason::surrender,state_.tick};
    services_.emit(*state_.result);return {};
}
uint64_t RoomCommandQueue::enqueue(Seat seat,CommandAttempt input){
    if(queue_.size()>=limit_)throw std::length_error("typed room input queue capacity exceeded");
    if(next_==std::numeric_limits<uint64_t>::max())throw std::overflow_error("typed room input order exhausted");
    const auto order=next_++;queue_.push_back({order,seat,std::move(input)});return order;
}
std::vector<std::pair<uint64_t,std::string>> RoomCommandQueue::drain(RoomCommands& commands){
    std::vector<std::pair<uint64_t,std::string>> result;result.reserve(queue_.size());
    while(!queue_.empty()){
        auto current=std::move(queue_.front());queue_.pop_front();
        result.emplace_back(current.order,commands.apply(current.seat,current.attempt));
    }
    return result;
}
} // namespace pvz::typed72
