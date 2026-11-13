#include "ui/hand/texture74_internal.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_native_style.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_replay.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/typed/native_dave_draw.h"
#include "sim/typed/native_status_state.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "core/render_cache.h"
#include "data/datastore.h"
#include <fstream>
#include <iostream>
using namespace pvz;namespace tx=pvz::texture74;namespace t=pvz::typed72;using J=nlohmann::json;
void require(bool b,const std::string& m){if(!b)throw std::runtime_error(m);}
V value(const J& j){return py::json_loads(V(j.dump()));}
J empty_pack(){return {{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}};}
int main(int argc,char** argv){
 if(argc<2)return 2;const auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);env_set_u8("PVP_USERDATA",p8(out/"userdata"));
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();V pg=pg::pygame_module();V screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(960),V(640)})});
 auto h=battle_from_scenario({{"seed",741},{"durable_heroes",true}});auto cold=typed72app::export_cold(h.battle,741);V app=pm_app::new_Application(Args{pg,screen,h.bridge});tx::initialize(app);
 auto action=[&](const char* op,const V& arg=V::none()){tx::action(app,V::tuple({V("texture74"),V(op),arg}));};
 auto capture=[&](const std::string& name){callm(app,SY("render"),Args{});callm(pg::image_module(),SY("save"),Args{screen,V(p8(out/u8p(name+".png")))});};
 J checks=J::array(),pack=empty_pack();int errors=0;pack["name"]="Hero and grave test";
 auto test=[&](const std::string& name,auto run){J row={{"name",name}};try{row["evidence"]=run();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++errors;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
 auto add=[&](const std::string& key,uint32_t color){const auto* r=tx::resource(key);require(r,"resource absent: "+key);std::vector<uint32_t> px(size_t(r->w)*r->h);for(int y=8;y<r->h-8;++y)for(int x=8;x<r->w-8;++x)if(x<r->w/2||y>r->h/2)px[size_t(y)*r->w+x]=color;pack["entries"][key]={{"width",r->w},{"height",r->h},{"png",tx::b64(tx::png_encode(tx::surface(r->w,r->h,px)))}};};
 test("heroes_browser_and_exact_canvas",[&]()->J{
  tx::action(app,V::tuple({V("texture74_open")}));action("filter",V("英雄"));capture("heroes-library");int heroes=0;
  for(const auto& control:getattr(getattr(app,SY("renderer")),SY("controls")).items()){const auto cmd=control.idx(1);if(cmd.t==V::TUPLE&&cmd.len()>1&&cmd.idx(0)==V("texture74")&&cmd.idx(1)==V("hero"))++heroes;}
  require(heroes==2,"hero buttons missing");for(const char* side:{"hero:plant","hero:zombie"}){action("hero",V(side));require(tx::state().canvas.w==96&&tx::state().canvas.h==96,"hero canvas dimensions changed");require(!tx::state().hero_filter.empty()&&tx::state().card_filter.empty(),"hero filter leaked card selection");capture(side==std::string("hero:plant")?"hero-plant-editor":"hero-zombie-editor");action("library");}
  return {{"buttons",heroes},{"canvas",{96,96}}};
 });
 test("terrain_excluded_and_old_pack_migrates",[&]()->J{
  for(const auto& c:tx::state().cards)require(c["name"]!="草坪"&&c["name"]!="石块","terrain card still editable");
  require(!tx::resource("world:草")&&!tx::resource("world:石")&&!tx::resource("raw:图片/土.png"),"terrain aliases still editable");
  require(tx::resource("world:石果子")&&tx::resource("world:土豆地雷"),"unrelated plants excluded");
  add("world:疯狂戴夫",0x40a020ff);auto legacy=pack;for(const auto& key:tx::state().excluded_keys)legacy["entries"][key]={{"legacy",true}};
  const auto clean=tx::validate_pack(legacy);require(clean["entries"].size()==1,"old terrain entries retained");tx::activate(legacy);require(tx::artwork("world:草").is_none()&&tx::artwork("world:石").is_none(),"legacy terrain override active");
  bool rejected=false;legacy["entries"]["world:unknown-invalid"]={};try{tx::validate_pack(legacy);}catch(...){rejected=true;}require(rejected,"unknown key accepted");return {{"ignored_old_aliases",tx::state().excluded_keys.size()},{"unknown_rejected",true}};
 });
 add("world:僵尸戴夫",0x3080b0ff);for(int stage=1;stage<=5;++stage)add("world:坟墓"+std::to_string(stage),0xe05828ff);
 tx::register_hooks();
 V resolver=V::func([](const Args& a){const auto key=py_str(a.pos.at(0));const auto* r=tx::resource(key);if(!r)throw std::runtime_error("original resolver absent: "+key);return tx::original(*r);});
 V display=V::func([resolver](const Args& a){return resolver.call(a);});display.box->fattrs.emplace_back(SY("__texture74_display_resolver__"),V(true));
 auto render=[&](const J& description,bool cosmetic){V replay=pm_native_animation::new_DrawReplay(Args{pg,cosmetic?display:resolver});return callm(replay,SY("surface"),Args{value(description)});};
 t::NativeCanvas canvas;canvas.install(cold.draw_atlas,{},J::object(),J::object());
 for(const char* skin:{"疯狂戴夫","僵尸戴夫"})test(std::string("production_hero_status_")+skin,[&]()->J{
  tx::activate(pack);std::vector<uint32_t> normal;J states=J::array();
  for(const char* status:{"normal","slow","frozen","poison1","poison2","frozen_poison"}){
   const std::string mode=status;t::HeroState hero;t::HeroFrame globals;hero.frame.skin.set(skin);hero.frame.hp.set(40.);hero.frame.facing.set(1.);hero.frame.position.set(std::make_shared<t::Motion>(t::Motion{144,144,0,0}));
   hero.ice.set(mode=="slow"?1.:mode=="frozen"||mode=="frozen_poison"?2000.:0.);
   if(mode.find("poison")!=std::string::npos){auto poison=std::make_shared<t::PoisonState>();poison->level.set(mode=="poison2"?2:1);hero.poison.set(poison);}
   canvas.frames.begin_frame(0);t::draw_dave(canvas,{hero,globals,48.,0,std::nullopt,true},[](const std::string& what){throw std::runtime_error(what);});require(canvas.frames.size()==1,"unexpected hero draw commands");
   const auto desc=canvas.describe(canvas.frames.frame().commands.front().image);V painted=render(desc,true),original=render(desc,false);auto px=tx::pixels(painted);require(px!=tx::pixels(original),"custom skin disappeared under status");
   if(mode=="normal"){normal=px;require(px==tx::pixels(tx::artwork(std::string("world:")+skin)),"normal hero did not use custom canvas");}
   else {require(px!=normal,"status did not tint custom skin");for(size_t i=0;i<px.size();++i)require((px[i]&255)==(normal[i]&255),"status changed custom silhouette");}
   callm(pg::image_module(),SY("save"),Args{painted,V(p8(out/u8p(std::string(skin)+"-"+mode+".png")))});states.push_back(mode);
  }
  return {{"states",states},{"silhouette_preserved",true}};
 });
 test("production_grave_variants_and_world_override",[&]()->J{
  auto grave_pack=pack;grave_pack["entries"].erase("world:疯狂戴夫");grave_pack["entries"].erase("world:僵尸戴夫");
  V art=pm_native_style::new_NativeArt(Args{pg,h.bridge});int changed=0;
  for(const char* name:{"脑光墓碑","双生脑光墓碑","坚固脑光墓碑","成长脑光墓碑","墓碑残骸"}){std::vector<uint32_t> before;for(bool custom:{false,true}){tx::activate(custom?grave_pack:empty_pack());callm(screen,SY("fill"),Args{V::tuple({V(20),V(30),V(40)})});callm(art,SY("grave"),Args{screen,V(name),V(120),V(120),V(48)});auto px=tx::pixels(screen);if(custom){require(px!=before,std::string(name)+" ignored custom grave sprite");++changed;}else before=std::move(px);}}
  // Graves are intentionally drawn by WorldView, outside native_frame.
  auto handle=battle_from_scenario({{"seed",741},{"durable_heroes",true}});V battle=typed72app::wrap_battle(handle.battle);V grave=callm(battle,SY("spawn"),Args{V("zombie:脑光墓碑"),V("zombie"),V(2136),V(864),V(-1)});require(!grave.is_none(),"grave spawn failed");for(int n=0;n<3;++n)callm(battle,SY("step"),Args{});V snap=callm(battle,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));V world=pm_world_view::new_WorldView(Args{pg,handle.bridge});std::vector<uint32_t> before;
  for(bool custom:{false,true}){tx::activate(custom?grave_pack:empty_pack());callm(world,SY("render"),Args{screen,snap,V::tuple({V(0),V(0),V(960),V(640)}),V("plant"),value({{"zoom",2.},{"world_quality","native"},{"replay_camera",{2136.,800.}}}),V::none(),V(true)});require(!getattr(world,SY("native_error")).truthy(),"WorldView grave rendering failed");auto px=tx::pixels(screen);if(custom)require(px!=before,"actual WorldView grave ignored pack");else before=std::move(px);callm(pg::image_module(),SY("save"),Args{screen,V(p8(out/(custom?"grave-world-custom.png":"grave-world-original.png")))});}
  callm(battle,SY("close"),Args{});tx::activate(pack);return {{"grave_kinds_changed",changed},{"actual_world_changed",true},{"resource_variants_editable",5}};
 });
 test("hero_grave_paint_cannot_change_authoritative_state",[&]()->J{
  std::vector<std::string> hashes;
  for(bool custom:{false,true}){tx::activate(custom?pack:empty_pack());auto handle=battle_from_scenario({{"seed",741}});V battle=typed72app::wrap_battle(handle.battle);for(int n=0;n<120;++n)callm(battle,SY("step"),Args{});hashes.push_back(py_str(pm_replay::f_state_hash(Args{battle})));callm(battle,SY("close"),Args{});}
  require(hashes[0]==hashes[1],"hero/grave painting changed battle state");tx::activate(pack);return {{"same_hash",hashes[0]}};
 });
 test("host_share_retains_hero_and_grave_then_restores_local",[&]()->J{
  auto& s=tx::state();const auto local=s.document;tx::activate(pack);const auto wire=s.wire,hash=s.wire_hash;setattr(app,SY("mode"),V("guest"));
  tx::receive(app,V("server"),value({{"type","texture74_offer"},{"hash",hash},{"bytes",wire.size()},{"chunks",1},{"name","host heroes"}}));tx::receive(app,V("server"),value({{"type","texture74_chunk"},{"hash",hash},{"index",0},{"data",tx::b64(wire)}}));
  require(s.remote&&s.guest_ready,"host pack not received");require(!tx::artwork("world:疯狂戴夫").is_none()&&!tx::artwork("world:僵尸戴夫").is_none()&&!tx::artwork("world:坟墓1").is_none(),"hero/grave resources lost in transfer");
  setattr(app,SY("mode"),V::none());tx::update(app,0.);require(!s.remote,"leaving room retained remote pack");require(s.document==local,"local artwork overwritten");return {{"host_pack_received",true},{"local_document_preserved",true}};
 });
 test("lru_bound_methods_keep_order",[&]()->J{
  V cache=native_render_cache();cache.box->inst->setitem(V("first"),V(1));cache.box->inst->setitem(V("second"),V(2));V move=getattr(cache,SY("move_to_end"));require(py::callable(move).truthy(),"bound method missing");move.call(Args{V("first")});auto popped=getattr(cache,SY("popitem")).call(Args({},{{SY("last"),V(false)}}));require(popped.idx(0)==V("second"),"LRU order changed");return {{"bound_call",true},{"eviction_order",true}};
 });
 tx::activate(empty_pack());std::ofstream(out/"summary.json",std::ios::binary)<<J{{"passed",errors==0},{"failures",errors},{"checks",checks}}.dump(2);callm(app,SY("close"),Args{});callm(h.battle,SY("close"),Args{});return errors?1:0;
}
