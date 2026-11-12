#pragma once
#include "sim/typed/native_tracking.h"
#include "sim/typed/ai_geometry.h"

namespace pvz::typed72 {
struct AiFieldSpot {Point point;bool water;};
class AiField {
public:
    AiField(const TargetSight& terrain,double width,double height,double tile,std::optional<std::string> hash={});
    std::vector<AiFieldSpot> candidates(int zone,double hero_x,std::optional<double> hero_y={},int64_t limit=8)const;
    std::vector<int> zones_in_view(double hero_x)const;
    double width,height,tile;
    std::optional<std::string> terrain_hash;
    std::array<std::vector<AiFieldSpot>,6> spots;
};
class AiFieldCache {
public:
    const AiField* update(const TargetSight*,double width,double height,double tile,int64_t revision,std::optional<std::string> hash={});
private:
    std::optional<int64_t> revision_;
    std::unique_ptr<AiField> field_;
};
} // namespace pvz::typed72
