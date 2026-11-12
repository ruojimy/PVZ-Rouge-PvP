#pragma once
#include "sim/typed/content_queries.h"
#include "sim/typed/seat_path_tracking.h"
#include <map>

namespace pvz::typed72 {
class SweetTaunts final : public ContentTaunts {
public:
    SweetTaunts(TypedBattleState& world,ZombieNavigation& navigation,SeatPathTracking& banks,
                const NativePathRules& rules,bool resist)
        :world_(world),navigation_(navigation),banks_(banks),paths_(world,navigation,rules),
         radius_(resist?3.:6.){}
    std::vector<PlantRef> potatoes()const;
    void mark_dirty(){dirty_=true;}
    void update();
    PlantRef taunting(const ContentTarget&)const;
    void apply(const ZombieRef&);
    void restore();
    std::optional<ContentTarget> taunt_target(const ContentTarget&,std::optional<ContentTarget>)override;
    const auto& fields()const{return fields_;}
    const auto& cached()const{return potatoes_;}
    const auto& baseline()const{return baseline_;}
    const auto& saved()const{return saved_;}
    size_t hidden_count()const{return hidden_.size();}
private:
    struct Hidden {TileRef tile;Field<bool> marker;};
    TypedBattleState& world_;
    ZombieNavigation& navigation_;
    SeatPathTracking& banks_;
    PathTracking paths_;
    double radius_;
    bool dirty_=true;
    std::vector<PlantRef> potatoes_;
    std::map<std::optional<std::string>,PathSnapshot> fields_;
    std::optional<PathSnapshot> baseline_;
    std::optional<ChaseSnapshot> saved_;
    std::vector<Hidden> hidden_;
    Point point(const CombatPlant&)const;
    static std::optional<std::string> key(const CombatPlant&);
};
} // namespace pvz::typed72
