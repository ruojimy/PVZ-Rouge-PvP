#pragma once
#include "sim/typed/content_queries.h"
#include "sim/typed/content_frost.h"
#include "sim/typed/content_plant70_state.h"
#include <set>
namespace pvz::typed72 {
using WaterCells=std::set<std::pair<int,int64_t>>;
struct Plant70Event {
    enum class Kind {tentacle_spawn,tentacle_hit,lettuce_freeze} kind;
    Field<std::string> source,head,target;
    WaterCells water;
    std::vector<std::string> targets;
};
struct LettuceFlash {int64_t tick;WaterCells water;Point point;};
class ContentPlant70Services {
public:
    virtual ~ContentPlant70Services()=default;
    virtual PlantRef spawn_tentacle_native(Cell,double facing)=0;
    virtual void register_tentacle(const PlantRef&,const Field<std::string>& parent)=0;
    virtual void plant70_event(const Plant70Event&)=0;
    virtual void sync_terrain()=0;
    virtual void tentacle_knock(size_t,double)=0;
};
class ContentPlants70 {
public:
    ContentPlants70(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,
                    ContentFrost& frost,ContentPlant70Services& services,const std::vector<std::string>& aquatic_cards)
        :world_(world),queries_(queries),targets_(targets),frost_(frost),services_(services),aquatic_cards_(aquatic_cards){}
    std::vector<std::pair<std::string,PlantRef>> basins;
    WaterCells head_cells;
    std::vector<LettuceFlash> flashes;
    bool configure(PlantRef,std::string_view,double hp);
    void plant_tick(PlantRef);
    std::vector<PlantRef> heads(const PlantRef&)const;
    static bool is_head(const PlantRef&);
    PlantRef spawn_head(PlantRef);
    std::vector<ContentTarget> head_targets(const PlantRef&,std::optional<size_t> limit={});
    void update_heads(const PlantRef&,std::vector<PlantRef>);
    Point head_rest(const PlantRef&,const PlantRef&);
    void head_hit(const PlantRef&,const PlantRef&,Point start,Point end);
    void anchor_head(const PlantRef&);
    WaterCells head_only_cells()const;
    bool plant_in(Cell,const PlantRef& exclude={})const;
    void invalidate_occupancy()const{occupancy_tick_=-1;}
    struct OccupancyWork {uint64_t rebuilds=0,indexed_plants=0,queries=0,candidates=0,full_scan_candidates=0;};
    const OccupancyWork& occupancy_work()const{return occupancy_work_;}
    void restore_marks();
    void before_tick();
    void remove_basin(const PlantRef&);
    WaterCells water_component(Cell)const;
    bool target_in_water(const CombatTarget&,const WaterCells&)const;
    void try_lettuce(const PlantRef&);
    bool alive(const ContentTarget&)const;
    static double plant_rate(const PlantRef&);
private:
    TypedBattleState& world_;ContentQueries& queries_;ContentTargets& targets_;ContentFrost& frost_;
    ContentPlant70Services& services_;const std::vector<std::string>& aquatic_cards_;
    bool seat_has(const PlantRef&,std::string_view)const;
    static double factor(const PlantRef&);
    std::optional<ContentTarget> registered(const Field<std::string>&)const;
    mutable int64_t occupancy_tick_=-1;
    mutable uint64_t occupancy_revision_=0;
    mutable const PlantRoster* occupancy_roster_=nullptr;
    mutable const PlantRef* occupancy_data_=nullptr;
    mutable size_t occupancy_count_=0;
    mutable int occupancy_rows_=0,occupancy_cols_=0;
    mutable std::vector<std::vector<PlantRef>> occupancy_buckets_;
    mutable std::vector<PlantRef> occupancy_outside_;
    mutable std::unordered_map<const CombatPlant*,Cell> occupancy_cells_;
    mutable OccupancyWork occupancy_work_;
    void prepare_occupancy(bool force=false)const;
    std::vector<PlantRef>& occupancy_bucket(Cell)const;
    bool plant_in_cached(Cell,const PlantRef& exclude={},bool non_head=false)const;
    void anchor_head_cached(const PlantRef&);
};
} // namespace pvz::typed72
