#pragma once
#include "sim/typed/hero_recovery.h"
#include "sim/typed/economy.h"
#include "sim/typed/seat_path_tracking.h"
#include <optional>
#include <variant>

namespace pvz::typed72 {
enum class RoomWinner { plant,zombie,draw };
enum class RoomResultReason { hero_death,waves_cleared,surrender };
struct RoomResult {
    RoomWinner winner=RoomWinner::draw;
    RoomResultReason reason=RoomResultReason::hero_death;
    int64_t tick=0;
    std::optional<double> coins;
    std::optional<uint64_t> fallen;
    friend bool operator==(const RoomResult&,const RoomResult&)=default;
};
struct RoomDeathmatchEvent {double multiplier;};
struct RoomSubsidyEvent {Seat seat;double amount;};
struct RoomFallenEvent {Seat seat;};
struct RoomHelpedEvent {Seat seat,helper;};
struct RoomRevivedEvent {Seat seat,helper;double hp;};
struct RoomSpawnBlockedEvent {std::string card;};
struct RoomRallyEvent {Seat seat;std::optional<Point> point;};
struct RoomCommandEvent {Seat seat;PathMode mode;int64_t sequence;};
struct RoomGiftEvent {Seat seat,to;int64_t amount;};
struct RoomSurrenderRequestEvent {Seat seat;int64_t request;};
struct RoomSurrenderVoteEvent {Seat seat;int64_t request;bool accepted;};
enum class RoomActionKind {plant_turned,select_grave,teleport,blink_heal,cannon_fire,shovel,basin_to_pot,clown_detonate};
struct RoomActionEvent {
    RoomActionKind kind;
    Seat seat;
    std::string entity,source;
    std::vector<std::string> entities;
    Point position;
    double facing=0.,amount=0.;
    bool right=false;
};
using RoomEvent=std::variant<RoomDeathmatchEvent,RoomSubsidyEvent,RoomFallenEvent,
    RoomHelpedEvent,RoomRevivedEvent,RoomSpawnBlockedEvent,RoomRallyEvent,
    RoomCommandEvent,RoomGiftEvent,RoomSurrenderRequestEvent,RoomSurrenderVoteEvent,RoomActionEvent,RoomResult>;
struct RoomPlayerState {
    uint64_t producer_lost=0;
    int64_t sequence=-1,last_input_tick=0;
    bool press_reported=false;
    double immune_until=0.,collect_locked_until=0.,gift_ready_at=0.;
    double teleport_ready_at=0.;
    std::optional<Cell> cannon_aim;
    std::vector<std::pair<std::string,double>> cooldown_spans;
};
struct RoomSurrenderRequest {int64_t id;Seat seat;double expires;};
struct RoomState {
    int64_t tick=0;
    int native_phase=0;
    bool deathmatch=false,capture_demand=false,capture_intermediate=false,defer_capture=false;
    uint64_t capture_frames=0,capture_deferred=0,fallen_count=0;
    std::optional<double> native_cost_ratio;
    std::optional<RoomResult> result;
    std::string audit_error;
    std::array<RoomPlayerState,4> players;
    std::array<double,4> revive{};
    std::array<std::optional<double>,4> down_since;
    std::vector<Seat> ai_subsidy_seats;
    int64_t ai_subsidy_paid=0,surrender_serial=0;
    std::array<std::optional<RoomSurrenderRequest>,2> surrender_requests;
    bool director=false,director_cycle=false,zombie_secrets=false;
};
struct RoomRules {
    int tick_rate=30;
    double deathmatch_seconds=0.,production_multiplier=1.;
    HeroRecoveryRules recovery;
    EconomyRules economy;
    double hero_lock_range=0.,mark_seconds=0.;
    double teleport_cooldown=20.;
    double dt()const{return 1./tick_rate;}
};

// Only the room/input-specific fields live here. HP, position, cooldowns,
// resources and native ticks continue to have exactly one existing owner.
class RoomEventSink {
public:
    virtual ~RoomEventSink()=default;
    virtual void emit(RoomEvent)=0;
};
} // namespace pvz::typed72
