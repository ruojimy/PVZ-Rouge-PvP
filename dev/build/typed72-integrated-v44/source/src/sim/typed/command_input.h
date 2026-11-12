#pragma once
#include "sim/typed/room_state.h"
#include <deque>

namespace pvz::typed72 {
enum class InputFieldState {missing,null,invalid,value};
template<class T>struct InputField {
    InputFieldState state=InputFieldState::missing;
    T value{};
    bool valid()const{return state==InputFieldState::value;}
    bool absent()const{return state==InputFieldState::missing;}
};
struct MoveCommand {InputField<int64_t> move;InputField<bool> jump;bool edge=false;};
struct RallyCommand {bool clear=false;InputField<double> x,y;};
struct ToggleCommand {};
struct CollectCommand {InputField<std::string> resource;};
struct MarkCommand {};
struct GiftCommand {InputField<int64_t> amount;};
enum class SurrenderAction {request,accept,decline,cancel};
struct SurrenderCommand {SurrenderAction action;InputField<double> request;};
enum class NativeCommandKind {turn,detonate,select_grave,wake,teleport,deploy,cannon,cannon_cancel,shovel};
struct NativeCommand {
    NativeCommandKind kind;
    InputField<std::string> card,target,grave,copy;
    InputField<double> x,y;
    InputField<int64_t> facing;
    InputField<bool> right;
};
struct UnknownCommand {};
using CommandPayload=std::variant<MoveCommand,RallyCommand,ToggleCommand,CollectCommand,
    MarkCommand,GiftCommand,SurrenderCommand,NativeCommand,UnknownCommand>;
struct CommandAttempt {
    bool dictionary=true;
    InputField<int64_t> sequence;
    CommandPayload payload=UnknownCommand{};
};
class CommandServices : public RoomEventSink {
public:
    virtual std::string native_command(Seat,const NativeCommand&)=0;
    virtual bool mark_line_of_sight(Seat source,Seat target)const=0;
    // The one ordered journal receives rejected attempts too; accepted input
    // audit records remain separate from the bounded display event queue.
    virtual void input_attempt(int64_t tick,Seat,const CommandAttempt&,const std::string& error)=0;
    virtual void input_accepted(int64_t tick,double time,Seat,const CommandAttempt&)=0;
    virtual void input_cleared(int64_t tick,Seat)=0;
};
class RoomCommands {
public:
    RoomCommands(TypedBattleState& w,RoomState& s,const RoomRules& r,Resources& resources,
                 SeatCommands& commands,RallyPoints& rally,CommandServices& services)
        :world_(w),state_(s),rules_(r),resources_(resources),commands_(commands),rally_(rally),services_(services){}
    std::string apply(Seat,const CommandAttempt&);
    void clear(Seat,bool record=true);
private:
    TypedBattleState& world_;RoomState& state_;const RoomRules& rules_;Resources& resources_;
    SeatCommands& commands_;RallyPoints& rally_;CommandServices& services_;
    std::string dispatch(Seat,const CommandAttempt&);
    std::string surrender(Seat,const SurrenderCommand&);
};
struct QueuedCommand {uint64_t order;Seat seat;CommandAttempt attempt;};
class RoomCommandQueue {
public:
    explicit RoomCommandQueue(size_t limit=4096):limit_(limit){}
    uint64_t enqueue(Seat,CommandAttempt);
    std::vector<std::pair<uint64_t,std::string>> drain(RoomCommands&);
    size_t size()const{return queue_.size();}
private:
    std::deque<QueuedCommand> queue_;
    size_t limit_;
    uint64_t next_=0;
};
} // namespace pvz::typed72
