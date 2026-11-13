#pragma once
#include "sim/typed/targets.h"

namespace pvz::typed72 {
// Both tables preserve insertion order. When columns are translated across
// the seam, two buckets can merge and their original order breaks ties.
using TargetBuckets=std::vector<std::pair<int64_t,std::vector<int64_t>>>;
struct TargetIndexes {
    std::shared_ptr<TargetBuckets> rows=std::make_shared<TargetBuckets>();
    std::shared_ptr<TargetBuckets> columns=std::make_shared<TargetBuckets>();
    std::vector<int64_t> ladders;
    std::optional<size_t> nearest;
    double nearest_distance=0.;
    void register_body(Cell,std::string_view kind={});
};
struct TrackingSource {
    std::shared_ptr<AttackSource> record;
    std::optional<Cell> plant_cell;
    std::optional<Point> position;
    static TrackingSource from(const EntityRef&);
    static TrackingSource from(const PlantRef&);
};
struct TargetSight {
    // Simulation.cell reads the last published map, including edits made
    // before the publish. Its solidity can differ from live native terrain.
    std::vector<std::vector<uint8_t>> solid;
    std::vector<std::vector<uint8_t>> water;
    double hero_lock_range=360.;
    bool water_at(Point,double tile,double width)const;
};
class NativeTracking {
public:
    NativeTracking(TypedBattleState& w,TargetIndexes& indexes,const TargetSight& sight)
        :world_(w),indexes_(indexes),sight_(sight){}
    NativeTracking(const NativeTracking&)=delete;
    ~NativeTracking(){restore();}
    void begin(const TrackingSource&);
    void restore();
    bool active()const{return active_;}
    void target_index(const TrackingSource& source={});
    void tracking_index(const TrackingSource&);
    bool hero_lock(const TrackingSource&,Seat)const;
    uint64_t nearest_queries=0,nearest_candidates=0,nearest_full_scan=0;
private:
    TypedBattleState& world_;
    TargetIndexes& indexes_;
    const TargetSight& sight_;
    std::shared_ptr<TargetBuckets> saved_rows_,saved_columns_;
    std::vector<std::pair<CombatTarget,std::shared_ptr<Motion>>> shifted_;
    bool active_=false;
    struct ChartEntry{double x;CombatTarget target;std::shared_ptr<Motion> motion;size_t index=0;bool ladder=false;};
    struct SearchEntry{double x;size_t index;};
    const TargetRoster* chart_roster_=nullptr;
    const CombatTarget* chart_data_=nullptr;
    size_t chart_count_=0;int64_t chart_tick_=-1;
    std::vector<ChartEntry> chart_entries_;
    std::vector<SearchEntry> search_entries_;
    std::vector<size_t> ladder_indices_,hero_indices_;
    bool search_ids_ready_=false;
    std::vector<uint64_t> search_seen_;uint64_t search_stamp_=0;
    void prepare_chart();
    std::shared_ptr<Motion> position(const CombatTarget&)const;
    bool within_sight(Point,Point,double)const;
};
} // namespace pvz::typed72
