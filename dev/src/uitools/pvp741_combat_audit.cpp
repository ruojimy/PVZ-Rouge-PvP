#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "core/render_cache.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_adaptive_pacing.h"
#include "ui/hand/pressure_pacing.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "ui/hand/texture74_internal.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_replay.h"
#include "ui/gen/pm_performance.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
J json(const V& v){return J::parse(dump(v));}
V value(const J& j){return py::json_loads(V(j.dump()));}
void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
int main(int argc,char**argv){
 if(argc<2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J checks=J::array();int failures=0;auto test=[&](std::string name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception&e){row["passed"]=false;row["error"]=e.what();++failures;}checks.push_back(row);std::cerr<<row.dump()<<std::endl;};
 test("dense_profiler_supports_duel_without_present_attribute",[&]()->J{
  auto h=battle_from_scenario({{"seed",741}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);J sample=json(pm_performance::f_crowd_sample(Args{b}));require(sample["heroes"].size()==2,"duel profiling lost a hero");callm(b,SY("close"),Args{});return {{"heroes",sample["heroes"].size()},{"routing_scope",sample["routing_scope"]}};
 });
 test("render_lru_order_values_and_full_frame_pixels_match",[&]()->J{
  V legacy=py::stdlib_call(V("collections.OrderedDict"),Args{}),fast=native_render_cache();
  for(const auto& cache:{legacy,fast}){for(int i=0;i<20;++i)setitem(cache,V(i),V(i*3));callm(cache,SY("move_to_end"),Args{V(2)});callm(cache,SY("move_to_end"),Args{V(8),V(false)});setitem(cache,V(3),V(99));}
  require(json(callm(legacy,SY("items"),Args{}))==json(callm(fast,SY("items"),Args{})),"cache order/update changed");
  require(json(callm(legacy,SY("popitem"),Args({},{{SY("last"),V(false)}})))==json(callm(fast,SY("popitem"),Args({},{{SY("last"),V(false)}}))),"cache eviction changed");
  V a=pm_native_animation::new_DrawReplay(Args{pg::pygame_module(),V::none()}),b=pm_native_animation::new_DrawReplay(Args{pg::pygame_module(),V::none()});setattr(a,SY("cache"),py::stdlib_call(V("collections.OrderedDict"),Args{}));setattr(a,SY("_local_scaled"),py::stdlib_call(V("collections.OrderedDict"),Args{}));
  V sa=pg::new_surface(320,180,true),sb=pg::new_surface(320,180,true);J commands=J::array();
  for(int i=0;i<520;++i){J base={{"size",{8,8}},{"alpha",nullptr},{"colorkey",nullptr},{"image",{{"op","canvas"},{"size",{8,8}},{"flags",65536},{"depth",32}}}};J image={{"size",{8,8}},{"alpha",220},{"colorkey",nullptr},{"image",{{"op","fill"},{"source",base},{"color",{i%251,(i/251)*100,80,255}},{"rect",nullptr},{"flags",0}}}};commands.push_back({{"op","image"},{"pos",{(i%30)*10,(i/30)*8}},{"surface",image},{"area",i%7?J(nullptr):J{1,1,6,6}},{"flags",0}});}
  for(int round=0;round<3;++round){if(round)std::reverse(commands.begin(),commands.end());V frame=value({{"protocol","native-draw-v1"},{"commands",commands}});for(const auto& screen:{sa,sb})callm(screen,SY("fill"),Args{V::tuple({V(11),V(19),V(27),V(255)})});callm(a,SY("render"),Args{sa,frame,V::none(),V(1.25)});callm(b,SY("render"),Args{sb,frame,V::none(),V(1.25)});require(texture74::pixels(sa)==texture74::pixels(sb),"LRU changed rendered pixels");for(const char* field:{"hits","misses","evictions","cache_bytes"})require(getattr(a,Sym(field))==getattr(b,Sym(field)),std::string("cache counter mismatch: ")+field);}
  require(getattr(b,SY("hits")).num()>0.&&getattr(b,SY("evictions")).num()>0.,"fixture missed hit/eviction paths");return {{"commands_per_frame",520},{"frames",3},{"pixels_identical",true},{"hits",getattr(b,SY("hits")).num()},{"evictions",getattr(b,SY("evictions")).num()}};
 });
 test("pvp_day_night_and_rain_remain_static",[&]()->J{
  J cases=J::array();for(bool night:{false,true})for(const char* weather:{"clear","rain"}){
   auto h=battle_from_scenario({{"seed",741},{"night",night},{"weather",weather},{"durable_heroes",true}});const J before=json(getattr(h.battle,SY("map")))["environment"];
   V b=typed72app::wrap_battle(h.battle);callm(b,SY("step"),Args{V(330)});const J after=json(getattr(b,SY("map")))["environment"];require(before==after,"static PvP environment was rewritten");cases.push_back({{"night",night},{"weather",weather},{"environment_unchanged",true}});callm(b,SY("close"),Args{});
  }return cases;
 });
 test("coop_day_night_day_public_environment",[&]()->J{
  auto h=battle_from_scenario({{"seed",741},{"mode","coop"},{"campaign_deck",true},{"director",{{"day",1},{"seed",741}}},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);J phases=J::array();
  for(double t:{0.,120.01,240.01}){for(int n=0;n<2000&&getattr(b,SY("time")).num()<t;++n){require(!getattr(b,SY("result")).truthy(),"cycle fixture ended early");callm(b,SY("step"),Args{V(8)});}callm(b,SY("step"),Args{});J s=json(callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}})));const bool map_night=s["map"]["environment"]["night"];const bool director_night=s["team"]["daylight"]["night"];phases.push_back({{"time",getattr(b,SY("time")).num()},{"map_night",map_night},{"director_night",director_night}});require(map_night==director_night,"display map and co-op director disagree");}
  callm(b,SY("close"),Args{});require(!phases[0]["map_night"].get<bool>()&&phases[1]["map_night"].get<bool>()&&!phases[2]["map_night"].get<bool>(),"wrong cycle: "+phases.dump());return phases;
 });
 int case_number=0;
 for(const char* kind:{"普通僵尸","海盗鹦鹉","小鬼僵尸","小型史莱姆","中型史莱姆","乌鸦"})test(std::string("cattail_")+kind,[&]()->J{
  auto h=battle_from_scenario({{"seed",741},{"night",true},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
  V p=callm(b,SY("spawn"),Args{V("plant:香蒲"),V("plant"),V(2136.),V(864.),V(1.)});require(!p.is_none(),"plant spawn failed");
  V z=callm(b,SY("spawn"),Args{V(std::string("zombie:")+kind),V("zombie"),V(2280.),V(864.),V(-1.)});require(!z.is_none(),"zombie spawn failed");V zid=rd(z,V("id"));
  callm(b,SY("fixture_place_zombie"),Args{zid,V::list({V(2280.),V(864.)}),V(-1.)});
  V object=rd(getattr(b,SY("_native_objects")),zid);setitem(object,V("出场"),V(500.));setitem(object,V("血量"),V(1000000.));setitem(object,V("黄油"),V(1000000.));
  double hp=1000000.;J trails=J::array();for(int t=0;t<600;++t){callm(b,SY("step"),Args{});if(t%50==0){V g=getattr(b,SY("g"));J entities=json(rd(g,V("实体")));J sample=J::array();for(const auto&e:entities)if(e.value("实体",std::string{})=="尖刺")sample.push_back(e);trails.push_back({{"tick",t},{"needles",sample}});} }
  J state=json(callm(b,SY("snapshot"),Args{}));for(const auto& u:state["units"])if(u["id"]==py_str(zid))hp=u["hp"];
  J final_object=json(rd(getattr(b,SY("_native_objects")),zid));const auto hash=py_str(pm_replay::f_state_hash(Args{b}));callm(b,SY("close"),Args{});
  J evidence={{"damage",1000000.-hp},{"target",final_object},{"trails",trails}};std::ofstream(std::string(argv[1])+".case"+std::to_string(case_number++)+".json",std::ios::binary)<<evidence.dump(2);
  require(hp<1000000.,"homing needles never hit");return {{"damage",1000000.-hp},{"state_hash",hash}};
 });
 test("flat_stroke_batch_has_identical_pixels",[&]()->J{
  J canvas={{"size",{192,128}},{"alpha",nullptr},{"colorkey",nullptr},{"image",{{"op","canvas"},{"size",{192,128}},{"flags",65536},{"depth",32}}}};
  J old=canvas,strokes=J::array();for(int n=0;n<147;++n){J args={{n%255,(n*3)%255,(n*11)%255,255},{n%180,n%120},{(n*7)%190,(n*13)%125},1+n%3};J stroke={{"primitive","line"},{"args",args},{"kwargs",J::object()}};strokes.push_back(stroke);old={{"size",{192,128}},{"alpha",nullptr},{"colorkey",nullptr},{"image",{{"op","draw"},{"source",old},{"primitive","line"},{"args",args},{"kwargs",J::object()}}}};}
  J batch={{"size",{192,128}},{"alpha",nullptr},{"colorkey",nullptr},{"image",{{"op","draw_batch"},{"source",canvas},{"strokes",strokes}}}};
  V replay=pm_native_animation::new_DrawReplay(Args{pg::pygame_module(),V::none()});auto a=texture74::pixels(callm(replay,SY("surface"),Args{value(old)}));auto b=texture74::pixels(callm(replay,SY("surface"),Args{value(batch)}));require(a==b,"flat batch changed drawing pixels");return {{"strokes",147},{"old_bytes",old.dump().size()},{"batch_bytes",batch.dump().size()},{"pixels_identical",true}};
 });
 test("grabber_hero_damage_matches_almanac",[&]()->J{
  auto h=battle_from_scenario({{"seed",741},{"night",true},{"durable_heroes",true}});
  V enemy=rd(getattr(h.battle,SY("avatars")),V("zombie"));setitem(enemy,V("玩家位置"),V::list({V(2280),V(864),V(0),V(0)}));setitem(enemy,V("黄油"),V(1000000.));
  V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);callm(b,SY("spawn"),Args{V("plant:抓人草"),V("plant"),V(2136.),V(864.),V(1.)});
  double damage=0.;for(int n=0;n<180&&!damage;++n){callm(b,SY("step"),Args{});J s=json(callm(b,SY("snapshot"),Args{}));damage=1000000.-s["players"]["zombie"]["hp"].get<double>();}
  callm(b,SY("close"),Args{});require(damage==4.,"user-confirmed rule is 4, actual first tentacle hit="+std::to_string(damage));return {{"first_hero_hit",damage}};
 });
 test("hero_cattail_waits_120_seconds_and_hits_for_two_without_mark_refresh",[&]()->J{
  auto h=battle_from_scenario({{"seed",741},{"night",true},{"durable_heroes",true}});
  for(const auto* side:{"plant","zombie"}){V avatar=rd(getattr(h.battle,SY("avatars")),V(side));setitem(avatar,V("玩家位置"),V::list({V(std::string(side)=="plant"?2136.:2280.),V(864),V(0),V(0)}));setitem(avatar,V("黄油"),V(1000000.));}
  V b=typed72app::wrap_battle(h.battle);callm(b,SY("step"),Args{V(3590)});
  J before=json(callm(b,SY("snapshot"),Args{}));require(before["time"].get<double>()<120.&&before["players"]["zombie"]["hp"]==1000000.,"hero tail fired before 120 seconds");
  double damage=0.;double when=0.;J player;for(int n=0;n<180&&!damage;++n){callm(b,SY("step"),Args{});J s=json(callm(b,SY("snapshot"),Args{}));player=s["players"]["zombie"];damage=1000000.-player["hp"].get<double>();when=s["time"];}
  callm(b,SY("close"),Args{});require(damage==2.&&when>=120.,"wrong tail activation or first damage="+std::to_string(damage));require(player.value("marked_until",0.)==0.,"tail refreshed hero mark");return {{"first_hit_time",when},{"first_hit_damage",damage},{"mark_not_refreshed",true}};
 });
 test("magnet_secret_removes_nine_tile_limit",[&]()->J{
  J cases=J::array();for(bool secret:{false,true}){
   J deck={"plant:向日葵","plant:磁力菇"};if(secret)deck.push_back("secret:磁力");auto h=battle_from_scenario({{"seed",741},{"night",true},{"durable_heroes",true},{"decks",{{"plant",deck},{"zombie",{"zombie:脑光墓碑","zombie:铁桶僵尸"}}}}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
   callm(b,SY("spawn"),Args{V("plant:磁力菇"),V("plant"),V(2136),V(864),V(1)});V z=callm(b,SY("spawn"),Args{V("zombie:铁桶僵尸"),V("zombie"),V(2808),V(864),V(-1)});V zid=rd(z,V("id"));callm(b,SY("fixture_place_zombie"),Args{zid,V::list({V(2808),V(864)}),V(-1)});V object=rd(getattr(b,SY("_native_objects")),zid);setitem(object,V("出场"),V(500));setitem(object,V("血量"),V(1000000));setitem(object,V("黄油"),V(1000000));callm(b,SY("step"),Args{V(20)});J target=json(rd(getattr(b,SY("_native_objects")),zid));require(target.contains("防具"),"missing armor field");const bool removed=target.at("防具").get<std::string>().empty();require(removed==secret,"magnet secret range differs: "+target.dump());cases.push_back({{"secret",secret},{"distance_tiles",14},{"armor_removed",removed}});callm(b,SY("close"),Args{});
  }return cases;
 });
 test("potted_fumeshroom_plant_zombie_multiple_hit",[&]()->J{
  J rows=J::array();for(const char* kind:{"普通僵尸","豌豆僵尸"}){
   auto h=battle_from_scenario({{"seed",741},{"night",true},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
   callm(b,SY("spawn"),Args{V("plant:花盆"),V("plant"),V(2136.),V(864.),V(1.)});
   V p=callm(b,SY("spawn"),Args{V("plant:大喷菇"),V("plant"),V(2136.),V(816.),V(1.)});
   V z=callm(b,SY("spawn"),Args{V(std::string("zombie:")+kind),V("zombie"),V(2256.),V(864.),V(-1.)});V zid=rd(z,V("id"));callm(b,SY("fixture_place_zombie"),Args{zid,V::list({V(2256.),V(864.)}),V(-1.)});
   V obj=rd(getattr(b,SY("_native_objects")),zid);setitem(obj,V("出场"),V(500.));setitem(obj,V("血量"),V(1000000.));setitem(obj,V("黄油"),V(1000000.));
   V plant=rd(getattr(b,SY("_native_objects")),rd(p,V("id")));setitem(plant,V("射"),V(1.));setitem(plant,V("射cd"),V(500.));
   double last=1000000.;J drops=J::array();for(int t=0;t<55;++t){callm(b,SY("step"),Args{});J s=json(callm(b,SY("snapshot"),Args{}));for(const auto&u:s["units"])if(u["id"]==py_str(zid)){const double now=u["hp"];if(now!=last){drops.push_back({{"tick",t},{"damage",last-now}});last=now;}}}
   rows.push_back({{"kind",kind},{"damage",1000000.-last},{"drops",drops}});callm(b,SY("close"),Args{});
  }require(rows[1]["damage"].get<double>()>rows[0]["damage"].get<double>(),"plant-zombie head did not receive extra bubble hits: "+rows.dump());return rows;
 });
 test("pressure_absolute_cost_model_does_not_compound_render_pressure",[&]()->J{
  auto h=battle_from_scenario({{"seed",741}});V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});V app=pm_app::new_Application(Args{pg,screen,h.bridge});callm(app,SY("create"),Args{V(true)});V room=getattr(app,SY("room"));J evidence=J::array();
  for(const auto& view:J::array({nullptr,J{{"phase","config"},{"battle",nullptr}},J{{"phase","battle"},{"battle",nullptr}},J{{"phase","battle"},{"battle",{{"time",1.},{"units",J::array()},{"native_frame",nullptr}}}}})){setattr(app,SY("view"),value(view));pressure741::record_advance(app,.001);pressure741::observe(app,1./60.,.001);}
  for(int scene=0;scene<3;++scene){const double cost_per_game=scene==0?.3:scene==1?1.7:5.,fixed_draw=scene==0?.04:scene==1?.013:.005,native_ratio=scene==2?5.:.3;
   V pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});setattr(room,SY("pacing"),pacing);setattr(pacing,SY("ratio"),V(native_ratio));J units=J::array();for(int i=0;i<100;++i)units.push_back({});V view=value({{"phase","battle"},{"battle",{{"units",units},{"time",0.}}}});setattr(app,SY("view"),view);V battle=py::m_get(view,SV("battle"));pressure741::record_advance(app,0.);
   double wall=0.,game=0.,budget=0.,elapsed=1./60.,minimum=1.;int frames=0;
   while(wall<25.&&frames++<4000){const double scale=getattr(pacing,SY("scale")).num();budget=std::min(.25,budget+elapsed*scale);const int ticks=std::min(2,int(budget*30.));const double advanced=ticks/30.;budget-=advanced;game+=advanced;setitem(battle,SV("time"),V(game));const double advance_work=cost_per_game*advanced+.0001;const double work=fixed_draw+advance_work;elapsed=std::max(1./60.,work);pressure741::record_advance(app,advance_work);pressure741::observe(app,elapsed,work);wall+=elapsed;const double next=getattr(pacing,SY("scale")).num();minimum=std::min(minimum,next);if(wall<5.)require(next==1.,"cost model slowed opening");}
   const double last=getattr(pacing,SY("scale")).num();if(scene==0)require(minimum>.65,"drawing-only pressure compounded to deep slow motion");if(scene==1)require(last>=.65&&last<.8&&minimum>=.65,"fixed publication cost caused deep slowing without native overload");if(scene==2)require(last<.25,"real simulation overload was not relieved");evidence.push_back({{"scene",scene},{"minimum",minimum},{"final_scale",last},{"target",py::m_get(getattr(app,SY("state")),SV("pressure_target")).num()},{"game_seconds",game}});
  }
  callm(app,SY("close_room"),Args{});callm(h.battle,SY("close"),Args{});return evidence;
 });
 test("pressure_gate_opening_sustained_load_and_recovery",[&]()->J{
  auto h=battle_from_scenario({{"seed",741}});V pg=pg::pygame_module();V screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});V app=pm_app::new_Application(Args{pg,screen,h.bridge});callm(app,SY("create"),Args{V(true)});V room=getattr(app,SY("room"));V pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});setattr(room,SY("pacing"),pacing);setattr(pacing,SY("ratio"),V(2.));
  J units=J::array();for(int i=0;i<100;++i)units.push_back({});setattr(app,SY("view"),value({{"phase","battle"},{"battle",{{"units",units}}}}));
  for(int n=0;n<100;++n)pressure741::observe(app,.049,.045);require(getattr(pacing,SY("scale")).num()==1.,"slow motion activated during opening");
  pressure741::observe(app,.25,.5);require(getattr(pacing,SY("scale")).num()==1.,"one stall activated slow motion");
  for(int n=0;n<80;++n)pressure741::observe(app,.05,.045);const double slow=getattr(pacing,SY("scale")).num();require(slow<.9,"sustained severe pressure not handled");require(py::m_get(getattr(app,SY("state")),V("pressure_interpolation")).truthy(),"pressure interpolation not enabled");
  setattr(pacing,SY("ratio"),V(1.));for(int n=0;n<10;++n)pressure741::observe(app,.05,.03);require(getattr(pacing,SY("scale")).num()<=slow,"ongoing overload raised the scale before recovery");
  setattr(app,SY("view"),value({{"phase","battle"},{"battle",{{"units",J::array()}}}}));for(int n=0;n<800;++n)pressure741::observe(app,1./60.,.005);require(getattr(pacing,SY("scale")).num()==1.,"recovery failed");callm(app,SY("close_room"),Args{});callm(h.battle,SY("close"),Args{});return {{"opening_scale",1.},{"overload_scale",slow},{"recovered_scale",1.}};
 });
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"checks",checks}}.dump(2);return failures?1:0;
}
