#include "sim/typed/zombie_pea.h"
#include "sim/typed/torch_rules.h"
#include "sim/typed/plant_lookup.h"
#include "core/pymath.h"
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
double number(const Field<double>& v,double fallback=0.){return v.present()&&!v.is_null()?v.get():fallback;}
bool truth(const Field<bool>& v){return v.present()&&!v.is_null()&&v.get();}
std::string_view text(const Field<std::string>& v){return v.present()&&!v.is_null()?std::string_view(v.get()):std::string_view{};}
bool live(const PlantRef& p){return !p->dead.present()&&!p->shovel_dead.present()&&number(p->hp,1.)>0.;}
bool charmed(const CombatTarget& t){return !t.is_hero()&&t.unit->source.charmed.present();}
}
bool ZombiePeas::is_pea(const EntityRef& e){return truth(e->pea.zombie_pea)||e->kind=="僵尸豌豆";}
Point ZombiePeas::xy(const EntityRef& e){const auto& p=e->motion.get();return {p.x,p.y};}
bool ZombiePeas::segment_hits(Point a,Point b,Point c,Point radii){return segment_hits_ellipse(a,b,{c,radii.x,radii.y});}
double ZombiePeas::fire_multiplier(const EntityRef& e){const auto fire=text(e->source.zombie_fire);return fire=="blue"?3.:fire=="fire"?2.:1.;}
bool ZombiePeas::i_zombie()const{return text(world_.heroes.globals.mode)=="我是僵尸";}
void ZombiePeas::splat(Point p){world_.runtime.sound("splat"+std::to_string(world_.runtime.rng.randint(1,3)),{p.x,p.y,0.,0.});}
std::shared_ptr<AttackSource> ZombiePeas::source_ref_for(const CombatTarget& t)const {return t.is_hero()?world_.heroes.proxy_source(t.hero):source_ref(t.unit);}
RecordId ZombiePeas::identity(const CombatTarget& t)const{return t.is_hero()?world_.heroes.cached_proxy(t.hero).identity:t.unit->identity;}
bool ZombiePeas::damage_player(double direction) {
    if(i_zombie())return false;auto& g=world_.heroes.globals;const auto before=g.hp;
    try{callbacks_.player_damage(1.);}catch(const std::exception&){}
    if(before.present()&&!before.is_null()&&g.hp.present()&&!g.hp.is_null()&&g.hp.get()==before.get()){g.hp.set(before.get()-1.);g.hurt.set(1.);}
    if(g.position.present()&&!g.position.is_null())g.position.get()->vx=(direction<0.?-1.:1.)*150.*world_.runtime.plk;return true;
}
bool ZombiePeas::damage_charmed(size_t index,CombatTarget target,const EntityRef& e,double direction) {
    const double amount=20.*fire_multiplier(e);bool surface_hit=false;std::optional<bool> result=false;
    try{result=callbacks_.surface_damage(index,direction,amount);surface_hit=result.value_or(false);}catch(const std::exception&){}
    if(!result){try{callbacks_.ordinary_damage(index,direction,amount);}catch(const std::exception&){if(target.is_hero()){const auto& p=world_.heroes.cached_proxy(target.hero);world_.heroes.write_proxy_hp(target.hero,p.hp-amount);}else target.unit->body.hp-=amount;}}
    if(!surface_hit&&amount>5.&&!e->tracking.present())try{callbacks_.knockback(index,direction*world_.runtime.plk*200.);}catch(const std::exception&){}
    return surface_hit;
}
void ZombiePeas::plant_damage(const PlantRef& p,double amount) {
    p->hurt.set(1.);double hp=number(p->hp);static const std::string no_hand;hp-=world_.protection.amount({hp,no_hand,p->source,p->protection},amount);p->hp.set(hp);
    if(hp<=0.)try{callbacks_.clear_plant(p->cell);}catch(const std::exception&){}
}
void ZombiePeas::torch_check(const EntityRef& e) {
    if(torches_){torches_->zombie_pea(e);return;}
    if(!world_.zombie_peas.pvp_active||!text(e->source.zombie_fire).empty())return;const double scale=world_.runtime.tile;if(scale<=0.)return;
    const auto point=xy(e);const double previous=number(e->pea.previous_x,point.x),lo=std::min(previous,point.x)-scale*.75,hi=std::max(previous,point.x)+scale*.75;
    const auto plants=*world_.plant_roster;
    for(const auto& p:plants)try{if(p->kind!="火炬树桩"||!live(p))continue;const auto q=patch_plant_point(world_,*p);if(!q||!(lo<=q->x&&q->x<=hi)||std::abs(point.y-q->y)>scale*1.7)continue;
        const auto& secrets=world_.heroes.globals.secrets;const bool blue=secrets.present()&&!secrets.is_null()&&secrets.get()&&std::find(secrets.get()->begin(),secrets.get()->end(),"蓝火")!=secrets.get()->end();e->source.zombie_fire.set(blue?"blue":"fire");return;
    }catch(const std::exception&){}
}
void ZombiePeas::splash(const EntityRef& e,Point impact,const PlantRef& direct_plant,std::optional<CombatTarget> direct_zombie,bool direct_player,const LegacyView* view) {
    struct SplashScope {
        Field<bool>* marker;
        explicit SplashScope(Field<bool>* value):marker(value){if(marker)marker->set(true);}
        ~SplashScope(){if(marker)marker->erase();}
    } scope(torches_?&e->source.melon_splash:nullptr);
    if(!world_.zombie_peas.pvp_active||text(e->source.zombie_fire).empty())return;const double mult=fire_multiplier(e),scale=world_.runtime.tile;if(scale<=0.)return;
    const double left=impact.x-scale*1.3,right=impact.x+scale*1.3,top=impact.y-scale*2.7,bottom=impact.y+scale;
    const auto in_range=[&](Point p){return left<=p.x&&p.x<=right&&top<p.y&&p.y<bottom;};
    const auto plants=*(view?view->plants:world_.plant_roster);
    for(const auto& p:plants)try{if(p==direct_plant||!live(p)||p->kind=="火炬树桩")continue;const auto point=patch_plant_point(world_,*p);if(point&&in_range(*point))plant_damage(p,2.*mult/3.);}catch(const std::exception&){}
    const auto targets=*(view?view->targets:world_.targets);
    for(size_t i=0;i<targets.size();++i)try{const auto t=targets[i];if((direct_zombie&&t==*direct_zombie)||t.is_hero()||!charmed(t)||t.unit->body.ash.present()||t.unit->body.hp<=0.)continue;
        if(in_range(aim_.zombie_point(t)))callbacks_.ordinary_damage(i,e->facing,20.*mult/3.);
    }catch(const std::exception&){}
    const auto& player=world_.heroes.globals.position;
    if(!direct_player&&!view&&player.present()&&!player.is_null()&&in_range({player.get()->x,player.get()->y-scale}))try{callbacks_.player_damage(2.);}catch(const std::exception&){}
}
void ZombiePeas::fire_splash(const EntityRef& e,Point p,const PlantRef& direct_plant,std::optional<CombatTarget> direct_zombie,bool direct_player){splash(e,p,direct_plant,direct_zombie,direct_player,nullptr);}
bool ZombiePeas::hit_charmed(const EntityRef& e,Point start,Point end,double scale,const LegacyView* view) {
    const auto targets=*(view?view->targets:world_.targets);
    for(size_t i=0;i<targets.size();++i)try{const auto t=targets[i];if(!charmed(t)||t.unit->body.ash.present()||t.unit->body.hp<=0.)continue;
        if(e->native_source_zombie.present()&&!e->native_source_zombie.is_null()&&e->native_source_zombie.get()==identity(t))continue;
        const auto center=aim_.zombie_point(t);const auto head=plant_zombie_head(*t.unit,scale,catalog_);const double size=std::max(.35,number(t.unit->body.size,1.));
        if(!segment_hits(start,end,center,head?Point{head->rx,head->ry}:Point{scale*.45*size,scale*.70*size}))continue;
        damage_charmed(i,t,e,e->facing);splash(e,end,{},t,false,view);splat(end);return true;
    }catch(const std::exception&){}return false;
}
bool ZombiePeas::raw_hit(const EntityRef& e) {
    std::optional<LegacyView> retained;if(i_zombie())retained=LegacyView{world_.targets,world_.plant_roster};const auto* view=retained?&*retained:nullptr;
    const double scale=world_.runtime.tile;const auto end=xy(e);const Point start{number(e->pea.previous_x,e->pea.previous_x.present()?end.x:number(e->pea.x,end.x)),number(e->pea.previous_y,e->pea.previous_y.present()?end.y:number(e->pea.y,end.y))};
    const auto plants=*(view?view->plants:world_.plant_roster);
    for(const auto& p:plants)try{if(!live(p)||p->kind=="火炬树桩")continue;const auto center=patch_plant_point(world_,*p);if(!center||!segment_hits(start,end,*center,{scale*.55,scale*.65}))continue;
        if(p->kind=="地刺"||p->kind=="地刺王"){splat(end);return true;}plant_damage(p,2.*fire_multiplier(e));splash(e,end,p,{},false,view);splat(end);return true;
    }catch(const std::exception&){}
    if(hit_charmed(e,start,end,scale,view))return true;const auto& player=world_.heroes.globals.position;
    if(!view&&player.present()&&!player.is_null()&&segment_hits(start,end,{player.get()->x,player.get()->y-scale},{scale*.40,scale*.80})){damage_player(e->facing);splash(e,end,{},std::nullopt,true,view);splat(end);return true;}return false;
}
bool ZombiePeas::hit(const EntityRef& e){PeaShellScope shells(world_);SourcedContext scope(world_,source_ref(e),CombatPhase::entities);const auto result=raw_hit(e);scope.finish();return result;}
bool ZombiePeas::raw_update_one(const EntityRef& e,double scale,double width,double height) {
    auto& p=e->motion.get();auto& pea=e->pea;const double old_x=number(pea.x,p.x),old_y=number(pea.y,p.y);
    if(!truth(pea.native_move)){p.x+=number(pea.vx);p.y+=number(pea.vy);p.vx=0.;p.vy=0.;}
    pea.previous_x.set(old_x);pea.previous_y.set(old_y);pea.x.set(p.x);pea.y.set(p.y);pea.age.set(std::trunc(number(pea.age))+1.);torch_check(e);if(hit(e))return false;
    if(truth(pea.native_move))return true;if(pea.age.get()>4000.||pea.x.get()<-scale*2.||pea.x.get()>width+scale*2.||pea.y.get()<-scale*2.||pea.y.get()>height+scale*2.)return false;return true;
}
bool ZombiePeas::update_one(const EntityRef& e,double scale,double width,double height){SourcedContext scope(world_,source_ref(e),CombatPhase::entities);const auto result=raw_update_one(e,scale,width,height);scope.finish();return result;}
void ZombiePeas::update_all() {
    const auto entities=world_.runtime.entities.list();const double scale=world_.runtime.tile,width=number(world_.world_width,20.*scale),height=number(world_.world_height,12.*scale);
    const auto captured=*entities;EntityRoster kept;kept.reserve(captured.size());bool changed=false;
    for(const auto& e:captured)try{if(is_pea(e)){e->pea.zombie_pea.set(true);e->pea.native_move.set(true);if(update_one(e,scale,width,height))kept.push_back(e);else changed=true;}else kept.push_back(e);}catch(const std::exception&){changed=true;}
    if(changed){*entities=std::move(kept);if(world_.runtime.entities.list()==entities)world_.runtime.entities.replace(entities);}
    if(world_.zombie_peas.legacy->empty())return;const auto legacy=*world_.zombie_peas.legacy;kept.clear();kept.reserve(legacy.size());
    for(const auto& e:legacy)try{if(update_one(e,scale,width,height))kept.push_back(e);}catch(const std::exception&){}
    *world_.zombie_peas.legacy=std::move(kept);
}
std::optional<bool> ZombiePeas::shotgun_volley(const std::optional<CombatTarget>& source) {
    if(!source||source->is_hero()||!world_.zombie_peas.secret_system_enabled||!world_.zombie_peas.shotgun)return {};
    const auto u=source->unit;if(text(u->protection.card)!="zombie:机枪僵尸"||world_.heroes.owner(source_ref(u))!=Seat::zombie)return {};
    auto& last=u->patch.shotgun_volley;if(last.present()&&!last.is_null()&&world_.heroes.tick-last.get()<200.)return false;last.set(double(world_.heroes.tick));return true;
}
bool ZombiePeas::raw_spawn(Point center,double angle,bool friendly,std::optional<CombatTarget> source) {
    callbacks_.ensure_plant_zombie_assets();auto& images=world_.runtime.other_images;const std::string name=friendly?"豌豆":"僵尸豌豆";if(std::find(images.begin(),images.end(),name)==images.end())images.push_back(name);
    const double scale=world_.runtime.tile,speed=std::max(1.,200.*world_.runtime.plk),radians=angle*(pi/180.),vx=std::cos(radians)*speed,vy=std::sin(radians)*speed;
    const Point start{center.x+std::cos(radians)*scale*.30,center.y+std::sin(radians)*scale*.30};const auto entities=world_.runtime.entities.list();const auto before=entities->size();
    try{callbacks_.add_entity(name,vx>=0.?1.:-1.,{start.x,start.y,vx,vy});if(entities->size()<=before)return false;const auto e=entities->back();e->facing=vx>=0.?1.:-1.;e->motion=Motion{start.x,start.y,vx,vy};auto& pea=e->pea;
        pea.x.set(start.x);pea.y.set(start.y);pea.previous_x.set(start.x);pea.previous_y.set(start.y);pea.vx.set(vx);pea.vy.set(vy);pea.age.set(0.);
        if(friendly){pea.charmed_pea.set(true);if(source)e->native_source_zombie.set(identity(*source));}else{pea.zombie_pea.set(true);pea.native_move.set(true);}++shots;return true;
    }catch(const std::exception&){return false;}
}
bool ZombiePeas::sourced_spawn(Point p,double a,bool friendly,std::optional<CombatTarget> source){SourcedContext scope(world_,source?source_ref_for(*source):nullptr,CombatPhase::zombies,SourcedCall::spawn);const bool result=raw_spawn(p,a,friendly,source);scope.finish();return result;}
bool ZombiePeas::spawn(Point p,double a,bool friendly,std::optional<CombatTarget> source) {
    const auto mode=friendly?std::optional<bool>{}:shotgun_volley(source);if(!mode)return sourced_spawn(p,a,friendly,source);if(!*mode)return true;
    bool fired=false;for(const auto offset:{-30.,-18.,-6.,6.,18.,30.})fired=sourced_spawn(p,a+offset,friendly,source)||fired;return fired;
}
bool ZombiePeas::hero_pea(Seat seat,std::span<const Seat> enemies,double width) {
    auto& hero=world_.heroes.hero(seat);if(hero.frame.hp.or_missing(0.)<=0.)return false;const auto position=hero.frame.position.get();const double x=position->x,y=position->y,tile=world_.runtime.tile,facing=hero.frame.facing.or_missing(1.)>=0.?1.:-1.,head_y=y-tile*1.6;
    std::optional<Point> best;double best_distance=0.;auto consider=[&](Point p){const double dx=wrap_delta(x,p.x,width),dy=p.y-head_y;if(!(0.<dx*facing&&dx*facing<=8.*tile&&std::abs(dy)<tile*1.6))return;const double d=std::hypot(dx,dy);if(!best||d<best_distance){best=p;best_distance=d;}};
    for(const auto& p:*world_.plant_roster)if(p->hp.or_missing(0.)>0.&&world_.heroes.owner(source_ref(p))==Seat::plant)consider({(p->cell.x+.5)*tile,(p->cell.y+.5)*tile});
    for(const auto side:enemies){const auto& h=world_.heroes.hero(side).frame;const auto point=h.position.get();if(h.hp.or_missing(0.)>0.)consider({point->x,point->y-tile});}
    if(!best)return false;const double angle=std::atan2(best->y-head_y,wrap_delta(x,best->x,width))*(180./pi);hero.pea_angle.set(angle);world_.heroes.proxy(seat);const auto proxy=CombatTarget::player(seat);const auto source=source_ref_for(proxy);const auto before=world_.runtime.entities.list()->size();
    {HeroContext scope(world_.heroes,{Seat::plant,Seat::zombie,CombatPhase::entities,source,{}});spawn({x+facing*tile*.2,head_y},angle,false,proxy);const auto entities=world_.runtime.entities.list();
        for(size_t i=before;i<entities->size();++i){const auto e=entities->at(i);world_.heroes.tag_entity(source_ref(e),&e->motion.get(),e->flight,Seat::zombie,source);e->source.seat=seat;}scope.close();}
    world_.runtime.events.emplace_back(ZombieHeroPeaEvent{seat});return true;
}
} // namespace pvz::typed72
