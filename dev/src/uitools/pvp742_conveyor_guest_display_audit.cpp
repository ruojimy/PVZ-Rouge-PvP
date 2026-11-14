// Real host publication / wire decoder / guest merge / WorldView, no user room.
#include "pvp742_guest_memory_fixture.h"
#include "core/trace.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_world_view.h"
#include <set>
using namespace pvz;using namespace pvz::guest_memory_audit;
namespace {
V val(const J& j){return py::json_loads(V(j.dump()));}
struct HostWire:PyObj {
 V incoming=V::list(),sent=V::list();
 const char* type_name()const override{return "ConveyorHostOutbound";}
 V method(Sym n)override{
  if(n==SY("poll"))return V::func([this](const Args&){V out=incoming;incoming=V::list();return out;});
  if(n==SY("send"))return V::func([this](const Args&a){sent.append(a.pos.at(a.pos.size()-1));return V(true);});
  if(n==SY("pending_bytes"))return V::func([](const Args&){return V(0);});
  if(n==SY("close")||n==SY("release_peer")||n==SY("set_max_peers")||n==SY("set_room_policy"))return V::func([](const Args&){return V::none();});
  return V();
 }
};
struct Host {
 BattleHandle h;V room,b,app;pm_room::C_Room* r;pm_app::C_Application* a;std::shared_ptr<HostWire> wire;
 explicit Host():h(battle_from_scenario({{"seed",742},{"night",true},{"durable_heroes",true}})){
  room=pm_room::new_Room(Args{h.bridge,getattr(h.battle,SY("rules"))});r=as<pm_room::C_Room>(room);V rows=V::list();
  for(int y=0;y<24;++y){V row=V::list();for(int x=0;x<72;++x)row.append(pm_maps::f__cell(Args{val({{"方块",y>=20||(y>=16&&x>=42&&x<48)?"土":"空"},{"里方块","空"}}),V::tuple({SV("空"),SV("水"),SV("花盆块"),SV("梯子块"),SV("坟墓")})}));rows.append(row);}
  r->a_map=pm_maps::new_MapSnapshot(Args({SV("传送带客机显示高台"),V(742),SV("conveyor-guest-742"),rows},{{SY("spawns"),val({{"plant",{2184,768}},{"zombie",{1944,960}}})},{SY("source"),SV("conveyor-guest-742")}}));
  r->a_rules=getattr(h.battle,SY("rules"));r->a_seed=V(742);r->a_replay_enabled=V(false);r->a_bans=V::list();r->a_mode=SV("coop");r->a_members=val({{"host","plant"},{"guest","plant2"}});r->a_connected=val({{"host",true},{"guest",true}});r->a_pve=val({{"day",10},{"seed",742},{"deck",{"plant:向日葵","plant:花盆"}},{"max_zombies",40},{"start_sun",100000}});
  callm(room,SY("_start_pve"),Args{});b=r->a_battle;typed72app::start_battle_session(b);r->a_phase=SV("battle");r->a_recording=V::none();r->a_loaded=val({{"plant",true},{"plant2",true}});r->a_match_id=SV("conveyor-guest-actual-match");r->a_match_number=V(1);
  for(const char* side:{"plant","plant2"})callm(b,SY("fixture_set_avatar"),Args{V(side),val({{"玩家位置",{2184,768,0,0}},{"玩家血量",1.e8}})});
  app=pm_app::new_Application(Args{pg::pygame_module(),pg::new_surface(1280,720,true),h.bridge});a=as<pm_app::C_Application>(app);a->a_mode=SV("host");a->a_peer_id=SV("host");a->a_room=room;a->a_game_audio=V::none();setitem(a->a_state,SV("screen"),SV("room"));setitem(a->a_state,SV("focused"),V(false));wire=std::make_shared<HostWire>();a->a_transport=V::inst(wire);
  // Exercise the production synchronous publication fallback. Codec and map
  // invalidation are real; async pack-worker scheduling is a separate audit.
  setattr(app,SY("_snapshot_pack_worker"),V::func([](const Args&){return V::none();}));
 }
 ~Host(){try{a->a_transport=V::none();callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});}catch(...) {}}
 V publish(){wire->sent=V::list();callm(app,SY("publish_network"),Args{V(.2)});V result=V::none();for(const auto& p:wire->sent.items())if(py::m_get(p,SV("type"))==SV("room_snapshot"))result=p;require(!result.is_none(),"production publish_network produced no snapshot");return result;}
 J build(){J first;std::set<std::string> seen;size_t retired=0;for(int t=0;t<2400;++t){callm(b,SY("step"),Args{});r->a_clock=V((t+1)/30.);require(!getattr(b,SY("result")).truthy(),"host battle ended before conveyor");const V objects=getattr(b,SY("_native_objects"));for(const auto& z:json(rd(getattr(b,SY("g")),SV("僵尸")))){const auto id=z.value("_pvp_id",std::string{});if(z.value("_pvp_card",std::string{})=="zombie:传送带僵尸"){if(first.is_null())first=z;}else if(!z.contains("_pvp_grave")&&z.value("血量",0.)>0.){setitem(rd(objects,V(id)),SV("血量"),V(0));++retired;}}
    const V map=getattr(b,SY("map"));const V cells=rd(map,SV("tiles"));for(int y=0;y<int(cells.len());++y)for(int x=0;x<int(cells.idx(y).len());++x){const V cell=cells.idx(y).idx(x);if(py::m_get(py::m_get(cell,SV("native"),V::dict()),SV("_pvp_belt"),V(false)).truthy())return {{"room_steps",t+1},{"row",y},{"col",x},{"cell",json(cell)},{"first_conveyor",first},{"background_units_retired",retired}};}
   }throw std::runtime_error("natural director produced no belt within 2400roomsteps");}
 void reconnect(){wire->incoming=val(J::array({J{{"type","reconnected"},{"peer_id","guest"},{"spectator",false}}}));callm(app,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));require(py::m_get(a->a_sent_map,SV("guest")).is_none(),"host reconnect did not invalidate guest sent_map");}
};
struct Guest {
 V app,screen;pm_app::C_Application* a;Receiver receiver;std::vector<std::string> wire{1};std::unique_ptr<Channel> channel;size_t sequence=0;
 explicit Guest(const V& bridge){screen=pg::new_surface(1280,720,true);app=pm_app::new_Application(Args{pg::pygame_module(),screen,bridge});a=as<pm_app::C_Application>(app);a->a_mode=SV("guest");a->a_peer_id=SV("guest");a->a_game_audio=V::none();a->a_transport=receiver.transport;setitem(a->a_state,SV("screen"),SV("room"));setitem(a->a_state,SV("focused"),V(false));setitem(a->a_state,SV("world_quality"),SV("native"));setitem(a->a_state,SV("zoom"),V(.8));channel=std::make_unique<Channel>(receiver,wire);}
 ~Guest(){channel->finish();a->a_transport=V::none();}
 J receive(const V& payload){wire[0]=py::bytes_data(pm_network::f_encode_frame(Args{py_dict({{SV("type"),SV("data")},{SV("seq"),V(double(++sequence))},{SV("payload"),payload}})}));channel->produce(0);callm(app,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));require(!py::m_get(a->a_state,SV("map_sync_error"),V(false)).truthy(),"guest map_sync_error");require(receiver.client->a__in_seq.num()==double(sequence),"guest dropped wire sequence");return json(a->a_view);}
 void center_cell(int row,int col){const double scale=64.*.8/48.;V rect=callm(pg::pygame_module(),SY("Rect"),Args{V::tuple({V(0),V(0),V(1280),V(720)})});setitem(a->a_state,SV("_render_camera"),V::tuple({V((col+.5)*48.-640./scale),V((row+.5)*48.-360./scale),V(scale),rect,V(72.*48.)}));}
 J draw(const std::filesystem::path& png){callm(app,SY("render"),Args{});const V world=getattr(a->a_renderer,SY("world"));require(py_str(getattr(world,SY("native_error"),SV(""))).empty(),"WorldView native_error");callm(pg::image_module(),SY("save"),Args{screen,V(p8(png))});return {{"pixels_sha256",texture74::digest(std::string(reinterpret_cast<const char*>(texture74::pixels(screen).data()),1280*720*4))},{"native_error",py_str(getattr(world,SY("native_error"),SV("")))}};}
};
J pixel_visibility(Guest& guest,int row,int col,const std::filesystem::path& prefix){
 const V world=getattr(guest.a->a_renderer,SY("world"));const J battle=json(rd(guest.a->a_view,SV("battle")));const J terrain=battle.at("map");const V rect=V::tuple({V(0),V(0),V(1280),V(720)});J removed=battle,ordinary=battle;
 auto& empty=removed["map"]["tiles"][row][col];empty["kind"]="空";empty["ladder"]=false;empty["native"]["方块"]="空";empty["native"]["_pvp_belt"]=false;
 ordinary["map"]["tiles"][row][col]["native"]["_pvp_belt"]=false;
 const V settings=py_dict({{SV("_render_camera"),rd(guest.a->a_state,SV("_render_camera"))}});std::vector<uint32_t> images[3];const J* variants[]={&battle,&removed,&ordinary};for(int i=0;i<3;++i){V screen=pg::new_surface(1280,720,true);callm(screen,SY("fill"),Args{V::tuple({V(11),V(19),V(27),V(255)})});callm(world,SY("render"),Args{screen,val(*variants[i]),rect,SV("plant2"),settings,val(variants[i]->at("map"))});images[i]=texture74::pixels(screen);callm(pg::image_module(),SY("save"),Args{screen,V(p8(prefix)+".tile-control-"+std::to_string(i)+".png")});}
 const auto diff=[](const std::vector<uint32_t>&a,const std::vector<uint32_t>&b){size_t n=0;for(size_t i=0;i<a.size();++i)n+=a[i]!=b[i];return n;};
 const size_t removed_diff=diff(images[0],images[1]),ordinary_diff=diff(images[0],images[2]);J probes=J::object();const V art=getattr(world,SY("art"));
 for(const auto& key:{"传送带块","梯子块"}){const V raw=callm(art,SY("raw"),Args{V(key)});J p={{"raw_none",raw.is_none()},{"cache_contains",py::in(V(key),getattr(art,SY("images")))}};if(!raw.is_none()){const auto pixels=texture74::pixels(raw);p["nontransparent_pixels"]=std::count_if(pixels.begin(),pixels.end(),[](uint32_t c){return (c&255)!=0;});p["width"]=getattr(raw,SY("get_width")).call(Args{}).num();p["height"]=getattr(raw,SY("get_height")).call(Args{}).num();callm(pg::image_module(),SY("save"),Args{raw,V(p8(prefix)+".asset-"+(std::string(key)=="传送带块"?"belt":"ladder")+".png")});}probes[key]=p;}
 // Isolate the exact private tile painter, independent of actors/native frame.
 std::vector<uint32_t> isolated[3];for(int i=0;i<3;++i){V surface=pg::new_surface(64,64,true);callm(surface,SY("fill"),Args{V::tuple({V(11),V(19),V(27),V(255)})});callm(world,SY("_tile"),Args{surface,val(variants[i]->at("map").at("tiles").at(row).at(col)),V::tuple({V(0),V(0),V(64),V(64)}),V(0),V::none(),SV("foreground")});isolated[i]=texture74::pixels(surface);callm(pg::image_module(),SY("save"),Args{surface,V(p8(prefix)+".isolated-tile-"+std::to_string(i)+".png")});}
 std::vector<uint32_t> no_frame[3];for(int i=0;i<3;++i){J b=*variants[i];b.erase("native_frame");V surface=pg::new_surface(1280,720,true);callm(world,SY("render"),Args{surface,val(b),rect,SV("plant2"),settings,val(b.at("map"))});no_frame[i]=texture74::pixels(surface);}
 const V point=callm(world,SY("point"),Args{V(col*48.),V(row*48.)});
 return {{"belt_vs_empty_changed_pixels",removed_diff},{"belt_vs_ordinary_ladder_changed_pixels",ordinary_diff},{"without_native_frame_vs_empty",diff(no_frame[0],no_frame[1])},{"without_native_frame_vs_ladder",diff(no_frame[0],no_frame[2])},{"isolated_tile_vs_empty",diff(isolated[0],isolated[1])},{"isolated_tile_vs_ladder",diff(isolated[0],isolated[2])},{"received_cell",terrain.at("tiles").at(row).at(col)},{"asset_probes",probes},{"cell_screen_point",json(point)},{"camera_scale",getattr(world,SY("camera")).idx(2).num()},{"scope","Same received battle through WorldView; only display-control cell toggled; extra controls remove native_frame or isolate _tile; default local assets"}};
}
bool belt(const J& view,int row,int col){return view.at("battle").at("map").at("tiles").at(row).at(col).at("native").value("_pvp_belt",false);}
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;install_crash_handler();const auto prefix=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(prefix.parent_path());SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();pm_network::init();J report;std::string phase="initialization";
 try{Host host;Guest guest(host.h.bridge);phase="initial_full_wire";const V first=host.publish();const J unpacked_initial=json(pm_app::f_unpack_snapshot(Args{first}));require(unpacked_initial.contains("map")&&unpacked_initial.at("battle").contains("map"),"initial snapshot omits maps");const J initial=guest.receive(first);guest.draw(prefix.string()+".initial.png");
  phase="actual_director_build";const auto built=host.build();report["host_actual_build"]=built;const int row=built.at("row"),col=built.at("col");require(!belt(initial,row,col),"baseline cell already had belt");
  phase="terrain_revision_wire";const V updated=host.publish();const auto raw_update=json(pm_app::f_unpack_snapshot(Args{updated}));require(raw_update.at("battle").contains("map"),"terrain revision change omitted battle map");const auto received=guest.receive(updated);require(belt(received,row,col),"belt lost during codec or guest merge");report["guest_wire_belt"]=true;guest.center_cell(row,col);const auto after_draw=guest.draw(prefix.string()+".after.png");const auto visible=pixel_visibility(guest,row,col,prefix);report["pixel_visibility"]=visible;
  phase="map_omission_retention";const V no_map=host.publish();const auto raw_no_map=json(pm_app::f_unpack_snapshot(Args{no_map}));require(!raw_no_map.contains("map")&&!raw_no_map.at("battle").contains("map"),"unchanged terrain unexpectedly resent full map");const auto retained=guest.receive(no_map);require(belt(retained,row,col),"no-map merge discarded existing belt terrain");
  phase="reconnect_full_wire";host.reconnect();Guest fresh(host.h.bridge);const V reconnected=host.publish();const auto raw_reconnect=json(pm_app::f_unpack_snapshot(Args{reconnected}));require(raw_reconnect.contains("map")&&raw_reconnect.at("battle").contains("map"),"reconnect initial snapshot omitted map");const auto restored=fresh.receive(reconnected);require(belt(restored,row,col),"fresh reconnect guest lost existing belt");fresh.center_cell(row,col);const auto reconnect_draw=fresh.draw(prefix.string()+".reconnect.png");const auto reconnect_visible=pixel_visibility(fresh,row,col,prefix.string()+".reconnect");
  report={{"passed",true},{"host_actual_build",built},{"terrain_revision_before",initial.at("battle").at("terrain_revision")},{"terrain_revision_after",received.at("battle").at("terrain_revision")},{"host_payload_has_updated_map",true},{"guest_wire_belt",true},{"no_map_payload_retained_belt",true},{"host_reconnect_invalidated_sent_map",true},{"fresh_reconnect_belt",true},{"actual_app_render",after_draw},{"pixel_visibility",visible},{"reconnect_app_render",reconnect_draw},{"reconnect_visibility",reconnect_visible},{"scope","Actual Room._start_pve director builds facility; production Application.publish_network synchronous fallback -> pack_snapshot -> encode_frame -> background ClientTransport/FrameDecoder -> UI poll/unpack/merge -> actual Application/WorldView. Transport endpoints only captured/replayed; no cloud sockets, live user pack or user process. Background non-conveyor retirement is the workload fixture; tested conveyor untouched."}};
  phase="visibility_assertions";require(visible.at("belt_vs_empty_changed_pixels").get<size_t>()>0,"actual guest WorldView shows no facility pixels vs empty cell");require(visible.at("belt_vs_ordinary_ladder_changed_pixels").get<size_t>()>0,"belt marker did not change visible pixels vs ordinary ladder");require(reconnect_visible.at("belt_vs_empty_changed_pixels").get<size_t>()>0,"reconnect has no visible belt pixels");
 }catch(const std::exception&e){print_last_cpp_throw(stderr);report["passed"]=false;report["phase"]=phase;report["error"]=e.what();}
 std::ofstream(prefix.string()+".json")<<report.dump(2);std::cout<<report.dump()<<std::endl;return report.value("passed",false)?0:1;
}
