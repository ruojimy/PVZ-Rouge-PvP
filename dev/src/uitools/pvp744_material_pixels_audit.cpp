#include "ui/hand/texture74_internal.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed/native_patch_draw.h"
#include "sim/typed/plant_zombie_target.h"
#include "core/gil.h"
#include "data/datastore.h"
#include <fstream>
#include <iostream>
using namespace pvz;namespace t=pvz::typed72;namespace tx=pvz::texture74;using J=nlohmann::json;
int main(int argc,char** argv){
 if(argc!=2)return 2;SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 const auto pg=pg::pygame_module();callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(16),V(16)})});tx::load_inventory();tx::register_hooks();
 auto handle=battle_from_scenario({{"seed",744}});const auto cold=typed72app::export_cold(handle.battle,744);
 std::unordered_map<std::string,t::SpritePixels> pixels;
 for(const auto& [name,p]:cold.atlas){t::SpritePixels px;px.width=p.width;px.height=p.height;px.pixels=p.rgba;pixels.emplace(name,std::move(px));}
 const auto install=[&](t::NativeCanvas& c){c.install(cold.draw_atlas,pixels,cold.cold["constants"]["scale_factor"],cold.cold["constants"]["rider_lift"]);c.patch_plant_zombie_assets();};
 V resolver=V::func([](const Args& a){const auto key=py_str(a.pos.at(0));const auto* r=tx::resource(key);if(r)return tx::original(*r);return py::native_hook(V("graphics.asset"),Args{V(key)});});
 V display=V::func([resolver](const Args& a){return resolver.call(a);});display.box->fattrs.emplace_back(SY("__texture74_display_resolver__"),V(true));
 // Fresh surface replay per comparison prevents the verifier from hiding a
 // stale producer recipe behind a second cache. The production renderer applies
 // the recipe (including alpha, transforms, masks and the cosmetic resolver).
 const auto raster=[&](const J& description){auto replay=pm_native_animation::new_DrawReplay(Args{pg,display});
  auto image=callm(replay,SY("surface"),Args{py::json_loads(V(description.dump()))});auto* s=pg::surf(image);
  auto target=pg::new_surface(s->w(),s->h(),true);callm(target,SY("blit"),Args{image,V::tuple({V(0),V(0)})});return tx::pixels(target);};
 const auto frame_pixels=[&](t::NativeCanvas& c){std::vector<std::vector<uint32_t>> out;for(const auto& cmd:c.frames.frame().commands)if(cmd.image)out.push_back(raster(c.describe(cmd.image)));return out;};
 J checks=J::array();int errors=0;const auto test=[&](std::string name,auto run){try{run();checks.push_back({{"name",name},{"passed",true}});}catch(const std::exception& e){++errors;checks.push_back({{"name",name},{"passed",false},{"error",e.what()}});}};
 const auto require=[](bool ok,const char* message){if(!ok)throw std::runtime_error(message);};
 for(const char* name:{"豌豆僵尸","机枪僵尸","大喷菇僵尸","坚果僵尸","高坚果僵尸","毁灭菇僵尸","辣椒僵尸","倭瓜僵尸","墓碑吞噬者僵尸","三叶草僵尸","路灯花僵尸","萝卜伞僵尸","吸金磁僵尸"})
 for(const char* armor:{"","路障","铁桶"})for(int level:{1,2})test(std::string("head/")+name+"/"+armor+"/"+std::to_string(level),[&]{
  t::NativeCanvas c;install(c);t::TypedBattleState world;auto u=std::make_shared<t::CombatZombie>();u->body.kind="普通僵尸";u->body.hp=100.;u->body.facing=-1.;u->body.motion.replace({300.,300.,0.,0.});u->body.armor=armor;u->body.armor_hp=100.;u->source.id.set("head");u->patch.plant_zombie.set(true);u->patch.plant_name.set(name);world.targets->push_back(t::CombatTarget::zombie(u));t::NativePatchDraw draw(world,c);
  const auto sample=[&]{c.frames.begin_frame(0);draw.plant_zombie_heads();return frame_pixels(c);};
  const auto healthy=sample();require(!healthy.empty(),"head produced no pixels");
  auto poison=std::make_shared<t::PoisonState>();poison->level.set(level);u->poison.poison.set(poison);const auto tinted=sample();require(tinted!=healthy,"poison did not change left-head pixels");
  u->poison.poison.erase();require(sample()==healthy,"poison pixels remained after clearing");
  // Same mutable handle, new recipe and alpha: neither key nor address changed.
  auto source=c.image(std::string(name)+"-植头");c.fill(source,J::array({60,210,70}),nullptr,3);t::NativeCanvas::set_alpha(source,117.);
  const auto changed=sample();require(changed!=healthy,"left cache ignored changed input recipe/alpha");
 });
 for(const char* armor:{"路障","铁桶","橄榄球头盔"})for(int level:{1,2})test(std::string("carrier/")+armor+"/"+std::to_string(level),[&]{
  t::NativeCanvas c,control;install(c);install(control);auto u=std::make_shared<t::CombatZombie>();u->body.kind="巨人僵尸";u->body.hp=1000.;u->body.armor=armor;u->body.armor_hp=100.;
  const auto sample=[&](t::NativeCanvas& canvas){canvas.expansion.gate(u);canvas.frames.begin_frame(0);canvas.display(canvas.image("巨人僵尸-首"),{0,0});return frame_pixels(canvas);};
  const auto healthy=sample(control);c.tint_roots({"巨人僵尸-身","巨人僵尸-首"},level);const auto poisoned=sample(c);require(poisoned!=healthy,"carrier poison pixels absent");
  c.expansion.clear();c.restore();require(sample(c)==healthy,"healthy carrier reused poison pixels");
 });
 test("armor/independent-scaled-resource",[&]{t::NativeCanvas c;install(c);
  const auto plate=c.expansion.armor_art("铁桶","小鬼僵尸");const auto key=t::NativeArtStore::art_key(plate);
  require(key&&*key=="world:小鬼僵尸-铁桶","scaled armor lost its independent resource key");
  const auto* r=tx::resource(*key);const auto before=raster(c.describe(plate)),other=raster(c.describe(c.image("铁桶")));
  tx::activate({{"format","pvz-texture-pack-v1"},{"name","armor"},{"entries",{{r->key,{{"width",r->w},{"height",r->h},{"png",tx::b64(tx::png_encode(tx::surface(r->w,r->h,std::vector<uint32_t>(size_t(r->w)*r->h,0xff50d0ff))))}}}}}});
  require(raster(c.describe(plate))!=before,"scaled armor override disappeared");require(raster(c.describe(c.image("铁桶")))==other,"scaled armor override changed regular armor");
  tx::activate({{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}});
 });
 test("alpha/copy-before-flip-scale",[&]{t::NativeCanvas c;install(c);const auto before=raster(c.describe(c.image("豌豆射手-受伤")));
  const auto a=c.with_alpha("豌豆射手-受伤",37),b=c.with_alpha("豌豆射手-受伤",183);
  const auto first=raster(c.describe(c.resize(t::NativeCanvas::flip(a),64,64))),second=raster(c.describe(c.resize(t::NativeCanvas::flip(b),64,64)));
  require(first!=second,"object alpha did not affect rendered pixels");require(raster(c.describe(c.image("豌豆射手-受伤")))==before,"alpha altered the shared asset");
 });
 test("scope/nested-exception-and-position",[&]{t::NativeCanvas c;install(c);c.frames.begin_frame(0);c.frames.entity_override=t::NativeFrameSource{"outer",{1,2}};
  try{t::NativeFrameScope owned(c.frames,{"inner",{10,20}});c.display(c.image("豌豆"),{0,0});throw std::runtime_error("test exit");}catch(const std::runtime_error&){}
  require(c.frames.entity_override->id=="outer","exception lost outer owner");{t::NativeFrameScope independent(c.frames);c.display(c.image("豌豆"),{0,0});}
  const auto& commands=c.frames.frame().commands;require(commands[0].entity==std::optional<std::string>("inner")&&!commands[1].entity,"draw borrowed another entity");require(c.frames.frame().positions.front().second.x==10,"wrong motion anchor");
 });
 test("workshop/pixels-scope-revision-and-disable",[&]{
  t::NativeCanvas c;install(c);auto world=c.describe(c.image("三叶草")),ui=c.describe(c.ui_image("三叶草"));
  const auto baseline_world=raster(world),baseline_ui=raster(ui);const auto* r=tx::resource("world:三叶草");
  for(uint32_t color:{0xff1040ffu,0x20e080ffu}){const auto image=tx::surface(r->w,r->h,std::vector<uint32_t>(size_t(r->w)*r->h,color));
   tx::activate({{"format","pvz-texture-pack-v1"},{"name","pixels"},{"entries",{{r->key,{{"width",r->w},{"height",r->h},{"png",tx::b64(tx::png_encode(image))}}}}}});
   const auto painted=raster(world);require(painted!=baseline_world&&painted.front()==color,"world paint missing or stale");require(raster(ui)==baseline_ui,"world override changed UI pixels");
  }
  tx::activate({{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}});require(raster(world)==baseline_world&&raster(ui)==baseline_ui,"disabling pack retained custom pixels");
 });
 std::ofstream(argv[1],std::ios::binary)<<J{{"passed",errors==0},{"errors",errors},{"checks",checks}}.dump(2);std::cout<<"pixel checks="<<checks.size()<<" errors="<<errors<<'\n';return errors?1:0;
}
