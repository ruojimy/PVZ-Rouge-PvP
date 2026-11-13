#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/moving_point_grid.h"
#include "sim/typed/moving_coverage_grid.h"
#include <unordered_set>

namespace pvz::typed72 {
class ContentTaunts {
public:
    virtual ~ContentTaunts()=default;
    virtual std::optional<ContentTarget> taunt_target(const ContentTarget&,std::optional<ContentTarget>)=0;
};
class ContentQueries {
public:
    ContentQueries(TypedBattleState& world,ContentTargets& targets,ContentTaunts& taunts)
        :world_(world),targets_(targets),taunts_(taunts){}
    std::vector<ContentTarget> enemies(const std::shared_ptr<AttackSource>& source);
    std::vector<ContentTarget> enemies_in_box(const std::shared_ptr<AttackSource>&,CoverageBox);
    std::optional<ContentTarget> nearest(const ContentTarget& source);
    std::optional<ContentTarget> route(const ContentTarget& source,std::optional<ContentTarget> goal,
                                      std::span<const ContentTarget> candidates)const;
    std::shared_ptr<AttackSource> source(const ContentTarget&)const;
    std::optional<ContentTarget> route_enemies(const ContentTarget&,std::optional<ContentTarget>,bool heroes=true);
    void moved(const ContentTarget&);
    void invalidate(){index_tick_=-1;}
    uint64_t local_queries=0,local_candidates=0;
    uint64_t range_queries=0,range_candidates=0,range_full_scan=0,range_exact_tests=0;
    uint64_t seeking_plant_ticks=0,max_seeking_plants=0;
    const MovingCoverageGrid& coverage_index()const{return zombie_coverage_;}
    size_t range_storage_bytes()const{return zombie_coverage_.storage_bytes()+plant_coverage_.storage_bytes();}
    const MovingPointGrid& moving_index()const{return points_;}
private:
    TypedBattleState& world_;
    ContentTargets& targets_;
    ContentTaunts& taunts_;
    MovingPointGrid points_;
    MovingCoverageGrid zombie_coverage_,plant_coverage_;
    int64_t coverage_tick_=-1,seeking_tick_=-1;
    std::unordered_set<const AttackSource*> seeking_;
    std::vector<ContentTarget> indexed_;
    std::unordered_map<const void*,size_t> object_ids_;
    const CombatTarget* zombie_data_=nullptr;const PlantRef* plant_data_=nullptr;
    const TargetRoster* zombie_roster_=nullptr;const PlantRoster* plant_roster_=nullptr;
    size_t zombie_count_=0,plant_count_=0;int64_t index_tick_=-1;
    std::vector<uint64_t> query_seen_;uint64_t query_stamp_=0;
    void prepare();
    void prepare_coverage();
    bool valid_index()const;
    bool eligible(const ContentTarget&,std::optional<Seat>)const;
    std::vector<ContentTarget> enemy_heroes(std::optional<Seat>);
    std::optional<ContentTarget> spatial_nearest(const ContentTarget&);
};
} // namespace pvz::typed72
