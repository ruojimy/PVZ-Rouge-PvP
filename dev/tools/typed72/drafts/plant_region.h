#pragma once
#include "sim/typed/world_regions.h"
#include "sim/typed/native_tracking.h"
#include "sim/typed/zombie_actions.h"

namespace pvz::typed72 {
struct PlantRegionRules {
    std::vector<std::string> air_plants,flying_plants,metal,bosses,thrown;
    bool lantern_secret=false;
};
struct PlantRegionState {
    std::optional<Cell> selected_cannon;
    Cell pointer;
    std::string held_card,placement_status;
    double wave=0.;
};
class PlantRegionServices : public NativeEntityConstructor {
public:
    virtual ~PlantRegionServices()=default;
    virtual void plant_gate(size_t)=0;
    virtual bool star_target()=0;
    virtual std::span<const int64_t> pitcher_columns()=0;
    virtual bool edible(size_t)=0;
    virtual bool wind_target(size_t)=0;
    virtual void ordinary(size_t,double facing,double damage)=0;
    virtual void surface(size_t,double facing,double damage)=0;
    virtual void summon_zombie(std::string,Motion,double facing)=0;
};
class PlantRegion {
public:
    PlantRegion(TypedBattleState& world,WorldRegionState& native,TargetIndexes& indexes,
                ZombieActionState& zombie_state,PlantRegionState& state,const PlantRegionRules& rules,
                PlantRegionServices& services,PlantLifecycle& lifecycle)
        :world_(world),native_(native),indexes_(indexes),zombie_state_(zombie_state),state_(state),
         rules_(rules),services_(services),lifecycle_(lifecycle){}
    void run();
private:
    struct Frame {size_t index;Cell cell;std::string name;};
    TypedBattleState& world_;
    WorldRegionState& native_;
    TargetIndexes& indexes_;
    ZombieActionState& zombie_state_;
    PlantRegionState& state_;
    const PlantRegionRules& rules_;
    PlantRegionServices& services_;
    PlantLifecycle& lifecycle_;
    CombatPlant& plant(size_t)const;
    ZombieRecordFields& body(size_t)const;
    ZombieNativeState& zombie_native(size_t)const;
    Motion& position(size_t)const;
    bool secret(std::string_view)const;
    bool needs_support(size_t)const;
    const std::vector<int64_t>* row(int64_t)const;
    bool ahead(const Frame&,double facing,double range)const;
    bool nearby_row(Cell,int radius)const;
    Point center(size_t)const;
    Entity& spawn(std::string,double,Motion);
    void sound(std::string,size_t);
    void imitation_clouds(const Frame&);
    void cannon(const Frame&);
    void squash(const Frame&);
    void fume(const Frame&);
    void puff(const Frame&);
    void split(const Frame&);
    void shooters(const Frame&);
    void cattail(const Frame&);
    void spikes(const Frame&);
    void umbrella(const Frame&);
    void chomper(const Frame&);
    void gloom(const Frame&);
    void pitcher(const Frame&);
    void lantern(const Frame&);
    void marigold(const Frame&);
    void magnet(const Frame&);
    void freezing(const Frame&);
    void imitation(const Frame&);
    void gravebuster(const Frame&);
    void blover(const Frame&);
    void mine(const Frame&);
    void producers(const Frame&);
};
} // namespace pvz::typed72
