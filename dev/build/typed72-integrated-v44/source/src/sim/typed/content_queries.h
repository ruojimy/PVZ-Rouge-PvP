#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/moving_point_grid.h"

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
    std::optional<ContentTarget> nearest(const ContentTarget& source);
    std::optional<ContentTarget> route(const ContentTarget& source,std::optional<ContentTarget> goal,
                                      std::span<const ContentTarget> candidates)const;
    std::shared_ptr<AttackSource> source(const ContentTarget&)const;
    std::optional<ContentTarget> route_enemies(const ContentTarget&,std::optional<ContentTarget>,bool heroes=true);
    void moved(const ContentTarget&);
    void invalidate(){index_tick_=-1;}
    uint64_t local_queries=0,local_candidates=0;
    const MovingPointGrid& moving_index()const{return points_;}
private:
    TypedBattleState& world_;
    ContentTargets& targets_;
    ContentTaunts& taunts_;
    MovingPointGrid points_;
    std::vector<ContentTarget> indexed_;
    std::unordered_map<const void*,size_t> object_ids_;
    const CombatTarget* zombie_data_=nullptr;const PlantRef* plant_data_=nullptr;
    const TargetRoster* zombie_roster_=nullptr;const PlantRoster* plant_roster_=nullptr;
    size_t zombie_count_=0,plant_count_=0;int64_t index_tick_=-1;
    std::vector<uint64_t> query_seen_;uint64_t query_stamp_=0;
    void prepare();
    bool valid_index()const;
    bool eligible(const ContentTarget&,std::optional<Seat>)const;
    std::vector<ContentTarget> enemy_heroes(std::optional<Seat>);
    std::optional<ContentTarget> spatial_nearest(const ContentTarget&);
};
} // namespace pvz::typed72
