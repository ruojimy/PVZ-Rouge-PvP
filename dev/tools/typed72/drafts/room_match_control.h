#pragma once
#include "sim/typed/replay_recording.h"
#include "sim/typed/command_gateway.h"
#include <set>
namespace pvz::typed72 {
enum class RoomPhase {config,banning,picking,loading,battle,result};
enum class RoomSettlementReason {hero_death,waves_cleared,surrender,leave,kick,disconnect,host_closed,load_timeout};
struct RoomSettlement {std::optional<RoomWinner> winner;RoomSettlementReason reason;int64_t tick=0;std::optional<Seat> forfeit;std::optional<int> pve_day;std::optional<double> coins;std::optional<uint64_t> fallen;};
struct RoomMember {std::string peer;Seat seat;bool connected=true;};
enum class RoomMembershipEventKind {joined,reconnected,left,kicked,disconnected,disconnected_after_result,forfeit,interrupted,result,role_changed,battle};
struct RoomMembershipEvent {RoomMembershipEventKind kind;std::string peer;std::optional<Seat> seat;std::optional<bool> spectator;std::optional<RoomSettlementReason> reason;std::optional<RoomSettlement> result;int64_t match_number=0;};
struct RoomMatchState {
    std::vector<RoomMember> members={{"host",Seat::plant,true}};std::vector<std::string> spectators;
    MatchMode mode=MatchMode::duel;std::set<std::string> ai_peers,subsidy_peers;
    std::span<const Seat> seats()const{return seats_for(mode);}
    bool scripted()const{return mode==MatchMode::pve||mode==MatchMode::coop;}
    bool duo()const{return mode==MatchMode::duo;}
    RoomPhase phase=RoomPhase::config;double clock=0.,deadline=0.,accumulator=0.;uint64_t revision=1,pause_epoch=0;
    std::optional<double> disconnect_deadline;std::optional<RoomSettlement> result;std::string status="等待对方加入并确认地图",audit_error,terrain_hash;
    std::optional<std::string> loading_id;std::array<bool,4> ready{},confirmed{},loaded{};
    std::set<Seat> pause_votes,restart_votes;std::vector<std::pair<Seat,int>> rematch_votes;
    bool paused=false,allow_spectators=true,same_deck_rematch=false;size_t max_spectators=4;int64_t match_number=0;std::optional<int> pve_day;
};
struct RoomMatchBattle {
    RoomState& state;const RoomRules& rules;RoomScheduler& scheduler;RoomInputGateway& input;ReplayRecording* recording;
    RoomMatchBattle(RoomState& s,const RoomRules& r,RoomScheduler& step,RoomInputGateway& commands,ReplayRecording* record=nullptr):state(s),rules(r),scheduler(step),input(commands),recording(record){input.recording(record);}
};
class RoomMatchServices {
public:
    virtual ~RoomMatchServices()=default;
    virtual std::string journal_error()const=0;
    virtual void record(const RoomMembershipEvent&)=0;
    virtual void save_replay()=0;
    virtual void close_battle()=0;
    virtual void reset_draft_fields()=0;
    virtual void forget_seat_deck(Seat)=0;
    virtual void drop_progress_peer(const std::string&)=0;
    virtual void drop_config_request(const std::string&)=0;
    virtual void sync_progress()=0;
    virtual void finish_progress(RoomSettlement&)=0;
    virtual double monotonic_seconds()=0;
    virtual void draft_timeout()=0;
};
// Authority for the outer room's live lifecycle. Native bodies stay owned by
// the composed battle; connection and pause state never live in transport.
class RoomMatchControl {
public:
    RoomMatchControl(RoomMatchState& state,RoomMatchServices& services):state_(state),services_(services){}
    void bind(RoomMatchBattle* battle){battle_=battle;paced_=nullptr;}
    std::optional<Seat> side_for(const std::string&)const;
    bool connected(const std::string&)const;
    std::vector<std::string> snapshot_peers()const;
    std::string connect(const std::string&,bool spectator=false,std::optional<Seat> seat={});
    std::string role_change_error(const std::string&,bool spectator,std::optional<Seat> seat={})const;
    std::string change_role(const std::string&,bool spectator,std::optional<Seat> seat={});
    void disconnect(const std::string&);void leave(const std::string&);void kick(const std::string&);void host_quit();
    std::string reopen();void reset_selection();void capture_result();
    std::string input(const std::string&,const WireObject&);
    std::string pause(const std::string&,const InputField<int64_t>& epoch,const InputField<bool>& desired,const InputField<bool>& cancel);
    std::string loaded(const std::string&,const std::optional<std::string>& loading_id,const std::optional<std::string>& terrain_hash);
    void update(double dt);
    std::string audit_error()const;std::string halt_for_audit(const std::string&);
private:
    RoomMatchState& state_;RoomMatchServices& services_;RoomMatchBattle* battle_=nullptr;RoomMatchBattle* paced_=nullptr;AdaptiveRoomPacing pacing_;
    bool all_connected()const;bool vacant(Seat)const;Seat free_seat()const;bool erase_spectator(const std::string&);
    void clear(Seat);void forget(std::optional<Seat>);void release(const std::string&,std::string);void forfeit(const std::string&,RoomSettlementReason);
    std::string record(RoomMembershipEvent);int64_t tick()const{return battle_?battle_->state.tick:0;}
};
} // namespace pvz::typed72
