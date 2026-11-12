#include "sim/typed/replay_driver.h"
#include <cmath>
#include <stdexcept>

namespace pvz::typed72 {
ReplayPlayer::ReplayPlayer(const ReplayData& data,ReplayFactory& factory):data_(data),factory_(factory){restart();}
void ReplayPlayer::restart(){
    battle_.reset();battle_=factory_.create();if(!battle_)throw std::logic_error("null typed replay composition");
    cursor_=0;verified=false;error.clear();credit=0.;inputs();
}
void ReplayPlayer::inputs(){
    const auto tick=battle_->room().tick;
    while(cursor_<data_.operations.size()&&data_.operations[cursor_].tick==tick){
        // Advance before execution: exception recovery/restart follows the
        // original operation cursor behavior.
        const auto& op=data_.operations[cursor_++];
        if(const auto* input=std::get_if<ReplayInput>(&op.value)){
            const auto result=battle_->commands().apply(input->seat,input->command);
            if(result!=input->expected_error)throw std::runtime_error("输入结果不一致，回放已停止（刻 "+std::to_string(tick)+"）");
        }else if(const auto* clear=std::get_if<ReplayClear>(&op.value))battle_->commands().clear(clear->seat);
        else if(!battle_->matches_snapshot(std::get<ReplayCheck>(op.value).sha256,data_.format,data_.build))
            throw std::runtime_error("战斗状态校验不一致，回放已停止（刻 "+std::to_string(tick)+"）");
    }
    if(tick==data_.ticks){
        if(!battle_->matches_snapshot(data_.final_hash,data_.format,data_.build))throw std::runtime_error("回放终点状态校验不一致");
        verified=true;playing=false;
    }
}
void ReplayPlayer::seek(int64_t tick){
    target=std::max<int64_t>(0,std::min(data_.ticks,tick));credit=0.;
    if(*target<battle_->room().tick||!error.empty())restart();
}
void ReplayPlayer::update(double dt,std::optional<int64_t> max_steps,std::optional<double> budget){
    if(!error.empty()||(!target&&!playing))return;
    if(!target)credit=std::min(double(data_.ticks-battle_->room().tick),credit+std::max(0.,dt)*speed/(1./data_.tick_rate));
    const auto count=max_steps.value_or(target?2000:std::max<int64_t>(60,std::min<int64_t>(2000,int64_t(credit)+1)));
    const auto seconds=budget.value_or(target||speed>1.?.035:.014);
    const auto end=target.value_or(std::min(data_.ticks,battle_->room().tick+int64_t(credit)));
    const auto deadline=factory_.monotonic_seconds()+seconds;
    try{
        for(int64_t unused=0;unused<count;++unused){
            if(battle_->room().tick>=end)break;
            const auto before=battle_->room().tick;battle_->scheduler().step();
            if(battle_->room().tick==before)throw std::runtime_error("回放在日志终点前意外结束");
            inputs();if(!target)credit=std::max(0.,credit-1.);
            if(factory_.monotonic_seconds()>=deadline)break;
        }
        if(target&&battle_->room().tick>=*target)target.reset();
    }catch(const std::logic_error& ex){error=ex.what();playing=false;target.reset();}
     catch(const std::runtime_error& ex){error=ex.what();playing=false;target.reset();}
}
} // namespace pvz::typed72
