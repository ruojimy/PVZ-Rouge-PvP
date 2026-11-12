#pragma once
#include "sim/typed/room_scheduler.h"
#include "sim/typed/command_input.h"
#include <memory>

namespace pvz::typed72 {
struct ReplayInput {Seat seat;CommandAttempt command;std::string expected_error;};
struct ReplayClear {Seat seat;};
struct ReplayCheck {std::string sha256;};
struct ReplayOperation {int64_t tick;std::variant<ReplayInput,ReplayClear,ReplayCheck> value;};
struct ReplayData {
    int64_t ticks=0;
    int tick_rate=30;
    std::string format,build,final_hash;
    std::vector<ReplayOperation> operations;
};
// Each replay session is a new complete typed composition. Only its cold
// initializer and public snapshot hash cross this interface; simulation and
// commands call the same concrete classes used by a live room.
class ReplayBattle {
public:
    virtual ~ReplayBattle()=default;
    virtual RoomState& room()=0;
    virtual RoomScheduler& scheduler()=0;
    virtual RoomCommands& commands()=0;
    virtual bool matches_snapshot(const std::string& hash,const std::string& format,const std::string& build)=0;
};
class ReplayFactory {
public:
    virtual ~ReplayFactory()=default;
    virtual std::unique_ptr<ReplayBattle> create()=0;
    virtual double monotonic_seconds()=0;
};
class ReplayPlayer {
public:
    ReplayPlayer(const ReplayData&,ReplayFactory&);
    bool playing=false,verified=false;
    double speed=1.,credit=0.;
    std::optional<int64_t> target;
    std::string error;
    void restart();
    void seek(int64_t tick);
    void update(double dt,std::optional<int64_t> max_steps={},std::optional<double> budget={});
    void close(){battle_.reset();}
    ReplayBattle* battle(){return battle_.get();}
    size_t cursor()const{return cursor_;}
    double duration()const{return double(data_.ticks)/data_.tick_rate;}
private:
    const ReplayData& data_;ReplayFactory& factory_;
    std::unique_ptr<ReplayBattle> battle_;
    size_t cursor_=0;
    void inputs();
};
} // namespace pvz::typed72
