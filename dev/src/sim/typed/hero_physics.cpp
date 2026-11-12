#include "sim/typed/hero_physics.h"
#include "sim/typed/flood.h"
#include "core/pymath.h"
#include <cmath>
#include <numbers>

namespace pvz::typed72 {
namespace {
// The original physics namespace is selected temporarily. Nested constructors
// see this seat, position aliases remain live, and only a completed region
// commits scalar fields to the avatar.
class PhysicsSelection {
public:
    PhysicsSelection(HeroFrame& globals,const HeroFrame& avatar):globals_(globals),saved_(globals){globals_.overlay(avatar,true);}
    ~PhysicsSelection(){globals_=std::move(saved_);}
    PhysicsSelection(const PhysicsSelection&)=delete;
private:
    HeroFrame& globals_;
    HeroFrame saved_;
};
bool has(const std::vector<std::string>& secrets,std::string_view key){
    return std::find(secrets.begin(),secrets.end(),key)!=secrets.end();
}
}
HeroFrame HeroPhysics::make_state(Point pos,std::string mode,double hp,std::vector<std::string> secrets)const{
    const double tile=world_.runtime.tile;
    if(!(tile>0.))throw std::invalid_argument("non-positive hero tile size");
    HeroFrame f;
    const bool zombie=mode=="我是僵尸";
    f.speed_max.set((tile/10000.)*(has(secrets,"疾行")||zombie?250.:200.));
    f.tail_cd.set(has(secrets,"猫尾")?1.:0.);
    f.position.set(std::make_shared<Motion>(Motion{pos.x,pos.y,0.,0.}));
    f.mode.set(std::move(mode));f.secrets.set(std::make_shared<std::vector<std::string>>(std::move(secrets)));
    f.hp.set(hp);f.facing.set(1.);f.in_water.set(false);f.skin.set(zombie?"僵尸戴夫":"疯狂戴夫");
    for(auto* field:{&f.jump,&f.double_jump,&f.down,&f.recovery,&f.hurt,&f.balloon,&f.water_ice,
                     &f.angle,&f.xx,&f.yy,&f.tail,&f.tail_swing,&f.tail_tip_x,&f.head_angle,&f.chili_launch,&f.chili_lock_until})field->set(0.);
    return f;
}
void HeroPhysics::environment(HeroFrame& g,HeroInput input,double plk){
    auto& w=world_.runtime;auto& map=world_.terrain;auto& p=*g.position.get();
    const auto c=terrain_cell({p.x,p.y},w.tile);
    g.wjx.set(double(c.x));g.wjy.set(double(c.y));g.speed.set(g.speed_max.get()/(g.water_ice.get()>0.?2.:1.));
    const Cell above{c.y-1,c.x};
    if(!map.outside(above.y,above.x) && map.native_at(above.y,above.x).block.get()=="雪")destroy_pvp_block(world_,plants_,above);
    if(g.mode.get()=="我是僵尸")indexes_.register_body(c);
    bool water=false,submerged=false;
    if(!map.outside(c.y,c.x)){
        const auto& block=map.native_at(c.y,c.x).block.get();
        water=block=="水";
        if(block=="梯子块" && g.down.get()==0.){
            g.jump.set(0.);
            if(input.jump_held){p.vy=-plk*150.;p.vx=p.vx*9./10.;}
        }
    }
    if(!map.outside(above.y,above.x) && map.native_at(above.y,above.x).block.get()=="水")water=submerged=true;
    g.water.set(water);g.sbs.set(submerged);
    if(water){
        g.speed.get()/=2.;
        if(!g.in_water.get()){
            g.jump.set(2.);g.in_water.set(true);w.play_sound("入水");w.emit_particles("水",{p.x,p.y},16);
        }
        if(p.vy>0.)p.vy-=plk*3.9;
        if(p.vy>50.*plk)p.vy=50.*plk;
        if(submerged && g.hp.get()>0.){p.vy=-plk*200.;g.jump.set(0.);}
    }else g.in_water.set(false);
    if(g.down.get()==0. || g.balloon.get()>0.){
        if(input.move<0){
            if(p.vx<0.)g.facing.set(-1.);
            if(p.vx>-g.speed.get())p.vx-=plk*7.;
        }else if(input.move>0){
            if(p.vx>0.)g.facing.set(1.);
            if(p.vx<g.speed.get())p.vx+=plk*7.;
        }
    }
}
void HeroPhysics::recover(HeroFrame& g,int balloon_hp){
    auto& w=world_.runtime;const auto& p=*g.position.get();
    g.angle.set(0.);g.yy.set(0.);
    if(g.down.get()>0.){
        if(++g.recovery.get()>2000. && g.hp.get()>0.){
            if(--g.down.get()==0. && g.balloon.get()>0.){
                g.balloon.set(-1.);w.emit_particles("气球",{p.x,p.y-w.tile*2.5},12);w.play_sound("气球爆炸");
            }
        }else{
            if(g.down.get()<90.)++g.down.get();
            if(g.balloon.get()==0. && g.hp.get()<=(balloon_hp==12?12.:10.)){g.balloon.set(1.);w.play_sound("气球");}
        }
        g.angle.set(std::min(90.,g.angle.get()+g.down.get()));
        g.yy.set(std::abs(g.angle.get())*w.tile*.008);
    }
    g.xx.set(0.);
    if(g.water_ice.get()>0.){
        const auto bi=w.tile/810.;
        g.xx.get()+=w.rng.randint(-2,2)*bi*10.;g.yy.get()+=w.rng.randint(-2,2)*bi*10.;
    }
}
void HeroPhysics::step(HeroState& avatar,HeroInput input,int jump_cap,int balloon_hp){
    auto& w=world_.runtime;auto& g=world_.heroes.globals;auto& map=world_.terrain;
    if(!(w.tile>0.))throw std::invalid_argument("non-positive hero tile size");
    const double plk=w.tile/10000.;
    PhysicsSelection selection(g,avatar.frame);
    NativeBirthScope native_birth(w,births_);
    if(g.hp.get()<=0.)g.balloon.set(-1.);
    auto& p=*g.position.get();
    const int landing=displace_body(p,1.,map,w.tile,plk,map.periodic_x);
    if(landing==1)g.jump.set(0.);
    if(map.periodic_x)p.x=py::mod(p.x,map.cols()*w.tile);
    environment(g,input,plk);
    if(g.chili_launch.get()>0. && py::mod(--g.chili_launch.get(),15.)==0.){
        p.vy=-700.*plk;
        w.construct_entity("火",-1.,{p.x+w.tile/2.,p.y-w.tile,0.,0.}).expires.set(900.);
    }
    recover(g,balloon_hp);
    if(g.speed_max.get()==0.)throw std::domain_error("zero hero speedmax");
    g.angle.get()+=p.vx/g.speed_max.get()*15.*g.facing.get();
    if(g.double_jump.get()>0.){
        const double t=100.-g.double_jump.get();
        if(++g.double_jump.get()==100.)g.double_jump.set(0.);
        g.angle.get()-=.072*t*t/2.;
    }
    if(jump_cap<1 || jump_cap>3)throw std::invalid_argument("invalid native jump cap");
    if(input.jump_down && g.down.get()==0. && g.jump.get()<jump_cap && g.double_jump.get()==0.){
        const double before=g.jump.get();
        if(++g.jump.get()==2.){g.double_jump.set(1.);p.vx+=g.facing.get()*plk*200.;}
        p.vy=-plk*380.;
        if(jump_cap==3 && before==2.)p.vy*=1.25;
    }
    avatar.frame.overlay(g,true);
    avatar.landing_result.set(landing);avatar.native_ticks.set(avatar.native_ticks.or_missing(0)+1);
}
void HeroPhysics::tail(HeroFrame& g){
    if(g.tail_cd.get()<=0.)return;
    auto& w=world_.runtime;const auto& p=*g.position.get();
    if(++g.tail_swing.get()==250.)g.tail_swing.set(0.);
    const double cd=++g.tail_cd.get();
    if(cd<=450. && py::mod(cd,150.)==0. && indexes_.nearest)g.tail.set(1.);
    if(cd==1000.)g.tail_cd.set(1.);
    const double sway=std::sin(std::numbers::pi*2.*(g.tail_swing.get()/250.))*10.;
    const double facing=g.facing.get();double recoil=0.;
    if(g.tail.get()>0. && g.tail.get()<100.){
        const double swing=-std::sin(std::numbers::pi*2.*(g.tail.get()/100.));
        g.tail_tip_x.set(swing*w.tile*.15*facing);g.head_angle.set(swing*20.*facing);recoil=swing*60.*facing;
    }
    renderer_.draw({w.presentation.sprite_name("香蒲尾"),{p.x-w.tile*.5-facing*w.tile*.25,
                    p.y-w.tile*1.5+std::abs(sway)*w.tile*.005+g.yy.get()},facing!=1.,recoil+sway,{}});
}
void HeroPhysics::effects(HeroState& avatar,bool tail_enabled){
    auto& w=world_.runtime;auto& g=world_.heroes.globals;
    if(!(w.tile>0.))throw std::invalid_argument("non-positive hero tile size");
    const double plk=w.tile/10000.;
    PhysicsSelection selection(g,avatar.frame);NativeBirthScope native_birth(w,births_);
    if(g.hp.get()<=0.)g.balloon.set(-1.);
    auto& p=*g.position.get();
    const auto previous_tail=g.tail,previous_cd=g.tail_cd,previous_swing=g.tail_swing;
    if(!tail_enabled){g.tail.set(0.);g.tail_cd.set(0.);g.tail_swing.set(0.);}
    if(g.tail.get()>0. && g.tail.get()<100. && ++g.tail.get()==50.){
        auto& spike=w.construct_entity("尖刺",1.,{p.x-g.facing.get()*w.tile*.5,p.y-w.tile*1.2+g.yy.get(),g.facing.get()*200.*plk,0.});
        spike.tracking.set(0.);spike.through_wall.set(0.);spike.expires.set(-1000.);spike.rotation.set(0.);
    }
    if(g.balloon.get()>0.){
        if(p.vy>-60.*plk && p.y>w.tile)p.vy-=5.*plk;
        const auto sprite=w.presentation.sprite_name("气球");
        if(++g.balloon.get()<100.){
            const double size=g.balloon.get()/100.*w.tile*2.;
            renderer_.draw({sprite,{p.x-size/2.,p.y-w.tile-size+g.yy.get()},false,{},Point{size,size}});
        }else renderer_.draw({sprite,{p.x-w.tile,p.y-w.tile*3.+g.yy.get()},false,{},{}});
    }
    tail(g);
    if(!tail_enabled){g.tail=previous_tail;g.tail_cd=previous_cd;g.tail_swing=previous_swing;}
    avatar.frame.overlay(g,true);
}
} // namespace pvz::typed72
