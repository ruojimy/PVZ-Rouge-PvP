// Independent actual workshop persistence / path / status-cache audit.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "core/resource_paths.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/hand/texture74_internal.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_native_style.h"
#include <fstream>
#include <iostream>
#include <set>
using namespace pvz;namespace tx=pvz::texture74;using J=nlohmann::json;
namespace {
void need(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
J blank(){return {{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}};}
J painted(const tx::Resource& r,uint32_t color){auto doc=blank();doc["name"]="synthetic controlled color";doc["entries"][r.key]={{"width",r.w},{"height",r.h},{"png",tx::b64(tx::png_encode(tx::surface(r.w,r.h,std::vector<uint32_t>(size_t(r.w)*r.h,color))))}};return doc;}
J stats(const V& image){std::set<uint32_t> colors;size_t opaque=0,cyan=0,clear=0;for(auto p:tx::pixels(image)){if(!(p&255)){++clear;continue;}++opaque;colors.insert(p);if((p>>24)<120&&((p>>16)&255)>100&&((p>>8)&255)>150)++cyan;}return {{"colors",colors.size()},{"opaque",opaque},{"clear",clear},{"cyan",cyan}};}
std::filesystem::path source_path(const tx::Resource& r){if(r.file.rfind("图片/",0)==0)return native_image_directory()/u8p(r.file.substr(7));return u8p(data::data_dir()).parent_path().parent_path()/u8p(r.file);}
void save_png(const V& image,const std::filesystem::path& path){auto bytes=tx::png_encode(image);std::ofstream file(path,std::ios::binary);file.write(bytes.data(),bytes.size());need(bool(file),"cannot write isolated PNG evidence");}
}
int main(int argc,char** argv){
 if(argc<2)return 2;install_crash_handler();const auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);bool complete=false,probe_missing=false;for(int i=2;i<argc;++i){complete|=std::string(argv[i])=="--require-components";probe_missing|=std::string(argv[i])=="--probe-missing-original";}
 env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();V pg=pg::pygame_module();V screen=callm(pg::display_module(),SY("set_mode"),Args{V::nums({1280,720})});auto battle=battle_from_scenario({{"seed",742}});V app=pm_app::new_Application(Args{pg,screen,battle.bridge});
 const auto op=[&](const char* name,V arg=V::none()){need(tx::action(app,V::tuple({SV("texture74"),V(name),arg})),"workshop action rejected");};
 const auto render=[&](){callm(app,SY("render"),Args{});};
 const auto* icon=tx::resource("icon:石化火炬-蓝火");need(icon,"Rage icon missing");const auto original=tx::pixels(tx::original(*icon));
 J checks=J::array();int failures=0;auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){print_last_cpp_throw(stderr);row["passed"]=false;row["error"]=e.what();++failures;}checks.push_back(row);std::cerr<<row.dump()<<std::endl;};
 test("rage_original_png_encode_decode",[&]()->J{auto image=tx::original(*icon);const auto info=stats(image);need(info["colors"].get<size_t>()>10&&info["cyan"].get<size_t>()>20,"original Rage asset is a flat/missing blue image");const auto bytes=tx::png_encode(image);need(tx::pixels(tx::png_decode(bytes,icon->w,icon->h))==original,"RGBA changed during original PNG encode/decode");save_png(image,out/"rage-original-roundtrip.png");return {{"key",icon->key},{"source",icon->file},{"stats",info},{"roundtrip_pixels_equal",true}};});
 test("actual_original_save_export_pack_reopen",[&]()->J{
  tx::action(app,V::tuple({SV("texture74_open")}));op("card",SV("zsecret:暴怒"));need(tx::state().selected_key==icon->key,"card selected a different resource");op("original");need(tx::state().canvas.flatten()==original,"original action produced different pixels");op("save");op("library");op("card",SV("zsecret:暴怒"));need(tx::state().canvas.flatten()==original,"save/reopen changed Rage original");
  auto file=out/"rage-original.pvptex";tx::export_pack(file);tx::import_pack(file);op("edit",V(icon->key));need(tx::state().canvas.flatten()==original,"export/import changed Rage original");render();save_png(screen,out/"rage-reopened-editor.png");return {{"saved_original_reopens",true},{"export_import_rgba_equal",true},{"layers",tx::state().canvas.layers.size()}};
 });
 test("retained_old_green_entry_is_explicit_pack_content",[&]()->J{
  // This intentionally constructs a saved green pack. It is not a reproduction
  // of the user's state or proof that a new/default pack becomes green.
  const auto legacy=painted(*icon,0x66cc66ff);auto file=out/"synthetic-legacy-green.pvptex";tx::save_file(file,legacy);tx::import_pack(file);op("card",SV("zsecret:暴怒"));need(tx::state().canvas.flatten()!=original,"controlled green pack was not loaded");render();save_png(screen,out/"synthetic-green-editor.png");
  op("default");need(!tx::active(),"original/default did not disable active replacements");op("library");op("card",SV("zsecret:暴怒"));const auto edited=tx::state().canvas.flatten();need(edited.at(0)==0x66cc66ff,"disabled saved pack no longer retains its editable source");
  op("original");op("save");render();need(tx::state().canvas.flatten()==original,"original/reset/save did not restore source PNG");
  save_png(tx::surface(128,128,tx::state().canvas.flatten()),out/"original-restored.png");return {{"synthetic_fixture_only",true},{"disabled_pack_remains_editable",true},{"original_reset_restores_blue",true},{"user_default_pack_not_assumed",true}};
 });
 test("display_status_and_revision_cache_restore",[&]()->J{
  tx::activate(blank());render();V art=pm_native_style::new_NativeArt(Args{pg,battle.bridge});const auto before=tx::pixels(callm(art,SY("raw"),Args{SV("蓝火炬1")}));const auto* flame=tx::resource("world:蓝火炬1");need(flame,"blue flame world resource absent");const auto color=painted(*flame,0xcc3366ff);tx::activate(color);render();V custom=callm(art,SY("raw"),Args{SV("蓝火炬1")});need(tx::pixels(custom)==std::vector<uint32_t>(size_t(flame->w)*flame->h,0xcc3366ff),"NativeArt cache did not invalidate on texture revision");
  V gray=tx::artwork("world:蓝火炬1-黑白");need(!gray.is_none(),"monochrome derived texture absent");for(auto p:tx::pixels(gray))need((p>>24)==((p>>16)&255)&&((p>>16)&255)==((p>>8)&255),"derived monochrome did not remain gray");
  tx::activate(blank());render();need(tx::pixels(callm(art,SY("raw"),Args{SV("蓝火炬1")}))==before,"NativeArt kept old custom pixels after disabling pack");return {{"active_and_disabled_cache_invalidation",true},{"monochrome_filter_kept",true},{"original_pixels_restored",true}};
 });
 test("android_layout_original_path_without_desktop_fallback",[&]()->J{
  const auto cwd=std::filesystem::current_path();const auto dir=data::data_dir();const auto root=out/u8p("模拟Android私有资源目录");std::vector<const tx::Resource*> resources={icon,tx::resource("world:蓝火炬1"),tx::resource("raw:图片/火炬树桩-秃.png")};std::vector<std::vector<uint32_t>> expected;
  for(const auto* r:resources){need(r,"required original component absent");expected.push_back(tx::pixels(tx::original(*r)));const auto dst=root/u8p(r->file);std::filesystem::create_directories(dst.parent_path());std::filesystem::copy_file(source_path(*r),dst,std::filesystem::copy_options::overwrite_existing);}
  std::filesystem::create_directories(root/"extract/data");struct Restore{std::filesystem::path cwd;std::string dir;~Restore(){std::filesystem::current_path(cwd);data::set_data_dir(dir);}} restore{cwd,dir};std::filesystem::current_path(root);data::set_data_dir(p8(root/"extract/data"));
  for(size_t i=0;i<resources.size();++i)need(tx::pixels(tx::original(*resources[i]))==expected[i],"unpacked Android-layout path resolved different original pixels");return {{"private_root_unicode",true},{"originals_checked",resources.size()},{"desktop_resource_fallback_needed",false},{"actual_android_assetmanager_or_document_picker_executed",false}};
 });
 test("rage_components_association",[&]()->J{
  const std::vector<std::string> needed={"world:蓝火炬1","world:蓝火炬2","world:蓝火炬3","raw:图片/火炬树桩-秃.png"};std::vector<std::string> missing,linked;for(const auto& r:tx::state().resources)if(std::find(r.cards.begin(),r.cards.end(),"zsecret:暴怒")!=r.cards.end())linked.push_back(r.key);
  for(const auto& key:needed){const auto* r=tx::resource(key);need(r,"actual component not inventoried: "+key);if(std::find(r->cards.begin(),r->cards.end(),"zsecret:暴怒")==r->cards.end())missing.push_back(key);}
  bool selectable=false;if(complete){
   need(missing.empty(),"Rage still lacks its editable actual components");op("card",SV("zsecret:暴怒"));op("library");render();std::set<std::string> buttons;
   const V controls=getattr(getattr(app,SY("renderer")),SY("controls"));for(const auto& entry:controls.items()){const V command=entry.idx(1);if(command.len()>=3&&command.idx(0)==SV("texture74")&&command.idx(1)==SV("edit"))buttons.insert(py_str(command.idx(2)));}
   for(const auto& key:needed){need(buttons.contains(key),"actual related-parts browser omitted "+key);op("edit",V(key));const auto* r=tx::resource(key);need(tx::state().selected_key==key&&tx::state().canvas.w==r->w&&tx::state().canvas.h==r->h,"component opened wrong canvas");need(tx::state().canvas.flatten()==tx::pixels(tx::original(*r)),"component editor loaded wrong original");}selectable=true;
  }return {{"linked",linked},{"missing_actual_components",missing},{"coverage_complete",missing.empty()},{"required_for_this_run",complete},{"actual_related_buttons_and_original_canvases",selectable}};
 });
 if(probe_missing)test("injected_missing_original_preserves_editor_transaction",[&]()->J{
  const auto* old=tx::resource("icon:脑光墓碑");need(old,"controlled previous icon absent");auto file=out/"synthetic-previous-green.pvptex";tx::save_file(file,painted(*old,0x66cc66ff));tx::import_pack(file);op("edit",V(old->key));auto& s=tx::state();s.canvas.dot(0,0,1,0x122334ff);s.dirty=true;
  const auto previous_key=s.selected_key;const auto previous_pixels=s.canvas.flatten();const auto previous_canvas=s.canvas;const auto previous_document=s.document;const auto previous_dirty=s.dirty;
  auto& injected=s.resources.at(s.by_key.at(icon->key));struct RestoreFile{std::string& target;std::string previous;~RestoreFile(){target.swap(previous);}} restore_file{injected.file,injected.file};const auto missing=out/"injected-nonexistent-rage.png";need(!std::filesystem::exists(missing),"injected missing path already exists");injected.file=p8(missing);
  op("card",SV("zsecret:暴怒"));const auto notice=s.notice;const bool key_ok=s.selected_key==previous_key,pixels_ok=s.canvas.flatten()==previous_pixels,dirty_ok=s.dirty==previous_dirty;
  // Actual later paint/save, in isolated synthetic userdata only, detects whether
  // the retained canvas can accidentally be committed under the failed key.
  s.canvas.dot(1,0,1,0xaabbccff);s.dirty=true;op("save");const bool wrong_entry=s.document["entries"].contains(icon->key);const bool previous_entry=s.document["entries"].contains(previous_key);
  J observed={{"synthetic_missing_resource_only",true},{"real_png_files_modified",false},{"notice",notice},{"previous_key",previous_key},{"selected_key_after_failure",key_ok?previous_key:icon->key},{"key_preserved",key_ok},{"pixels_preserved",pixels_ok},{"unsaved_flag_preserved",dirty_ok},{"later_save_created_failed_rage_entry",wrong_entry},{"previous_entry_still_present",previous_entry}};std::ofstream(out/"open-failure-observation.json")<<observed.dump(2);
  // Restore fixture identity before a failed assertion or application shutdown.
  s.selected_key=previous_key;s.canvas=previous_canvas;s.document=previous_document;s.dirty=previous_dirty;
  need(notice.find("操作未完成")!=std::string::npos,"missing-resource failure was not reported by actual action");need(key_ok&&pixels_ok&&dirty_ok&&!wrong_entry&&previous_entry,"failed resource load changed canvas identity/dirty state or allowed a later save under the failed Rage key");return observed;
 });
 if(probe_missing)test("same_key_alias_reopen_preserves_unsaved_layers",[&]()->J{
  auto& s=tx::state();op("edit",SV("icon:脑光墓碑"));op("add_layer");s.canvas.layers.back().name="synthetic retained overlay";s.canvas.layers.back().opacity=173;s.canvas.dot(2,1,1,0x9966ccff);s.dirty=true;const auto before=s.canvas.flatten();const auto count=s.canvas.layers.size();const auto name=s.canvas.layers.back().name;const auto opacity=s.canvas.layers.back().opacity;
  tx::open_resource(s.selected_key);need(s.selected_key=="icon:脑光墓碑"&&s.canvas.flatten()==before&&s.canvas.layers.size()==count&&s.canvas.layers.back().name==name&&s.canvas.layers.back().opacity==opacity,"reopening a key aliased to selected_key lost unsaved layers or pixels");need(!s.dirty,"successful same-key reopen did not finish save");return {{"key_argument_aliases_state",true},{"unsaved_layer_count",count},{"layer_name_opacity_and_rgba_preserved",true}};
 });
 std::ofstream(out/"summary.json")<<J{{"passed",failures==0},{"failures",failures},{"checks",checks},{"user_specific_platform_and_saved_state_available",false},{"limits","Real PC shared C++ path with synthetic isolated userdata. Android-layout filesystem resolution tested; Android JNI AssetManager/document picker not executed. Deliberate saved green content and a deliberately missing fixture resource are controlled fault cases, not a reproduction of an unexplained green default."}}.dump(2);callm(app,SY("close"),Args{});callm(battle.battle,SY("close"),Args{});return failures?1:0;
}
