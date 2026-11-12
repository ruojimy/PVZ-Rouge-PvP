#pragma once
#include "sim/typed/native_status.h"
#include "sim/typed/content_queries.h"
#include "sim/typed/native_barrels.h"
#include "sim/typed/projectile_rules.h"
namespace pvz::typed72 {
class DartPresentation {
public:
    virtual ~DartPresentation()=default;
    virtual void draw_dart(const EntityRef&,Point,double angle)=0;
};
class ContentDarts {
public:
    ContentDarts(TypedBattleState& world,ContentQueries& queries,ContentTargets& damage,
                 NativeStatus& status,const CollisionCatalog& collision,DartPresentation& presentation,
                 const bool& drawing)
        :world_(world),queries_(queries),damage_(damage),status_(status),collision_(collision),
         presentation_(presentation),drawing_(drawing){}
    bool broad_phase=true;
    std::shared_ptr<EntityRoster> pending=std::make_shared<EntityRoster>();
    static bool content(std::string_view name){return name=="回旋镖射手"||name=="毒镖射手";}
    static void prepare(const EntityRef&);
    void separate();
    void projectiles();
    void clover_blow();
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& damage_;
    NativeStatus& status_;
    const CollisionCatalog& collision_;
    DartPresentation& presentation_;
    const bool& drawing_;
    static ZombieRef body(const ContentTarget&);
    static bool same(const ContentTarget&,const ContentTarget&);
    std::optional<Ellipse> head(const ContentTarget&)const;
    bool head_overlaps(const ContentTarget&,Point,double radius)const;
};
} // namespace pvz::typed72
