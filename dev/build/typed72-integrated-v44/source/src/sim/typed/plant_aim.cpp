#include "sim/typed/plant_aim.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
class QueryChart {
public:
    QueryChart(NativeTracking& chart,const PlantRef& plant):chart_(chart),restore_(!chart.active()) {
        if(restore_)chart_.begin(TrackingSource::from(plant));
    }
    ~QueryChart(){if(restore_)chart_.restore();}
private:
    NativeTracking& chart_;
    bool restore_;
};
void append_column(TargetBuckets& rows,Cell cell,int64_t column) {
    const auto found=std::find_if(rows.begin(),rows.end(),[&](const auto& row){return row.first==cell.y;});
    if(found==rows.end())rows.emplace_back(cell.y,std::vector<int64_t>{column});
    else found->second.push_back(column);
}
double desired_angle(const std::optional<PlantAimTarget>& target,Point center,double base,double width) {
    if(!target)return base;
    const auto dx=wrap_delta(center.x,target->point.x,width);
    return std::atan2(target->point.y-center.y,dx)*(180./0x1.921fb54442d18p+1);
}
double difference(double angle,double base){return py::mod(angle-base+180.,360.)-180.;}
}

std::vector<std::optional<PlantAimTarget>> pick_tripea_targets(TypedBattleState& world,NativeTracking& chart,
    const PlantRef& plant,double facing,std::span<const Point> centers) {
    QueryChart scope(chart,plant);
    if(centers.empty())return {};
    const double direction=facing<0.?-1.:1.;
    std::vector<PlantAimTarget> alive;
    alive.reserve(world.targets->size());
    for(size_t index=0;index<world.targets->size();++index) {
        const auto target=world.targets->at(index);
        const auto& body=target.is_hero()?static_cast<const ZombieRecordFields&>(world.heroes.cached_proxy(target.hero)):
                                          static_cast<const ZombieRecordFields&>(target.unit->body);
        const auto& source=target.is_hero()?world.heroes.cached_proxy(target.hero).source:target.unit->source;
        if(body.hp<=0. || source.charmed.present() || body.ash.present())continue;
        const auto& point=target.is_hero()?*world.heroes.cached_proxy(target.hero).position:target.unit->body.motion.get();
        const auto size=body.size.present()&&!body.size.is_null()?body.size.get():2.;
        alive.push_back({index,target,{point.x,point.y-world.runtime.tile*.42*std::max(.8,size)}});
    }
    std::vector<std::optional<PlantAimTarget>> targets;
    targets.reserve(centers.size());
    std::vector<uint8_t> used(world.targets->size());
    for(const auto center:centers) {
        const PlantAimTarget* nearest=nullptr;
        const PlantAimTarget* unused=nullptr;
        double nearest_score=0.,unused_score=0.;
        for(const auto& candidate:alive) {
            const double dx=candidate.point.x-center.x,dy=candidate.point.y-center.y;
            if(dx*direction < -1.)continue;
            const double score=dx*dx+dy*dy;
            if(!nearest || score<nearest_score){nearest=&candidate;nearest_score=score;}
            if(!used[candidate.index] && (!unused || score<unused_score)){unused=&candidate;unused_score=score;}
        }
        const auto selected=unused?unused:nearest;
        if(selected){used[selected->index]=1;targets.push_back(*selected);}
        else targets.push_back(std::nullopt);
    }
    return targets;
}

void PeaHybrid::restore(){if(saved_rows_)indexes_.rows=std::move(saved_rows_);}
void PeaHybrid::gate(const PlantRef& plant,bool enabled) {
    restore();
    if(!plant)return;
    const auto& content=plant->source.content;
    if(content.present() && !content.is_null() && !content.get().empty() && content.get()!="原始豌豆射手")return;
    static constexpr std::string_view shooters[]={"豌豆射手","寒冰射手","双发射手","机枪射手","裂荚射手"};
    if(!enabled || plant->sleep.present() || std::find(std::begin(shooters),std::end(shooters),plant->kind)==std::end(shooters))return;
    aim(plant);
}
std::optional<PlantAimTarget> PeaHybrid::target(const PlantRef& plant,Point center,double facing) {
    return pick_tripea_targets(world_,chart_,plant,facing,std::span<const Point>(&center,1)).front();
}
void PeaHybrid::aim(const PlantRef& plant) {
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    const auto cell=plant->cell;
    if(plant->kind=="裂荚射手") {
        const auto saved=indexes_.rows;
        auto rows=std::make_shared<TargetBuckets>(*saved);
        if(!plant->split_pea_angles.present()) {
            std::array<Field<double>,2> angles;
            angles[0].set(0.);angles[1].set(180.);
            plant->split_pea_angles.set(std::move(angles));
        }
        for(size_t side=0;side<2;++side) {
            const double direction=side==0?1.:-1.;
            const Point center{(cell.x+.5+direction*.3)*tile,(cell.y+.4)*tile};
            auto chosen=target(plant,center,direction);
            const double base=direction>0.?0.:180.;
            double desired=desired_angle(chosen,center,base,width);
            if(std::abs(difference(desired,base))>45.){chosen.reset();desired=base;}
            auto& angle=plant->split_pea_angles.get().at(side);
            const double old=angle.or_missing(base);
            angle.set(old+difference(desired,old)*.3);
            if(chosen)append_column(*rows,cell,int64_t(std::floor(chosen->point.x/tile)));
        }
        if(*rows!=*saved){saved_rows_=saved;indexes_.rows=std::move(rows);}
        return;
    }
    const Point center{(cell.x+.5)*tile,(cell.y+.4)*tile};
    auto chosen=target(plant,center,plant->facing);
    const double base=plant->facing>0.?0.:180.;
    double desired=desired_angle(chosen,center,base,width);
    if(std::abs(difference(desired,base))>45.){chosen.reset();desired=base;}
    const auto old=plant->pea_angle.or_missing(base);
    plant->pea_angle.set(old+difference(desired,old)*.3);
    if(chosen) {
        auto rows=std::make_shared<TargetBuckets>(*indexes_.rows);
        append_column(*rows,cell,int64_t(std::floor(chosen->point.x/tile)));
        saved_rows_=std::exchange(indexes_.rows,std::move(rows));
    }
}
void PeaHybrid::after_birth(const PlantRef& source,size_t first) {
    if(!source || (!source->pea_angle.present() && !source->split_pea_angles.present()))return;
    const auto entities=world_.runtime.entities.list();
    for(size_t index=first;index<entities->size();++index) {
        const auto& entity=*entities->at(index);
        if(entity.kind!="豌豆" && entity.kind!="冰豆" && entity.kind!="火豆" && entity.kind!="蓝火豆")continue;
        auto& motion=entities->at(index)->motion.get();
        const auto degrees=source->split_pea_angles.present()?source->split_pea_angles.get().at(motion.vx>=0.?0:1).get():source->pea_angle.get();
        const auto radians=degrees*(0x1.921fb54442d18p+1/180.);
        const auto speed=std::hypot(motion.vx,motion.vy);
        motion.vx=std::cos(radians)*speed;motion.vy=std::sin(radians)*speed;
    }
}
} // namespace pvz::typed72
