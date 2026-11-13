// Real Application/Room/typed battle regression. Only the transport event source is queued;
// no live game, real user data, network route or remote room is touched.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/function_profile.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_room.h"
#include "ui/gen/pm_adaptive_pacing.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
#include <functional>
#include <cmath>
using namespace pvz;using J=nlohmann::json;
namespace {
J json(const V& v){return J::parse(dump(v));}
V value(const J& j){return py::json_loads(V(j.dump()));}
void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
struct QueuedTransport:PyObj {
 V incoming=V::list(),sent=V::list();
 const char* type_name()const override{return "NetworkRefreshAuditTransport";}
 V method(Sym n)override{
  if(n==SY("poll"))return V::func([this](const Args&){V out=incoming;incoming=V::list();return out;});
  if(n==SY("send")||n==SY("send_spectator"))return V::func([this](const Args& a){sent.append(a.pos.at(a.pos.size()-1));return V(true);});
  if(n==SY("pending_bytes"))return V::func([](const Args&){return V(0);});
  if(n==SY("close")||n==SY("release_peer")||n==SY("set_max_peers")||n==SY("set_room_policy"))return V::func([](const Args&){return V::none();});
  return V();
 }
 void event(const J& j){incoming.append(value(j));}
 void command(const J& input){event({{"type","message"},{"peer_id","guest"},{"payload",{{"type","room_command"},{"payload",{{"type","input"},{"input",input}}}}}});}
};
struct Fixture {
 BattleHandle h;
 V app,battle,room,transport;
 pm_app::C_Application* application=nullptr;
 pm_room::C_Room* r=nullptr;
 std::shared_ptr<QueuedTransport> wire;
 J accepted=J::array();
 std::function<void()> events=[]{};
 explicit Fixture(bool coop=true):h(battle_from_scenario({{"seed",742},{"mode",coop?"coop":"duel"},{"durable_heroes",true},{"campaign_deck",coop}})){
  V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})});
  app=pm_app::new_Application(Args{pg,screen,h.bridge});application=as<pm_app::C_Application>(app);
  callm(app,SY("create"),Args{V(true)});room=getattr(app,SY("room"));r=as<pm_room::C_Room>(room);
  if(coop)require(!callm(room,SY("set_mode"),Args{V("coop")}).truthy(),"cannot configure coop fixture");
  // NativeBattle.map is the live physical projection and may contain changed cells;
  // create the tested battle through Room._start_battle so Room retains its admitted,
  // checksum-valid MapSnapshot exactly as a real match does.
  r->a_rules=getattr(h.battle,SY("rules"));r->a_replay_enabled=V(false);
  r->a_decks=V::dict();for(const auto& item:py::items_vec(getattr(h.battle,SY("players"))))setitem(r->a_decks,item.first,py::list_it(rd(item.second,V("deck"))));
  callm(room,SY("_start_battle"),Args{});battle=r->a_battle;typed72app::start_battle_session(battle);
  r->a_phase=V("battle");r->a_recording=V::none();r->a_match_id=V("network-refresh-audit");r->a_match_number=V(1);
  r->a_loaded=value(coop?J{{"plant",true},{"plant2",true}}:J{{"plant",true},{"zombie",true}});
  application->a_mode=V("host");application->a_peer_id=V("host");application->a_game_audio=V::none();
  wire=std::make_shared<QueuedTransport>();transport=V::inst(wire);application->a_transport=transport;
  setitem(application->a_state,V("focused"),V(false));setitem(application->a_state,V("screen"),V("room"));
  // Replace only SDL event collection; all Application.step/command/poll/refresh and Room methods remain real.
  setattr(app,SY("handle_events"),V::func([this](const Args&){events();return V::none();}));
  setattr(room,SY("command"),V::func([this](const Args& a){V result=r->m_command(a);V p=a.pos.at(1);if(py::m_get(p,V("type"))==V("input"))accepted.push_back({{"peer",py_str(a.pos.at(0))},{"input",json(py::m_get(p,V("input")))},{"error",py_str(result)}});return result;}));
  callm(app,SY("refresh"),Args{});
 }
 ~Fixture(){try{application->a_transport=V::none();callm(app,SY("close_room"),Args{});callm(h.battle,SY("close"),Args{});}catch(...){} }
 int64_t seq(const char* seat){return int64_t(json(getattr(battle,SY("players"))).at(seat).at("seq").get<double>());}
 J frame(double dt=0.){
  const auto deferred0=py::m_get(application->a_state,V("deferred_move_refreshes"),V(0)).num();
  function_profile::reset();const auto start=std::chrono::steady_clock::now();
  callm(app,SY("step"),Args{V(dt),V(false)});
  const double wall=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
  auto times=function_profile::snapshot();const auto row=times["Application::refresh"];
  require(!py::m_get(application->a_state,V("frame_service_active"),V(false)).truthy(),"frame service scope leaked");
  for(const auto& c:accepted)require(c.at("error")=="","input was rejected: "+c.dump());
  return {{"refreshes",row.calls},{"refresh_ms",row.total_ms},{"frame_ms",wall},
          {"typed_snapshot_calls",times["TypedBattle::snapshot"].calls},{"typed_frame_projections",times["TypedBattle::frame_projection"].calls},
          {"typed_frame_projection_ms",times["TypedBattle::frame_projection"].total_ms},
          {"deferred",py::m_get(application->a_state,V("deferred_move_refreshes"),V(0)).num()-deferred0}};
 }
 void no_error_messages(){for(const auto& message:wire->sent.items())require(py::m_get(message,V("type"))!=V("error"),"host emitted input error: "+dump(message));}
};
J move(int64_t seq,int direction=0,bool jump=false){return {{"type","move"},{"seq",seq},{"move",direction},{"jump",jump}};}
bool optimized(){const char* p=std::getenv("PVP742_INPUT_REFRESH");return !p||std::string(p)!="0";}
}
int main(int argc,char**argv){
 if(argc<2||!std::getenv("PVP_USERDATA"))return 2;
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 require(function_profile::enabled(),"run with PVP741_PROFILE=1 to measure real Application refresh calls");
 J checks=J::array();int failures=0;
 auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["error"]=e.what();row["passed"]=false;++failures;}checks.push_back(row);J brief=row;brief.erase("evidence");std::cerr<<brief.dump()<<std::endl;};
 test("production_application_remote_neutral_bursts",[&]{Fixture f;J out=J::array();int64_t seq=0;
  for(int count:{25,50}){const auto before=f.accepted.size();for(int i=0;i<count;++i)f.wire->command(move(++seq));J row=f.frame();
   require(f.accepted.size()-before==size_t(count),"burst lost/coalesced commands");require(f.seq("plant2")==seq,"burst seq acknowledgement wrong");
   require(row["refreshes"]==(optimized()?1:count+1),"real nested input path did not use expected refresh count: "+row.dump());
   require(row["deferred"]==(optimized()?count:0),"deferred count wrong");f.no_error_messages();row["commands"]=count;row["ack_seq"]=seq;out.push_back(row);
  }return out;
 });
 test("production_application_local_burst_and_frame_outside_api",[&]{Fixture f;f.events=[&]{for(int i=0;i<50;++i)require(!callm(f.app,SY("input"),Args({V("plant"),V("move")},{{SY("move"),V(0)},{SY("jump"),V(false)}})).truthy(),"local input rejected");};J row=f.frame();f.events=[]{};
  require(f.accepted.size()==50&&f.seq("plant")==50,"local command seq missing");require(row["refreshes"]==(optimized()?1:51),"local burst not deferred");
  function_profile::reset();require(!callm(f.app,SY("input"),Args({V("plant"),V("move")},{{SY("move"),V(1)},{SY("jump"),V(true)}})).truthy(),"frame-outside input rejected");
  require(function_profile::snapshot()["Application::refresh"].calls==1,"frame-outside local API stopped refreshing");row["outside_refreshes"]=1;row["ack_seq"]=f.seq("plant");return row;
 });
 test("dense_plane_tentacle_view_remote_burst",[&]{Fixture f(false); // duel deliberately avoids co-op's admitted zombie cap
  for(int i=0;i<300;++i){const char* card=i<50?"plant:芦笋战机":i<100?"plant:抓人草":"zombie:普通僵尸";
   callm(f.battle,SY("spawn"),Args{V(card),V(i<100?"plant":"zombie"),V(1800.+(i%50)*12.),V(864.-(i%3)*48.),V(i<100?1:-1)});
  }callm(f.app,SY("refresh"),Args{});const auto units=json(callm(f.battle,SY("snapshot"),Args{})).at("units").size();require(units>=300,"dense view fixture lost actors: "+std::to_string(units));
  for(int seq=1;seq<=25;++seq)f.wire->command(move(seq));J row=f.frame();require(f.seq("zombie")==25,"dense burst acknowledgement lost");require(row["refreshes"]==(optimized()?1:26),"dense burst refresh count wrong");
  f.no_error_messages();row["units"]=units;row["commands"]=25;row["mode"]="duel";row["simulated_ticks"]=getattr(f.battle,SY("tick")).num();return row;
 });
 test("remote_jump_edges_and_non_move_input_order",[&]{Fixture f;J inputs=J::array({move(1,0,false),move(2,1,true),move(3,0,false),move(4,-1,true),J{{"type","gift"},{"seq",5},{"amount",25}},move(6,0,false),move(7,1,true),move(8,0,false)});
  for(const auto& input:inputs)f.wire->command(input);J row=f.frame();J seen=J::array();for(const auto& input:f.accepted)seen.push_back(input["input"]);
  require(seen==inputs,"move/jump/gift order was changed");require(row["refreshes"]==(optimized()?2:9),"nonmove input did not preserve immediate refresh");require(f.seq("plant2")==8,"edge burst final seq differs");
  f.no_error_messages();row["accepted_order"]=seen;row["players"]=json(getattr(f.battle,SY("players")));row["battle"]=json(callm(f.battle,SY("snapshot"),Args{}));return row;
 });
 test("remote_poll_outside_frame_and_reconnection",[&]{Fixture f;for(int i=1;i<=3;++i)f.wire->command(move(i));function_profile::reset();callm(f.app,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));require(function_profile::snapshot()["Application::refresh"].calls==3,"frame-outside remote API stopped refreshing");
  f.wire->event({{"type","disconnected"},{"peer_id","guest"}});f.frame();require(!f.r->a_disconnect_deadline.is_none(),"disconnect did not enter recovery window");
  f.wire->event({{"type","reconnected"},{"peer_id","guest"}});f.wire->command(move(4,1,true));J row=f.frame();require(f.r->a_disconnect_deadline.is_none(),"reconnect did not clear timeout");require(f.seq("plant2")==4,"reconnect failed to accept next sequence");f.no_error_messages();row["ack_seq"]=4;row["outside_refreshes"]=3;return row;
 });
 test("guest_rejoin_restores_acknowledged_sequence",[&]{Fixture host;for(int i=1;i<=50;++i)host.wire->command(move(i));host.frame();
  V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})}),guest=pm_app::new_Application(Args{pg,screen,host.h.bridge});auto* app=as<pm_app::C_Application>(guest);auto wire=std::make_shared<QueuedTransport>();app->a_mode=V("guest");app->a_peer_id=V("guest");app->a_transport=V::inst(wire);
  // A real configuration Room has an explicit battle=None. It is a normal
  // snapshot, not a missing-key error; receiving it must not change seat seq.
  V config_room=pm_room::new_Room(Args{host.h.bridge});
  require(!callm(config_room,SY("set_mode"),Args{V("coop")}).truthy(),"config fixture mode rejected");
  require(!callm(config_room,SY("connect"),Args{V("guest"),V(false),V("plant2")}).truthy(),"config fixture guest rejected");
  V configuration=callm(config_room,SY("snapshot"),Args{V("guest")});
  require(py::m_get(configuration,V("battle")).is_none()&&py::m_get(configuration,V("phase"))==V("config"),"configuration did not preserve explicit battle=None");
  wire->event({{"type","message"},{"peer_id","server"},{"payload",json(pm_app::f_pack_snapshot(Args{configuration}))}});
  callm(guest,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));
  require(app->a_received_snapshots.num()==1&&rd(app->a_sequence,V("plant2")).num()==0,"configuration snapshot changed sequence or was rejected");
  V snapshot=callm(host.room,SY("snapshot"),Args{V("guest")});V packed=pm_app::f_pack_snapshot(Args{snapshot});wire->event({{"type","message"},{"peer_id","server"},{"payload",json(packed)}});
  callm(guest,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));require(rd(app->a_sequence,V("plant2")).num()==50,"guest rejoin did not restore seq from authoritative snapshot");
  const auto before=wire->sent.len();require(!callm(guest,SY("input"),Args({V("plant"),V("move")},{{SY("move"),V(0)},{SY("jump"),V(false)}})).truthy(),"guest move rejected");require(wire->sent.len()>before,"guest heartbeat was not sent");V command=wire->sent.items().back();require(py::m_get(command,V("type"))==V("room_command"),"wrong guest wire envelope");
  host.wire->event({{"type","message"},{"peer_id","guest"},{"payload",json(command)}});host.frame();require(host.seq("plant2")==51,"restored guest seq was rejected by host");host.no_error_messages();app->a_transport=V::none();callm(guest,SY("close_room"),Args{});return J{{"configuration_battle_was_explicit_none",true},{"configuration_seq_unchanged",true},{"restored_seq",50},{"next_accepted_seq",51},{"map_sync_error",py::m_get(app->a_state,V("map_sync_error"),V(false)).truthy()}};
 });
 test("idle_guest_foreground_heartbeat_background_suspension",[&]{Fixture host;
  V pg=pg::pygame_module(),screen=callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(720)})}),guest=pm_app::new_Application(Args{pg,screen,host.h.bridge});auto* app=as<pm_app::C_Application>(guest);auto wire=std::make_shared<QueuedTransport>();app->a_mode=V("guest");app->a_peer_id=V("guest");app->a_transport=V::inst(wire);
  V snapshot=callm(host.room,SY("snapshot"),Args{V("guest")});wire->event({{"type","message"},{"peer_id","server"},{"payload",json(pm_app::f_pack_snapshot(Args{snapshot}))}});callm(guest,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));
  app->a_keys=V::func([](const Args&){return V::dict();});setitem(app->a_state,V("focused"),V(true));setitem(app->a_state,V("screen"),V("room"));
  auto count=[&]{int n=0;for(const V& packet:wire->sent.items())if(py::m_get(packet,V("type"))==V("room_command"))++n;return n;};
  const int initial=count();for(int frame=0;frame<25;++frame)callm(guest,SY("move_inputs"),Args{V(.04)});const int foreground=count()-initial;
  setitem(app->a_state,V("focused"),V(false));for(int frame=0;frame<25;++frame)callm(guest,SY("move_inputs"),Args{V(.04)});const int background=count()-initial-foreground;
  setitem(app->a_state,V("focused"),V(true));callm(guest,SY("move_inputs"),Args{V(.04)});const int resumed=count()-initial-foreground-background;
  require(foreground==25&&background==0&&resumed==1,"real idle heartbeat/focus behavior differs");app->a_transport=V::none();callm(guest,SY("close_room"),Args{});
  return J{{"foreground_idle_commands_per_second",foreground},{"background_idle_commands_per_second",background},{"resumed_first_frame_commands",resumed}};
 });
 test("coop_knockdown_heartbeats_and_real_revival",[&]{Fixture f;V avatars=getattr(f.battle,SY("avatars"));setitem(rd(avatars,V("plant2")),V("玩家血量"),V(0));
  const V start=rd(getattr(f.battle,SY("players")),V("plant"));const double x=py::m_get(start,V("x")).num(),y=py::m_get(start,V("y")).num();
  int64_t seq=0;bool saw_down=false,saw_revived=false;for(int tick=0;tick<160;++tick){
   // Keep the helper in physical contact; the production team scheduler must still
   // accumulate all four seconds and emit its own revival, without setting positive HP.
   V live_avatars=getattr(f.battle,SY("avatars"));for(const char* seat:{"plant","plant2"})setitem(rd(live_avatars,V(seat)),V("玩家位置"),V::list({V(x),V(y),V(0),V(0)}));
   f.wire->command(move(++seq));f.frame(1./30.);const double hp=py::m_get(rd(getattr(f.battle,SY("players")),V("plant2")),V("hp")).num();saw_down|=hp<=0.;if(saw_down&&hp>0.){saw_revived=true;break;}require(f.r->a_phase==V("battle"),"coop ended during teammate revival");}
  require(saw_down&&saw_revived&&seq>=120,"fixture did not exercise real coop knockdown and 4-second teammate revival");J revived_events=J::array();for(const auto& event:json(getattr(f.battle,SY("log"))))if(event.is_object()&&event.value("event",std::string{})=="hero_revived")revived_events.push_back(event);require(!revived_events.empty(),"positive HP was not caused by the production hero_revived event");require(f.seq("plant2")==seq,"revival sequence acknowledgement wrong");f.no_error_messages();require(f.r->a_disconnect_deadline.is_none(),"revival created disconnect timeout");return J{{"saw_downed",saw_down},{"saw_revived",saw_revived},{"heartbeats_accepted",seq},{"revival_events",revived_events},{"players",json(getattr(f.battle,SY("players")))}};
 });
 test("real_room_keeps_long_frame_credit_and_drains_zero_delta",[&]{Fixture f;
  f.r->a__paced_battle=f.battle;auto* pacing=as<pm_adaptive_pacing::C_AdaptivePacing>(f.r->a_pacing);pacing->frame_gated=true;pacing->a_scale=V(1.);f.application->a_ai_room=V::none();
  const double dt=getattr(f.battle,SY("dt")).num();const int64_t before=int64_t(getattr(f.battle,SY("tick")).num());J first=f.frame(1.7);const int64_t initial=int64_t(getattr(f.battle,SY("tick")).num())-before;
  const double debt=f.r->a_accumulator.num();require(initial==12,"long frame did not respect Room's 12-tick work cap");require(std::abs(debt-(1.7-12*dt))<1e-8,"Application clipped credited elapsed time before Room accumulator");
  int drain_frames=0;while(f.r->a_accumulator.num()+1e-9>=dt&&drain_frames++<12)f.frame(0.);const double elapsed=getattr(f.battle,SY("time")).num();
  require(std::abs(elapsed-1.7)<1e-8,"zero-delta draining lost simulated wall-clock credit");require(std::abs(f.r->a_accumulator.num())<1e-8,"remaining accumulator after drain differs");
  return J{{"first_frame_ticks",initial},{"first_frame_credit_remaining_seconds",debt},{"drain_frames",drain_frames},{"simulated_seconds",elapsed},{"remaining_seconds",f.r->a_accumulator.num()},{"frame_measurement",first}};
 });
 test("real_application_lifecycle_discards_suspension_interval",[&]{Fixture f;
  f.r->a__paced_battle=f.battle;auto* pacing=as<pm_adaptive_pacing::C_AdaptivePacing>(f.r->a_pacing);pacing->frame_gated=true;pacing->a_scale=V(1.);f.application->a_ai_room=V::none();
  f.frame(.1);const double before=getattr(f.battle,SY("time")).num();setitem(f.application->a_state,V("wall_clock_debt"),V(5.));
  callm(f.app,SY("app_background"),Args{});callm(f.app,SY("app_foreground"),Args{});require(py::m_get(f.application->a_state,V("wall_clock_debt")).num()==0.,"lifecycle retained outer wall-clock debt");
  f.frame(1.7);const double resumed=getattr(f.battle,SY("time")).num();require(std::abs(resumed-before)<1e-8,"first resumed frame credited the suspension interval");
  f.frame(getattr(f.battle,SY("dt")).num());const double after=getattr(f.battle,SY("time")).num();require(after>resumed,"normal clock advancement did not resume after lifecycle reset");
  f.no_error_messages();return J{{"before_suspension_seconds",before},{"first_resumed_frame_seconds",resumed},{"next_frame_seconds",after},{"discarded_suspension_seconds",1.7},{"outer_debt",py::m_get(f.application->a_state,V("wall_clock_debt")).num()}};
 });
 J report={{"test","pvp742_network_refresh_audit"},{"optimized",optimized()},{"transport","queued event source; production Application.step, Room and typed battle"},{"failures",failures},{"checks",checks}};std::ofstream(argv[1])<<report.dump(2);std::cout<<"failures="<<failures<<std::endl;return failures?1:0;
}
