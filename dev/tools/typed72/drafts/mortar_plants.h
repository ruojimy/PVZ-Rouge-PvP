#pragma once
#include "sim/typed/ballistics.h"
#include "sim/typed/content_queries.h"

namespace pvz::typed72 {
struct SpringSwipe {int64_t tick;Point point;double angle;};
struct MortarPlantEvent {
    Field<std::string> source;
    bool spring=false;
    size_t shots=0;
    std::vector<std::string> targets;
};
struct MortarAim {Point start;std::optional<BallisticSolution> solution;};
class MortarPlantServices {
public:
    virtual ~MortarPlantServices()=default;
    virtual void mortar_event(const MortarPlantEvent&)=0;
    virtual void spring_knockback(size_t index,double amount)=0;
};
class MortarPlants {
public:
    MortarPlants(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,MortarPlantServices& services)
        :world_(world),queries_(queries),targets_(targets),services_(services),
         gravity_(4.*world.runtime.plk),speed_(800.*world.runtime.plk){}
    std::vector<SpringSwipe> swipes;
    bool configure(const PlantRef&,std::string_view);
    void advance(const PlantRef&);
    std::vector<ContentTarget> enemies(const PlantRef&);
    std::pair<Point,double> muzzle(const PlantRef&)const;
    std::vector<ContentTarget> mortar_targets(const PlantRef&);
    Point lead(const ContentTarget&)const;
    MortarAim aim(const PlantRef&,const ContentTarget&)const;
    bool mortar(const PlantRef&);
    bool spring(const PlantRef&);
    static void red_pea(const EntityRef&);
    void split_pea_blue(const EntityRef&)const;
    void before_entities();
    static double projectile_damage(const EntityRef&,const ContentTarget&,double amount);
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    MortarPlantServices& services_;
    double gravity_,speed_;
    bool blue_secret()const;
};
size_t reflect_mortar_projectiles(TypedBattleState&,const AttackSource&,Point center,double radius_tiles);
} // namespace pvz::typed72
