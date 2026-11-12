#pragma once
#include "sim/typed/flood.h"
#include "sim/typed/native_tracking.h"
#include "sim/typed/plant_spawn.h"
#include "sim/typed/projectile_rules.h"

namespace pvz::typed72 {
struct ZombieNavigation {
    std::array<FloodState,2> flood;
    std::array<std::shared_ptr<std::vector<int>>,2> chase_fields;
    Cell hero_cell,target_position;
    double output_plants=0.;
    bool initialized=false;
    int64_t target_plant=-1;
    double hold_plant=0.;
    double wave=0.,running=1.,screen_height=576.;
    bool scripted=false,director_available=false,cactus_secret=false,charm_secret=false;
    int64_t ladder_count=0,ladder_cooldown=0;
    std::vector<std::string> bosses;
    std::string water_sprite;
};
struct ZombieMotionFrame {
    size_t index=0;
    Cell cell;
    int flood_index=0,heading=0,original_heading=0,collision=0;
    bool immobile=false,can_bite=true,ladder=false;
};
class ZombieMotionServices : public NativeEntityConstructor {
public:
    virtual ~ZombieMotionServices()=default;
    virtual void ordinary(size_t,double,double)=0;
    virtual void surface(size_t,double,double)=0;
    virtual void request_ladder(const ZombieRef&)=0;
    virtual std::optional<Point> rally_destination(const ZombieRef&)=0;
};
// First half of the original mobile body at 68444..79050, after its per-body
// gate. Coordinate and index registration are also used by stationary targets.
class ZombieMotion {
public:
    ZombieMotion(TypedBattleState& w,ZombieNavigation& routes,TargetIndexes& indexes,
                 ZombieMotionServices& callbacks,PlantLifecycle& plants)
        :world_(w),routes_(routes),indexes_(indexes),callbacks_(callbacks),plants_(plants){}
    ZombieMotionFrame advance(size_t index);
    void register_body(Cell,std::string_view kind);
    void register_stationary(size_t index);
private:
    TypedBattleState& world_;
    ZombieNavigation& routes_;
    TargetIndexes& indexes_;
    ZombieMotionServices& callbacks_;
    PlantLifecycle& plants_;
    ZombieRef zombie(size_t index)const;
    bool secret(std::string_view)const;
    TileRef tile(int row,int64_t col)const;
    int flood(int field,int row,int64_t col)const;
    void entry(ZombieMotionFrame&);
    void environment(ZombieMotionFrame&);
    void status(ZombieMotionFrame&);
    void bite(ZombieMotionFrame&);
    void bite_plant(ZombieMotionFrame&,size_t target);
    void bite_write(size_t,size_t,double);
    double plant_bite(const ZombieRef&)const;
    double bite_rate(const ZombieRef&)const;
    double bite_amount(const ZombieRef&,const ZombieRef& target)const;
    void reciprocal(size_t target,const ZombieRef& attacker);
    void bite_hero(const ZombieRef&);
    void chase(ZombieMotionFrame&);
    void sound_at(const char*,int,size_t);
};
} // namespace pvz::typed72
