#pragma once
#include "sim/typed/native_tick.h"
#include "sim/typed/room_state.h"

namespace pvz::typed72 {
// Required typed controllers. There is no optional legacy implementation.
// Production composition must supply the still separately migrated public
// registry/card policy, director and secret controllers before activation.
class RoomServices : public RoomEventSink {
public:
    virtual double monotonic_seconds()=0;
    virtual void capture_deferred(bool)=0;
    virtual void cycle_step()=0;
    virtual double card_cooldown(Seat,const std::string& key)=0;
    virtual std::optional<bool> copied_card_is_producer(const std::string& key)=0;
    virtual void sync_public(bool terrain)=0;
    virtual void zombie_secrets_step(double elapsed)=0;
    virtual void director_step()=0;
    virtual bool director_cleared()const=0;
};
class RoomScheduler {
public:
    RoomScheduler(TypedBattleState&,RoomState&,const RoomRules&,NativeTickState&,
                  NativeTick&,HeroRecovery&,Economy&,Resources&,RoomServices&);
    void step(int64_t steps=1);
    void clear_input(Seat);
    void publish_heroes();
private:
    TypedBattleState& world_;
    RoomState& state_;
    const RoomRules& rules_;
    NativeTickState& native_state_;
    NativeTick& native_;
    HeroRecovery& recovery_;
    Economy& economy_;
    Resources& resources_;
    RoomServices& services_;
    void begin_deathmatch();
    void subsidy();
    void team_step(double elapsed);
    void revive(Seat,Seat);
    void finish_result();
    bool touching(const HeroState&,const HeroState&)const;
};

// Wall clock pacing is not a battle clock. Credits are retained and each
// requested room step still runs all 250 Hz native ticks.
struct AdaptiveRoomPacing {
    double scale=1.,ratio=0.,observed=0.,over=0.,under=0.;
    double sample(double cost,double simulated);
};
struct RoomWallClock {
    double accumulator=0.;
    AdaptiveRoomPacing pacing;
    int credit(double dt,double room_dt);
    void consume(int count,double room_dt,double spent);
};
} // namespace pvz::typed72
