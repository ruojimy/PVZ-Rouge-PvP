#pragma once
#include "sim/typed/path_tracking.h"
#include "sim/typed/hero_phase.h"

namespace pvz::typed72 {
struct PathFieldSnapshot {
    std::shared_ptr<std::vector<int>> field;
    std::shared_ptr<std::vector<Cell>> queue;
    int cooldown=0,sign=-1;
};
struct ChaseSnapshot {
    std::array<std::shared_ptr<std::vector<int>>,2> fields;
    Cell goal;
    int64_t target=-1;
    double running=1.,output=0.;
};
// A native tracking dictionary saves scalars by value and matrices/queues by
// identity. Saving a bank never copies a grid or a frontier.
struct PathSnapshot {
    std::array<PathFieldSnapshot,2> flood;
    ChaseSnapshot chase;
    Cell hero_cell;
    double hold=0.;
    Field<double> wjx,wjy;
    bool initialized=false;
};
struct SeatCommands {
    PathMode shared=PathMode::follow_hero;
    std::array<PathMode,4> by_seat{PathMode::follow_hero,PathMode::follow_hero,
                                  PathMode::follow_hero,PathMode::follow_hero};
    PathMode for_owner(MatchMode mode,std::optional<Seat> seat)const {
        return mode==MatchMode::duo?by_seat.at(seat_index(seat.value_or(Seat::zombie))):shared;
    }
};
struct RallyPathBank {
    PathSnapshot path;
    std::optional<Point> goal;
};
class SeatPathTracking {
public:
    SeatPathTracking(TypedBattleState& world,ZombieNavigation& navigation,const NativePathRules& rules,
                     const TargetSight& published,const RallyPoints& flags,const SeatCommands& commands)
        :world_(world),navigation_(navigation),paths_(world,navigation,rules),published_(published),
         flags_(flags),commands_(commands){}
    PathSnapshot capture()const;
    void restore(const PathSnapshot&);
    Seat advance_team(std::span<const Seat> present);
    void advance_rallies(std::span<const Seat> present,uint64_t published_revision);
    std::optional<Point> destination(std::optional<Seat> owner,uint64_t published_revision);
    void begin_zombies();
    void end_zombies();
    void switch_for(const CombatZombie&,std::span<const Seat> present);
    void select_rally(const CombatZombie&);
    void restore_rally();
    const auto& seats()const{return seats_;}
    const auto& rally_seats()const{return rally_seats_;}
    const auto& shared_rally()const{return shared_rally_;}
    const auto& rally_base()const{return rally_base_;}
    const auto& selected_seat()const{return selected_;}
private:
    struct DestinationCache {Point flag,goal;uint64_t revision=0;};
    TypedBattleState& world_;
    ZombieNavigation& navigation_;
    PathTracking paths_;
    const TargetSight& published_;
    const RallyPoints& flags_;
    const SeatCommands& commands_;
    std::array<std::optional<PathSnapshot>,4> seats_;
    std::array<std::optional<RallyPathBank>,4> rally_seats_;
    std::optional<RallyPathBank> shared_rally_;
    std::array<std::optional<DestinationCache>,4> destinations_;
    std::optional<DestinationCache> shared_destination_;
    std::optional<ChaseSnapshot> rally_base_;
    std::optional<PathSnapshot> phase_baseline_;
    std::optional<Seat> selected_;
    ChaseSnapshot capture_chase()const;
    void restore_chase(const ChaseSnapshot&);
    PathSnapshot independent(const PathSnapshot&)const;
    void advance_flag(RallyPathBank&,Point);
    std::span<const Seat> team_seats(std::span<const Seat>,Seat,bool alive,std::array<Seat,4>& output)const;
};
} // namespace pvz::typed72
