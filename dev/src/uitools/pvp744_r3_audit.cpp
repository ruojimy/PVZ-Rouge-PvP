#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "sim/typed/attention.h"
#include "ui/hand/texture74_internal.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_touch.h"
#include "ui/gen/pm_battle_view.h"
#include "sim/pvp/gen/pm_pve.h"
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;using Session=typed72app::Session;
namespace {
void need(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
V val(const J& j){return py::json_loads(V(j.dump()));}
J json(const V& v){return J::parse(dump(v));}
J units(Session& s){return s.native_view()["g"]["僵尸"];}
J unit(Session& s,const std::string& id){for(const auto& r:units(s))if(r["_pvp_id"]==id)return r;return nullptr;}
void steps(Session& s,int n){for(int i=0;i<n;++i)s.step();}
std::unique_ptr<Session> game(const char* mode="duel",int day=1,bool test=true,int budget=0,const std::string& electroSeat=""){
 J scenario={{"fixture_flat",true},{"seed",74403},{"mode",mode},{"night",true},{"weather","clear"},{"durable_heroes",true},
 {"decks",{{"plant",{"plant:豌豆射手","plant:向日葵"}},{"zombie",{"zombie:普通僵尸","zombie:脑光墓碑"}}}},
 {"rules",{{"deathmatch_seconds",100000.},{"local_test_mode",test},{"pve_max_zombies",200}}}};
 if(std::string(mode)=="duo"||std::string(mode)=="coop")scenario["decks"]["plant2"]=scenario["decks"]["plant"];
 if(std::string(mode)=="duo")scenario["decks"]["zombie2"]=scenario["decks"]["zombie"];
  if(!electroSeat.empty())scenario["decks"][electroSeat].push_back("secret:电疗");
 if(std::string(mode)=="coop"||std::string(mode)=="pve")scenario["director"]={{"day",day},{"seed",74403},{"max_zombies",200}};
 auto b=battle_from_scenario(scenario);auto cold=typed72app::export_cold(b.battle,74403.);callm(b.battle,SY("close"),Args{});
 if(cold.cold.contains("director")){cold.cold["scripted_spawn_limit"]=200;cold.cold["director"]["max_zombies"]=200;cold.cold["director"]["plan"]=J::array({{{"time",budget?0.:100000.},{"budget",budget},{"flag",false}}});cold.cold["director"]["pool"]=J::array({J::array({"zombie:普通僵尸",1,1.})});}
 return Session::create(std::move(cold),"r3-feedback");
}
V tuple(std::initializer_list<V> v){return V::tuple(v);}
}
int main(int argc,char** argv){
 if(argc<2)return 2;auto out=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(out);
 env_set_u8("PVP_USERDATA",p8(out/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J checks=J::array();int failures=0;auto check=[&](const char* name,auto fn){J r={{"name",name}};try{r["evidence"]=fn();r["passed"]=true;}catch(const std::exception& e){r["passed"]=false;r["error"]=e.what();++failures;}checks.push_back(r);std::cerr<<r.dump()<<std::endl;};
 check("attention_consecutive_real_damage_expiry_and_all_marked_fallback",[]()->J{
  using namespace typed72;auto a=std::make_shared<CombatZombie>(),b=std::make_shared<CombatZombie>();a->attention.hits=3;a->attention.seconds=6.;a->body.hp=b->body.hp=100.;
  ContentTarget x=CombatTarget::player(Seat::plant),y=CombatTarget::player(Seat::plant2);
  auto hit=[&](ContentTarget t,double amount=1.){attention_damage(source_ref(a),t,amount,10.);};
  hit(x);hit(x);hit(y);hit(x);hit(x);hit(x,0.);need(a->attention.marked.empty(),"another victim/zero damage did not break or respect streak");hit(x);
  need(a->attention.marked.at("hero:plant")==16.,"wrong expiry");std::vector<ContentTarget> list{x,y};attention_prefer(a,list,10.);need(list==std::vector<ContentTarget>{y},"marked victim preferred while alternative exists");
  list={x};attention_prefer(a,list,10.);need(list.size()==1,"only marked target incorrectly excluded");
  list={x,y};attention_prefer(b,list,10.);need(list.size()==2,"private marks leaked to same-type unit");
  hit(y);hit(y);hit(y);list={x,y};attention_prefer(a,list,10.);need(list.size()==2,"all-marked fallback missing");
  list={x,y};attention_prefer(a,list,16.);need(list.size()==2&&!a->attention.contains("hero:plant",16.),"expiry is not exact");return true;
 });
 check("worm_chain_owner_split_and_skeleton_independence",[]()->J{
  using namespace typed72;std::vector<ZombieRef> z;for(int i=0;i<5;++i){auto u=std::make_shared<CombatZombie>();u->body.hp=150.;u->terraria=std::make_shared<TerrariaNpcState>();u->terraria->type=i?14:13;u->attention.hits=1;u->attention.seconds=10.;if(i)u->terraria->ahead=z.back();z.push_back(u);}
  attention_damage(source_ref(z[4]),CombatTarget::player(Seat::plant),13.,1.);need(z[0]->attention.contains("hero:plant",1.)&&z[4]->attention.marked.empty(),"body did not record on head");
  z[2]->body.hp=0.;attention_damage(source_ref(z[4]),CombatTarget::player(Seat::plant2),13.,2.);need(attention_owner(z[4])==z[3]&&z[3]->attention.contains("hero:plant2",2.),"split did not establish independent owner");need(!z[0]->attention.contains("hero:plant2",2.)&&!z[3]->attention.contains("hero:plant",2.),"split states share marks");
  for(int type:{4,5,35,36}){auto a=std::make_shared<CombatZombie>(),b=std::make_shared<CombatZombie>();for(auto u:{a,b}){u->body.hp=600.;u->terraria=std::make_shared<TerrariaNpcState>();u->terraria->type=type;u->attention.hits=3;u->attention.seconds=6.;}b->terraria->parent=a;for(int i=0;i<3;++i)attention_damage(source_ref(b),CombatTarget::player(Seat::plant),1.,5.);need(b->attention.contains("hero:plant",5.)&&a->attention.marked.empty(),"parent or same species shares marks unexpectedly");}return true;
 });
 check("eye_contacts_mark_and_retarget_in_production",[]()->J{
  auto s=game();auto victim=s->spawn("zombie:普通僵尸","zombie",2400.,960.,1.,false);need(bool(victim),"victim spawn");s->native_set(false,*victim,{{"魅惑",200.},{"血量",100000.},{"冰冻",20000.}});
  auto eye=s->spawn("zombie:克苏鲁之眼","zombie",2400.,912.,1.,false);need(bool(eye),"eye spawn");s->native_set(false,*eye,{{"冰冻",20000.}});steps(*s,45);auto row=unit(*s,*eye);
  need(row.contains("attention")&&row["attention"]["marked"].contains(*victim),"three real contact hits did not mark: "+row.dump());need(row["terraria"]["target"]=="hero:plant","eye did not choose unmarked Dave: "+row["terraria"].dump());return row["attention"];
 });
 check("magnet_sleep_absorption_and_day_transition",[]()->J{
  auto s=game();auto p=s->spawn("plant:磁力菇","plant",2136.,960.,1.,false);need(bool(p),"magnet spawn");s->native_set(false,*p,{{"吸",500.},{"睡觉",0.}});steps(*s,3);auto frame=s->reference_native_frame().dump();need(frame.find("睡觉-吸")==std::string::npos,"invalid combined recipe");
  need(s->command("plant",{{"seq",1},{"type","test_mode"},{"op","daylight"},{"night",false}}).empty(),"daylight");steps(*s,3);auto native=s->native_view();for(const auto& r:native["g"]["植物"])if(r["_pvp_id"]==*p){need(r.value("吸",0.)>0.,"cooldown erased instead of fixing draw");return r;}throw std::runtime_error("magnet disappeared");
 });
 check("boss_diamonds_full_credit_and_odd_coin_carry",[]()->J{
  auto c=pm_pve::new_Campaign(Args{});setattr(c,SY("coins"),V(0));setattr(c,SY("coin_half"),V(0));
  need(callm(c,SY("_credit_pickups"),Args{V(1005),V(1000)})==V(1002),"diamond halved");need(getattr(c,SY("coin_half"))==V(1),"odd half lost");need(callm(c,SY("_credit_pickups"),Args{V(1),V(0)})==V(1),"carry lost");return json(getattr(c,SY("coins")));
 });
 check("only_three_coop_days_project_red_sky_and_awake_mushrooms",[]()->J{
  for(int day:{7,8,9,16,24,25}){auto s=game("coop",day,false);const bool red=day==8||day==16||day==24;need(s->coop_red_sky()==red,"red-sky day selection");if(red){need(s->coop_map_night()==true,"red sky changed night mechanics");auto p=s->spawn("plant:磁力菇","plant",2136.,960.,1.,false);need(bool(p),"mushroom spawn");steps(*s,2);auto native=s->native_view();for(const auto& row:native["g"]["植物"])if(row["_pvp_id"]==*p)need(!row.contains("睡觉"),"mushroom needs coffee in red sky");}}auto s=game("pve",8,false);need(!s->coop_red_sky(),"red sky leaked into solo");return true;
 });
 check("coop_coin_drop_probability_halved_amounts_unchanged",[]()->J{
  J result=J::object();for(auto mode:{"coop","pve"}){auto s=game(mode,1,false,4950);steps(*s,150);auto rows=units(*s);int killed=0;for(const auto& r:rows)if(r.contains("_pvp_wave_index")&&r.value("_pvp_card",std::string{})=="zombie:普通僵尸"){
   s->native_set(false,r["_pvp_id"],{{"位置",J::array({288.+(killed%30)*96.,-500.-(killed/30)*96.,0.,0.})},{"黄油",2000.}});++killed;
  }need(killed>=190,"population fixture too small: "+std::to_string(killed));steps(*s,1);for(const auto& r:rows)if(r.contains("_pvp_wave_index")&&r.value("_pvp_card",std::string{})=="zombie:普通僵尸")s->native_set(false,r["_pvp_id"],{{"血量",0.}});steps(*s,1);int drops=0;auto snap=s->snapshot(false,false);for(const auto& r:snap["resources"])if(r.contains("coin")){double n=r["amount"];need(n==5.||n==30.||n==100.,"surviving coin amount changed: "+r.dump());++drops;}result[mode]={{"kills",killed},{"drops",drops}};if(std::string(mode)=="coop")need(drops>=70&&drops<=130,"chance not near half: "+std::to_string(drops));else need(drops==killed,"solo chance changed");}return result;
 });
 check("electrotherapy_actual_attacks_all_modes_direct_only_team_shared",[]()->J{
  J evidence=J::array();for(auto mode:{"duel","duo","pve","coop"})for(auto reed:{"闪电芦苇","超载芦苇"})for(auto seat:{"","plant","plant2"}){
   const bool team=std::string(mode)=="coop"||std::string(mode)=="duo";if(!team&&std::string(seat)=="plant2")continue;
   auto s=game(mode,1,false,0,seat);auto p=s->spawn(std::string("plant:")+reed,"plant",1512.,960.,1.,false);need(bool(p),"reed spawn");
   auto a=s->spawn("zombie:普通僵尸","zombie",1740.,960.,-1.,false),b=s->spawn("zombie:普通僵尸","zombie",1776.,960.,-1.,false);need(a&&b,"reed targets");for(const auto& id:{*a,*b})s->native_set(false,id,{{"血量",1000.}});steps(*s,46);
   auto direct=unit(*s,std::string(reed)=="闪电芦苇"?*a:*b),other=unit(*s,std::string(reed)=="闪电芦苇"?*b:*a);need(direct["血量"].get<double>()<1000.,"reed did not attack");const double stun=direct.value("眩晕",0.);need((stun>0.)==!std::string(seat).empty(),std::string(mode)+" "+reed+" holder="+seat+" direct stun="+std::to_string(stun));need(other.value("眩晕",0.)<=0.,"chain/path contact unexpectedly stunned");evidence.push_back({{"mode",mode},{"reed",reed},{"holder",seat},{"stun",stun}});
  }return evidence;
 });
 check("team_ai_gifts_twenty_percent_threshold_and_no_pingpong",[]()->J{
  using typed72::Seat;J results=J::array();for(auto mode:{"coop","duo","duel"}){auto s=game(mode,1,false);for(auto seat:std::string(mode)=="duo"?std::vector<Seat>{Seat::plant,Seat::plant2,Seat::zombie,Seat::zombie2}:std::vector<Seat>{Seat::plant}){
   auto mate=typed72::team_of(seat)==Seat::plant?(seat==Seat::plant?Seat::plant2:Seat::plant):(seat==Seat::zombie?Seat::zombie2:Seat::zombie);
   for(auto pair:{std::pair{119.,100.},std::pair{120.,100.},std::pair{150.,0.},std::pair{0.,0.},std::pair{1000.,100.}}){
    const std::string side(typed72::seat_name(seat)),other(typed72::seat_name(mate));s->fixture_player(side,{{"resource",pair.first}});if(std::string(mode)!="duel")s->fixture_player(other,{{"resource",pair.second}});s->fixture_clock({{"time",s->clock().time+20.}});s->ai_observe(seat);s->ai_plan(seat,false);int gifts=0,amount=0;
    s->ai_control(seat,"r22",[&](const std::string& kind,const typed72app::ai::Args& args){if(kind!="gift")return std::string("audit ignores tactical inputs");++gifts;J cmd={{"type","gift"}};for(const auto& [k,v]:args)cmd[k]=int(std::get<double>(v));amount=cmd["amount"];return s->command(side,cmd);});
    const bool expected=std::string(mode)!="duel"&&pair.first>pair.second&&pair.first*5>=pair.second*6;need(gifts==int(expected),"threshold/team mismatch "+std::string(mode)+side);if(expected){double own=s->players()[side]["resource"],theirs=s->players()[other]["resource"];need(own>=theirs&&own+theirs==pair.first+pair.second,"gift overbalanced or created money");need(amount<=100,"gift cap ignored");}
    results.push_back({{"mode",mode},{"seat",side},{"mine",pair.first},{"mate",pair.second},{"gift",amount}});
   }
  }}return results;
 });
 check("material_derived_status_never_mutates_dave_base",[]()->J{
  auto& st=texture74::state();texture74::new_pack();for(auto name:{"疯狂戴夫","僵尸戴夫"}){std::string key="world:"+std::string(name);const auto* r=texture74::resource(key);need(r!=nullptr,"Dave inventory");auto image=texture74::original(*r);auto before=texture74::pixels(image);st.overrides[key]=image;st.active_name="r3 audit";
   for(int repeat=0;repeat<20;++repeat){for(auto suffix:{"-受伤","-灰烬","-冰冻","-魅惑","-黑白"}){auto derived=texture74::artwork(key+suffix);need(!derived.is_none(),"status did not derive");}st.derived.clear();need(texture74::pixels(texture74::artwork(key))==before,"derived status damaged shared Dave pixels");}
  }st.overrides.clear();st.active_name.clear();return true;
 });
 check("workshop_includes_all_24_terraria_sheets_and_can_edit",[]()->J{
  int count=0;auto inventory=texture74::inventory();for(const auto& e:inventory["entries"])if(e["key"].get<std::string>().starts_with("world:terraria/")){auto key=e["key"].get<std::string>();const auto* r=texture74::resource(key);need(r&&!r->cards.empty(),"unassigned boss part");texture74::open_resource(key);need(texture74::state().canvas.w==r->w&&texture74::state().canvas.h==r->h,"sheet canvas mismatch");++count;}need(count==24,"missing NPC/minion/arm/gore sheets: "+std::to_string(count));return count;
 });
 pm_app::init();int once=0;V callback=V::func([&](const Args& a){if(once++)return V(true);V app=a.pos[0];setattr(app,SY("running"),V(false));auto state=getattr(app,SY("state")),r=getattr(app,SY("renderer"));auto* touch=as<pm_touch::C_TouchControls>(getattr(app,SY("touch")));
 check("hud_slots_are_movable_scaled_clickable_and_persistent",[&]()->J{
  need(touch,"touch runtime");setitem(state,V("touch_mode"),V(true));setitem(state,V("screen"),V("touch_layout"));auto screen=pg::new_surface(1280,720,true);setattr(r,SY("screen"),screen);setattr(app,SY("surface"),screen);
  for(auto slot:{"own_bank","mate_bank","minimap","timer","stage_info","team_info","battle_menu"}){touch->a_editor_selected=V(slot);touch->m__editor_drag(Args{V(slot),tuple({V(150),V(260)}),V(0),V(0)});touch->m_editor_scale_selected(Args{V(-.2)});auto rect=rd(pm_touch::f_placed_slots(Args{V(1280),V(720),state}),V(slot));need(rect.idx(0)==V(150)&&rect.idx(1)==V(260),"HUD position lost");need(rd(rd(state,V("touch_layout")),V(slot)).idx(2)==V(.8),"HUD scale lost");}
  auto saved=pm_touch::f_layout_overrides(Args{rd(state,V("touch_layout"))});need(saved.len()>=7,"settings validator discarded HUD slots");setitem(state,V("touch_layout"),V::dict());touch->a_editor_selected=V("minimap");touch->a_editor_panel=V(false);setattr(r,SY("controls"),V::list({}));touch->m_draw_editor(Args{});callm(pg::image_module(),SY("save"),Args{screen,V(p8(out/"hud-layout-editor.png"))});return json(saved);
 });
 check("gyro_sensitivity_increases_as_threshold_decreases",[&]()->J{
  touch->m_editor_option(Args{V("gyro_threshold"),V(12)});touch->m_editor_option(Args{V("gyro_threshold"),V(11)});need(rd(pm_touch::f_control_options(Args{rd(state,V("touch_options"))}),V("gyro_threshold"))==V(11),"sensitivity direction");touch->m_editor_option(Args{V("gyro_threshold"),V(-10)});need(rd(pm_touch::f_control_options(Args{rd(state,V("touch_options"))}),V("gyro_threshold"))==V(2),"high sensitivity lower bound");return true;
 });
 check("mobile_coop_wave_hud_survives_messages_and_moved_bank_hitboxes",[&]()->J{
  auto s=game("coop",8,false);steps(*s,1);auto snap=s->snapshot();J map={{"tiles",s->map_tiles()},{"tile_size",48},{"width",3456},{"height",1152},{"environment",{{"night",true},{"background","红天"}}}};snap["map"]=map;
  auto view=val({{"mode","coop"},{"phase","battle"},{"battle",snap},{"rules",{{"extra_slot",false}}},{"local_sides",{"plant"}}});setitem(state,V("screen"),V("room"));setitem(state,V("active_side"),V("plant"));setitem(state,V("message"),V("卡牌冷却中"));setitem(state,V("touch_layout"),val({{"own_bank",{.05,.35,.8}},{"minimap",{.74,.62,1.2}}}));
  pm_battle_view::f_draw_touch(Args{r,view,state});auto slots=pm_touch::f_placed_slots(Args{V(1280),V(720),state});auto info=rd(slots,V("stage_info")),bank=rd(slots,V("own_bank"));bool wave=false,card=false;for(const auto& control:getattr(r,SY("controls")).items()){auto action=control.idx(1);auto rect=control.idx(0);if(action.idx(0)==V("hud_block")&&getattr(rect,SY("y"))==info.idx(1))wave=true;if(action.idx(0)==V("select_card")&&getattr(rect,SY("y")).num()>=bank.idx(1).num())card=true;}
  need(wave&&card,"wave bar missing or bank hitboxes stayed at old position");callm(pg::image_module(),SY("save"),Args{getattr(r,SY("screen")),V(p8(out/"mobile-red-sky-hud.png"))});return true;
 });return V(true);});
 try{pm_app::f_run(Args({},{{SY("auto_test"),callback}}));}catch(const std::exception& e){++failures;checks.push_back({{"name","UI harness"},{"passed",false},{"error",e.what()}});}
 std::ofstream(out/"results.json")<<J{{"failures",failures},{"checks",checks}}.dump(2);return failures?1:0;
}
