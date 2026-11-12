#pragma once
#include "sim/typed/entity_contacts.h"
#include "sim/typed/squash_effects.h"
#include "sim/typed/plant_spawn.h"
namespace pvz::typed72 {
using EntitySprite=std::variant<std::string,uint64_t>;
struct EntityDraw {
    EntitySprite sprite;
    Point position;
    bool mirrored=false;
    std::optional<double> rotation;
    std::optional<Point> dimensions;
};
// Interface to per-match targeting gates and the platform's sprite atlas.
// Each call is synchronous. Even a hidden draw still advances native rotation.
class EntityRenderer {
public:
    virtual ~EntityRenderer()=default;
    virtual void draw(EntityDraw)=0;
    virtual void alpha(const EntitySprite&,double)=0;
};
class EntityRegionBindings : public EntityRenderer {
public:
    virtual void tracking_gate(size_t index)=0;
    virtual std::optional<size_t> nearest_target()const=0;
};
struct EntityRegionEnvironment {
    double driving=0.,camera_y=0.;
    std::string water_particle;
    int last_landing=0;
};
class EntityRegion {
public:
    EntityRegion(TypedBattleState& world,EntityRegionEnvironment& env,const EntityRegionRules& rules,
                 EntityContacts& contacts,ProjectileRules& flight,SquashEffects& squash,
                 SquashCallbacks& damage,PlantLifecycle& plants,EntityRegionBindings& bindings)
        :world_(world),env_(env),rules_(rules),contacts_(contacts),flight_(flight),squash_(squash),
         damage_(damage),plants_(plants),bindings_(bindings){}
    void run();
private:
    struct Frame {
        size_t index;
        std::string name,suffix;
        bool remove=false;
        int collision=0;
        Cell cell;
    };
    TypedBattleState& world_;
    EntityRegionEnvironment& env_;
    const EntityRegionRules& rules_;
    EntityContacts& contacts_;
    ProjectileRules& flight_;
    SquashEffects& squash_;
    SquashCallbacks& damage_;
    PlantLifecycle& plants_;
    EntityRegionBindings& bindings_;
    EntityRef entity(size_t i)const{return world_.runtime.entities.list()->at(i);}
    Motion& position(const CombatTarget&)const;
    ZombieRecordFields& body(const CombatTarget&)const;
    TileRef tile_at(Cell)const;
    void move(Frame&);
    void special(Frame&);
    void basketball(Frame&);
    void seaweed(Frame&);
    void environment(Frame&);
    void render(Frame&);
    void impact(Frame&);
};
} // namespace pvz::typed72
