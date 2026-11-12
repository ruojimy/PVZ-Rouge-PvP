#pragma once
#include "sim/typed/ai_observation.h"
#include <array>

namespace pvz::typed72 {
// A view of already published facts, never a second simulation world. The
// caller projects only the named fields of the existing authoritative records.
struct AiPublicHero {
    Point position,velocity;
    double w=38.,h=91.,hp=0.,max_hp=1.,resource=0.,teleport_ready=0.;
    int64_t facing=1,jump_cap=2,jumps=0,poison=0;
    bool grounded=false,frozen=false,slowed=false,buttered=false,absent=false,cannon_aimed=false;
};
struct AiDeckCardView {
    std::string id,name,behavior;
    double cost=0.,cooldown_ready=0.;
    std::optional<double> range;
    bool producer=false,mushroom=false,secret=false;
    bool aquatic=false,lob=false,star=false,homing=false;
};
struct AiPublicResource {std::string id;Seat side=Seat::plant;Point position;double amount=0.;std::optional<std::string> source;};
struct AiObservationFrame {
    const AiPublicHero* mine=nullptr;
    const AiPublicHero* enemy=nullptr;
    std::span<const AiUnitView> units;
    std::span<const AiVisibleShot> shots;
    std::span<const AiPublicResource> resources;
    std::span<const AiDeckCardView> cards;
    double time=0.;int64_t tick=0;
    bool night=false,deathmatch=false,enemy_input_present=false;
};
struct AiObservedThreat {std::string type;bool from_left=false;int64_t eta_ms=0;double severity=0.;bool splash=false,projectile=false;};
struct AiObservedZone {int zone=0;int64_t friendly_value=0,enemy_value=0;double pressure=0.;};
struct AiObservedTarget {Point position;int64_t dx=0,dy=0;double plant_y=0.;int zone=0;std::string card;bool producer=false;};
struct AiObservedUnit {std::string card;std::optional<std::string> name,behavior;int64_t dx=0,dy=0;int zone=0;double hp_pct=0.;bool mobile=false;};
struct AiObservedAnchor {std::string id;int zone=0;int64_t x=0;double hp_pct=0.;};
struct AiObservedCollectable {std::string id;int64_t dx=0,amount=0;std::optional<std::string> source;};
struct AiObservedTool {std::string id,card;std::optional<std::string> name;int64_t dx=0,dy=0;int zone=0;double hp_pct=0.;};
struct AiObservedCard {std::string id,name,behavior;double cost=0.,cooldown_left=0.;bool affordable=false,ready=false,producer=false,mushroom=false;std::optional<double> range;};
struct AiObservedHero {double hp_pct=0.;int64_t x=0,y=0,vx=0,vy=0;int zone=0;int64_t facing=1,jumps_left=0,poison_level=0;bool grounded=false,frozen=false,slowed=false,buttered=false;double teleport_ready_in=0.;};
struct AiObservedEnemyHero {double hp_pct=0.;int64_t dx=0,dy=0;int zone=0;int64_t facing=1,resource=0;};
struct AiObservation {
    int64_t match_id=0,observation_id=0,tick=0,plan_id=0;
    double time=0.,width=0.,income=0.,danger=0.;Seat side=Seat::plant;
    bool night=false,deathmatch=false,cannon_aimed=false;
    int64_t resource=0;size_t producer_count=0,my_unit_count=0,enemy_unit_count=0;
    AiObservedHero hero;AiObservedEnemyHero enemy_hero;
    std::array<AiObservedZone,6> zones;
    std::vector<AiObservedTarget> sleeping_plants,empty_supports;
    std::vector<AiObservedCard> cards;
    std::vector<AiObservedThreat> threats;
    std::vector<AiObservedUnit> enemy_units;
    std::vector<AiObservedAnchor> deploy_anchors;
    std::vector<AiObservedCollectable> collectable;
    std::vector<AiObservedTool> cannons,shovel_targets;
};
class AiObservationBuilder {
public:
    AiObservationBuilder(Seat side,double width,double height,double tile,bool night=false);
    AiObservation build(const AiObservationFrame&,int64_t plan_id=0,int64_t match_id=0,int64_t observation_id=0);
    std::array<AiObservedZone,6> zones(std::span<const AiUnitView>)const;
    int zone(double x)const;
private:
    Seat side_;double width_,height_,tile_;bool night_;
    std::optional<double> last_time_,last_resource_;
    std::vector<AiObservedThreat> threats(const AiObservationFrame&)const;
    std::vector<AiObservedTarget> plant_targets(const AiObservationFrame&,bool supports)const;
};
} // namespace pvz::typed72
