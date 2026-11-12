// Mobile zombie wordcode 79050..97986 and its installed PvP call sites.
#include "sim/typed/zombie_actions.h"
#include "sim/typed/plant_lookup.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <numbers>

namespace pvz::typed72 {
namespace {
constexpr double pi=std::numbers::pi;
bool named(const Field<std::string>& f,std::string_view s){return f.present()&&!f.is_null()&&f.get()==s;}
bool active(const Field<double>& f){return f.present()&&!f.is_null()&&f.get()>0.;}
bool has(const std::vector<std::string>& values,std::string_view name){return std::find(values.begin(),values.end(),name)!=values.end();}
Point point(const Motion& m){return {m.x,m.y};}
bool car(const ZombieRecordFields& b){return b.kind=="雪橇车僵尸" || b.kind=="投篮车僵尸";}
int bottom_empty(const WorldTerrain& terrain,int64_t col){
    int row=terrain.rows()-1;
    while(row>0 && !terrain.empty(row,col))--row;
    return row;
}
}
ZombieRef ZombieActions::unit(size_t index)const{
    auto u=world_.targets->at(index).unit;
    if(!u)throw std::logic_error("hero in mobile zombie actions");
    return u;
}
void ZombieActions::draw(std::string sprite,Point p,bool mirror,std::optional<double> angle){
    renderer_.draw({world_.runtime.presentation.sprite_name(sprite),p,mirror,angle,{}});
}
void ZombieActions::alpha(const std::string& sprite,double value){
    renderer_.alpha(world_.runtime.presentation.sprite_name(sprite),value);
}
void ZombieActions::player_hit(double amount){
    const auto& h=world_.heroes;
    if(const auto s=h.source();s && h.source_index && h.active && h.active->phase==CombatPhase::zombies){
        const auto u=unit(size_t(*h.source_index));
        if(u->patch.no_attack.present()&&!u->patch.no_attack.is_null()&&u->patch.no_attack.get())return;
        if(amount==1.&&u->patch.bite_plant.present()&&!u->patch.bite_plant.is_null()&&u->patch.bite_plant.get()!=0.)amount=u->patch.bite_plant.get();
    }
    world_.heroes.player_damage(amount);
}
void ZombieActions::blast_terrain(Cell center){
    for(int row=-2;row<=2;++row)for(int col=-2;col<=2;++col){
        Cell c{center.y+row,center.x+col};
        if(std::abs(row)+std::abs(col)<=3 && !world_.terrain.outside(c.y,c.x))destroy_pvp_block(world_,plants_,c);
    }
}
void ZombieActions::dance(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;
    auto& angle=world_.heroes.globals.angle.get();
    if(active(b.dancing) && b.hp>0.){
        auto& t=b.dancing.get();if(++t==1000.)t=0.;
        if(py::mod(t,250.)==0. && n.light.present()){
            int64_t light;do{light=w.rng.randint(1,4);}while(light==n.light.get());
            n.light.set(double(light));
        }
        angle=std::sin(pi*2.*(t/250.))*50.;b.facing=angle>0.?-1.:1.;
    }
    if(!n.dance_cd.present() || actions_.hold_dance() || --n.dance_cd.get()!=0.)return;
    n.dance_cd.set(2000.);b.dancing.set(1.);
    for(const auto& other:*world_.targets)if(other.unit->body.kind=="伴舞僵尸")other.unit->body.dancing.set(1.);
    for(int slot=0;slot<4;++slot){
        const auto col=f.cell.x-4+slot*2+(slot>1?2:0);
        if(world_.terrain.outside(0,col))continue;
        for(int row=world_.terrain.rows()-1;row>=0;--row)if(world_.terrain.empty(row,col)){
            if(!actions_.defer_dancer({(col+.5)*w.tile,(row+.9)*w.tile},b.facing,slot)) {
                actions_.summon_zombie("伴舞僵尸",{col*w.tile+w.tile*.5,row*w.tile+w.tile*.9,0.,0.},b.facing);
                const auto child=world_.targets->back().unit;
                if(u->source.charmed.present())child->source.charmed.set(0.);
                child->native.entry.set(300.);
            }
            break;
        }
    }
}
void ZombieActions::waking(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& n=u->native;
    if(!n.wake.present())return;
    motion_.register_body(f.cell,{});
    if(n.wake.get()>0.){
        const double t=++n.wake.get();
        world_.heroes.globals.angle.set(u->body.facing*(1.-std::pow(t/8000.,7.))*90.);
        if(t==8000.)n.wake.erase();
    }else{
        world_.heroes.globals.angle.set(u->body.facing*90.);
        if(f.collision==1){world_.runtime.screen_shake.set({150.,0.,0.});world_.runtime.sound("巨锤",u->body.motion.get());blast_terrain(f.cell);n.wake.set(1.);}
    }
}
bool ZombieActions::crush(Cell c){
    const auto index=lookup_pvp_plant(world_,c,false);if(!index)return false;
    const auto get=[&]{return world_.plant_roster->at(*index);};
    const auto original=get();auto& heroes=world_.heroes;auto& w=world_.runtime;
    const auto source=heroes.source();
    if(source && source->has_zombie_name() && heroes.owner(source)==heroes.owner(source_ref(original)))return false;
    if(named(original->source.content,"抓人草"))original->crushed.set(true);
    auto& atlas=w.presentation.source_art;
    struct Restore {
        decltype(atlas) chart;
        std::vector<std::pair<std::string,std::optional<std::string>>> saved;
        ~Restore(){for(auto& [key,name]:saved){if(name)chart[key]=std::move(*name);else chart.erase(key);}}
    } restore{atlas,{}};
    if(original->source.content.present() && !original->source.content.is_null() && actions_.has_sprite(original->source.content.get())){
        for(const char* suffix:{"","-受伤","-黑白"}){
            const auto old=original->kind+suffix,next=original->source.content.get()+suffix;
            if(old==next || !actions_.has_sprite(old) || !actions_.has_sprite(next))continue;
            const auto it=atlas.find(old);restore.saved.emplace_back(old,it==atlas.end()?std::nullopt:std::optional(it->second));
            atlas[old]=w.presentation.sprite_name(next);
        }
    }
    w.sound("吃"+std::to_string(w.rng.randint(1,2)),{c.x*w.tile+w.tile*.5,c.y*w.tile+w.tile*.5,0.,0.});
    if(original->virtual_hp.present()){
        original->hurt.set(1.);if(--original->virtual_hp.get()==1.)original->virtual_hp.erase();return true;
    }
    plants_.clear(c);
    const auto p=get();
    if(p->kind=="缠绕海草")p->shovel_dead.set(DeathMarker(0.));
    double y=w.tile*1.2;
    if(p->kind=="海蘑菇" && !has(*heroes.globals.secrets.get(),"水兵"))y-=w.tile*.6;
    if(p->kind=="缠绕海草" || p->kind=="睡莲")y-=w.tile*.8;
    if(p->kind=="香蒲")y-=w.tile*.9;
    move_.add_entity(p->kind,p->facing,{c.x*w.tile+w.tile*.8,c.y*w.tile+w.tile*.1+y,0.,0.});
    const auto e=w.entities.list()->back();
    const auto sprite=p->kind+(p->monochrome.present()?"-黑白":"");
    e->flat_sprite.set(actions_.flat_sprite(w.presentation.sprite_name(sprite),{w.tile*1.4,w.tile*.3},get()->facing==-1.));
    e->expires.set(800.);return true;
}
void ZombieActions::vehicle(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    auto& p=b.motion.get();const bool sled=b.kind=="雪橇车僵尸";
    if(sled || n.advance.get()!=0.){
        double factor=1.;
        if(world_.heroes.owner(source_ref(u))==Seat::zombie){
            double sum=0.;for(const auto& entry:u->patch.speed_factors)sum+=entry.second;factor+=sum;
        }
        p.vx=b.facing*(named(u->source.content,"小鬼炮")?n.move_speed.get():w.plk*40.*factor);
        ++n.wheel.get();if(n.crash.get()>0.)--n.crash.get();
    }
    auto& hero=*g.position.get();bool crash=false;
    if(std::abs(hero.x-p.x-b.facing*w.tile/2.)<=w.tile*1.5 && std::abs(hero.y-p.y)<=w.tile*.5 && n.crash.get()==0.){
        crash=true;w.screen_shake.set({70.,0.,0.});
        hero.vx+=(p.x>hero.x?-400.:400.)*w.plk;hero.vy-=400.*w.plk;
        if(!u->source.charmed.present())player_hit(1.);
    }
    const Cell front{f.cell.y,f.cell.x+int64_t(b.facing)};
    const Cell upper{front.y-1,front.x},above{f.cell.y-1,f.cell.x},below{f.cell.y+1,f.cell.x};
    for(const Cell c:{front,f.cell}){
        if(const auto target=lookup_pvp_plant(world_,c,false)){
            auto plant=world_.plant_roster->at(*target);
            if(plant->kind=="地刺" || plant->kind=="地刺王"){
                if(plant->kind=="地刺")plant->dead.set(DeathMarker(0.));
                move_.ordinary(f.index,b.facing,300.);
            }
        }
    }
    if(b.hp>0.){if(!crush(f.cell) && !(sled && crush(above)) && !crush(front) && sled)crush(upper);}
    auto& map=world_.terrain;
    if(sled){
        const auto wall=[&](Cell c){return !map.outside(c.y,c.x) && !map.empty(c.y,c.x) && map.native_at(c.y,c.x).block.get()!="雪";};
        if(wall(front) || wall(upper))move_.ordinary(f.index,b.facing,100.);
        for(const auto c:{f.cell,above,front,upper})
            if(!map.outside(c.y,c.x) && c.y!=map.rows()-1 && !map.empty(c.y,c.x))destroy_pvp_block(world_,plants_,c);
        if(n.entry.get()==500. && map.outside(0,front.x))b.hp=0.;
    }
    g.angle.set(0.);
    if(sled && !map.outside(below.y,below.x)){
        auto& t=map.native_at(below.y,below.x);
        if(t.block.get()=="空" && !t.plant.present() && n.crash.get()==0. && n.snow_capacity.get()>0. && !actions_.hold_sled()){
            if(--n.snow_capacity.get()<4.){
                const int edge=b.facing==1.?0:map.cols()-1;
                if(map.native_at(below.y,edge).block.get()=="雪"){
                    actions_.summon_zombie("雪橇车小队僵尸",{edge*w.tile+w.tile*.5,f.cell.y*w.tile+w.tile,0.,0.},b.facing);
                    auto child=world_.targets->back().unit;child->native.split.set(20000.);
                    child->native.entry_start.get().x-=w.tile*10.*child->body.facing;
                }
            }
            destroy_pvp_block(world_,plants_,below);crash=true;
            auto& snow=map.native_at(below.y,below.x);snow.block.set("雪");snow.snow_gone.set(0.);
            plants_.important(below,"雪");Point at{f.cell.x*w.tile+w.tile*.5,f.cell.y*w.tile+w.tile*1.5};
            w.emit_particles("雪",at,8);w.sound("雪",{at.x,at.y,0.,0.});
        }
    }
    if(crash)n.crash.set(80.);
}
void ZombieActions::locomotion(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;auto& g=world_.heroes.globals;auto& p=b.motion.get();
    if(car(b) && !b.ash.present() && n.entry.get()==500.)vehicle(f);
    else if(f.collision==1 || g.water.get()){
        if(f.collision==1){
            p.vy=std::max(-std::abs(p.vx)*5.,-w.plk*200.);
            if(b.hp>0. && !b.ash.present()){
                if(b.kind=="雪人僵尸")p.vy=-w.plk*400.;
                if(b.hand=="弹跳杆"){
                    p.vy=-w.plk*500.;
                    if(n.entry.get()==500. && !b.in_water.get() && n.explosion_sound.get()==0.){n.explosion_sound.set(20.);w.sound("蹦蹦",p);}
                }
            }
        }
        if(b.hp>0. && !b.ash.present() && n.jump_cd.get()==0. && f.can_bite && !world_.terrain.outside(f.cell.y,f.cell.x) &&
           (f.original_heading==2 || (p.vx==0. && (b.kind=="潜水僵尸" || u->source.charmed.present())))){
            p.vy=-w.plk*(n.red_eye.present()?420.:300.);n.jump_cd.set(200.+w.rng.randint(-20,20));
        }
    }
    if(b.kind=="飞贼僵尸"){
        if(n.entry.get()==500.){
            if(n.leaving.present())b.hp=-1025.;
            else if(!lookup_pvp_plant(world_,f.cell,false) || b.hp<=0.){
                n.leaving.set(0.);n.entry.set(0.);n.entry_end=n.entry_start;n.entry_start.set(point(p));
            }
        }
        const auto camera=w.presentation.camera,rope=n.rope_start.get();
        actions_.line({rope.x-camera.x,rope.y-camera.y},{p.x-camera.x,p.y-camera.y-w.tile});
    }
    if(active(b.pole_vault))g.angle.set(std::sin(pi*(b.pole_vault.get()/200.))*180.*-b.facing);
    if(n.explosion_sound.get()>0.)--n.explosion_sound.get();
    if(b.balloon.present() && b.balloon.get()<200.){
        if(b.balloon.get()==0.){if(p.vy>-60.*w.plk && p.y>w.tile)p.vy-=5.*w.plk;}
        else ++b.balloon.get();
        g.angle.set(std::sin(pi*((200.-b.balloon.get())/400.))*60.*b.facing);
    }
    for(double* t:{&b.hurt,&b.hand_hurt})if(*t>0. && ++*t==50.)*t=0.;
}
void ZombieActions::body_art(const ZombieMotionFrame& f,Art& art){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& p=b.motion.get();
    auto& w=world_.runtime;auto& g=world_.heroes.globals;const double size=b.size.get();
    if(b.ash.present()){
        const auto age=++b.ash.get();
        if(age==500. && b.hp>0.){
            b.hp=-1025.;move_.add_entity(b.kind+"-首-灰烬",b.facing,p);
            auto e=w.entities.list()->back();auto& m=e->motion.get();
            if(size==3.)m.x-=w.tile/2.;
            m.y-=w.tile*(size-2.);e->gravity.set(0.);m.y-=w.tile*1.5;e->expires.set(1.);
        }
        art.add(b.kind+"-身-灰烬",Layer::ash_body);art.ash_height=w.tile*size;
        if(b.hp>0. && age>400.){
            art.ash_height=art.ash_height*(500.-age)/100.;
            if(py::mod(age,20.)==0.){
                const auto count=w.rng.randint(4,6);
                for(int i=0;i<count;++i){
                    const double x=p.x+w.rng.randint(int64_t(-w.tile*size/4.),int64_t(w.tile*size/4.));
                    const double y=p.y-(w.tile*size-art.ash_height)/2.-w.tile/2.;
                    w.particle_state.push_back({{0,0,0,0},{x,y,0.,w.rng.randint(200,250)*w.plk},0.});
                }
            }
        }
    }else{
        art.add(b.kind+"-身",Layer::body);
        if(active(b.ice))art.add(b.kind+"-身-冰冻",Layer::ice);
        if(active(u->source.charmed))art.add(b.kind+"-身-魅惑",Layer::charm);
    }
    if(n.entry.get()<500.){
        const auto start=n.entry_start.get(),end=n.entry_end.get();
        p.x=timed_coordinate(start.x,end.x,500.,n.entry.get());p.y=timed_coordinate(start.y,end.y,500.,n.entry.get());
        if(py::mod(n.entry.get(),50.)==0.){
            const auto c=terrain_cell(point(p),w.tile);
            if(!world_.terrain.outside(c.y,c.x)){
                const auto& block=world_.terrain.native_at(c.y,c.x).block.get();
                if(block!="空")w.emit_particles(block,{c.x*w.tile+w.tile*.5,c.y*w.tile-w.tile*.5},n.emerged.present()?12:4);
            }
        }
    }
    g.xx.set(p.x-w.tile*size/2.);g.yy.set(p.y-w.tile*size);
    if(b.hp>0. || has(state_.large_zombies,b.kind)){
        if(b.ash.present())art.add(b.kind+"-首-灰烬",Layer::ash_head);
        else{
            const std::string prefix=b.berserk.present()?"狂暴":n.red_eye.present()?"红眼":"";
            art.add(prefix+b.kind+"-首",Layer::head);
            if(active(b.ice))art.add(b.kind+"-首-冰冻",Layer::ice_head);
            if(active(u->source.charmed))art.add(b.kind+"-首-魅惑",Layer::charm_head);
        }
    }
}
void ZombieActions::explode(const ZombieRef& u,Point origin,Cell cell,bool vehicle_death){
    auto& w=world_.runtime;auto& g=world_.heroes.globals;
    auto& b=u->body;auto& hero=*g.position.get();const auto& p=b.motion.get();const bool sled=b.kind=="雪橇车僵尸";
    w.screen_shake.set({100.,0.,0.});w.sound("樱桃炸弹",p);
    if((!vehicle_death || sled) && std::abs(hero.x-p.x)<=w.tile*2.5 && std::abs(hero.y-p.y)<=w.tile*2.5){
        hero.vx+=(p.x>hero.x?-500.:500.)*w.plk;hero.vy-=500.*w.plk;
        if(vehicle_death || !u->source.charmed.present())player_hit(10.);
    }
    const auto explosion=[&](double fx,Motion m){
        move_.add_entity("小丑爆炸",fx,m);auto e=w.entities.list()->back();
        e->expires.set(900.);e->rotation.set(double(w.rng.randint(0,360)));
    };
    const int64_t count=w.rng.randint(4,5);
    for(int i=0;i<count;++i){
        const double fx=i%2==0?-1.:1.,fy=i/2%2==0?1.:-1.;
        explosion(fx,{origin.x,origin.y,fx*w.plk*w.rng.randint(300,400),w.plk*w.rng.randint(200,300)*fy});
    }
    explosion(w.rng.randint(0,1)==0?-1.:1.,{origin.x,origin.y,0.,0.});
    if(!vehicle_death && u->source.charmed.present()){
        const size_t targets=world_.targets->size();
        for(size_t i=0;i<targets;++i){const auto& other=unit(i)->body.motion.get();
            if(std::abs(other.x-p.x)<=w.tile*2.5 && std::abs(other.y-p.y)<=w.tile*2.5)actions_.ash_zombie(i);
        }
    }else if(!vehicle_death || sled)blast_terrain(cell);
}
bool ZombieActions::death(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    const Point origin{g.xx.get(),g.yy.get()};
    if(car(b) && !b.ash.present()){b.hp=-1025.;explode(u,origin,f.cell,true);}
    b.hurt=0.;--b.hp;
    double lean=b.kind=="旗帜僵尸" || b.kind=="小丑僵尸"?std::abs(std::min(0.,b.hp+800.)):std::abs(b.hp);
    if(b.hand=="玩偶匣" && !b.ash.present()){
        if(b.hp==-300.){explode(u,origin,f.cell,false);b.hp=-1025.;b.hand.clear();}
        lean=std::abs(std::min(0.,b.hp+300.));
    }
    if(b.kind=="巨人僵尸"){
        lean=py::floordiv(b.hp+500.,2.);
        if(lean==-90.){
            w.screen_shake.set({50.,0.,0.});
            if(!n.linger.present()){w.sound("巨锤",b.motion.get());n.linger.set(1500.);}
        }
        lean=lean>0.?std::sin(pi*2.*(lean/250.))*20.:-std::abs(lean);
        if(active(n.linger) && b.hp<-900.){--n.linger.get();++b.hp;}
    }
    auto& angle=g.angle.get();angle=std::clamp(angle-lean*b.facing,-90.,90.);g.yy.get()+=std::abs(angle)*w.tile*.008;
    if(b.hp>-1025.)return false;
    if(++state_.coin_count==5){
        state_.coin_count=0;const auto& p=b.motion.get();
        state_.coins.push_back({0.,{p.x,p.y-w.tile,0.,-w.rng.randint(350,450)*w.plk},-300.,"银币"});
    }
    world_.erase_mobile_at(f.index);return true;
}
void ZombieActions::miner(const ZombieMotionFrame& f,Art& art){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;
    if(!n.emerged.present() || (b.hand!="矿镐" && !n.emerged.get()))return;
    art.size=0;if(n.entry.get()!=500. && n.entry.get()!=1.)return;
    const auto x=f.cell.x;const auto& p=b.motion.get();auto& map=world_.terrain;
    const auto& plants=*world_.plant_roster;
    double goal=nav_.target_plant==-1?world_.heroes.globals.wjx.get():double(plants.at(size_t(nav_.target_plant))->cell.x);
    const auto rally=[&]()->std::optional<Point>{
        if(b.hp<=0. || b.ash.present() || u->source.charmed.present())return {};
        return move_.rally_destination(u);
    };
    if(const auto dest=rally()){goal=py::floordiv(dest->x,w.tile);u->patch.miner_rally.set(*dest);}
    bool emerge=x==goal;int row=map.outside(0,x)?0:bottom_empty(map,x);
    if(const auto dest=rally();dest && x==py::floordiv(dest->x,w.tile))
        row=std::clamp(int(std::nearbyint(dest->y/w.tile))-1,0,map.rows()-1);
    if(const auto target=lookup_pvp_plant(world_,{row,x},true)){
        auto plant=plants.at(*target);
        if(plant->kind=="土豆地雷" && plant->buried.get()==0.){
            plant->dead.set(DeathMarker(0.));actions_.ash_zombie(f.index);emerge=true;
        }
    }
    if(emerge || n.emerged.get()){
        b.hand.clear();b.facing=-b.facing;n.entry.set(0.);n.emerged.erase();
        n.entry_end.set({p.x,row*w.tile+w.tile*1.2});n.entry_start.set(point(p));
        if(nav_.target_plant!=-1){
            const auto dx=world_.plant_roster->at(size_t(nav_.target_plant))->facing*w.tile*.5;
            n.entry_end.get().x-=dx;n.entry_start.get().x-=dx;
        }
        w.sound("出坟墓",p);
    }else{
        n.entry.set(300.);n.entry_start.set(point(p));const auto col=x+int64_t(b.facing);
        if(map.outside(0,col)){n.emerged.set(true);return;}
        row=bottom_empty(map,col);
        if(row==map.rows()-1)n.emerged.set(true);
        else {n.entry_end.set({col*w.tile+w.tile*.5,row*w.tile+w.tile*3.});b.facing=goal>x?1.:-1.;}
    }
}
void ZombieActions::giant(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    auto& p=b.motion.get();auto& hero=*g.position.get();auto& anim=n.hand_animation.get();
    if(!b.ash.present() && b.hp>0. && std::abs(p.x-hero.x)<=w.tile*.8 && std::abs(p.y-w.tile-hero.y)<=w.tile){
        if(p.x>hero.x && b.facing==-1.)hero.vx=-200.*w.plk;else if(b.facing==1.)hero.vx=200.*w.plk;
        g.jump.set(2.);
    }
    const bool frozen=active(b.ice) && (py::mod(b.ice.get(),2.)==0. || b.ice.get()>1000.);
    if(!frozen && !active(b.butter) && !b.ash.present()){
        const int count=py::mod(n.biting.get(),2.)==0.?2:1;
        for(int i=0;i<count;++i){
            if(anim[5]>0. || anim[4]==2.){
                anim[5]=-1.;
                for(const int idx:{1,0})if(anim[idx+2]!=0.){anim[idx]+=anim[idx+2];anim[idx+2]+=anim[idx+2]>0.?-1.:1.;}
            }else ++anim[5];
            if(anim[3]==0. && anim[2]==0. && anim[4]>0.){
                ++anim[4];
                if(anim[4]==2.){p.vy=800.*w.plk;anim[2]=60.;anim[3]=-70.;}
                if(anim[4]==3.){
                    w.screen_shake.set({30.,0.,0.});
                    if(std::abs(hero.x-p.x-b.facing*w.tile)<=w.tile*1.5 && std::abs(hero.y-p.y+w.tile)<=w.tile*2.){
                        w.screen_shake.set({70.,0.,0.});hero.vx+=(p.x>hero.x?-400.:400.)*w.plk;hero.vy-=400.*w.plk;player_hit(10.);
                    }
                    anim[5]=-100.;anim[2]=-33.;anim[3]=36.;w.sound("巨锤",p);
                    for(const auto c:{f.cell,Cell{f.cell.y-1,f.cell.x},Cell{f.cell.y,f.cell.x+int64_t(b.facing)},Cell{f.cell.y-1,f.cell.x+int64_t(b.facing)}})
                        if(crush(c))break;
                }
                if(anim[4]==4.)anim[4]=0.;
            }
        }
        if(n.biting.get()>350.){
            n.biting.set(350.);n.hand_animation.set({0.,0.,-50.,60.,1.,1.});
            w.sound("巨人"+std::to_string(w.rng.randint(1,2)),p);
        }
    }
    auto& angle=g.angle.get();angle-=py::floordiv(anim[1],40.)*b.facing;g.yy.get()+=std::abs(angle)*w.tile*.004;
    if(n.throw_imp.present() || b.hp<=0. || b.ash.present())return;
    if(b.hp<=n.half_hp.get() && !actions_.hold_giant()){
        n.throw_imp.set(0.);w.sound("小鬼"+std::to_string(w.rng.randint(1,2)),p);
        actions_.summon_zombie("小鬼僵尸",p,b.facing);
        auto child=world_.targets->back().unit;child->native.entry.set(500.);child->native.rotation.set(0.);
        auto& m=child->body.motion.get();m.vx=b.facing*800.*w.plk;m.vy=-600.*w.plk;m.y-=w.tile*1.5;
    }
    const bool mirror=b.facing!=1.;
    draw("小鬼僵尸",{mirror?g.xx.get()+w.tile*.9:g.xx.get()+w.tile-w.tile*.9,g.yy.get()-w.tile*.7},mirror,angle);
}
void ZombieActions::render(const ZombieRef& u,const Art& art){
    if(!state_.drawing)return;
    auto& w=world_.runtime;auto& g=world_.heroes.globals;auto& b=u->body;auto& n=u->native;
    auto& x=g.xx.get();auto& y=g.yy.get();auto& angle=g.angle.get();const auto& m=b.motion.get();
    if(n.light.present())draw("灯光"+std::to_string(int(n.light.get())),{x,y-w.tile*8.});
    Point base{x,y};
    const auto jitter=[&](double amplitude){return w.rng.randint(-int64_t(amplitude),int64_t(amplitude))*(w.tile/810.)*10.;};
    if(active(b.stun)){
        const double amplitude=py::floordiv(b.stun.get(),500.)+1.;
        base.x+=jitter(amplitude);base.y+=jitter(amplitude);
    }
    const bool mirror=b.facing!=1.;
    for(size_t i=0;i<art.size;++i){
        const auto& [sprite,layer]=art.layers[i];
        const bool head=layer==Layer::head || layer==Layer::ice_head || layer==Layer::charm_head;
        const bool armor=layer==Layer::armor || layer==Layer::ice_armor;
        x=base.x;y=base.y;
        if((b.kind=="小丑僵尸" || b.berserk.present()) && head){y+=jitter(1.);x+=jitter(1.);}
        if(armor)y-=m.vy/w.plk*w.tile/3000.;
        double rotation=angle;
        if(layer==Layer::hand){
            x+=m.vx/w.plk*w.tile/1000.;y-=m.vy/w.plk*w.tile/2000.;
            if(sprite.starts_with("锤")){
                x+=b.facing*w.tile/3.;y+=w.tile/3.;const auto& anim=n.hand_animation.get();
                rotation-=py::floordiv(anim[1],10.)*b.facing;x+=anim[0]/1000.*w.tile*b.facing;y+=anim[0]/1000.*w.tile;
            }
        }
        if(n.biting.get()>0. && b.kind!="巨人僵尸" && (head || armor)){
            const double phase=pi*(n.biting.get()/120.);
            const double bob=(-2./pi*phase+2.)*std::sin(phase)*w.tile*.1;
            if(b.kind!="飞贼僵尸")x+=bob*b.facing;
            y+=bob*2.;angle+=phase;
        }
        alpha(sprite,b.hp<-1000.?(1025.+b.hp)*10.:255.);
        if(layer==Layer::ice || layer==Layer::ice_head || layer==Layer::ice_armor || layer==Layer::charm || layer==Layer::charm_head)alpha(sprite,100.);
        if(layer==Layer::ash_body)actions_.crop(w.presentation.sprite_name(sprite),{x,y},mirror,{w.tile*b.size.get(),art.ash_height});
        else draw(sprite,{x,y},mirror,rotation);
        if(layer==Layer::hand && b.hand_hurt>0.){
            const auto hurt=sprite+"-受伤";alpha(hurt,std::sin(pi*(b.hand_hurt/50.))*150.);draw(hurt,{x,y},mirror,angle);
        }
        if(b.hurt>0. && (layer==Layer::body || layer==Layer::armor || layer==Layer::head)){
            const auto hurt=sprite+"-受伤";alpha(hurt,std::sin(pi*(b.hurt/50.))*150.);draw(hurt,{x,y},mirror,angle);
        }
    }
    if(active(b.butter)){
        const auto extra=b.size.get()>2.?w.tile/2.:0.;
        draw("黄油砸",{x+b.facing*w.tile/4.+extra+w.tile/2.,y+w.tile/5.+extra});
    }
    if(b.kind=="雪橇车僵尸" && !b.ash.present()){
        angle=n.wheel.get()*b.facing;
        for(const auto offset:b.facing==-1.?std::array{-.35,.75}:std::array{.75,1.85})
            draw("轮子",{x+w.tile*offset,y+w.tile*1.9},false,angle);
    }
}
void ZombieActions::cart(const ZombieMotionFrame& f){
    const auto u=unit(f.index);auto& n=u->native;auto& b=u->body;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    const double x=g.xx.get(),y=g.yy.get();auto& angle=g.angle.get();const auto& p=b.motion.get();
    angle=n.wheel.get()*b.facing;draw("轮子",{x+w.tile*(b.facing==-1.?-.05:1.55),y+w.tile*1.9},false,angle);
    if(n.advance.get()>0.)--n.advance.get();
    if(!f.immobile){
        if(n.basketball_cd.get()>0. && --n.basketball_cd.get()==0.)n.shooting.set(1.);
        if(n.shooting.get()>0.){
            const auto tick=++n.shooting.get();
            if(tick==120.){
                w.sound("投篮",p);move_.add_entity("篮球",b.facing,{p.x,p.y-w.tile*2.,b.facing*w.plk*300.,-900.*w.plk});
                auto e=w.entities.list()->back();e->gravity.set(0.);e->squash.bounce_x.set(10.);e->rotation.set(double(w.rng.randint(0,360)));
            }
            if(tick==200.){
                n.shooting.set(0.);n.basketball_cd.set(300.);--u->protection.basketball.get();--n.basketball_total.get();
                if(!named(u->protection.card,"zombie:投篮车僵尸") && n.basketball_total.get()<=0.)move_.ordinary(f.index,b.facing,10000.);
                if(!named(u->protection.card,"zombie:投篮车僵尸") && u->protection.basketball.get()==0.){
                    u->protection.basketball.set(3.);const auto col=f.cell.x+int64_t(b.facing);const int row=f.cell.y;
                    const auto& map=world_.terrain;
                    if(!map.outside(row,col) && !map.empty(row,col) && !map.outside(row-1,col) && map.empty(row-1,col)){
                        n.advance.set(500.);n.entry.set(0.);n.entry_start.set(point(p));n.entry_end.set({col*w.tile+w.tile/2.,row*w.tile+w.tile*.2});
                    }else n.advance.set(400.);
                }
            }
        }
    }
    angle=0.;std::string arm="投篮臂";
    if(n.shooting.get()>0.){
        if(n.shooting.get()>120.)arm="投篮臂-空";
        angle=-std::sin(pi*2.*(n.shooting.get()/200.))*120.*b.facing;
    }
    draw(std::move(arm),{x,y},b.facing!=1.,angle);
}
void ZombieActions::pole(const ZombieRef& u){
    auto& b=u->body;if(!active(b.pole_vault))return;
    auto& w=world_.runtime;auto& g=world_.heroes.globals;auto& p=b.motion.get();const double t=++b.pole_vault.get();
    if(t==100.){p.vx=b.facing*500.*w.plk;p.vy=-600.*w.plk;w.sound("撑杆跳",p);}
    if(t<100.){
        const double swing=std::sin(pi*(t/200.));
        draw("撑杆",{g.xx.get(),g.yy.get()+swing*w.tile},false,b.facing*swing*90.);
    }
    if(t==200.)b.pole_vault.erase();
}
void ZombieActions::finish(ZombieMotionFrame f){
    LiveBattleSources sources(world_);NativeBirthScope births(world_.runtime,move_);world_.heroes.source_index=int64_t(f.index);
    auto u=unit(f.index);auto& b=u->body;auto& n=u->native;auto& g=world_.heroes.globals;
    if(n.move_speed.get()==0.)throw std::domain_error("zero native zombie base speed");
    g.angle.set(std::clamp(b.motion.get().vx/n.move_speed.get()*10.,-10.,10.));
    dance(f);waking(f);locomotion(f);
    Art art;body_art(f,art);
    if(b.hp<=0. && death(f))return;
    if(n.rotation.present() && n.rotation.get()<120.)g.angle.get()+=++n.rotation.get()*3.*b.facing;
    if(!b.armor.empty() && !b.ash.present()){
        art.add(b.armor,Layer::armor);if(active(b.ice))art.add(b.armor+"-冰冻",Layer::ice_armor);
    }
    if(!b.hand.empty() && !b.ash.present() && b.hand!="气球")art.add(b.hand,Layer::hand);
    if(b.hand=="气球"){
        draw("气球",{g.xx.get(),g.yy.get()-world_.runtime.tile});
        if(f.collision==2)n.midfield.erase();
    }
    miner(f,art);
    if(b.kind=="巨人僵尸")giant(f);
    render(u,art);
    if(b.kind=="投篮车僵尸" && !b.ash.present())cart(f);
    pole(u);
}
void ZombieActions::run(){
    LiveBattleSources sources(world_);NativeBirthScope births(world_.runtime,move_);
    // range(len(...)-1,-1,-1) freezes the count, not the index contents.
    for(size_t i=world_.targets->size();i-- >0;){
        world_.heroes.source_index=int64_t(i);actions_.zombie_gate(i);
        finish(motion_.advance(i));
    }
}
} // namespace pvz::typed72
