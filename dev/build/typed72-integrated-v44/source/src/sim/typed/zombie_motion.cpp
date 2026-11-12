#include "sim/typed/zombie_motion.h"
#include "sim/typed/plant_lookup.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
bool field_is(const Field<std::string>& f,std::string_view s){return f.present()&&!f.is_null()&&f.get()==s;}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool black(const CombatZombie& z){
    const auto& v=z.source.variant;
    return field_is(v,"黑普通僵尸")||field_is(v,"黑路障僵尸")||field_is(v,"黑铁桶僵尸")||
           field_is(v,"黑旗帜僵尸")||field_is(v,"黑撑杆僵尸")||field_is(v,"黑橄榄僵尸");
}
double value(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool one_of(std::string_view s,std::initializer_list<std::string_view> kinds){
    return std::find(kinds.begin(),kinds.end(),s)!=kinds.end();
}
bool vehicle(std::string_view s){return one_of(s,{"雪橇车僵尸","投篮车僵尸"});}
Point xy(const Motion& p){return {p.x,p.y};}
auto bucket(TargetBuckets& b,int64_t k){return std::find_if(b.begin(),b.end(),[k](const auto& row){return row.first==k;});}
}
ZombieRef ZombieMotion::zombie(size_t i)const {
    auto u=world_.targets->at(i).unit;
    if(!u)throw std::logic_error("hero collider in mobile zombie phase");
    return u;
}
bool ZombieMotion::secret(std::string_view s)const{
    const auto& secrets=*world_.heroes.globals.secrets.get();
    return std::find(secrets.begin(),secrets.end(),s)!=secrets.end();
}
TileRef ZombieMotion::tile(int row,int64_t col)const{
    return world_.terrain.valid_row(row)?world_.terrain.at(row,world_.terrain.wrap(col)):TileRef{};
}
int ZombieMotion::flood(int field,int row,int64_t col)const{
    return std::abs(routes_.chase_fields.at(field)->at(size_t(row)*world_.terrain.cols()+world_.terrain.wrap(col)));
}
void ZombieMotion::sound_at(const char* stem,int variants,size_t i){
    auto& w=world_.runtime;const auto suffix=w.rng.randint(1,variants);
    w.sound(stem+std::to_string(suffix),zombie(i)->body.motion.get());
}
void ZombieMotion::entry(ZombieMotionFrame& f) {
    auto u=zombie(f.index);auto& n=u->native;auto& b=u->body;
    auto& p=b.motion.get();auto& w=world_.runtime;
    if(n.entry.get()<500.){
        p.vx=p.vy=0.;n.entry.get()+=1.;
        if(n.entry.get()==0. && b.kind=="飞贼僵尸")
            w.sound("蹦极"+std::to_string(w.rng.randint(1,3)),{p.x,world_.heroes.globals.position.get()->y-w.tile*9.,0.,0.});
    }
    f.cell=player_flood_seed(xy(p),w.tile);
    if(n.split.present()){
        if(n.split.get()>0.)n.split.get()-=1.;
        if(n.split.get()==0.)f.flood_index=routes_.target_plant==-1;
        else if(!(routes_.target_plant==-1 && std::abs(world_.heroes.globals.wjx.get()-f.cell.x)<=8. && std::abs(world_.heroes.globals.wjy.get()-f.cell.y)<=2.)){
            bool ladder=n.divide.get()>0.;
            if(ladder)n.divide.get()-=1.;
            else ladder=std::any_of(indexes_.ladders.begin(),indexes_.ladders.end(),[&](int64_t x){return std::abs(double(f.cell.x)-x)<=8.;});
            if(ladder && routes_.hold_plant==0.){n.divide.set(300.);f.flood_index=1;}
        }
    }
    const auto cell=tile(f.cell.y,f.cell.x);
    if(!cell)f.heading=1;
    else if(b.kind=="潜水僵尸" && cell->block.get()=="水"){
        f.heading=flood(f.flood_index,int(world_.terrain.water_surface),f.cell.x);n.divide.set(300.);
    }else f.heading=flood(f.flood_index,f.cell.y,f.cell.x);
    f.original_heading=f.heading;
}
void ZombieMotion::environment(ZombieMotionFrame& f) {
    auto& g=world_.heroes.globals;g.water.set(false);g.sbs.set(false);
    auto u=zombie(f.index);
    if(u->native.entry.get()!=500.)return;
    const auto above=tile(f.cell.y-1,f.cell.x);
    if(above && above->block.get()=="雪")destroy_pvp_block(world_,plants_,{f.cell.y-1,f.cell.x});
    u=zombie(f.index);auto& w=world_.runtime;auto& b=u->body;auto& n=u->native;auto& p=b.motion.get();
    const int foot=terrain_cell(xy(p),w.tile).y;
    const auto low=tile(foot,f.cell.x),high=tile(foot-1,f.cell.x);
    const bool submerged=high && high->block.get()=="水";
    const bool wet=submerged || (low && low->block.get()=="水");
    g.water.set(wet);g.sbs.set(submerged);
    if(!wet){b.in_water.set(false);return;}
    if(!b.in_water.get()){
        b.in_water.set(true);
        if(n.explosion_sound.get()==0.){
            n.explosion_sound.set(20.);w.sound("入水",p);w.emit_particles(routes_.water_sprite,xy(p),16);
        }
    }
    if(p.vy>0.)p.vy-=w.plk*(b.kind=="潜水僵尸"?3.:3.9);
    if(p.vy>50.*w.plk)p.vy=50.*w.plk;
    if(submerged && b.hp>0. && !b.ash.present() && (b.kind!="潜水僵尸" || n.biting.get()>0.)){
        if(b.kind.starts_with("鸭") || b.hand=="海豚")p.vy=-w.plk*150.;
        else if(!vehicle(b.kind))p.vy=-w.plk*200.;
        n.breath.get()+=1.;
        if(n.breath.get()>10000. && py::mod(n.breath.get(),300.)==0.)callbacks_.ordinary(f.index,b.facing,30.);
    }else n.breath.set(0.);
    zombie(f.index)->native.jump_cd.set(0.);
}
void ZombieMotion::status(ZombieMotionFrame& f) {
    const auto u=zombie(f.index);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;
    if(b.kind=="报纸僵尸" && b.hand.empty() && !b.berserk.present()){
        sound_at("二爷",2,f.index);n.garlic.set(399.);b.berserk.set(0.);n.move_speed.set(300.*w.plk);
    }
    if(n.biting.get()>0.){
        if(n.jump_cd.get()<=1.)n.jump_cd.set(2.);
        const auto ice=value(b.ice);
        if(value(b.butter)<=0. && !((ice>0. && py::mod(ice,2.)==0.) || ice>1000.))n.biting.get()-=1.;
        if(one_of(b.kind,{"橄榄球僵尸","黑橄榄球僵尸","小鬼僵尸","飞贼僵尸"}) ||
           (u->source.charmed.present() && secret("魅惑")))n.biting.get()-=1.;
        if(b.berserk.present())n.biting.get()-=4.;
        n.biting.get()=std::max(0.,n.biting.get());
    }
    if(value(b.butter)>0.){b.butter.get()-=1.;f.can_bite=false;f.immobile=true;}
    if(value(b.ice)>0.){b.ice.get()-=1.;if(b.ice.get()>1000.){f.can_bite=false;f.immobile=true;}}
    if(u->source.charmed.present() && u->source.charmed.get()<200.)f.can_bite=false;
    if(value(b.stun)>0.){b.stun.get()-=1.;n.garlic.set(100.);f.immobile=true;}
    if(value(n.garlic)>0.){
        if(n.garlic.get()==400.){
            sound_at("大蒜",2,f.index);b.facing=-b.facing;
            b.motion.get().vx=b.facing*350.*w.plk;b.motion.get().vy=-450.*w.plk;
        }
        n.garlic.get()-=1.;f.can_bite=false;
    }
    if(b.hp<=0. || vehicle(b.kind))f.can_bite=false;
    if(b.hand=="撑杆" && !b.in_water.get()){
        const Cell c{f.cell.y,f.cell.x+int64_t(b.facing)};const auto next=tile(c.y,c.x);
        if(next && next->plant.present())if(const auto i=lookup_pvp_plant(world_,c,false);
            i && !one_of(world_.plant_roster->at(*i)->kind,{"地刺","地刺王"})){
            n.garlic.set(200.);b.hand.clear();b.pole_vault.set(1.);n.move_speed.set(60.*w.plk);
        }
    }
}
double ZombieMotion::plant_bite(const ZombieRef& u)const{
    if(black(*u))return 3.;
    if(field_is(u->protection.card,"zombie:墓碑吞噬者僵尸") || u->body.kind=="墓碑吞噬者僵尸")
        return u->body.hp<=value(u->max_hp,300.)*.5?6.:3.;  // PvP73
    return value(u->patch.bite_plant,1.);
}
double ZombieMotion::bite_rate(const ZombieRef& u)const{
    double rate=1.;
    if(world_.protection.secrets.enabled && world_.heroes.owner(source_ref(u))==Seat::zombie) {
        if(world_.protection.focused(u->damage_target()))rate+=1.;
        if(world_.protection.berserk())rate+=1.;
    }
    return rate;
}
double ZombieMotion::bite_amount(const ZombieRef& attacker,const ZombieRef& target)const{
    if(flag(attacker->patch.no_attack))return 0.;
    const auto& card=attacker->protection.card;
    double base=plant_bite(attacker);
    if(card.present() && !card.is_null() && one_of(card.get(),{"zombie:巨人僵尸","zombie:红眼巨人","zombie:角斗士巨人"}))base=10.;
    const double rate=(attacker->body.berserk.present()?4.:1.)*bite_rate(attacker);
    if(!target)return (black(*attacker)?3.:base)*rate;
    double amount=base*rate*10.;
    if(target->source.charmed.present() && !attacker->source.charmed.present() && routes_.charm_secret)amount*=.5;
    return amount;
}
void ZombieMotion::reciprocal(size_t i,const ZombieRef& attacker){
    auto target=zombie(i);auto& h=world_.heroes;
    if(h.tick<value(target->protection.anchor_until))return;
    auto source=source_ref(attacker);const auto owner=h.owner(source).value();
    const double amount=bite_amount(attacker,target);
    HeroContext scope(h,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::zombies,source,{}});
    callbacks_.ordinary(i,target->body.facing,amount);
}
void ZombieMotion::bite_hero(const ZombieRef& u){
    if(flag(u->patch.no_attack))return;
    auto& h=world_.heroes;const auto target=h.active.value().target;
    h.proxy(target);
    const auto damage=h.player_damage(bite_amount(u,{}));
    if(damage.value_or(0.)!=0. && (field_is(u->source.content,"海盗鹦鹉")||field_is(u->source.content,"乌鸦"))) {
        h.proxy(target);
        const auto& secrets=h.players.at(seat_index(target)).value().secrets;
        if(std::find(secrets.begin(),secrets.end(),"secret:体香")!=secrets.end())u->body.stun.set(std::max(value(u->body.stun),125.));
    }
}
void ZombieMotion::bite_write(size_t l,size_t z,double damage){
    const auto u=zombie(l);if(flag(u->patch.no_attack))return;
    const auto p=world_.plant_roster->at(z);
    static const std::string no_hand;
    auto& hp=p->hp.get();
    hp-=world_.protection.amount({hp,no_hand,p->source,p->protection},damage*(plant_bite(u)*bite_rate(u)));
    if(p->kind=="雷蘑菇" || field_is(p->protection.card,"plant:雷蘑菇") || (p->kind=="大喷菇"&&secret("雷霆")))
        u->body.stun.set(std::max(value(u->body.stun),250.));
    if((field_is(u->source.content,"海盗鹦鹉") || field_is(u->source.content,"乌鸦")) && p->kind=="大蒜")
        u->body.stun.set(std::max(value(u->body.stun),125.));
}
void ZombieMotion::bite_plant(ZombieMotionFrame& f,size_t z) {
    const auto l=f.index;auto& w=world_.runtime;
    const auto get=[&]{return world_.plant_roster->at(z);};
    auto u=zombie(l);auto& b=u->body;auto& n=u->native;
    if(b.hand=="撑杆" && !b.in_water.get()){
        n.garlic.set(200.);b.hand.clear();b.pole_vault.set(1.);n.move_speed.set(60.*w.plk);return;
    }
    if(b.hand=="海豚" && n.jump_cd.get()==0. && b.in_water.get() && (int64_t(z)!=routes_.target_plant || f.flood_index==0)){
        n.jump_cd.set(100.);w.sound("海豚跳跃",b.motion.get());n.garlic.set(200.);
        b.motion.get().vx=b.facing*500.*w.plk;b.motion.get().vy=-600.*w.plk;b.hand.clear();
        callbacks_.add_entity("海豚",b.facing,b.motion.get());const auto e=w.entities.list()->back();e->gravity.set(0.);
        auto& m=e->motion.get();m.x-=w.tile*.5;m.y-=w.tile*1.5;m.vx=zombie(l)->body.facing*w.plk*400.;
        m.vy=-w.rng.randint(200,250)*w.plk;e->expires.set(1.);return;
    }
    b.motion.get().vx/=2.;
    if(b.kind!="巨人僵尸"){
        if(get()->expires.present()&&!get()->sleep.present()){
            if(get()->kind=="石果子"){
                get()->hurt.set(1.);
                if(black(*u) && !flag(u->patch.no_attack))get()->hp.get()-=3.;
            }
        }else{
            bite_write(l,z,1.);if(zombie(l)->body.berserk.present())bite_write(l,z,3.);
            get()->hurt.set(1.);
            if(field_is(world_.heroes.globals.mode,"我是僵尸")){
                get()->sleep.erase();if(one_of(get()->kind,{"向日葵","阳光菇","双子向日葵","金盏花"}))get()->burst.set(124.);
            }
        }
    }
    auto p=get();
    if((p->kind=="土豆地雷" && p->emerged.get()>0. && !p->dead.present()) || (p->kind=="缠绕海草"&&!p->dead.present()))
        p->dead.set(DeathMarker(0.));
    else if(p->kind=="魅惑菇" && !p->sleep.present() &&
            (std::find(routes_.bosses.begin(),routes_.bosses.end(),b.kind)==routes_.bosses.end() || field_is(world_.heroes.globals.mode,"测试模式")) &&
            b.size.get()==2.){
        p->sleep.set(0.);n.biting.set(120.);n.jump_cd.set(300.);p->dead.set(DeathMarker(0.));
        w.sound("魅惑",b.motion.get());u->source.charmed.set(0.);
        for(int i=0;i<3;++i){
            const double fx=w.rng.randint(1,2)==1?1.:-1.;const auto& m=zombie(l)->body.motion.get();
            const Motion pos{m.x+w.tile/2.,m.y-w.tile,w.rng.randint(-50,50)*w.plk,w.rng.randint(-100,-50)*w.plk};
            callbacks_.add_entity("魅惑",fx,pos);auto e=w.entities.list()->back();e->expires.set(900.);e->rotation.set(double(w.rng.randint(0,360)));
        }
    }else if(p->hp.get()<=0. && b.kind!="巨人僵尸" && !p->dead.present()){
        w.sound("吃掉",b.motion.get());if(p->kind=="花盆")destroy_pvp_block(world_,plants_,f.cell);else plants_.clear(f.cell);
    }else if(b.kind!="巨人僵尸"){
        if(p->kind=="仙人掌"){
            if(routes_.cactus_secret)callbacks_.ordinary(l,b.facing>=0.?1.:-1.,7.5);
            callbacks_.ordinary(l,zombie(l)->body.facing,routes_.cactus_secret?10.:5.);
        }
        if(get()->kind=="大蒜")zombie(l)->native.garlic.set(500.);
        zombie(l)->native.biting.set(120.);zombie(l)->native.jump_cd.set(300.);
        w.emit_particles(get()->kind,{f.cell.x*w.tile+w.tile*.5,f.cell.y*w.tile+w.tile*.5},4);
        sound_at("吃",2,l);
    }
    if(zombie(l)->body.kind=="巨人僵尸")zombie(l)->native.biting.set(500.);
}
void ZombieMotion::bite(ZombieMotionFrame& f){
    const size_t l=f.index;auto u=zombie(l);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;
    if(u->source.charmed.present()){
        const auto count=world_.targets->size();
        for(size_t z=0;z<count;++z){
            auto other=zombie(z);auto& t=other->body;
            if(other->source.charmed.present()||t.hp<=0.||std::abs(b.motion.get().x-t.motion.get().x)+std::abs(b.motion.get().y-t.motion.get().y)>w.tile)continue;
            n.biting.set(110.);n.jump_cd.set(300.);b.motion.get().vx/=2.;
            if(t.size.get()==2.){
                t.facing=-b.facing;t.motion.get().vx/=2.;other->native.biting.set(120.);other->native.jump_cd.set(300.);
                reciprocal(l,other);if(zombie(z)->body.hp>0.)sound_at("吃",2,z);
            }
            reciprocal(z,zombie(l));if(zombie(l)->body.hp>0.)sound_at("吃",2,l);break;
        }
        return;
    }
    if(!tile(f.cell.y,f.cell.x))return;
    const auto upper=tile(f.cell.y-1,f.cell.x);
    if(upper && upper->plant.present())--f.cell.y;
    const auto cell=tile(f.cell.y,f.cell.x);
    std::optional<size_t> target;
    if(cell->plant.present()){
        target=lookup_pvp_plant(world_,f.cell,false);
        const auto& plants=*world_.plant_roster;
        const auto p=plants.at(target.value_or(plants.size()-1));
        if(one_of(p->kind,{"地刺","地刺王"}) || (p->kind=="海蘑菇" && secret("水兵")))target.reset();
    }
    if(target && b.kind!="雪人僵尸"){bite_plant(f,*target);return;}
    if(b.kind=="巨人僵尸" && cell->plant.present()){n.biting.set(500.);return;}
    auto& g=world_.heroes.globals;
    if(field_is(g.mode,"我是僵尸")||flag(u->source.no_hero_attack)||g.hp.get()<=0.)return;
    const double d=std::abs(b.motion.get().x-g.position.get()->x)+std::abs(b.motion.get().y-g.position.get()->y);
    if(b.kind=="巨人僵尸" && d<=w.tile*1.5){n.biting.set(500.);b.motion.get().vx/=2.;return;}
    if(d>w.tile)return;
    n.biting.set(120.);b.motion.get().vx/=2.;n.jump_cd.set(130.);sound_at("吃",2,l);
    if(py::mod(g.hp.get(),2.)==0. && secret("体香"))n.garlic.set(500.);
    w.screen_shake.set({50.,0.,0.});bite_hero(u);g.position.get()->vx=zombie(l)->body.facing*100.*w.plk;
}
void ZombieMotion::chase(ZombieMotionFrame& f) {
    const auto l=f.index;auto u=zombie(l);
    auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;auto& g=world_.heroes.globals;
    const auto [y,x]=f.cell;
    if(f.heading==2 && n.jump_cd.get()==0.) {
        const auto here=tile(y,x),above=tile(y-1,x),below=tile(y+1,x);
        f.ladder=(above && flood(f.flood_index,y-1,x)==2) || (below && below->block.get()=="梯子块");
        if(b.hand=="梯子" && f.ladder && below && below->block.get()!="空" && here->block.get()=="空") {
            here->block.set("梯子块");
            w.emit_particles("梯子块",{x*w.tile+w.tile*.5,y*w.tile+w.tile*.5},6);
            w.sound("铁桶2",b.motion.get());
        }
        const auto col=bucket(*indexes_.columns,x);
        const bool occupied=col!=indexes_.columns->end() && std::find(col->second.begin(),col->second.end(),y)!=col->second.end();
        if((occupied && b.kind!="巨人僵尸" && b.hand!="弹跳杆" && b.hand!="梯子") ||
           here->block.get()=="梯子块" || (above && above->block.get()=="梯子块")) {
            b.motion.get().vy=-w.plk*200.;b.motion.get().vx=b.facing*10.*w.plk;n.jump_cd.set(70.);f.heading=5;
        }else if(routes_.scripted && routes_.director_available && routes_.ladder_count>0 && routes_.ladder_cooldown==0 &&
                 b.kind!="梯子僵尸" && f.ladder && !u->source.charmed.present())callbacks_.request_ladder(u);
    }
    if(b.hand=="气球") {
        if(n.midfield.present()) {
            if(x>35)f.heading=4;
            else if(x<35)f.heading=3;
            else n.midfield.erase();
        }else if(f.heading==1)callbacks_.surface(l,b.facing,1.);
    }else if(f.heading<=2 || (field_is(u->source.content,"滚桶僵尸") && b.hand_hp>0. && !u->source.charmed.present())) {
        f.heading=b.facing==-1.?4:3;
    }else if(u->source.charmed.present() && u->source.charmed.get()<3000.) {
        if(f.heading==3 || f.heading==4)f.heading=7-f.heading;
    }
    double speed=n.move_speed.get();
    if(!u->source.charmed.present() && !u->protection.grave) {
        if(const auto dest=callbacks_.rally_destination(u);dest &&
           std::abs(wrap_delta(b.motion.get().x,dest->x,world_.world_width.get()))<w.tile*.4 &&
           std::abs(b.motion.get().y-dest->y)<w.tile)speed=0.;
    }
    const auto& camera=w.presentation.camera;
    auto& p=b.motion.get();
    if(routes_.wave>0. && (p.x<camera.x-w.tile*2. || p.x>camera.x+w.presentation.screen_width+w.tile*2. ||
                          p.y-b.size.get()*w.tile>camera.y+routes_.screen_height)) {
        n.respawn.get()-=routes_.running;
        if(n.respawn.get()<=0.) {
            n.respawn.set(double(w.rng.randint(10000,15000)));n.entry.set(0.);
            const bool right=routes_.running==1.?x<35:w.rng.randint(0,1)==1;
            const bool far_edge=right||world_.placement.boss_battle;
            const int col=far_edge?world_.terrain.cols()-1:0;
            const double facing=far_edge?-1.:1.;
            g.xx.set(double(col));
            for(int row=0;row<world_.terrain.rows();++row) {
                g.yy.set(double(row));const auto& kind=tile(row,col)->block.get();
                if((!world_.terrain.is_empty(kind) && kind!="雪") || kind=="水")break;
            }
            b.facing=facing;const double edge=col*w.tile+w.tile*.5;
            n.entry_end.set({edge,g.yy.get()*w.tile});n.entry_start.set({edge-w.tile*5.*facing,25.*w.tile});
            const auto& start=n.entry_start.get();w.sound("出坟墓",{start.x,start.y,0.,0.});
        }
        speed=60.*w.plk;
        if(routes_.running>1.)speed+=(l%10)*20.*w.plk;
        if(b.kind=="梯子僵尸")speed=150.*w.plk;
    }
    if(g.water.get() && b.hand=="海豚")speed*=3.;
    else if(g.water.get() && !b.kind.starts_with("鸭") && b.kind!="潜水僵尸")speed/=2.;
    if(value(b.ice)>0.)speed/=2.;
    g.speed.set(speed);
    if(value(b.dancing)>0. || f.immobile)return;
    if(f.heading==4) {
        if(p.vx<0.)b.facing=-1.;
        if(p.vx>-speed)p.vx-=w.plk*3.;
    }else if(f.heading==3) {
        if(p.vx>0.)b.facing=1.;
        if(p.vx<speed)p.vx+=w.plk*3.;
    }
}
void ZombieMotion::register_body(Cell cell,std::string_view kind) {
    indexes_.register_body(cell,kind);
}
void TargetIndexes::register_body(Cell cell,std::string_view kind) {
    const auto [y,x]=cell;
    auto& cols=*columns;auto col=bucket(cols,x);
    if(col==cols.end())cols.emplace_back(x,std::vector<int64_t>{y,y-1});
    else {col->second.push_back(y-1);col->second.push_back(y);}
    auto& row_chart=*rows;
    for(const int row:{y,y-1}) {
        auto it=bucket(row_chart,row);
        if(it==row_chart.end())it=row_chart.emplace(row_chart.end(),row,std::vector<int64_t>{});
        it->second.push_back(x);
        if(kind=="飞贼僵尸") {
            const int side=row==y?-1:1;
            it->second.push_back(x+side);it->second.push_back(x-side);
        }
    }
}
void ZombieMotion::register_stationary(size_t index) {
    const auto& t=world_.targets->at(index);
    if(t.is_hero()) {
        const auto& p=world_.heroes.cached_proxy(t.hero);
        if(p.hp>0.){
            world_.heroes.source_index=int64_t(index);
            register_body(player_flood_seed(xy(*p.position),world_.runtime.tile),{});
        }
    }else if(t.unit->body.hp>0. && (t.unit->protection.grave || t.unit->orphan_barrel)) {
        world_.heroes.source_index=int64_t(index);
        register_body(player_flood_seed(xy(t.unit->body.motion.get()),world_.runtime.tile),{});
    }
}
ZombieMotionFrame ZombieMotion::advance(size_t l) {
    LiveBattleSources sources(world_);world_.heroes.source_index=int64_t(l);
    NativeBirthScope births(world_.runtime,callbacks_);
    ZombieMotionFrame f;f.index=l;entry(f);environment(f);
    auto u=zombie(l);auto& b=u->body;auto& n=u->native;auto& w=world_.runtime;
    if(n.wake.present()){f.can_bite=false;f.immobile=true;}
    if((b.hp>0. || one_of(b.kind,{"旗帜僵尸","小丑僵尸"})) && n.entry.get()==500. && !b.ash.present() && !n.wake.present()) {
        status(f);
        if(n.biting.get()==0. && f.can_bite)bite(f);
        if((n.biting.get()==0. && f.can_bite) || (b.hp<=0. && b.hp>-800.))chase(f);
        if(n.jump_cd.get()>0.)n.jump_cd.get()-=1.;
        register_body(f.cell,b.kind);
    }
    if(world_.heroes.globals.water.get() && b.kind=="雪人僵尸")b.motion.get().vy=-w.plk*400.;
    if(u->source.charmed.present()) {
        u->source.charmed.get()+=1.;
        if(n.biting.get()>0.)u->source.charmed.set(200.);
        if(u->source.charmed.get()>10000. || (world_.targets->size()==1 && world_.heroes.hero(Seat::zombie).frame.hp.get()<=0.))
            callbacks_.ordinary(l,b.facing,10000.);
    }
    if(b.kind=="飞贼僵尸")b.motion.get().vx=b.motion.get().vy=0.;
    else f.collision=displace_body(b.motion.get(),1.,world_.terrain,w.tile,w.plk,true);
    return f;
}
} // namespace pvz::typed72
