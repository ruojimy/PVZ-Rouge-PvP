#include "pg/pg.h"
#include "core/gil.h"
#include "core/render_cache.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_app.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "ui/hand/pressure_pacing.h"
#include "ui/hand/texture74_internal.h"
#include "sim/typed/moving_coverage_grid.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <limits>
using namespace pvz;using J=nlohmann::json;
static void require(bool ok,const char* error){if(!ok)throw std::runtime_error(error);}
static V value(const J& j){return py::json_loads(V(j.dump()));}
int main(int argc,char** argv){
 if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J cases=J::array();int failed=0;auto test=[&](const char* name,auto run){J row={{"name",name}};try{run();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}cases.push_back(row);std::cerr<<row.dump()<<'\n';};
 test("wall_time_credit_debt_pause_and_guest",[]{
  auto p=std::make_shared<pm_app::C_Application>();p->a_state=V::dict();p->a_mode=V("local");p->a_view=value({{"phase","battle"},{"paused",false},{"audit_error",""}});V app=V::inst(p);
  require(pressure741::service_delta(app,600.)==.6,"250ms truncation remains");
  require(pressure741::service_delta(app,5000.)==2.,"unbounded service update");
  require(p->a_state.get(V("wall_clock_debt")).num()==3.,"lost elapsed debt");
  require(pressure741::service_delta(app,0.)==2.,"debt did not drain");
  require(pressure741::service_delta(app,0.)==1.,"debt remainder lost");
  setitem(p->a_view,V("paused"),V(true));require(pressure741::service_delta(app,600.)==.25,"paused UI changed");
  require(p->a_state.get(V("wall_clock_debt")).num()==0.,"pause retained old wall debt");
  p->a_mode=V("host");require(pressure741::authority_delta(app,1.7)==1.7,"secondary one-second clamp still loses credit");
  pressure741::reset_wall_clock(app);require(pressure741::authority_delta(app,1.7)==0.,"lifecycle suspension caught up as combat");
  require(pressure741::authority_delta(app,.04)==.04,"lifecycle reset swallowed the next frame");
  setitem(p->a_view,V("paused"),V(false));p->a_mode=V("guest");require(pressure741::service_delta(app,600.)==.25,"guest authority changed");
 });
 test("recipe_key_exact_fields_and_order",[]{
  V a=value({{"alpha",255},{"size",{12,13}},{"image",{{"op","asset"},{"key","world:pea"},{"size",{12,13}}}}});
  V b=V::dict();const auto pairs=a.kv();for(auto it=pairs.rbegin();it!=pairs.rend();++it)b.at(it->first)=it->second;
  require(native_recipe_key(a,V::none(),V(1.))==native_recipe_key(b,V::none(),V(1.)),"dict insertion order changed key");
  require(native_recipe_key(a,V::none(),V(1.))!=native_recipe_key(a,V::none(),V(1.0000000000000002)),"scale precision lost");
  require(native_recipe_key(a,V::none(),V(1.))!=native_recipe_key(a,V::list({V(0.),V(0.),V(1.),V(1.)}),V(1.)),"crop omitted");
  setitem(b,V("alpha"),V(254.));require(native_recipe_key(a,V::none(),V(1.))!=native_recipe_key(b,V::none(),V(1.)),"alpha omitted");
 });
 test("early_result_keeps_the_final_native_frame",[]{
  auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true}});
  auto a=typed72app::Session::create(typed72app::export_cold(h.battle,742),"ending-frame");
  auto b=typed72app::Session::create(typed72app::export_cold(h.battle,742),"ending-frame");
  for(auto* s:{a.get(),b.get()})s->fixture_set_avatar("zombie",{{"玩家血量",0}});
  a->step();for(int i=0;i<12&&!b->finished();++i)b->step();
  require(a->finished()&&b->finished(),"fixture did not end before a twelve-step request");
  const auto expected=a->snapshot(),actual=b->snapshot();
  require(expected.at("native_frame")==actual.at("native_frame"),"batched request lost the ending native frame");
  require(!actual.at("native_frame").at("commands").empty(),"ending native frame was empty");
  require(a->rng_state()==b->rng_state(),"ending frame altered RNG");callm(h.battle,SY("close"),Args{});
 });
 test("movement_refresh_protocol_and_frame_boundary",[]{
  auto p=std::make_shared<pm_app::C_Application>();p->a_state=V::dict();V app=V::inst(p);
  V move=value({{"type","input"},{"input",{{"type","move"},{"move",0},{"jump",false},{"seq",1}}}});
  require(pressure741::command_refresh_needed(app,move),"standalone command lost immediate view");
  {pressure741::FrameServiceScope frame(app);
   require(!pressure741::command_refresh_needed(app,move),"real nested move did not defer duplicate refresh");
   require(pressure741::command_refresh_needed(app,value({{"type","input"},{"input",{{"type","deploy"}}}})),"deployment snapshot was deferred");
   require(pressure741::command_refresh_needed(app,value({{"type","move"}})),"invalid outer command was treated as heartbeat");}
  require(pressure741::command_refresh_needed(app,move),"frame marker escaped its scope");
 });
 test("moving_volume_grid_dynamic_coverage_and_cache",[]{
  using namespace typed72;MovingCoverageGrid grid;grid.reset(48.,3456.,120);
  std::vector<CoverageBox> boxes;
  for(size_t i=0;i<120;++i){const double x=double((i*173)%3456),y=double((i*79)%1300)-100.;const double r=8.+double(i%7)*15.;boxes.push_back({x-r,y-r*2.,x+r,y});grid.cover(i,boxes.back());}
  const auto overlaps=[](CoverageBox a,CoverageBox b){if(a.top>b.bottom||a.bottom<b.top)return false;for(int wrap=-2;wrap<=2;++wrap){const double dx=wrap*3456.;if(a.left+dx<=b.right&&a.right+dx>=b.left)return true;}return false;};
  for(int t=0;t<600;++t){
   const size_t id=size_t(t*47)%120;auto& b=boxes[id];const double dx=t%9==0?1700.:.2,dy=t%7==0?-31.:.1;b.left+=dx;b.right+=dx;b.top+=dy;b.bottom+=dy;grid.cover(id,b);
   const double x=double((t*211)%3456),y=double((t*109)%1300)-100.;CoverageBox query{x-70.,y-60.,x+95.,y+85.};
   auto result=grid.rectangle(query);std::vector<size_t> ids(result.begin(),result.end());
   require(std::is_sorted(ids.begin(),ids.end())&&std::adjacent_find(ids.begin(),ids.end())==ids.end(),"duplicate or unordered candidate");
   for(size_t i=0;i<boxes.size();++i)if(overlaps(boxes[i],query))require(std::binary_search(ids.begin(),ids.end(),i),"moving or wrapped large body omitted");
   auto again=grid.rectangle(query);require(std::vector<size_t>(again.begin(),again.end())==ids,"candidate cache drift");
  }
  require(grid.cache_hits>=600,"fixed-region candidates were not reused");
  MovingCoverageGrid local;local.reset(48.,3456.,1);local.cover(0,{3.,3.,10.,10.});(void)local.rectangle({0.,0.,48.,48.});
  const auto changes=local.cell_changes;local.cover(0,{3.1,3.,10.1,10.});require(local.cell_changes==changes,"within-cell motion invalidated membership");
  require(local.rectangle({0.,0.,48.,48.}).size()==1,"within-cell exact candidate disappeared");
  MovingCoverageGrid partial;partial.reset(48.,3456.,8);partial.cover(3,{0.,0.,20.,20.});
  const auto fallback=partial.rectangle({0.,0.,std::numeric_limits<double>::infinity(),20.});
  require(fallback.size()==1&&fallback.front()==3,"fallback included unregistered faction IDs");
 });
 test("cached_and_uncached_frame_pixels",[]{
  V pg=pg::pygame_module();V cached=pm_native_animation::new_DrawReplay(Args{pg}),reference=pm_native_animation::new_DrawReplay(Args{pg});
  setattr(reference,SY("cache_limit"),V(0.));V a=pg::new_surface(400,240,true),b=pg::new_surface(400,240,true);
  J commands=J::array();
  for(int i=0;i<520;++i){J image={{"size",{12,12}},{"alpha",i%256},{"colorkey",nullptr},{"image",{{"op","fill"},{"source",{{"size",{12,12}},{"alpha",nullptr},{"colorkey",nullptr},{"image",{{"op","canvas"},{"size",{12,12}},{"flags",65536},{"depth",32}}}}},{"color",{i%255,(i*11)%255,(i*31)%255,255}},{"rect",nullptr},{"flags",0}}}};
   commands.push_back({{"op","image"},{"surface",image},{"pos",{(i%30)*11,(i/30)*9}},{"area",i%7?J(nullptr):J{1,1,6,6}},{"flags",0}});}
  for(int n=0;n<3;++n){if(n)std::reverse(commands.begin(),commands.end());V frame=value({{"protocol","native-draw-v1"},{"commands",commands}});
   for(const auto& screen:{a,b})callm(screen,SY("fill"),Args{V::tuple({V(11.),V(19.),V(27.),V(255.)})});
   callm(cached,SY("render"),Args{a,frame,V::none(),V(1.25)});callm(reference,SY("render"),Args{b,frame,V::none(),V(1.25)});
   require(texture74::pixels(a)==texture74::pixels(b),"cache changed rendered pixels");}
  require(getattr(cached,SY("hits")).num()>0.,"cache hit case not reached");
 });
 J result={{"passed",failed==0},{"checks",cases}};std::ofstream(argv[1],std::ios::binary)<<result.dump(2);return failed?1:0;
}
