#pragma once
#include "sim/typed/targets.h"
#include "sim/typed/ai_geometry.h"
#include <unordered_map>

namespace pvz::typed72 {
struct AiVisibleShot {
    std::string id,asset;
    Seat side;
    Point position,velocity;
    double gravity=0.,damage=10.;
    bool damage_estimated=true,slow=false,control=false;
    double splash=0.;
};
class AiNativeShotView {
public:
    const std::vector<AiVisibleShot>& sample(const EntityRoster&,double now,double width);
    std::vector<AiVisibleShot> visible(Point hero,double width)const;
    uint64_t seen()const{return seen_;}
private:
    struct Previous {Point position;double time;Point velocity;bool observed_before;};
    std::unordered_map<std::string,Previous> previous_;
    std::optional<double> last_time_;
    std::vector<AiVisibleShot> cached_;
    uint64_t seen_=0;
};
struct AiPublicCard {
    std::optional<std::string> name;
    std::string behavior;
    std::optional<double> cost,range;
    double damage=0.;
    bool producer=false,mushroom=false;
};
struct AiUnitView {
    std::string id,card;
    Seat side=Seat::plant;
    std::optional<Seat> seat;
    Point position;
    double hp=0.,plant_y=0.;
    bool grave=false;
    double max_hp=1.;
    Point velocity;
    bool mobile=false,awake=true;
    std::optional<std::string> behavior;
    AiPublicCard card_info;
};
using AiCardCounts=std::vector<std::pair<std::string,size_t>>;
AiCardCounts ai_own_counts(std::span<const AiUnitView>,Seat side,std::optional<Seat> seat={});
} // namespace pvz::typed72
