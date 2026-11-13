// Original 98618..108808 plus installed PvP72 predicates and call gates.
#include "sim/typed/entity_region.h"
#include "sim/typed/flood.h"
#include "sim/typed/plant_lookup.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
Point xy(const Motion& m){return {m.x,m.y};}
bool has(const std::vector<std::string>& values,std::string_view value){
    return std::find(values.begin(),values.end(),value)!=values.end();
}
std::string frame_number(double timer){
    return std::to_string(int(py::mod(py::floordiv(timer,10.),3.)));
}
}
Motion& EntityRegion::position(const CombatTarget& t)const {
    return t.is_hero()?*world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.get();
}
ZombieRecordFields& EntityRegion::body(const CombatTarget& t)const {
    if(t.is_hero())return world_.heroes.cached_proxy(t.hero);
    return t.unit->body;
}
TileRef EntityRegion::tile_at(Cell c)const {
    const auto& terrain=world_.terrain;
    if(!terrain.valid_row(c.y) || terrain.cols()==0)return {};
    return terrain.at(c.y,terrain.wrap(c.x));
}
void EntityRegion::move(Frame& f) {
    const auto e=entity(f.index);
    auto& p=e->motion.get();auto& w=world_.runtime;
    if(e->gravity.present()) {
        f.collision=displace_body(p,e->gravity.get(),world_.terrain,w.tile,w.plk,true);
        env_.last_landing=f.collision;
        if(f.collision>0 && !e->expires.present())f.remove=true;
    } else if(e->service.attract.present()) {
        const double age=e->service.attract.get()+1.;
        e->service.attract.set(age);e->service.attract_is_boolean=false;
        const auto start=e->service.attract_start.get(),end=e->service.attract_end.get();
        p.x=timed_coordinate(start.x,end.x,100.,age);
        p.y=timed_coordinate(start.y,end.y,100.,age);
    } else {
        p.x+=p.vx;p.y+=p.vy;
    }
}
void EntityRegion::special(Frame& f) {
    const auto e=entity(f.index);
    auto& w=world_.runtime;const double tile=w.tile;auto& p=e->motion.get();
    if(e->monochrome.present())f.suffix="-黑白";
    if(f.name=="爆炸" || f.name=="小丑爆炸" || f.name=="模仿"){p.vx-=p.vx/50.;p.vy-=p.vy/50.;}
    if(f.name=="毁灭2")f.name+="."+frame_number(e->expires.get());
    if(f.name=="大泡泡" || f.name=="蓝泡泡"){p.vx-=p.vx/100.;p.vy-=p.vy/100.;}
    if(f.name=="玉米炮") {
        world_.heroes.globals.xx.get()-=tile*.5;
        if(e->cannon_lock.get()==0.) {
            f.name="上玉米炮";p.vy=-1000.*w.plk;
            if(p.y<env_.camera_y-world_.world_height.get()*3.){
                e->cannon_lock.set(1.);p.vy=300.*w.plk;
            }
        } else {f.name="下玉米炮";p.x=e->cannon_column.get()*tile+tile*.5;}
    }
    if(f.name=="窝瓜x") {
        f.name="窝瓜";world_.heroes.globals.xx.get()+=tile*.5;world_.heroes.globals.yy.get()-=tile*.3;
        auto& q=e->squash;q.big_sit.set(q.big_sit.get()-1.);
        if(q.big_sit.get()==0.){p.vx=0.;p.vy=w.plk*700.;}
        if(p.vy==0. && f.collision==1 && q.sit.get()==0.) {
            e->expires.set(800.);q.sit.set(1.);w.screen_shake.set({50.,0.,0.});w.sound("巨锤",p);
            const auto count=world_.targets->size();
            for(size_t z=0;z<count;++z) {
                const auto current=entity(f.index);
                const auto& origin=current->motion.get();
                const auto& tpos=position(world_.targets->at(z));
                if(yes(current->squash.zombie_entity) || std::abs(tpos.x-origin.x)>tile ||
                   std::abs(tpos.y-origin.y)>tile*2.)continue;
                damage_.damage_zombie(z,current->facing,500.);
                if(has(*world_.heroes.globals.secrets.get(),"压顶")) {
                    const auto target=world_.targets->at(z);
                    if(target.is_hero())world_.heroes.write_proxy_status(target.hero,HeroStatus::stun,2000.);
                    else target.unit->body.stun.set(2000.);
                }
            }
        }
        auto& sit=entity(f.index)->squash.sit;
        if(sit.get()>0. && sit.get()<30.)sit.set(sit.get()+1.);
    }
    const auto current=entity(f.index);auto& bounce=current->squash.bounce_x;
    if(!bounce.present())return;
    auto& m=current->motion.get();f.remove=false;
    if(m.vx==0.){bounce.set(bounce.get()-1.);current->facing=-current->facing;if(current->in_water.present())bounce.set(0.);}
    m.vx=current->facing*w.plk*300.;
    if(current->in_water.present())m.vx/=5.;
    if(f.collision!=0) {
        bounce.set(bounce.get()-1.);if(current->in_water.present())bounce.set(0.);
        m.vy=(f.collision==1?-500.:500.)*w.plk;
    }
    if(bounce.get()<=0.)f.remove=true;
}
void EntityRegion::basketball(Frame& f) {
    if(f.name!="篮球")return;
    const auto e=entity(f.index);const auto& p=e->motion.get();
    auto& w=world_.runtime;const double tile=w.tile;
    const Cell c=terrain_cell(xy(p),tile);
    const auto cell=tile_at(c);
    if(cell && world_.heroes.owner(source_ref(e))!=Seat::plant && cell->plant.present()) {
        f.remove=true;
        const auto& list=*world_.plant_roster;
        const auto z=lookup_pvp_plant(world_,c,false).value_or(list.size()-1);
        const auto plant=list.at(z);
        if(plant->kind!="地刺" && plant->kind!="地刺王"){
            static const std::string no_hand;
            auto& hp=plant->hp.get();
            hp-=world_.protection.amount({hp,no_hand,plant->source,plant->protection},2.);
            plant->hurt.set(1.);if(hp<=0.)plants_.clear(c);
        }
    } else {
        const auto& player=*world_.heroes.globals.position.get();
        if(!(p.x>player.x-tile*.15*2. && p.x<player.x+tile*.15*2. &&
             p.y>player.y-tile*.85*2. && p.y<player.y))return;
        f.remove=true;damage_.player_damage(1.);
        world_.heroes.globals.position.get()->vx=entity(f.index)->facing*150.*w.plk;
    }
    w.sound("splat"+std::to_string(w.rng.randint(1,3)),{c.x*tile+tile/2.,c.y*tile+tile/2.,0.,0.});
}
void EntityRegion::seaweed(Frame& f) {
    if(f.name!="缠绕海草x")return;
    const auto tile=world_.runtime.tile;
    world_.heroes.globals.xx.get()+=tile*.5;f.name="缠绕海草";
    const auto e=entity(f.index);
    const auto cell=tile_at(terrain_cell(xy(e->motion.get()),tile));
    if(!cell || cell->block.get()!="水")return;
    const bool hurt=py::mod(e->expires.get(),100.)==0.;
    for(size_t z=world_.targets->size();z-- >0;) {
        const auto t=world_.targets->at(z);
        const auto& s=t.is_hero()?world_.heroes.cached_proxy(t.hero).source:t.unit->source;
        const auto& p=entity(f.index)->motion.get();
        if(s.charmed.present() || body(t).hp<=0. || !yes(body(t).in_water) ||
           std::abs(p.x-position(t).x)>tile*.6 || std::abs(p.y-position(t).y)>tile*.3)continue;
        if(hurt) {
            damage_.damage_zombie(z,body(t).facing,15.);
            world_.runtime.sound("splat"+std::to_string(world_.runtime.rng.randint(1,3)),position(world_.targets->at(z)));
        }
        auto& m=position(world_.targets->at(z));const double y=entity(f.index)->motion.get().y;
        const auto barrier=tile_at(terrain_cell({m.x,y},tile));
        if(barrier && world_.terrain.is_empty(barrier->block.get()))m.y=y;
        m.vx=m.vy=0.;
    }
}
void EntityRegion::environment(Frame& f) {
    const auto e=entity(f.index);auto& p=e->motion.get();auto& w=world_.runtime;
    f.cell=terrain_cell(xy(p),w.tile);
    const auto cell=tile_at(f.cell);
    if(e->expires.present()) {
        world_.heroes.globals.xx.get()-=w.tile*.5;
        const double age=e->expires.get()+1.;e->expires.set(age);
        if(age==1025.)f.remove=true;
        if(age>1000.)bindings_.alpha(e->flat_sprite.present()?EntitySprite(e->flat_sprite.get()):EntitySprite(f.name+f.suffix),(1025.-age)*10.);
    } else if(cell && !world_.terrain.is_empty(cell->block.get())) f.remove=true;
    if(f.cell.y>=world_.terrain.rows())f.remove=true;
    if(!e->gravity.present() || !cell)return;
    const bool water=cell->block.get()=="水";
    if(e->in_water.present() && f.name!="缠绕海草") {
        p.vy+=p.vy>0.?-w.plk*3.9:w.plk*2.;
        if(!water)e->in_water.erase();
    }
    if(water && !e->in_water.present()) {
        e->in_water.set(true);
        if(f.name!="玉米粒"){w.sound("入水",p);w.emit_particles(env_.water_particle,xy(p),16);}
        if(f.name!="缠绕海草"){p.vx/=5.;p.vy/=10.;}
    }
}
void EntityRegion::render(Frame& f) {
    auto& w=world_.runtime;const auto tile=w.tile;
    const auto get_pos=[&](double dx,double dy){
        const auto& p=entity(f.index)->motion.get();
        return Point{p.x-tile*dx+world_.heroes.globals.xx.get(),p.y-tile*.5+world_.heroes.globals.yy.get()+dy};
    };
    if(f.name=="火豆") {
        const auto e=entity(f.index);auto& lit=e->source.fire_lit;
        std::string tail="火尾"+std::to_string(int(py::mod(py::floordiv(lit.get(),10.),3.))+1);
        // Explicit shot colour (multi-direction red fire) takes priority over
        // the global blue-torch secret, just as it does for damage / splash.
        if(projectile_fire_color(e->source,world_.heroes.globals)=="blue"){f.name="蓝火豆";tail="蓝"+tail;}
        lit.set(lit.get()+1.);const bool flip=e->facing!=1.;
        // The content drawing pass owns the velocity-aligned trail for these
        // shots; keep their legacy flame timer advancing without drawing twice.
        if(!yes(e->mortar.mortar)&&!yes(e->mortar.multi_red))bindings_.draw({tail,get_pos(flip?.1:.9,0.),flip});
    }
    const auto e=entity(f.index);const auto& sit=e->squash.sit;
    if(f.name=="窝瓜" && sit.present() && sit.get()>0.) {
        const double squash=sit.get()/30.*tile/3.;
        bindings_.draw({f.name+f.suffix,get_pos(.5,squash),e->facing!=1.,{},Point{tile,tile-squash}});
    } else if(e->flat_sprite.present()) {
        bindings_.draw({e->flat_sprite.get(),get_pos(.5,0.)});
    } else if(!yes(e->mortar.mortar) && !yes(e->mortar.multi_red) && !ZombiePeas::is_pea(e) && (!e->through_wall.present() || e->kind=="星星" || e->kind=="尖刺")) {
        const bool flip=e->facing!=1.;
        std::optional<double> angle;
        if(e->rotation.present())angle=flip?-e->rotation.get():e->rotation.get();
        bindings_.draw({f.name+f.suffix,get_pos(.5,0.),flip,angle});
        if(angle){auto& rotation=entity(f.index)->rotation;rotation.set(rotation.get()+1.);}
    }
    if(entity(f.index)->expires.present())bindings_.alpha(f.name+f.suffix,255.);
}
void EntityRegion::impact(Frame& f) {
    const auto original=entity(f.index);
    if(yes(original->squash.zombie_entity) && !yes(original->squash.hit))
        squash_.hit(original,original->squash.target,original->motion.get().x);
    flight_.impact(entity(f.index),&damage_);
    auto& w=world_.runtime;
    const auto tile=w.tile;
    int particles=4;
    if(entity(f.index)->kind=="玉米炮") {
        particles=30;const auto center=xy(entity(f.index)->motion.get());
        world_.heroes.globals.xx.set(center.x);world_.heroes.globals.yy.set(center.y);
        auto& player=*world_.heroes.globals.position.get();
        if(std::abs(player.x-center.x)<=tile*2. && std::abs(player.y-center.y)<=tile*2.) {
            player.vx+=(center.x>player.x?-500.:500.)*w.plk;player.vy-=500.*w.plk;
        }
        const size_t n=world_.targets->size();
        for(size_t z=0;z<n;++z){const auto& p=position(world_.targets->at(z));if(std::abs(p.x-center.x)<=tile*2.5 && std::abs(p.y-center.y)<=tile*2.5)damage_.ash_zombie(z);}
        for(int y=-2;y<=2;++y)for(int x=-2;x<=2;++x) {
            if(std::abs(y)+std::abs(x)>3)continue;
            const Cell target{f.cell.y+y,f.cell.x+x};const auto cell=tile_at(target);
            if(cell && cell->block.get()=="梯子块")destroy_pvp_block(world_,plants_,target);
        }
        damage_.add_entity("爆炸印",w.rng.randint(0,1)==0?-1.:1.,{center.x-tile,center.y-tile*2.,0.,0.});
        w.entities.list()->back()->expires.set(0.);
        w.screen_shake.set({100.,0.,0.});w.sound("毁灭菇",{center.x,center.y,0.,0.});
    }
    if(f.name=="西瓜" || f.name=="冰瓜") {
        w.sound("西瓜"+std::to_string(w.rng.randint(1,2)),entity(f.index)->motion.get());
        particles=10;if(f.name=="冰瓜")contacts_.freeze_melon(f.index);
    }
    const auto e=entity(f.index);
    if(!e->expires.present() || (e->through_wall.present() && e->expires.get()<1025.)) {
        std::optional<int> direction;
        if(has(rules_.damaging,f.name))direction=f.collision?f.collision:e->facing==1.?3:4;
        w.emit_particles(f.name,xy(e->motion.get()),particles,direction);
    }
}
void EntityRegion::run() {
    auto& entities=world_.runtime.entities;
    auto& heroes=world_.heroes;
    LiveBattleSources sources(world_);
    for(size_t l=entities.list()->size();l-- >0;) {
        heroes.source_index=int64_t(l);
        bindings_.tracking_gate(l);
        Frame f{l,entity(l)->kind};
        world_.heroes.globals.xx.set(0.);world_.heroes.globals.yy.set(0.);
        move(f);
        if(flight_.expired(entity(l))){entities.erase_at(l);continue;}
        special(f);basketball(f);
        if(f.name=="窝瓜")contacts_.invalidate_spatial();
        if(contacts_.strike(l,f.name,env_.driving))f.remove=true;
        if(f.name=="篮球x"){f.name="篮球";world_.heroes.globals.xx.get()+=world_.runtime.tile*.5;}
        contacts_.home(l,bindings_.nearest_target());
        if(f.name=="火"){
            auto& age=entity(l)->expires;const auto n=age.get();
            if(n<900.){age.set(n+1.);continue;}
            f.name+=n<930.?"1.1":n<960.?"1.2":n<990.?"1.3":n<1010.?"2":"3";
        }
        seaweed(f);if(f.name=="缠绕海草")contacts_.invalidate_spatial();
        environment(f);render(f);
        if(f.remove){impact(f);contacts_.invalidate_spatial();entities.erase_at(l);}
    }
}
} // namespace pvz::typed72
