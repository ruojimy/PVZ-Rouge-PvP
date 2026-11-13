// Dynamic typed host -> real wire decode / merge -> real Application / world replay.
#include "pvp742_guest_memory_fixture.h"
#include "core/function_profile.h"
#include "core/sym.h"
#include "core/trace.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/hand/draw_replay_diagnostics.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_native_style.h"
#include "ui/gen/pm_native_animation_pixels.h"
#include "pg/render_stats.h"
#include <unordered_set>
using namespace pvz;using J=nlohmann::json;using namespace pvz::guest_memory_audit;
namespace {
uint64_t length(const V& v){return v.has()&&!v.is_none()?uint64_t(py::len(v).num()):0;}
uint64_t pixels(const V& v){if(auto* image=as<pg::Surface>(v))return image->s?uint64_t(image->s->pitch)*uint64_t(image->h()):0;return 0;}
const pg::Surface* storage_owner(const V& v){const auto* surface=as<pg::Surface>(v);for(int depth=0;surface&&surface->parent.has()&&!surface->parent.is_none();++depth){require(depth<128,"Surface parent chain cycle");surface=as<pg::Surface>(surface->parent);}return surface;}
struct Storage {std::unordered_set<const pg::Surface*> seen;uint64_t visible=0,retained=0,parents=0;void add(const V& v){auto* surface=as<pg::Surface>(v);if(!surface)return;visible+=pixels(v);if(surface->parent.has()&&!surface->parent.is_none())++parents;const auto* root=storage_owner(v);if(root&&seen.insert(root).second)retained+=root->s?uint64_t(root->s->pitch)*uint64_t(root->h()):0;}};
J check_surface_copy(){
 V base=pg::new_surface(2048,2048,true);std::weak_ptr<PyObj> weak=base.box->inst;
 V crop=callm(base,SY("subsurface"),Args{pg::make_rect(100,100,8,8)});require(storage_owner(crop)==as<pg::Surface>(base),"subsurface did not retain real parent");
 V copy=callm(crop,SY("copy"),Args{}),scaled=callm(pg::transform_module(),SY("scale"),Args{copy,V::nums({16,16})});
 require(!as<pg::Surface>(copy)->parent.has()&&storage_owner(copy)==as<pg::Surface>(copy),"cropped copy retained parent backing");
 require(!as<pg::Surface>(scaled)->parent.has()&&storage_owner(scaled)==as<pg::Surface>(scaled),"scaled copy retained parent backing");
 require(as<pg::Surface>(copy)->s->pixels!=as<pg::Surface>(crop)->s->pixels,"copy did not allocate independent pixel storage");base=V::none();crop=V::none();require(weak.expired(),"large source stayed alive after only copied crop and scale remained");
 return {{"passed",true},{"source_bytes",2048*2048*4},{"crop_copy_owned_bytes",pixels(copy)},{"scaled_owned_bytes",pixels(scaled)},{"source_released",weak.expired()},{"copied_parent_chain_empty",true}};
}
struct DrawStats {
 uint64_t recipe_items=0,recipe_bytes=0,local_items=0,local_bytes=0,asset_items=0,frame_keys=0,frame_key_bytes=0;
 uint64_t source_items=0,source_surface_bytes=0,dynamic_loads=0,renderer_images=0,renderer_scaled=0,art_images=0,art_scaled=0,visuals=0,world_layer_bytes=0;
 uint64_t runtime_creations=0,world_runtime_creations=0,symbols=0;pg::ReplayAssetCacheStats resolved;gfx::AtlasPixelCacheStats sampled,bridge;
 uint64_t recipe_visible=0,recipe_retained=0,recipe_parents=0,local_visible=0,local_retained=0,local_parents=0;pg::SurfaceMemoryStats surfaces;
};
DrawStats draw_stats(const V& renderer){
 DrawStats s;s.surfaces=pg::surface_memory_stats();s.symbols=sym_count();s.resolved=pg::replay_asset_cache_stats();s.sampled=gfx::sampled_atlas_pixel_cache_stats();s.bridge=gfx::native_bridge_surface_cache_stats();
 s.renderer_images=length(getattr(renderer,SY("images")));s.renderer_scaled=length(getattr(renderer,SY("scaled")));
 {const auto profile=function_profile::snapshot();if(auto i=profile.find("NativeRuntime::init");i!=profile.end())s.runtime_creations=i->second.calls;if(auto i=profile.find("WorldView::create_native_replay");i!=profile.end())s.world_runtime_creations=i->second.calls;}
 const auto world=getattr(renderer,SY("world"),V::none());if(world.is_none())return s;auto* w=as<pm_world_view::C_WorldView>(world);
 const auto replay=getattr(world,SY("_native_replay"),V::none());
 if(!replay.is_none()){
  s.recipe_items=length(getattr(replay,SY("cache")));s.recipe_bytes=uint64_t(getattr(replay,SY("cache_bytes")).num());s.local_items=length(getattr(replay,SY("_local_scaled")));s.local_bytes=uint64_t(getattr(replay,SY("local_bytes")).num());s.asset_items=length(getattr(replay,SY("assets")));s.frame_keys=length(getattr(replay,SY("_frame_keys")));s.frame_key_bytes=uint64_t(getattr(replay,SY("_frame_key_bytes")).num());
  {Storage main,local;V main_values=py::iter_list(callm(getattr(replay,SY("cache")),SY("values"),Args{})),local_values=py::iter_list(callm(getattr(replay,SY("_local_scaled")),SY("values"),Args{}));for(const auto& image:main_values.items())main.add(image);for(const auto& entry:local_values.items()){local.add(entry.idx(0));local.add(entry.idx(1));}s.recipe_visible=main.visible;s.recipe_retained=main.retained;s.recipe_parents=main.parents;s.local_visible=local.visible;s.local_retained=local.retained;s.local_parents=local.parents;}
 }
 const auto graphics=getattr(world,SY("_native_graphics"),V::none());
 if(!graphics.is_none()){
  const auto sources=getattr(graphics,SY("sources"));s.source_items=length(sources);
  {std::unordered_set<const pg::Surface*> seen;for(const auto& [key,image]:py::items_vec(sources))if(auto* surface=as<pg::Surface>(image))if(seen.insert(surface).second)s.source_surface_bytes+=pixels(image);}
 }
 s.dynamic_loads=uint64_t(w->a__native_dynamic_loads.num());s.visuals=length(w->a_last_visuals);
 const auto layer=getattr(world,SY("_world_layer"),V::none());if(!layer.is_none())s.world_layer_bytes=pixels(getattr(layer,SY("surface"),V::none()));
 s.renderer_images=length(getattr(renderer,SY("images")));s.renderer_scaled=length(getattr(renderer,SY("scaled")));
 const auto art=getattr(world,SY("art"));s.art_images=length(getattr(art,SY("images")));s.art_scaled=length(getattr(art,SY("scaled")));
 {const auto profile=function_profile::snapshot();if(auto i=profile.find("NativeRuntime::init");i!=profile.end())s.runtime_creations=i->second.calls;if(auto i=profile.find("WorldView::create_native_replay");i!=profile.end())s.world_runtime_creations=i->second.calls;}
 s.symbols=sym_count();s.resolved=pg::replay_asset_cache_stats();s.sampled=gfx::sampled_atlas_pixel_cache_stats();s.bridge=gfx::native_bridge_surface_cache_stats();return s;
}
J draw_json(const DrawStats& s){return {{"surface_live_instances",s.surfaces.live_surfaces},{"surface_live_owned_bytes",s.surfaces.owned_bytes},{"surface_peak_owned_bytes",s.surfaces.peak_owned_bytes},{"recipe_visible_bytes",s.recipe_visible},{"recipe_backing_retained_bytes",s.recipe_retained},{"recipe_parented_surfaces",s.recipe_parents},{"local_visible_bytes",s.local_visible},{"local_backing_retained_bytes",s.local_retained},{"local_parented_surfaces",s.local_parents},{"recipe_items",s.recipe_items},{"recipe_bytes",s.recipe_bytes},{"local_items",s.local_items},{"local_bytes",s.local_bytes},{"replay_asset_items",s.asset_items},{"frame_key_items",s.frame_keys},{"frame_key_bytes",s.frame_key_bytes},{"world_sources",s.source_items},{"world_source_surface_bytes",s.source_surface_bytes},{"dynamic_loads",s.dynamic_loads},{"renderer_images",s.renderer_images},{"renderer_scaled",s.renderer_scaled},{"art_images",s.art_images},{"art_scaled",s.art_scaled},{"last_visuals",s.visuals},{"world_layer_bytes",s.world_layer_bytes},{"native_runtime_creations",s.runtime_creations},{"world_runtime_creations",s.world_runtime_creations},{"interned_symbols",s.symbols},{"resolved_asset_cache",{{"items",s.resolved.entries},{"bytes",s.resolved.bytes},{"dynamic_items",s.resolved.dynamic_entries},{"dynamic_bytes",s.resolved.dynamic_bytes},{"max_width",s.resolved.max_width},{"max_height",s.resolved.max_height}}},{"sampled_png_cache",{{"items",s.sampled.entries},{"bytes",s.sampled.bytes}}},{"bridge_surface_cache",{{"items",s.bridge.entries},{"bytes",s.bridge.bytes}}}};}
struct FrameSample {size_t frame=0;uint64_t live=0,peak=0,private_memory=0,slab=0,units=0,commands=0,entities=0;double step_ms=0,network_ms=0,render_ms=0;DrawStats draw;};
}
int main(int argc,char** argv){
 install_crash_handler();
 if(argc<3)return 2;const auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output.parent_path());const std::string scene=argv[2];const int frames=argc>3?std::stoi(argv[3]):64,units=argc>4?std::stoi(argv[4]):120,cap_mib=argc>5?std::stoi(argv[5]):256;const uint64_t cap_bytes=uint64_t(cap_mib)*1024*1024;
 std::vector<FrameSample> samples;samples.reserve(size_t(std::max(0,frames))+3);J report;std::string phase="setup";int frame=-1;bool tracing=false;
 try{
  require(scene=="mixed"||scene=="grabber"||scene=="dense","invalid scene");require(cap_mib==256||(cap_mib==512&&scene=="grabber"&&units==120&&frames==64),"512MiB permitted only for the bounded 60root/180head/60zombie64frame check");require(frames>=64&&frames<=256&&units>=20&&units<=240,"bounded fixture: 64..256 frames, 20..240 units");
  env_set_u8("PVP_USERDATA",p8(output.parent_path()/u8p(output.stem().string()+"-userdata")));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");env_set_u8("PVP741_PROFILE","1");env_set_u8("PVP742_SURFACE_MEMORY","1");
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();(void)callm(pg::pygame_module(),SY("init"),Args{});init_pvp_modules();pm_network::init();const auto copy_check=check_surface_copy();
  auto source=battle_from_scenario({{"seed",742},{"rules",{{"plant_slots",16},{"hero_hp",1.e8}}},{"decks",{{"plant",{"plant:向日葵","plant:杨桃","plant:香蒲","plant:机枪射手","plant:抓人草","plant:芦笋战机","secret:密植","secret:触手"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}}}});
  V room=pm_room::new_Room(Args{source.bridge,getattr(source.battle,SY("rules"))});auto* host=as<pm_room::C_Room>(room);setitem(host->a_members,SV("guest"),SV("zombie"));setitem(host->a_connected,SV("guest"),V(true));host->a_decks=V::dict();for(const auto& item:py::items_vec(getattr(source.battle,SY("players"))))setitem(host->a_decks,item.first,py::list_it(rd(item.second,SV("deck"))));
  // A legal MapSnapshot, admitted by the real Room constructor path. Roots are
  // on a flat ground line, avoiding a map-dependent buried plant fixture.
  V rows=V::list();for(int y=0;y<24;++y){V row=V::list();for(int x=0;x<72;++x)row.append(pm_maps::f__cell(Args{py_dict({{SV("方块"),V(y>=20?"土":"空")},{SV("里方块"),SV("空")}}),V::tuple({SV("空"),SV("水"),SV("花盆块"),SV("梯子块"),SV("坟墓")})}));rows.append(row);}
  host->a_map=pm_maps::new_MapSnapshot(Args({SV("动态渲染平地测试"),V(742),SV("memory742"),rows},{{SY("spawns"),py_dict({{SV("plant"),V::nums({1008.,960.})},{SV("zombie"),V::nums({1680.,960.})}})},{SY("source"),SV("memory742")}}));host->a_seed=V(742);host->a_map_id=SV("动态渲染平地测试");
  callm(room,SY("_start_battle"),Args{});host->a_phase=SV("battle");host->a_recording=V::none();host->a_match_id=SV("dynamic-render-memory-audit");host->a_match_number=V(1);host->a_loading_id=SV("dynamic-render-loading");host->a_loaded=py_dict({{SV("plant"),V(true)},{SV("zombie"),V(true)}});host->a_pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});typed72app::start_battle_session(host->a_battle);const V battle=host->a_battle;
  for(const char* side:{"plant","zombie"}){V hero=rd(getattr(battle,SY("avatars")),V(side));setitem(hero,SV("玩家位置"),V::nums({std::string(side)=="plant"?1008.:1680.,960.,0.,0.}));setitem(hero,SV("玩家血量"),V(1.e8));}
  std::vector<std::string> roots;const char* mix[]={"plant:杨桃","plant:香蒲","plant:机枪射手","plant:芦笋战机","plant:抓人草"};
  for(int i=0;i<units;++i){const bool plant=i%2==0;const auto key=plant?(scene=="grabber"?"plant:抓人草":mix[(i/2)%5]):"zombie:普通僵尸";const double x=plant?(scene=="dense"?1008.:864.+((i/2)%8)*48.):1392.+((i/2)%12)*24.;V spawned=callm(battle,SY("spawn"),Args{V(key),V(plant?"plant":"zombie"),V(x),V(960),V(plant?1:-1)});require(!spawned.is_none(),std::string("spawn failed: ")+key);V id=rd(spawned,SV("id"));V record=rd(getattr(battle,SY("_native_objects")),id);if(plant){setitem(record,SV("植物血"),V(1.e8));setitem(record,SV("植物血上限"),V(1.e8));if(std::string(key)=="plant:抓人草")roots.push_back(py_str(id));}else{setitem(record,SV("血量"),V(1.e8));setitem(record,SV("_pvp_max_hp"),V(1.e8));setitem(record,SV("黄油"),V(1.e8));setitem(record,SV("啃咬"),V(1.e8));}}
  for(int cycle=0;cycle<2;++cycle){for(const auto& id:roots)setitem(rd(getattr(battle,SY("_native_objects")),V(id)),SV("_pvp70_clock"),V(10000));callm(battle,SY("step"),Args{V(1)});}
  V pygame=pg::pygame_module(),screen=pg::new_surface(1280,720,true),app=pm_app::new_Application(Args{pygame,screen,source.bridge});auto* guest=as<pm_app::C_Application>(app);guest->a_mode=SV("guest");guest->a_peer_id=SV("guest");guest->a_game_audio=V::none();setitem(guest->a_state,SV("screen"),SV("room"));setitem(guest->a_state,SV("focused"),V(false));setitem(guest->a_state,SV("world_quality"),SV("native"));setitem(guest->a_state,SV("zoom"),V(.8));
  double clock=0.;setattr(guest->a_presentation,SY("clock"),V::func([&](const Args&){return V(clock);}));V renderer=guest->a_renderer;std::vector<std::string> wire(1);Receiver receiver;guest->a_transport=receiver.transport;Channel channel(receiver,wire);size_t sequence=0;const uint64_t baseline_private=private_bytes(),baseline_slabs=native_small_allocator_stats().slab_bytes;const auto baseline_draw=draw_stats(renderer);bool stopped=false;
  native_alloc_trace_start();tracing=true;
  for(frame=0;frame<frames;++frame){FrameSample sample;sample.frame=size_t(frame);phase="typed_step";auto t=std::chrono::steady_clock::now();callm(battle,SY("step"),Args{V(1)});host->a_clock=V((frame+1)/30.);sample.step_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();
   phase="pack_decode_merge";t=std::chrono::steady_clock::now();{V snapshot=callm(room,SY("snapshot"),Args{SV("guest"),V(frame==0)});V payload=pm_app::f_pack_snapshot(Args{snapshot});wire[0]=py::bytes_data(pm_network::f_encode_frame(Args{py_dict({{SV("type"),SV("data")},{SV("seq"),V(double(++sequence))},{SV("payload"),payload}})}));}channel.produce(0);clock=(frame+1)/30.;callm(app,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));sample.network_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();require(!py::m_get(guest->a_state,SV("map_sync_error"),V(false)).truthy(),"guest map validation failed");
   phase="render";clock=(frame+1)/30.+1./60.;t=std::chrono::steady_clock::now();callm(app,SY("render"),Args{});sample.render_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();const V world=getattr(renderer,SY("world"));const auto error=py_str(getattr(world,SY("native_error"),SV("")));require(error.empty(),"actual world replay failed: "+error);
   phase="sample";{const auto view_battle=py::m_get(guest->a_view,SV("battle"));sample.units=length(py::m_get(view_battle,SV("units")));sample.commands=length(py::m_get(py::m_get(view_battle,SV("native_frame")),SV("commands")));}sample.draw=draw_stats(renderer);sample.private_memory=private_bytes();sample.slab=native_small_allocator_stats().slab_bytes;native_alloc_trace_read(sample.live,sample.peak);samples.push_back(sample);native_alloc_trace_reset_peak();
   if(sample.private_memory>=baseline_private+cap_bytes){stopped=true;break;}
  }
  uint64_t held_live=0,held_peak=0;native_alloc_trace_read(held_live,held_peak);native_alloc_trace_stop();tracing=false;phase="final_compare";
  const auto host_state=json(callm(battle,SY("snapshot"),Args{})),final_view=json(guest->a_view);const auto state_hash=texture74::digest(host_state.dump());const auto frame_hash=texture74::digest(host_state.value("native_frame",J(nullptr)).dump());const auto view_hash=texture74::digest(final_view.dump());const auto pixel_hash=texture74::digest(py::bytes_data(callm(pg::image_module(),SY("tobytes"),Args{screen,SV("RGBA")})));
  const auto last_draw=draw_stats(renderer);callm(app,SY("close_room"),Args({},{{SY("graceful"),V(false)}}));channel.finish();
  report={{"passed",true},{"surface_copy_storage_check",copy_check},{"scene",scene},{"allocator",native_small_allocator_stats().legacy?0:1},{"requested_frames",frames},{"completed_frames",samples.size()},{"requested_units",units},{"stopped_at_memory_cap",stopped},{"private_growth_cap_bytes",cap_bytes},{"baseline_private_bytes",baseline_private},{"final_private_bytes",private_bytes()},{"slab_bytes_added",native_small_allocator_stats().slab_bytes-baseline_slabs},{"requested_held_live_bytes",held_live},{"host_state_sha256",state_hash},{"native_frame_sha256",frame_hash},{"guest_view_sha256",view_hash},{"rendered_pixels_sha256",pixel_hash},{"draw_before",draw_json(baseline_draw)},{"draw_after",draw_json(last_draw)},{"scope","Real typed NativeBattle.step(1) each frame; one Room snapshot, real zlib pack and background outer FrameDecoder, UI poll/unpack/merge, actual Application.render / world DrawReplay. One overwriting wire slot, fixed simulation inputs and presentation clock, no live sockets / user saves. Growth stops at the reported bounded private-growth cap, including first-render resource warmup. No scene is claimed stable when stopped early."}};
  callm(room,SY("close"),Args{});callm(source.battle,SY("close"),Args{});
 }catch(const std::exception& e){print_last_cpp_throw(stderr);if(tracing)native_alloc_trace_stop();report={{"passed",false},{"scene",scene},{"frame",frame},{"phase",phase},{"error",e.what()},{"completed_frames",samples.size()},{"private_bytes",private_bytes()}};}
 J rows=J::array();for(const auto& s:samples)rows.push_back({{"frame",s.frame},{"requested_live_bytes",s.live},{"requested_peak_bytes",s.peak},{"private_bytes",s.private_memory},{"slab_bytes",s.slab},{"units",s.units},{"draw_commands",s.commands},{"step_ms",s.step_ms},{"network_ms",s.network_ms},{"render_ms",s.render_ms},{"draw",draw_json(s.draw)}});report["samples"]=rows;std::ofstream(output,std::ios::binary)<<report.dump(2);std::cout<<J{{"passed",report.value("passed",false)},{"scene",scene},{"completed_frames",report.value("completed_frames",size_t(0))},{"phase",report.value("phase",std::string{})},{"error",report.value("error",std::string{})}}.dump()<<'\n';return report.value("passed",false)?0:1;
}
