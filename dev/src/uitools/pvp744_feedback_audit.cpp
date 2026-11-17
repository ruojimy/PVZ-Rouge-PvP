#include "pg/pg.h"
#include "pg/motion_sensor.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_touch.h"
#include "ui/hand/texture74_internal.h"
#include "ui/hand/test_mode74.h"
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;using Session=typed72app::Session;
namespace {
void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
V val(const J& j){return py::json_loads(V(j.dump()));}
J json(const V& v){return J::parse(dump(v));}
void steps(Session& s,int n){for(int i=0;i<n;++i)s.step();}
J zombies(Session& s){return s.native_view()["g"]["僵尸"];}
J waves(Session& s){return s.snapshot(false,false)["team"]["waves"];}
std::unique_ptr<Session> coop(int day,const char* mode="coop",int cap=40,bool delayed=false){
 J scenario={{"fixture_flat",true},{"seed",744},{"mode",mode},{"night",false},{"weather","clear"},{"durable_heroes",true},{"campaign_deck",true},
 {"decks",{{"plant",{"plant:豌豆射手"}},{"plant2",{"plant:向日葵"}},{"zombie",{"zombie:普通僵尸"}}}},
 {"rules",{{"deathmatch_seconds",100000.},{"pve_max_zombies",cap}}},{"director",{{"day",day},{"seed",744},{"max_zombies",cap}}}};
 auto h=battle_from_scenario(scenario);auto cold=typed72app::export_cold(h.battle,744.);callm(h.battle,SY("close"),Args{});
 cold.cold["director"]["plan"]=J::array({{{"time",delayed?100000.:0.},{"budget",225},{"flag",false}}});
 cold.cold["scripted_spawn_limit"]=cap;cold.cold["director"]["max_zombies"]=cap;
 cold.cold["director"]["pool"]=J::array({J::array({"zombie:普通僵尸",1,1.})});
 return Session::create(std::move(cold),"coop-feedback-audit");
}
int types(Session& s,int type){int n=0;for(const auto& u:zombies(s))if(u.contains("terraria")&&u["terraria"]["type"]==type)++n;return n;}
std::vector<std::string> wave_ids(Session& s){std::vector<std::string> ids;for(const auto& z:zombies(s))if(z.contains("_pvp_wave_index"))ids.push_back(z["_pvp_id"]);return ids;}
void kill(Session& s,const std::string& id){s.native_set(false,id,{{"血量",0.}});}
V tuple(std::initializer_list<V> values){return V::tuple(values);}
V hitpoint(V renderer,V action){auto controls=getattr(renderer,SY("controls"));for(size_t i=0;i<controls.len();++i){auto c=controls.idx(i);if(c.idx(1)==action)return getattr(c.idx(0),SY("center"));}throw std::runtime_error("missing clickable control: "+dump(action));}
}
int main(int argc,char** argv){
 if(argc<2)return 2;auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output);
 env_set_u8("PVP_USERDATA",p8(output/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J checks=J::array();int failures=0;auto check=[&](std::string name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failures;}checks.push_back(row);std::cerr<<row.dump()<<std::endl;};
 check("gyro_no_startup_bias_symmetric_all_orientations",[]()->J{
  for(auto o:{SDL_ORIENTATION_PORTRAIT,SDL_ORIENTATION_LANDSCAPE,SDL_ORIENTATION_PORTRAIT_FLIPPED,SDL_ORIENTATION_LANDSCAPE_FLIPPED}){
   int axis=(o==SDL_ORIENTATION_LANDSCAPE||o==SDL_ORIENTATION_LANDSCAPE_FLIPPED)?1:0;double sign=(o==SDL_ORIENTATION_LANDSCAPE||o==SDL_ORIENTATION_PORTRAIT_FLIPPED)?-1.:1.;
   pg::MotionTilt f;std::array<double,3> a{0,0,8.492808};a[axis]=-4.903325*sign;
   need(std::abs(f.sample(a,{0,0,0},.016,o,false)-30.)<.01,"startup incorrectly rebased tilted phone");double angle=0;
   for(int i=0;i<500;++i)angle=f.sample({0,0,9.80665},{0,0,0},.016,o,false);need(std::abs(angle)<.01,"flat drifts after tilted startup");
   for(int direction:{-1,1}){a[axis]=direction*-4.903325*sign;for(int i=0;i<500;++i)angle=f.sample(a,{0,0,0},.016,o,false);need(std::abs(angle-direction*30.)<.01,"unequal left/right thresholds");}
  }return true;
 });
 for(int day:{8,16,24})check("coop_boss_day_"+std::to_string(day),[&,day]()->J{
  auto s=coop(day);steps(*s,150);auto ids=wave_ids(*s);need(ids.size()==10,"expected ten final-wave units: "+waves(*s).dump());need(!waves(*s)["boss_spawned"].get<bool>(),"early boss");
  for(int i=0;i<7;++i)kill(*s,ids[i]);steps(*s,1);need(waves(*s)["clear_percent"]==70&&!waves(*s)["boss_spawned"].get<bool>(),"boss before 80 percent");
  kill(*s,ids[7]);steps(*s,1);auto triggered=waves(*s);need(triggered["boss_spawned"]==true&&triggered["boss_active"]==true,"missing boss at 80 percent: "+triggered.dump());
  int type=day==8?4:day==16?13:35;need(types(*s,type)==1,"wrong boss root");if(day==16)need(types(*s,14)==65&&types(*s,15)==1,"incomplete worm");if(day==24){steps(*s,1);need(types(*s,36)==2,"missing hands");}
  for(const auto& z:zombies(*s))if(z.contains("terraria")){int t=z["terraria"]["type"];double expected=t==4?2800.:t==35?4400.:t==36?600.:150.;need(std::abs(z["血量"].get<double>()-expected)<.01,"ordinary boss health scaled by campaign");}
  need(!s->command("plant",{{"type","test_mode"},{"op","economy"},{"value",100000}}).empty(),"coop gained cheats");need(!s->spawn("zombie:克苏鲁之眼","zombie",100.,100.,1.,false),"player can summon test-only boss");
  need(s->coop_map_night()==std::optional<bool>(true),"boss day not night");
  for(int i=8;i<10;++i)kill(*s,ids[i]);steps(*s,2);need(!s->finished(),"victory before boss defeated");
  if(day==16){std::string head;for(const auto& z:zombies(*s))if(z.contains("terraria")&&z["terraria"]["type"]==13)head=z["_pvp_id"];kill(*s,head);steps(*s,2);need(!s->finished()&&waves(*s)["boss_active"]==true,"head kill ended surviving worm");}
  for(int round=0;round<4&&!s->finished();++round){for(const auto& z:zombies(*s))kill(*s,z["_pvp_id"]);steps(*s,2);}steps(*s,65);need(s->finished()&&s->result_json()["winner"]=="plant","boss defeat did not clear day");need(s->result_json().value("diamond_coins",0.)==1000.,"boss diamond not credited once");
  int events=0;for(const auto& e:s->events(10000))if(e.value("event",std::string{})=="pve_boss")++events;need(events==1,"duplicate boss spawn event");return triggered;
 });
 check("boss_waits_for_final_wave_queue",[]()->J{auto s=coop(8,"coop",2);steps(*s,150);auto ids=wave_ids(*s);need(!ids.empty()&&ids.size()<=2,"cap fixture: "+waves(*s).dump()+" ids="+std::to_string(ids.size()));for(const auto& id:ids)kill(*s,id);steps(*s,1);auto w=waves(*s);need(w["spawn_queued"].get<int>()>0&&w["boss_spawned"]==false,"partial-wave clear spawned boss");return w;});
 check("ordinary_days_and_single_pve_keep_original_rules",[]()->J{for(auto pair:{std::pair{7,"coop"},std::pair{9,"coop"},std::pair{8,"pve"}}){auto s=coop(pair.first,pair.second);steps(*s,1);need(!waves(*s).contains("boss_card"),"boss metadata leaked to ordinary day");if(std::string(pair.second)=="coop"){auto first=s->coop_map_night();steps(*s,3630);need(first!=s->coop_map_night(),"ordinary cycle frozen");}}return true;});
 check("permanent_night_survives_two_phase_boundaries",[]()->J{J evidence=J::array();for(int day:{8,16,24}){auto s=coop(day,"coop",40,true);for(int tick=1;tick<=7202;++tick){s->step();if(tick==1||tick==3602||tick==7202){need(s->coop_map_night()==std::optional<bool>(true),"special day became daylight");auto snapshot=s->snapshot(false,false);for(const auto& r:snapshot["resources"])need(r.value("source",std::string{})!="sky","sky sun fell on permanent night");evidence.push_back({{"day",day},{"tick",tick},{"night",true}});}}}return evidence;});
 pm_app::init();int done=0;V callback=V::func([&](const Args& a){if(done++)return V(true);auto app=a.pos[0];setattr(app,SY("running"),V(false));auto state=getattr(app,SY("state")),renderer=getattr(app,SY("renderer"));
 auto action=[&](V command,bool right=false){callm(app,SY("action"),Args{command,V(right)});};
 auto reset_controls=[&](){setattr(renderer,SY("controls"),V::list({}));};
 auto save_image=[&](const std::string& file){callm(pg::image_module(),SY("save"),Args{getattr(renderer,SY("screen")),V(p8(output/file))});};
 auto click=[&](V cmd){auto point=hitpoint(renderer,cmd);need(callm(renderer,SY("hit"),Args{point})==cmd,"overlaid button: "+dump(cmd));callm(app,SY("pointer_down"),Args{point,V(1)});callm(app,SY("pointer_up"),Args{point,V(1)});};
 check("touch_editor_modes_clickable_and_hidden_keys_restorable",[&]()->J{
  setitem(state,V("screen"),V("touch_layout"));setitem(state,V("touch_mode"),V(true));auto touch=getattr(app,SY("touch"));auto* t=as<pm_touch::C_TouchControls>(touch);need(t!=nullptr,"touch runtime unavailable");
  for(auto size:{std::pair{1280,578},std::pair{960,540},std::pair{960,640}}){auto screen=pg::new_surface(size.first,size.second,true);setattr(renderer,SY("screen"),screen);setattr(app,SY("surface"),screen);t->a_editor_selected=V("left");t->a_editor_panel=V(true);
   for(auto mode:{"joystick","off","buttons"}){reset_controls();t->m_draw_editor(Args{});click(tuple({V("touch_option"),V("movement"),V(mode)}));need(rd(rd(state,V("touch_options")),V("movement"))==V(mode),"click did not switch movement");}
   callm(touch,SY("editor_option"),Args{V("movement"),V("off")});t->a_editor_panel=V(false);reset_controls();t->m_draw_editor(Args{});click(tuple({V("touch_option"),V("movement_settings"),V(0)}));need(t->a_editor_panel.truthy(),"hidden controls have no restoration route");reset_controls();t->m_draw_editor(Args{});click(tuple({V("touch_option"),V("movement"),V("joystick")}));reset_controls();t->m_draw_editor(Args{});save_image("touch-"+std::to_string(size.first)+"x"+std::to_string(size.second)+".png");
  }return true;
 });
 check("replay_delete_confirmation_and_file_scope",[&]()->J{
  auto folder=u8p(py_str(getattr(app,SY("replay_folder"))));std::filesystem::create_directories(folder);auto a=folder/"delete-me.json",b=folder/"keep-me.json",outside=folder.parent_path()/"outside.json";for(const auto& p:{a,b,outside})std::ofstream(p)<<"{}";
  callm(app,SY("replay_library"),Args{});action(tuple({V("replay_delete"),V(p8(a))}));need(std::filesystem::exists(a),"first click deleted immediately");action(tuple({V("replay_delete_cancel")}));action(tuple({V("replay_delete_confirm"),V(p8(a))}));need(std::filesystem::exists(a),"cancel ineffective");
  action(tuple({V("replay_delete"),V(p8(a))}));callm(app,SY("render"),Args{});save_image("replay-delete.png");action(tuple({V("replay_delete_confirm"),V(p8(a))}));need(!std::filesystem::exists(a)&&std::filesystem::exists(b),"target deletion failed or removed other replay");action(tuple({V("replay_delete"),V(p8(outside))}));action(tuple({V("replay_delete_confirm"),V(p8(outside))}));need(std::filesystem::exists(outside),"out-of-list deletion admitted");return true;
 });
 check("texture_manual_save_overwrite_and_confirmed_delete",[&]()->J{
  texture74::initialize(app);auto& s=texture74::state();auto files=[&](){texture74::refresh_pack_choices();return s.pack_choices.size();};auto initial=files();
  auto cmd=[&](const char* op,V arg=V::none()){texture74::action(app,tuple({V("texture74"),V(op),arg}));};
  setitem(state,V("screen"),V("texture_library"));texture74::new_pack();cmd("rename");auto e=V::inst(std::make_shared<PyObj>());setattr(e,SY("type"),V(SDL_TEXTINPUT));setattr(e,SY("text"),V("甲"));texture74::event(app,e);texture74::persist_editor(app);need(files()==initial,"new/rename autosaved");
  texture74::open_resource("world:豌豆射手");s.canvas.dot(1,1,1,0xff3366ff,false);s.dirty=true;texture74::open_resource("world:向日葵");need(files()==initial&&s.unsaved,"resource switch saved to disk");
  cmd("save");auto path=s.root/"packs"/(s.local_id+".pvptex");need(files()==initial+1,"explicit save missing");std::string first=s.wire_hash;cmd("rename");texture74::event(app,e);cmd("save");need(files()==initial+1&&std::filesystem::exists(path),"rename created another pack");
  for(int i=0;i<3;++i)texture74::load_saved_pack(path);need(files()==initial+1,"load created duplicate pack");
  cmd("rename");texture74::event(app,e);cmd("home");need(s.pending_op=="home","unsaved changes discarded without choice");cmd("pending_cancel");need(texture74::has_unsaved(),"cancel lost draft");cmd("home");cmd("pending_discard");need(!texture74::has_unsaved()&&files()==initial+1,"discard autosaved");
  setitem(state,V("screen"),V("texture_library"));cmd("delete_pack",V(p8(path)));cmd("pending_cancel");need(std::filesystem::exists(path),"cancel deleted pack");cmd("delete_pack",V(p8(path)));reset_controls();texture74::draw(app);save_image("texture-delete.png");cmd("pending_discard");need(!std::filesystem::exists(path)&&!texture74::active()&&files()==initial,"delete failed or active override remained");
  texture74::new_pack();s.document["name"]="房间切换测试";texture74::open_resource("world:豌豆射手");s.canvas.dot(0,0,1,0x33ff66ff,false);s.dirty=true;texture74::save_current();return {{"saved_for_room_test",s.local_id}};
 });
 check("local_test_button_visible_and_room_texture_all_modes",[&]()->J{
  callm(app,SY("create"),Args{V(true)});auto room=getattr(app,SY("room"));auto& tex=texture74::state();auto path=tex.root/"packs"/(tex.local_id+".pvptex");
  for(auto mode:{"duel","duo","coop"}){callm(room,SY("set_mode"),Args{V(mode)});callm(app,SY("refresh"),Args{});setitem(state,V("screen"),V("room"));
   for(auto size:{std::pair{1280,578},std::pair{960,540}}){auto surface=pg::new_surface(size.first,size.second,true);setattr(renderer,SY("screen"),surface);setattr(app,SY("surface"),surface);callm(app,SY("render"),Args{});
    save_image(std::string("prep-plain-")+mode+"-"+std::to_string(size.first)+".png");
    if(std::string(mode)=="duel"){auto cmd=tuple({V("test74"),V("start")});auto p=hitpoint(renderer,cmd);need(callm(renderer,SY("hit"),Args{p})==cmd,"local test button obscured");}
    click(tuple({V("texture74"),V("room_packs"),V::none()}));need(tex.room_picker,"room pack picker did not open");callm(app,SY("render"),Args{});save_image(std::string("prep-")+mode+"-"+std::to_string(size.first)+".png");click(tuple({V("texture74"),V("room_default"),V::none()}));need(!texture74::active(),"original selection failed");callm(app,SY("render"),Args{});click(tuple({V("texture74"),V("room_packs"),V::none()}));callm(app,SY("render"),Args{});click(tuple({V("texture74"),V("room_load"),V(p8(path))}));need(texture74::active()&&!tex.room_picker,"saved pack selection failed");
   }
  }return true;
 });
 check("coop_private_readiness_and_guest_summary_before_rewards",[&]()->J{
  auto room=getattr(app,SY("room"));callm(room,SY("set_mode"),Args{V("coop")});setattr(app,SY("mode"),V("host"));setattr(app,SY("peer_id"),V("host"));callm(room,SY("set_pve"),Args{V(1),val({"plant:豌豆射手","plant:向日葵"})});callm(app,SY("refresh"),Args{});setitem(getattr(room,SY("confirmed")),V("plant2"),V(true));setitem(getattr(room,SY("confirmed")),V("plant"),V(true));callm(app,SY("refresh"),Args{});action(tuple({V("pve_open")}));need(!rd(getattr(room,SY("confirmed")),V("plant")).truthy(),"opening card selection retained ready: "+dump(py::m_get(state,V("message"))));need(rd(state,V("screen"))==V("pve"),"selection not open");need(rd(getattr(room,SY("confirmed")),V("plant2")).truthy(),"opening selection cleared teammate");callm(room,SY("setup_changed"),Args{V("plant")});need(rd(getattr(room,SY("confirmed")),V("plant2")).truthy(),"deck edit cleared teammate");auto before=json(getattr(getattr(app,SY("campaign")),SY("deck")));action(tuple({V("pve_toggle"),V("plant:豌豆射手")}),true);need(rd(state,V("screen"))==V("almanac")&&rd(state,V("detail"))==V("plant:豌豆射手"),"right-click did not open almanac");need(json(getattr(getattr(app,SY("campaign")),SY("deck")))==before,"right click changed deck");
  setattr(room,SY("members"),val({{"host","plant"},{"guestA","plant2"}}));setattr(room,SY("connected"),val({{"host",true},{"guestA",true}}));auto result=val({{"winner","plant"},{"pve_day",1},{"tick",60},{"coins",0},{"fallen",0}});callm(getattr(room,SY("coop_progress")),SY("finish"),Args{room,result});setattr(room,SY("result"),result);setattr(room,SY("phase"),V("result"));auto view=callm(room,SY("snapshot"),Args{V("guestA")});setattr(app,SY("room"),V::none());setattr(app,SY("mode"),V("guest"));setattr(app,SY("peer_id"),V("guestA"));setattr(app,SY("view"),view);setitem(state,V("screen"),V("room"));callm(app,SY("pve_apply_guest_result"),Args{view});need(rd(state,V("screen"))==V("room"),"guest bypassed result animation/summary");action(tuple({V("pve_open")}));need(rd(state,V("screen"))==V("pve"),"summary cannot enter reward screen before host prep");auto rewards=getattr(getattr(app,SY("campaign")),SY("rewards"));need(rewards.len()>0,"guest reward missing");auto error=callm(room,SY("command"),Args{V("guestA"),val({{"type","coop_reward"},{"revision",json(getattr(room,SY("revision")))},{"card",py_str(rewards.idx(0))}})});need(!error.truthy(),"guest reward rejected before host prep: "+py_str(error));need(getattr(room,SY("phase"))==V("result"),"test advanced host prematurely");setattr(app,SY("room"),room);return true;
 });
 check("coop_host_guest_win_loss_outro_curtain_then_summary",[&]()->J{
  J evidence=J::array();
  for(auto role:{"host","guest"})for(auto winner:{"plant","zombie"}){
   setattr(app,SY("mode"),V("host"));callm(app,SY("create"),Args{V(true)});auto room=getattr(app,SY("room"));callm(room,SY("set_mode"),Args{V("coop")});callm(room,SY("set_pve"),Args{V(1),val({"plant:豌豆射手"})});
   setattr(room,SY("members"),val({{"host","plant"},{"guestA","plant2"}}));setattr(room,SY("connected"),val({{"host",true},{"guestA",true}}));
   auto result=val({{"winner",winner},{"pve_day",1},{"tick",90},{"coins",0},{"fallen",0}});setattr(room,SY("result"),result);setattr(room,SY("phase"),V("result"));
   const bool guest=std::string(role)=="guest";auto view=callm(room,SY("snapshot"),Args{V(guest?"guestA":"host")});auto session=coop(1,"coop",40,true);steps(*session,1);auto battle=session->snapshot();battle["map"]=json(rd(view,V("map")));battle["result"]=json(result);setitem(view,V("battle"),val(battle));
   auto old=py::dict_of(view);setitem(old,V("phase"),V("battle"));setitem(old,V("result"),V::none());setattr(app,SY("view"),old);setattr(app,SY("mode"),V(role));setattr(app,SY("peer_id"),V(guest?"guestA":"host"));if(guest)setattr(app,SY("room"),V::none());setitem(state,V("screen"),V("room"));setitem(state,V("sound"),V(false));
   callm(app,SY("merge_view"),Args{view});need(rd(state,V("screen"))==V("room")&&py::m_get(state,V("result_animation_pending")).truthy(),"result bypassed animation start");
   callm(app,SY("render"),Args{});auto outro=getattr(app,SY("result_outro")),curtain=getattr(app,SY("result_animation"));need(getattr(outro,SY("active")).truthy()&&!getattr(curtain,SY("active")).truthy(),"outro absent or curtain started early");
   if(std::string(winner)=="plant")need(getattr(outro,SY("already_down")).truthy(),"victorious Dave must not topple");
   callm(pg::image_module(),SY("save"),Args{getattr(renderer,SY("screen")),V(p8(output/(std::string(role)+"-"+winner+"-outro.png")))});
   setattr(outro,SY("started"),getattr(outro,SY("started"))-V(3.));callm(app,SY("render"),Args{});need(!getattr(outro,SY("active")).truthy()&&getattr(curtain,SY("active")).truthy(),"outro did not transition to curtain");
   setattr(curtain,SY("started"),getattr(curtain,SY("started"))-V(5.));callm(app,SY("render"),Args{});need(!getattr(curtain,SY("active")).truthy(),"curtain did not finish");hitpoint(renderer,tuple({V("pve_open")}));
   callm(pg::image_module(),SY("save"),Args{getattr(renderer,SY("screen")),V(p8(output/(std::string(role)+"-"+winner+"-summary.png")))});setattr(app,SY("room"),room);evidence.push_back({{"role",role},{"winner",winner},{"order","outro > curtain > summary"}});
  }return evidence;
 });
 check("coop_shop_gold_gifts_ui_authority_validation_and_persistence",[&]()->J{
  callm(app,SY("create"),Args{V(true)});setattr(app,SY("mode"),V("host"));setattr(app,SY("peer_id"),V("host"));auto room=getattr(app,SY("room"));callm(room,SY("set_mode"),Args{V("coop")});callm(room,SY("set_pve"),Args{V(1),val({"plant:豌豆射手"})});setattr(room,SY("members"),val({{"host","plant"},{"guestA","plant2"}}));setattr(room,SY("connected"),val({{"host",true},{"guestA",true}}));
  callm(app,SY("bind_coop_progress"),Args{});auto progress=getattr(room,SY("coop_progress")),campaigns=getattr(progress,SY("campaigns")),a=rd(campaigns,V("plant")),b=rd(campaigns,V("plant2"));setattr(a,SY("coins"),V(5000));setattr(b,SY("coins"),V(200));callm(progress,SY("sync"),Args{room});setattr(room,SY("confirmed"),val({{"plant",true},{"plant2",true}}));callm(app,SY("refresh"),Args{});
  for(auto size:{std::pair{1280,578},std::pair{960,540}}){auto screen=pg::new_surface(size.first,size.second,true);setattr(renderer,SY("screen"),screen);setattr(app,SY("surface"),screen);setitem(state,V("screen"),V("pve_shop"));callm(app,SY("render"),Args{});click(tuple({V("pve_gift")}));callm(app,SY("render"),Args{});click(tuple({V("pve_gift_amount"),V(500)}));need(rd(state,V("pve_gift_amount"))==V("500"),"preset amount missing");save_image("shop-gift-"+std::to_string(size.first)+".png");click(tuple({V("pve_gift_cancel")}));}
  callm(app,SY("render"),Args{});click(tuple({V("pve_gift")}));setitem(state,V("pve_gift_amount"),V("375"));callm(app,SY("render"),Args{});click(tuple({V("pve_gift_send")}));need(getattr(a,SY("coins"))==V(4625)&&getattr(b,SY("coins"))==V(575),"host shop transfer failed");
  auto send=[&](V amount,V to=V("plant"),const char* peer="guestA"){return callm(room,SY("command"),Args{V(peer),py_dict({{V("type"),V("coop_gift")},{V("amount"),amount},{V("to"),to},{V("revision"),getattr(room,SY("revision"))}})});};
  for(auto amount:{V(-1),V(0),V(1.5),V(true),V("10"),V(1000000001),V(576)})need(send(amount).truthy(),"invalid/overdraft amount accepted");need(send(V(10),V("plant2")).truthy(),"self transfer accepted");need(send(V(10),V("plant"),"spectator").truthy(),"spectator transfer accepted");
  setitem(getattr(room,SY("connected")),V("host"),V(false));need(send(V(10)).truthy(),"disconnected recipient accepted");setitem(getattr(room,SY("connected")),V("host"),V(true));
  auto payload=py_dict({{V("type"),V("coop_gift")},{V("amount"),V(75)},{V("to"),V("plant")},{V("revision"),getattr(room,SY("revision"))}});need(!callm(room,SY("command"),Args{V("guestA"),payload}).truthy(),"guest transfer failed");need(callm(room,SY("command"),Args{V("guestA"),payload}).truthy(),"duplicate transfer accepted");need(getattr(a,SY("coins"))==V(4700)&&getattr(b,SY("coins"))==V(500),"balances not conserved");need(rd(getattr(room,SY("confirmed")),V("plant")).truthy()&&rd(getattr(room,SY("confirmed")),V("plant2")).truthy(),"gift changed readiness");
  auto guest=callm(room,SY("snapshot"),Args{V("guestA")});auto remote=rd(rd(rd(guest,V("pve")),V("guest_campaigns")),V("plant2"));need(rd(remote,V("coins"))==V(500),"guest balance not published");std::ifstream stream(u8p(py_str(getattr(progress,SY("path")))));J saved;stream>>saved;stream.close();need(saved["seats"]["plant"]["coins"]==4700&&saved["seats"]["plant2"]["coins"]==500,"transfer not persisted");
  setattr(room,SY("phase"),V("battle"));need(send(V(10)).truthy(),"shop gift admitted during battle");setattr(room,SY("phase"),V("result"));need(!send(V(10)).truthy(),"result shop transfer rejected");setattr(room,SY("mode"),V("duel"));need(send(V(10)).truthy(),"non-coop gift accepted");setattr(room,SY("mode"),V("coop"));return {{"host",json(getattr(a,SY("coins")))},{"guest",json(getattr(b,SY("coins")))},{"total",5200}};
 });return V(true);});
 try{pm_app::f_run(Args({},{{SY("auto_test"),callback}}));}catch(const std::exception& e){++failures;checks.push_back({{"name","UI harness"},{"passed",false},{"error",e.what()}});}need(done>0,"UI callback missing");
 std::ofstream(output/"results.json")<<J{{"failures",failures},{"checks",checks}}.dump(2);return failures?1:0;
}
