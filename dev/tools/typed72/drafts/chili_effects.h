#pragma once
#include "sim/typed/terrain_effects.h"
#include <set>
namespace pvz::typed72 {
struct FlameBox {double left=0.,right=0.,top=0.,bottom=0.;};
struct FireSnap {int64_t row=0,col=0;std::optional<int64_t> ground;double y=0.;};
using FireRows=std::set<int64_t>;
class ChiliEffects;
class ChiliImpactDispatch {
public:
    virtual ~ChiliImpactDispatch()=default;
    virtual void chili_ash(size_t)=0;
    virtual bool chili_hit_one(ChiliEffects&,const EntityRef&,size_t,const CombatTarget&,std::vector<ChiliKey>&,FlameBox,double,const std::optional<FireRows>&)=0;
    virtual bool chili_player_launch(const EntityRef&)const=0;
};
class ChiliServices {
public:
    virtual ~ChiliServices()=default;
    virtual void add_entity(std::string,double facing,Motion)=0;
    virtual void damage_player(double)=0;
};
// These four calls are wrapped by NativeCombatPatch.bind_targets. Keeping the
// calls explicit permits the same synchronous nested source contexts, rather
// than bypassing them with private helper calls when the full driver binds.
class ChiliDispatch {
public:
    virtual ~ChiliDispatch()=default;
    virtual std::optional<int> row_hint(const CombatTarget&,bool force)=0;
    virtual void enemy_scan(const EntityRef&,FlameBox,double scale)=0;
    virtual void player_hit(const EntityRef&,FlameBox,double scale)=0;
    virtual void hit_zombies(const EntityRef&,FlameBox,double scale,bool charmed_only,const std::optional<FireRows>&)=0;
};
class ChiliEffects {
public:
    ChiliEffects(TypedBattleState& w,TargetDamage& d,PlantLifecycle& p,ChiliServices& s,ChiliDispatch& calls)
        :world_(w),damage_(d),plants_(p),services_(s),calls_(calls){}
    ChiliCounters counters;
    void bind_impacts(ChiliImpactDispatch& installed){
        if(impacts_&&impacts_!=&installed)throw std::logic_error("chili impacts already bound");impacts_=&installed;
    }
    bool has_installed_impacts()const noexcept{return impacts_!=nullptr;}
    void require_installed_impacts(bool required=true){impacts_required_=required;}
    bool enemy_fire(const Entity&)const;
    FireRows target_rows(const Entity&,double scale)const;
    std::optional<FireSnap> snap(const EntityRef&);
    void patch_fire(const EntityRef&);
    bool spawn_fire(const ZombieRef&,bool friendly);
    void scan();
    std::optional<int> row_hint(const CombatTarget&,bool force=false);
    void update_hints();
    FireRows source_rows(const ZombieRef&,std::optional<double> scale={});
    bool launch_locked(std::optional<double> now={})const;
    void launch_guard(std::optional<double> now={});
    const Field<ChiliHits>& mark_player(const EntityRef&);
    void player_hit(const EntityRef&,FlameBox,double scale);
    void damage_player(double center_x,FlameBox,double scale,const ChiliKey&,const std::optional<FireRows>&);
    void hit_plants(const EntityRef&,FlameBox,double scale,const std::optional<FireRows>&);
    bool hit_one(const EntityRef&,size_t index,const CombatTarget&,std::vector<ChiliKey>&,FlameBox,double scale,const std::optional<FireRows>&);
    bool raw_hit_one(const EntityRef&,size_t index,const CombatTarget&,std::vector<ChiliKey>&,FlameBox,double scale,const std::optional<FireRows>&);
    void hit_zombies(const EntityRef&,FlameBox,double scale,bool charmed_only,const std::optional<FireRows>&);
    void enemy_scan(const EntityRef&,FlameBox,double scale);
private:
    TypedBattleState& world_;
    TargetDamage& damage_;
    PlantLifecycle& plants_;
    ChiliServices& services_;
    ChiliDispatch& calls_;
    ChiliImpactDispatch* impacts_=nullptr;
    bool impacts_required_=false;
    RecordId identity(const CombatTarget&)const;
    const Motion& position(const CombatTarget&)const;
    ChiliHits hits(const EntityRef&);
    FlameBox box(const Entity&,double scale)const;
};
} // namespace pvz::typed72
