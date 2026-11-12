#pragma once
#include "sim/typed/plant_aim.h"
#include "sim/typed/mortar_plants.h"
#include "sim/typed/squash_effects.h"
#include "sim/typed/bonus_projectiles.h"

namespace pvz::typed72 {
struct StarBurst {
    double created = 0.;
    Point origin;
    double speed = 1., direction = 1.;
    std::vector<EntityRef> stars;
    bool done = false;
};

class BonusPlantServices {
public:
    virtual ~BonusPlantServices() = default;
    virtual void prepare_star_atlas() = 0;
    virtual bool prepare_blue_pea_atlas() = 0;
    virtual void stored_add_entity(std::string name, double facing, Motion position) = 0;
};

class BonusPlants {
public:
    BonusPlants(TypedBattleState& world, NativeTracking& chart, SquashEffects& squash,
                BonusImpactServices& impacts, BonusPlantServices& assets)
        : world_(world), chart_(chart), squash_(squash), impacts_(impacts), assets_(assets), ballistics_(world) {}
    std::vector<std::shared_ptr<StarBurst>> pending_stars;
    std::vector<std::pair<RecordId, double>> grave_bites;
    uint64_t star_patches = 0, star_shots = 0, tripea_shots = 0, grave_bite_hits = 0;
    static std::array<double, 5> star_angles(double facing);
    static void apply_star(const EntityRef&, Point, Point velocity);
    void record_star(const EntityRef&, double facing);
    void finalize_stars();
    size_t spawn_stars(Point origin, double speed, double facing);
    bool star_target(Point origin, double facing);
    void starfruit();
    void star_damage();
    void tripea();
    void cleanup_stones();
    void grave_damage();
private:
    TypedBattleState& world_;
    NativeTracking& chart_;
    SquashEffects& squash_;
    BonusImpactServices& impacts_;
    BonusPlantServices& assets_;
    NativeBallistics ballistics_;
    std::array<Point, 3> centers(const PlantRef&) const;
    std::vector<double> angles(const PlantRef&, std::span<const Point>,
                              std::span<const std::optional<PlantAimTarget>>);
    bool spawn_tripea(Point origin, double angle, bool upgraded);
    bool grave_touch(const ZombieRef&, const PlantRef&, double scale) const;
};
} // namespace pvz::typed72
