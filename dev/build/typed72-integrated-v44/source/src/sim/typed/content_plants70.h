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
    bool configure(const PlantRef&,std::string_view,double hp);
    void plant_tick(const PlantRef&);
    std::vector<PlantRef> heads(const PlantRef&)const;
    static bool is_head(const PlantRef&);
    PlantRef spawn_head(const PlantRef&);
    std::vector<ContentTarget> head_targets(const PlantRef&);
    void update_heads(const PlantRef&,std::vector<PlantRef>);
    Point head_rest(const PlantRef&,const PlantRef&);
    void head_hit(const PlantRef&,const PlantRef&,Point start,Point end);
    void anchor_head(const PlantRef&);
    WaterCells head_only_cells()const;
    bool plant_in(Cell,const PlantRef& exclude={})const;
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
};
} // namespace pvz::typed72
