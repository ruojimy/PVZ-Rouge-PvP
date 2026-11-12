// The raw-stage caller and the live native plant roster share this attack body.
#include "sim/typed/shooter.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
struct StageShooter {
    Shooter& plant;
    size_t targets;
    ShooterKind kind()const{return plant.kind;}
    double row()const{return plant.row;}
    double column()const{return plant.col;}
    double facing()const{return plant.facing;}
    double& cooldown(){return plant.cooldown;}
    double& animation(){return plant.animation;}
    double& double_shot(){return plant.double_shot;}
    double& gatling_shot(){return plant.gatling_shot;}
    size_t target_count()const{return targets;}
};
struct RosterShooter {
    TypedBattleState& world;
    size_t index;
    ShooterKind selected_kind;
    CombatPlant& plant()const{return *world.plant_roster->at(index);}
    ShooterKind kind()const{return selected_kind;}
    double row()const{return double(plant().cell.y);}
    double column()const{return double(plant().cell.x);}
    double facing()const{return plant().facing;}
    double& cooldown(){return plant().shoot_cd.get();}
    double& animation(){return plant().shooting.get();}
    double& double_shot(){return plant().double_shot.get();}
    double& gatling_shot(){return plant().gatling.get();}
    size_t target_count()const{return world.targets->size();}
};
template<class Access,class Coordinate>
void attack(CombatRuntime& runtime,Access plant,const std::vector<Coordinate>* targets,bool emperor,bool star_target) {
    ++runtime.shot_calls;
    if(runtime.branch(32,plant.cooldown()<=0.)) {
        bool shoot=false;
        if(plant.kind()==ShooterKind::star)shoot=star_target;
        else if(targets) {
            const double range=plant.kind()==ShooterKind::cactus?72.:24.;
            for(const auto target:*targets) {
                if(((plant.facing()==1. && target>=plant.column()) || (plant.facing()==-1. && target<=plant.column())) &&
                    std::abs(target-plant.column())<=range){shoot=true;break;}
            }
        }
        if(runtime.branch(33,shoot)) {
            plant.animation()=1.;
            if(runtime.branch(34,plant.cooldown()==-1.))plant.cooldown()=double(runtime.rng.randint(0,200));
            plant.cooldown()+=500.;
            if(plant.kind()==ShooterKind::repeater) {
                if(runtime.branch(35,plant.double_shot()==0.)){plant.cooldown()=100.;++plant.double_shot();}
                else plant.double_shot()=0.;
            }
            if(plant.kind()==ShooterKind::gatling) {
                if(runtime.branch(36,plant.gatling_shot()<=2.)){plant.cooldown()=50.;++plant.gatling_shot();}
                else plant.gatling_shot()=0.;
            }
            const std::string name=plant.kind()==ShooterKind::cactus?"尖刺":plant.kind()==ShooterKind::ice_pea?"冰豆":"豌豆";
            runtime.sound(plant.kind()==ShooterKind::ice_pea?"冰豆":"射豆",
                          {plant.column()*runtime.tile+runtime.tile*.5,plant.row()*runtime.tile+runtime.tile*.5,0.,0.});
            if(plant.kind()==ShooterKind::star) {
                const double bonus=double(plant.target_count())*10.;
                if(runtime.branch(37,emperor))plant.cooldown()-=double(plant.target_count())*7.;
                runtime.native_constructor->add_entity("星星",plant.facing(),
                    {plant.column()*runtime.tile+runtime.tile*.5,plant.row()*runtime.tile+runtime.tile*.5,
                     plant.facing()*(200.+bonus)*runtime.plk,0.});
                runtime.native_constructor->add_entity("星星",-plant.facing(),
                    {plant.column()*runtime.tile+runtime.tile*.5,plant.row()*runtime.tile+runtime.tile*.5,
                     -plant.facing()*(200.+bonus)*runtime.plk,0.});
                // The source writes the current two tail entries after both
                // constructors, including any roster replacement they cause.
                for(size_t offset=0;offset<2;++offset) {
                    const auto& list=*runtime.entities.list();
                    auto& entity=*list.at(list.size()-1-offset);
                    entity.through_wall.set(0.);entity.expires.set(-1000.);
                }
            }else {
                runtime.native_constructor->add_entity(name,plant.facing(),
                    {plant.column()*runtime.tile+runtime.tile*.5+plant.facing()*runtime.tile*.3,
                     plant.row()*runtime.tile+runtime.tile*.5,plant.facing()*200.*runtime.plk,0.});
                if(runtime.branch(38,name=="尖刺")) {
                    const auto entities=runtime.entities.list();auto& entity=*entities->at(entities->size()-1);
                    entity.through_wall.set(0.);entity.expires.set(-2000.);
                }
            }
        }else plant.cooldown()=-1.;
    }else --plant.cooldown();
    if(runtime.branch(39,plant.animation()>0. && plant.animation()<100.))++plant.animation();
}
}
void shooter_attack(CombatStages& runtime,Shooter& plant,const std::vector<double>* targets,size_t count,bool emperor) {
    attack(runtime,StageShooter{plant,count},targets,emperor,targets!=nullptr);
}
void shooter_attack(TypedBattleState& world,size_t index,ShooterKind kind,
                    const std::vector<int64_t>* targets,bool emperor,bool star_target) {
    attack(world.runtime,RosterShooter{world,index,kind},targets,emperor,star_target);
}
} // namespace pvz::typed72
