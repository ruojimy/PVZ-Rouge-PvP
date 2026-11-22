#include "sim/typed/terraria_bosses.h"
#include "sim/typed/attention.h"
#include "sim/typed/pvp75_content.h"
#include <algorithm>
#include "sim/typed/projectile_rules.h"
#include <cmath>
#include <cstdlib>
#include <string>
#include <limits>
namespace pvz::typed72 {
namespace {
constexpr double pi=3.14159265358979323846;
const TerrariaDefinition definitions[]={
 {4,"克苏鲁之眼",2800,15,12,100,110,110,166,6},
 {5,"克苏鲁之仆",8,12,0,20,20,20,32,2},
 {13,"世界吞噬者",150,22,2,38,38,46,90,1},
 {14,"世界吞噬者体节",150,13,4,38,38,46,90,1},
 {15,"世界吞噬者尾节",150,11,8,38,38,46,90,1},
 {35,"骷髅王",4400,32,10,80,102,114,132,2},
 {36,"骷髅王之手",600,20,14,52,52,58,78,2}};
struct GoreSize {int id,w,h;};
constexpr GoreSize gore_sizes[]={{2,16,22},{6,20,14},{7,20,24},{8,46,32},{9,48,52},{10,52,80},{24,46,54},{25,44,38},{26,26,56},{27,26,52},{28,28,36},{29,36,60},{54,80,76},{55,54,38},{56,44,76},{57,10,38}};
double sign(double x){return x<0.?-1.:1.;}
Point aim(Point d,double speed){const auto n=std::hypot(d.x,d.y);return n>1e-9?Point{d.x*speed/n,d.y*speed/n}:Point{};}
void accelerate(double& v,double target,double a,bool doubled=true){if(v<target){v+=a;if(doubled&&v<0.&&target>0.)v+=a;}else if(v>target){v-=a;if(doubled&&v>0.&&target<0.)v-=a;}}
void seek(TerrariaNpcState& n,Point d,double speed,double acceleration,bool doubled=true){const auto v=aim(d,speed);accelerate(n.vx,v.x,acceleration,doubled);accelerate(n.vy,v.y,acceleration,doubled);}
void assign_velocity(TerrariaNpcState& n,Point d,double speed){const auto v=aim(d,speed);n.vx=v.x;n.vy=v.y;}
bool alive(const ZombieRef& u){return u&&u->body.hp>0.&&u->terraria&&!u->terraria->removed;}
void drift(double& v,double distance,double acceleration,double limit){if(distance<0.){if(v>0.)v*=.96;v-=acceleration;if(v>limit)v=limit;}else if(distance>0.){if(v<0.)v*=.96;v+=acceleration;if(v< -limit)v=-limit;}}
}
const TerrariaDefinition& terraria_definition(int type){for(const auto& d:definitions)if(d.type==type)return d;throw std::invalid_argument("unknown Terraria NPC");}
int terraria_type(std::string_view key){for(const auto& d:definitions)if(key==std::string("zombie:")+d.name)return d.type;return 0;}
bool terraria_summon(int type){return type==4||type==13||type==35;}
const ColdCatalogData& terraria_catalog(){
 static const auto data=[](){auto d=compiled_cold_catalog();const auto found=std::find_if(d.cards.begin(),d.cards.end(),[](const auto& c){return c.id=="zombie:普通僵尸";});if(found==d.cards.end())throw std::logic_error("missing zombie template");const auto base=*found;
  for(const auto& npc:definitions){
   // PvP75: zombie:克苏鲁之仆 is a real card in the compiled catalog; keep that record.
   if(std::any_of(d.cards.begin(),d.cards.end(),[&](const auto& card){return card.id==std::string("zombie:")+npc.name;}))continue;
   auto c=base;c.id=c.base_id=c.resolved_id=std::string("zombie:")+npc.name;c.name=npc.name;c.family=npc.name;c.asset="terraria/NPC_"+std::to_string(npc.type)+".png";c.native_source=npc.name;c.behavior="terraria";c.hp.set(npc.hp);c.defense.set(npc.defense);c.attention_hits.set(npc.type>=13&&npc.type<=15?1.:3.);c.attention_seconds.set(npc.type>=13&&npc.type<=15?10.:6.);c.damage=npc.damage;c.cost=0.;c.cooldown=0.;c.producer=false;c.selectable=terraria_summon(npc.type);c.spawn_only.set(!c.selectable);c.pvp_regular_unit.set(true);c.height.set(npc.height*3.);c.description="仅本地测试模式 · 泰拉瑞亚普通模式";d.cards.push_back(std::move(c));}
  return d;}();return data;
}
Point TerrariaBosses::center(const ZombieRef& u)const{const auto& m=u->body.motion.get();return {m.x,m.y-world_.runtime.tile};}
void TerrariaBosses::sound(const ZombieRef& u,const char* name){const auto c=center(u);world_.runtime.sound(std::string("terraria_")+name,{c.x,c.y,0.,0.});}
void TerrariaBosses::feedback(const ZombieRef& u,double damage,bool death,bool transform){
 const auto& n=*u->terraria;auto c=center(u);const Point top{c.x-n.width*scale()/2.,c.y-n.height*scale()/2.};
 // Cosmetic randomness has its own deterministic stream. It never samples the
 // combat RNG or contributes a collision entity.
 auto random=[&](){uint64_t x=(++visual_serial_)*0x9e3779b97f4a7c15ull;x=(x^(x>>30))*0xbf58476d1ce4e5b9ull;x=(x^(x>>27))*0x94d049bb133111ebull;return double((x^(x>>31))>>11)*0x1p-53;};
 const int dust=transform?20:death?(n.type==5?20:(n.type>=13&&n.type<=15)?50:150):std::min(150,int(std::ceil(damage/u->max_hp.or_missing(150.)*(n.type==5?50.:100.))));
 const Color color=n.type>=35?Color{203,198,177,255}:n.type>=13?Color{135,90,144,255}:Color{146,24,31,255};
 for(int i=0;i<dust&&debris_.size()<4096;++i)debris_.push_back({0,0,{top.x+random()*n.width*scale(),top.y+random()*n.height*scale()},{(random()*4.-2.)*scale(),(random()*2.-3.)*scale()},0.,color});
 std::vector<int> sprites;
 if(transform)sprites={8,7,6,8,7,6};
 else if(death){if(n.type==4){sprites={2,7,9,10,2,7,9,10};sound(u,"Roar_0");}else if(n.type==5)sprites={6,7};else if(n.type>=13&&n.type<=15){int first=24+(n.type-13)*2;sprites={first,first+1};}else if(n.type==35)sprites={54,55};else if(n.type==36)sprites={56,57,57,57};}
 for(int sprite:sprites)if(debris_.size()<4096){Point v{n.vx*scale(),n.vy*scale()};if(transform||n.type==4)v={(random()*12.-6.)*scale(),(random()*12.-6.)*scale()};debris_.push_back({sprite,0,top,v,0.,{255,255,255,255}});}
}
void TerrariaBosses::advance_debris(){
 for(auto& d:debris_){++d.age;d.velocity.y+=(d.sprite?.2:.1)*scale();d.rotation+=d.velocity.x/scale()*.05;auto next=Point{d.point.x+d.velocity.x,d.point.y+d.velocity.y};
  const int row=int(std::floor(next.y/world_.runtime.tile)),col=int(std::floor(next.x/world_.runtime.tile));
  if(row>=0&&row<world_.terrain.rows()&&!world_.terrain.empty(row,col)&&d.velocity.y>0.){next.y=row*world_.runtime.tile-1.;d.velocity.y=0.;d.velocity.x*=.97;}
  d.point=next;
 }
 std::erase_if(debris_,[](const auto& d){return d.age>(d.sprite?855:90);});
}
void TerrariaBosses::draw_debris(NativeCanvas& c){
 NativeFrameScope source(c.frames);NativeFrameTransientScope transient(c.frames);
 for(const auto& d:debris_){if(c.frames.skip_transient())break;if(!d.sprite){auto color=d.color;color[3]=uint8_t(std::clamp((90-d.age)*6,0,255));c.frames.primitive({"rect",color,d.point.x,d.point.y,2.*scale(),2.*scale(),0});continue;}
  auto& art=sheets_[1000+d.sprite];if(!art)for(const auto& size:gore_sizes)if(size.id==d.sprite){art=std::make_shared<NativeArtImage>();art->width=size.w;art->height=size.h;auto recipe=std::make_shared<NativeArtRecipe>();recipe->key="world:terraria/Gore_"+std::to_string(d.sprite);art->recipe=recipe;break;}
  if(!art)continue;auto scaled=c.resize(art,art->width*scale(),art->height*scale());NativeCanvas::set_alpha(scaled,255.-std::max(0,d.age-600));c.rotated(scaled,d.point,d.rotation*180./pi);
 }
}
Point TerrariaBosses::delta(Point a,Point b)const{return {wrap_delta(a.x,b.x,world_.world_width.get())/scale(),(b.y-a.y)/scale()};}
std::string TerrariaBosses::id(const ContentTarget& t)const{if(const auto* p=std::get_if<PlantRef>(&t))return (*p)->source.id.or_missing("p"+std::to_string((*p)->identity.value));const auto& z=std::get<CombatTarget>(t);return z.is_hero()?std::string("hero:")+std::string(seat_name(z.hero)):z.unit->source.id.or_missing("z"+std::to_string(z.unit->identity.value));}
bool TerrariaBosses::live_enemy(const ContentTarget& t)const{
 if(const auto* p=std::get_if<PlantRef>(&t))return (*p)->hp.or_missing(0.)>0.&&!(*p)->dead.present()&&world_.heroes.owner(source_ref(*p))==Seat::plant;
 const auto& z=std::get<CombatTarget>(t);
 if(z.is_hero())return world_.heroes.contains(z.hero)&&world_.heroes.hero(z.hero).frame.hp.get()>0.;
 return z.unit&&z.unit->body.hp>0.&&world_.heroes.owner(source_ref(z.unit))==Seat::plant;
}
std::vector<ContentTarget> TerrariaBosses::enemies()const{
 // PvP76: inside one AI frame the roster is listed once; each use re-checks the same
 // liveness/allegiance conditions, so the result equals a fresh listing (no plant or
 // plant-side unit is created during the frame). A 67-part worm used to list it ~134 times.
 if(enemy_cache_){std::vector<ContentTarget> out;out.reserve(enemy_cache_->size());for(const auto& t:*enemy_cache_)if(live_enemy(t))out.push_back(t);return out;}
 std::vector<ContentTarget> out;for(const auto& p:*world_.plant_roster)if(p->hp.or_missing(0.)>0.&&!p->dead.present()&&world_.heroes.owner(source_ref(p))==Seat::plant)out.emplace_back(p);
 for(const auto& t:*world_.targets)if(t.unit&&t.unit->body.hp>0.&&world_.heroes.owner(source_ref(t.unit))==Seat::plant)out.emplace_back(t);
 for(const auto seat:seats_for(world_.mode))if(team_of(seat)==Seat::plant&&world_.heroes.contains(seat)&&world_.heroes.hero(seat).frame.hp.get()>0.)out.emplace_back(CombatTarget::player(seat));return out;
}
std::optional<ContentTarget> TerrariaBosses::target(const ZombieRef& u,bool closest){auto owner=attention_owner(u);if(owner!=u){auto result=target(owner,closest);u->terraria->target_id=owner->terraria->target_id;return result;}auto list=enemies();attention_prefer(owner,list,world_.heroes.time);auto& n=*u->terraria;if(!closest)for(const auto& t:list)if(id(t)==n.target_id)return t;std::optional<ContentTarget> result;double best=std::numeric_limits<double>::infinity();for(const auto& t:list){auto d=delta(center(u),hits_.point(t));double dist=std::abs(d.x)+std::abs(d.y); // Terraria NPC.TryTrackingTarget (without player aggro equipment).
if(dist<best){best=dist;result=t;}}n.target_id=result?id(*result):"";if(result&&n.type==35)u->body.facing=sign(delta(center(u),hits_.point(*result)).x);return result;}
ZombieRef TerrariaBosses::summon(int type,Point c){if((!world_.local_test_mode&&!world_.scripted_terraria_boss)||!terraria_summon(type))return {};auto root=factory_(type,c,{});if(!root)return {};
 if(type==13){auto previous=root;for(int i=1;i<67;++i){auto part=factory_(i==66?15:14,{c.x,c.y+i*.01*scale()},root);if(!part)break;previous->terraria->behind=part;part->terraria->ahead=previous;previous=part;}}
 if(type==35)root->terraria->ai[0]=1.;
 if(type==35)for(int side:{-1,1}){auto part=factory_(36,c,root);if(part){part->terraria->parent=root;part->terraria->ai[0]=side;if(side==1)part->terraria->ai[3]=150.;}}
 return root;
}
ZombieRef TerrariaBosses::summon_servant(Point c,double facing){
 auto unit=factory_(5,c,{});if(!unit)return {};
 unit->terraria->vx=(facing<0.?-1.:1.)*2.5;unit->body.facing=facing<0.?-1.:1.;return unit;
}
void TerrariaBosses::advance(){
 // PvP75 servants run in every mode; Bosses still need the test mode or the scripted days.
 if(!world_.local_test_mode&&!world_.scripted_terraria_boss&&std::none_of(world_.targets->begin(),world_.targets->end(),[](const CombatTarget& t){return t.unit&&t.unit->terraria;}))return;
 // PvZ status durations remain on the production 250 Hz clock.
 for(const auto& t:*world_.targets)if(t.unit&&t.unit->terraria){auto& b=t.unit->body;
  if(t.unit->terraria->type!=5)pvp75::convert_boss_control(*t.unit); // PvP75: Bosses are slowed, never held
  if(b.hurt>0.&&++b.hurt>=50.)b.hurt=0.;
  for(auto* status:{&b.ice,&b.butter,&b.stun})if(status->present()&&!status->is_null()&&status->get()>0.)status->get()-=1.;
 }
 accumulator_+=60;if(accumulator_<250)return;accumulator_-=250;++frames_;
 for(const auto seat:seats_for(world_.mode))if(world_.heroes.contains(seat))world_.heroes.proxy(seat);
 advance_debris();enemy_cache_.reset();
 // PVP76_TERRARIA_CACHE=0 (diagnostic A/B only) lists the roster at every use as before.
 {const char* v=std::getenv("PVP76_TERRARIA_CACHE");if(!(v&&std::string(v)=="0"))enemy_cache_=enemies();}struct ClearCache{std::optional<std::vector<ContentTarget>>& c;~ClearCache(){c.reset();}} clear_cache{enemy_cache_};
 auto units=*world_.targets;for(const auto& t:units)if(t.unit&&t.unit->terraria&&t.unit->body.hp>0.){
  const auto& u=t.unit;auto [last,first]=observed_hp_.try_emplace(u->identity.value,u->body.hp);
  if(!first&&u->body.hp<last->second){sound(u,u->terraria->type>=35?"NPC_Hit_2":"NPC_Hit_1");feedback(u,last->second-u->body.hp);}last->second=u->body.hp;
  if(u->terraria->type==5)absorb_wind(u);step(u);if(u->terraria->type==5)publish_wind(u);
 }reap();
 std::erase_if(contact_until_,[&](const auto& item){return item.second<frames_-60;});
}
// PvP76 r2: wind pushes (plant blover, 三叶草僵尸) add to the motion velocity between AI
// frames, which the next frame used to overwrite. A servant now carries that change
// into its own velocity, capped like a size-2 flyer (parrot / crow) under the blover.
void TerrariaBosses::absorb_wind(const ZombieRef& u){
 auto& n=*u->terraria;const auto& m=u->body.motion.get();if(!n.wind_ref)return;
 const double dvx=m.vx-n.wind_vx,dvy=m.vy-n.wind_vy;if(std::abs(dvx)<1e-12&&std::abs(dvy)<1e-12)return;
 const double k=250./(60.*scale());n.vx+=dvx*k;n.vy+=dvy*k;
 const double cap=std::max(1.,world_.wind_environment.zombie_speed_max)*36./8.*k;
 if(dvx>0.&&n.vx>cap)n.vx=std::max(cap,n.vx-dvx*k);else if(dvx<0.&&n.vx< -cap)n.vx=std::min(-cap,n.vx-dvx*k);
}
void TerrariaBosses::publish_wind(const ZombieRef& u){
 auto& n=*u->terraria;if(n.removed)return;const auto& m=u->body.motion.get();n.wind_vx=m.vx;n.wind_vy=m.vy;n.wind_ref=true;
}
void TerrariaBosses::step(const ZombieRef& u){auto& n=*u->terraria;u->source.charmed.erase();const Point before=center(u);auto t=target(u,n.type==5);Point d=t?delta(center(u),hits_.point(*t)):Point{0.,500.};
 const auto parent=n.parent.lock();const bool hand_retreat=n.type==36&&alive(parent)&&parent->terraria->ai[1]==3.;
 if(!t&&n.type!=4&&n.type!=35&&n.type!=36){if(--n.despawn<=0){n.removed=true;return;}}else if(t&&!hand_retreat&&!(n.type==4&&world_.placement.day!="黑天")&&!(n.type==35&&n.ai[1]==3.))n.despawn=750;
 const auto& body=u->body;const double ice=body.ice.or_missing(0.);
 if((body.butter.or_missing(0.)>0.||body.stun.or_missing(0.)>0.||ice>1000.)||(ice>0.&&frames_%2==0)){auto& m=u->body.motion.get();m.vx=m.vy=0.;contacts(u);return;}
 if(n.type==4){if(world_.placement.day!="黑天"||!t){n.vy-=.04;bool nearby=false;for(const auto& e:enemies()){auto d=delta(center(u),hits_.point(e));if(std::abs(d.x)<960.+n.width&&std::abs(d.y)<600.+n.height)nearby=true;}if(nearby)n.despawn=750;else if(--n.despawn>10)n.despawn=10;if(n.despawn<=0)n.removed=true;}else eye(u,d);}
 else if(n.type==5){
  // aiStyle 5 rounds both centers to an 8-pixel grid before normalizing.
  // A zero-length delta preserves velocity; dead-target retreat is diagonal up.
  const auto c=center(u);const Point origin{c.x/scale(),c.y/scale()};
  const Point quantized{std::trunc((origin.x+d.x)/8.)*8.-std::trunc(origin.x/8.)*8.,std::trunc((origin.y+d.y)/8.)*8.-std::trunc(origin.y/8.)*8.};
  auto desired=t?(std::hypot(quantized.x,quantized.y)>0.?aim(quantized,5.):Point{n.vx,n.vy}):Point{u->body.facing*2.5,-2.5};
  accelerate(n.vx,desired.x,.03);accelerate(n.vy,desired.y,.03);n.rotation=std::atan2(n.vy,n.vx)-pi/2.;
 }
 else if(n.type==35){if(!t)n.ai[1]=3.;skeleton(u,d);}
 else if(n.type==36)hand(u,d);else worm(u,d);
 if(n.removed)return;auto& m=u->body.motion.get();m.x+=n.vx*scale();m.y+=n.vy*scale();
 const double width=world_.world_width.get();m.x=std::fmod(std::fmod(m.x,width)+width,width);m.vx=n.vx*scale()*60./250.;m.vy=n.vy*scale()*60./250.;if(n.type!=35)u->body.facing=n.vx<0.?-1.:1.;
 if(n.type>=13&&n.type<=15){auto front=n.ahead.lock();if(n.type==13||(alive(front)&&front->terraria->alpha<85.)){auto moved=delta(before,center(u));if(std::hypot(moved.x,moved.y)>2.)n.alpha=std::max(0.,n.alpha-42.);}}
 // The original game's ordinary collision immunity is shared per victim.
 contacts(u);++n.frame_ticks;n.frame=n.type==4?(n.frame_ticks%21)/7:n.type==5?(n.frame_ticks/8)%2:0;
}
void TerrariaBosses::eye(const ZombieRef& u,Point d){auto& n=*u->terraria;auto& a=n.ai;const double desired=std::atan2(d.y+4.,d.x)-pi/2.;
 if(a[0]==1.||a[0]==2.){if(a[0]==1.)a[2]=std::min(.5,a[2]+.005);else a[2]=std::max(0.,a[2]-.005);n.rotation+=a[2];n.vx*=.98;n.vy*=.98;if(std::abs(n.vx)<.1)n.vx=0.;if(std::abs(n.vy)<.1)n.vy=0.;if(++a[1]>=100.){++a[0];a[1]=0.;}if(a[0]==2.&&a[1]==0.){sound(u,"NPC_Hit_1");sound(u,"Roar_0");feedback(u,0.,false,true);}if(a[0]==3.)a={3.,0.,0.,0.};return;}
 const bool second=a[0]==3.;double half=21.;if(auto t=target(u)){auto b=hits_.bounds(*t);half=(b.bottom-b.top)/(2.*scale());}n.damage=second?23.:15.;u->body.defense.set(second?0.:12.);
 double turn=std::remainder(desired-n.rotation,2.*pi);const double rate=a[1]==0.?(second?.05:.02):(a[1]==2.&&a[2]>40.?(second?.08:.05):0.);n.rotation+=std::clamp(turn,-rate,rate);
 if(a[1]==0.){Point hover{d.x,d.y-(second?120.:200.)};seek(n,hover,second?6.:5.,second?.07:.04);if(++a[2]>=(second?200.:600.)){a[1]=1.;a[2]=a[3]=0.;n.target_id.clear();}
  else if(!second&&d.y>55.+half&&std::hypot(hover.x,hover.y)<500.&&++a[3]>=110.){a[3]=0.;n.rotation=desired;auto v=aim(d,5.);auto c=center(u);auto servant=factory_(5,{c.x+v.x*10.*scale(),c.y+v.y*10.*scale()},u);if(servant){servant->terraria->vx=v.x;servant->terraria->vy=v.y;sound(servant,"NPC_Hit_1");}}
 }else if(a[1]==1.){assign_velocity(n,d,second?6.8:6.);n.rotation=desired;a[1]=2.;}
 else if(a[1]==2.){++a[2];if(a[2]>=40.){n.vx*=second?.97:.98;n.vy*=second?.97:.98;if(std::abs(n.vx)<.1)n.vx=0.;if(std::abs(n.vy)<.1)n.vy=0.;}else n.rotation=std::atan2(n.vy,n.vx)-pi/2.;if(a[2]>=(second?130.:150.)){a[2]=0.;if(++a[3]>=3.){a[1]=a[3]=0.;}else a[1]=1.;n.target_id.clear();n.rotation=desired;}}
 if(!second&&u->body.hp<u->max_hp.or_missing(2800.)*.5)a={1.,0.,0.,0.};
}
void TerrariaBosses::skeleton(const ZombieRef& u,Point d){auto& n=*u->terraria;auto& a=n.ai;n.damage=32.;u->body.defense.set(10.);
 if(std::abs(d.x)>2000.||std::abs(d.y)>2000.){auto t=target(u,true);d=t?delta(center(u),hits_.point(*t)):Point{0.,3000.};if(std::abs(d.x)>2000.||std::abs(d.y)>2000.)a[1]=3.;}
 const auto t=target(u);double half=21.;if(t){auto b=hits_.bounds(*t);half=(b.bottom-b.top)/(2.*scale());}const double hover=d.y-199.-half;if(world_.placement.day!="黑天"&&a[1]!=3.&&a[1]!=2.){a[1]=2.;sound(u,"Roar_0");}
 if(a[1]==0.){if(++a[2]>=800.){a[1]=1.;a[2]=0.;target(u,true);sound(u,"Roar_0");}n.rotation=n.vx/15.;
  if(hover<0.){if(n.vy>0.)n.vy*=.98;n.vy-=.02;if(n.vy>2.)n.vy=2.;}else{if(n.vy<0.)n.vy*=.98;n.vy+=.02;if(n.vy< -2.)n.vy=-2.;}
  if(d.x<0.){if(n.vx>0.)n.vx*=.98;n.vx-=.05;if(n.vx>8.)n.vx=8.;}else{if(n.vx<0.)n.vx*=.98;n.vx+=.05;if(n.vx< -8.)n.vx=-8.;}
 }else if(a[1]==1.){u->body.defense.set(0.);if(++a[2]>=400.){a[1]=a[2]=0.;}n.rotation+=u->body.facing*.3;assign_velocity(n,d,1.5);}
 else if(a[1]==2.){n.damage=9999.;u->body.defense.set(9999.);n.rotation+=u->body.facing*.3;assign_velocity(n,d,8.);}
 else{n.vy+=.1;if(n.vy<0.)n.vy*=.95;n.vx*=.95;n.despawn=std::min(n.despawn,50);if(--n.despawn<=0)n.removed=true;}
}
void TerrariaBosses::hand(const ZombieRef& u,Point d){auto& n=*u->terraria;auto p=n.parent.lock();if(!alive(p)){u->body.hp=0.;n.removed=true;return;}auto& a=n.ai;auto tohead=delta(center(u),center(p));const auto state=p->terraria->ai[1];const auto t=target(u);double half=21.;if(t){auto b=hits_.bounds(*t);half=(b.bottom-b.top)/(2.*scale());}
 if(a[2]==0.||a[2]==3.){if(state==3.){n.despawn=std::min(n.despawn,10);if(--n.despawn<=0){n.removed=true;return;}}if(state!=0.){drift(n.vy,tohead.y-125.,.07,6.);drift(n.vx,tohead.x-120.*a[0],.1,8.);}else{if(++a[3]>=300.){++a[2];a[3]=0.;}drift(n.vy,tohead.y+205.,.04,3.);drift(n.vx,tohead.x-200.*a[0],.07,8.);}n.rotation=std::atan2(tohead.y+179.,tohead.x-200.*a[0])+pi/2.;}
 else if(a[2]==1.){n.vx*=.95;n.vy=std::max(-8.,n.vy-.1);n.rotation=std::atan2(tohead.y+179.,tohead.x-200.*a[0])+pi/2.;if(tohead.y>225.){a[2]=2.;auto t=target(u,true);assign_velocity(n,t?delta(center(u),hits_.point(*t)):d,18.);}}
 else if(a[2]==2.){if(d.y<half-26.||n.vx*d.x+n.vy*d.y<=0.||std::hypot(d.x,d.y)>2000.||n.vy<0.)a[2]=3.;}
 else if(a[2]==4.){n.vy*=.95;n.vx=std::clamp(n.vx-.1*a[0],-8.,8.);n.rotation=std::atan2(tohead.y+179.,tohead.x-200.*a[0])+pi/2.;if(std::abs(tohead.x)>500.){a[2]=5.;auto t=target(u,true);assign_velocity(n,t?delta(center(u),hits_.point(*t)):d,17.);}}
 else if(a[2]==5.&&((n.vx>0.&&d.x<0.)||(n.vx<0.&&d.x>0.)||n.vx*d.x+n.vy*d.y<=0.||std::hypot(d.x,d.y)>2000.))a[2]=0.;
}
bool TerrariaBosses::solid(const ZombieRef& u)const{const auto c=center(u);const auto& n=*u->terraria;const double tile=world_.runtime.tile;for(int y=int(std::floor((c.y-n.height*scale()/2.)/tile));y<=int(std::floor((c.y+n.height*scale()/2.)/tile));++y)for(int x=int(std::floor((c.x-n.width*scale()/2.)/tile));x<=int(std::floor((c.x+n.width*scale()/2.)/tile));++x){if(y>=world_.terrain.rows())return true;if(y<0)continue;auto cell=world_.terrain.at(y,world_.terrain.wrap(x));if(cell&&cell->block.present()&&!cell->block.is_null()&&(!world_.terrain.is_empty(cell->block.get())||world_.terrain.water(y,x)))return true;}return false;}
void TerrariaBosses::worm(const ZombieRef& u,Point d){auto& n=*u->terraria;auto a=n.ahead.lock(),b=n.behind.lock();bool head=alive(a),tail=alive(b);
 if(!head&&!tail){n.removed=true;return;}if(n.type==13&&!tail){n.removed=true;return;}if(n.type==15&&!head){n.removed=true;return;}
 if(n.type==14&&(!head||!tail)){
  // NPC.Transform calls SetDefaults, keeps velocity and surviving links, then
  // restores the integer life ratio and immediately chooses the closest target.
  const int next=head?15:13;const auto& def=terraria_definition(next);
  const double hp=std::max(1.,std::floor(u->body.hp*def.hp/u->max_hp.or_missing(150.)));
  const double vx=n.vx,vy=n.vy;n=TerrariaNpcState{};n.type=next;n.vx=vx;n.vy=vy;
  n.width=def.width;n.height=def.height;n.damage=def.damage;n.alpha=255.;
  if(head)n.ahead=a;if(tail)n.behind=b;u->body.hp=hp;u->max_hp.set(def.hp);u->body.kind=def.name;u->body.defense.set(def.defense);u->protection.card.set(std::string("zombie:")+def.name);
  auto selected=target(u,true);if(selected)d=delta(center(u),hits_.point(*selected));
 }
 if(n.type!=13&&alive(a)){auto v=delta(center(u),center(a));double distance=std::hypot(v.x,v.y);n.rotation=std::atan2(v.y,v.x)+pi/2.;if(distance>1e-8){auto& m=u->body.motion.get();m.x+=v.x*(distance-38.)/distance*scale();m.y+=v.y*(distance-38.)/distance*scale();}n.vx=n.vy=0.;return;}
 const auto c=center(u);Point origin{c.x/scale(),c.y/scale()};d={std::trunc((origin.x+d.x)/16.)*16.-std::trunc(origin.x/16.)*16.,std::trunc((origin.y+d.y)/16.)*16.-std::trunc(origin.y/16.)*16.};
 n.burrowing=solid(u);if(!n.burrowing){bool near=false;for(const auto& t:enemies()){auto dd=delta(center(u),hits_.point(t));if(std::abs(dd.x)<1019.&&std::abs(dd.y)<1019.)near=true;}n.burrowing=!near;}if(!n.burrowing){target(u,true);n.vy=std::min(10.,n.vy+.11);if(std::abs(n.vx)+std::abs(n.vy)<4.)n.vx+=sign(n.vx)*.077;else if(n.vy==10.)accelerate(n.vx,d.x,.07,false);else if(n.vy>4.)n.vx-=sign(n.vx)*.063;}
 else{if(dig_until_[u->identity.value]<=frames_){sound(u,"eow_dig");dig_until_[u->identity.value]=frames_+int(std::clamp(std::hypot(d.x,d.y)/40.,10.,20.));}auto v=aim(d,10.);if(n.vx*v.x>0.||n.vy*v.y>0.){accelerate(n.vx,v.x,.07,false);accelerate(n.vy,v.y,.07,false);if(std::abs(v.y)<2.&&n.vx*v.x<0.)n.vy+=sign(n.vy)*.14;if(std::abs(v.x)<2.&&n.vy*v.y<0.)n.vx+=sign(n.vx)*.14;}else if(std::abs(d.x)>std::abs(d.y)){accelerate(n.vx,v.x,.077,false);if(std::abs(n.vx)+std::abs(n.vy)<5.)n.vy+=sign(n.vy)*.07;}else{accelerate(n.vy,v.y,.077,false);if(std::abs(n.vx)+std::abs(n.vy)<5.)n.vx+=sign(n.vx)*.07;}}
 n.rotation=std::atan2(n.vy,n.vx)+pi/2.;
}
void TerrariaBosses::contacts(const ZombieRef& u){auto& n=*u->terraria;for(const auto& t:enemies()){auto d=delta(center(u),hits_.point(t));auto b=hits_.bounds(t);if(std::abs(d.x)>n.width/2.+(b.right-b.left)/scale()/2.||std::abs(d.y)>n.height/2.+(b.bottom-b.top)/scale()/2.)continue;const auto key=id(t);if(contact_until_[key]>frames_)continue;contact_until_[key]=frames_+40;const auto* z=std::get_if<CombatTarget>(&t);hits_.damage(source_ref(u),t,n.damage*(z&&!z->is_hero()?1.:.1),sign(d.x));}}
void TerrariaBosses::reap(){for(size_t i=world_.targets->size();i-->0;){auto u=world_.targets->at(i).unit;if(u&&u->terraria&&(u->body.hp<=0.||u->terraria->removed||u->body.ash.present())){if(u->body.hp<=0.||u->body.ash.present()){sound(u,u->terraria->type>=35?"NPC_Killed_2":"NPC_Killed_1");feedback(u,0.,true);}observed_hp_.erase(u->identity.value);dig_until_.erase(u->identity.value);u->terraria->removed=true;if(u->source.id.present())world_.native_objects.erase(u->source.id.get());world_.erase_mobile_at(i);}}}
void TerrariaBosses::draw(NativeCanvas& c){if(!c.drawing())return;for(const auto& t:*world_.targets){auto u=t.unit;if(!u||!u->terraria||u->terraria->removed||u->body.hp<=0.)continue;auto& n=*u->terraria;const auto& d=terraria_definition(n.type);auto& sheet=sheets_[n.type];if(!sheet){sheet=std::make_shared<NativeArtImage>();sheet->width=d.sprite_width;sheet->height=d.sprite_height*d.frames;auto recipe=std::make_shared<NativeArtRecipe>();recipe->key="world:terraria/NPC_"+std::to_string(n.type);sheet->recipe=recipe;}
  int frame=n.frame;if(n.type==4)frame=n.frame%3+(n.ai[0]>=2.?3:0);if(n.type==35||n.type==36)frame=0;
  const auto draw_start=c.frames.size();
  auto art=c.crop(sheet,0.,double(frame*d.sprite_height),d.sprite_width,d.sprite_height);art=c.resize(art,d.sprite_width*scale(),d.sprite_height*scale());auto p=center(u);NativeFrameScope owner(c.frames,{u->source.id.get(),{p.x,p.y}});
  if(n.type==36){if(auto parent=n.parent.lock();alive(parent)){auto pc=center(parent);pc.x=p.x+wrap_delta(p.x,pc.x,world_.world_width.get());auto& bone=sheets_[1000];if(!bone){bone=std::make_shared<NativeArtImage>();bone->width=26;bone->height=98;auto recipe=std::make_shared<NativeArtRecipe>();recipe->key="world:terraria/Arm_Bone";bone->recipe=recipe;}auto boneArt=c.resize(bone,26.*scale(),98.*scale());Point joint{p.x-5.*n.ai[0]*scale(),p.y-6.*scale()};for(int j=0;j<2;++j){Point d{(pc.x-joint.x)/scale()-(j?50.:200.)*n.ai[0],(pc.y-joint.y)/scale()+(j?80.:130.)};auto v=aim(d,j?60.:92.);joint.x+=v.x*scale();joint.y+=v.y*scale();c.rotated(boneArt,{joint.x-boneArt->width/2.,joint.y-boneArt->height/2.},(std::atan2(d.y,d.x)-pi/2.)*180./pi);if(!j){joint.x+=v.x*scale()/2.;joint.y+=v.y*scale()/2.;}}}if(n.ai[0]>0.)art=NativeArtStore::flip(art,true,false);}
  // Subtle PvZ palette adaptation remains a display recipe, never collision pixels.
  c.fill(art,{244,255,238,255},nullptr,8);if(u->body.hurt>0.)c.fill(art,{70,70,70,0},nullptr,6);if(u->body.ice.or_missing(0.)>0.)c.fill(art,{170,205,255,255},nullptr,8);NativeCanvas::set_alpha(art,255.-n.alpha);
  // PvP76: worm parts are drawn at 3-degree steps (display only; motion and hits keep the exact angle)
  // so the 67 parts reuse cached rotated images instead of rotating pixels every frame.
  double degrees=n.rotation*180./pi;if(n.type>=13&&n.type<=15)degrees=std::round(degrees/3.)*3.;
  c.rotated(art,{p.x-art->width/2.,p.y-art->height/2.},degrees);
  if(n.type>=13&&n.type<=15)c.frames.tag_layer(draw_start,"below_ground");
 }draw_debris(c);}
}
