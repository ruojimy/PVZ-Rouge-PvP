// Focused regression cases use the real app, renderer and simulation.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_maps.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_replay.h"
#include "ui/gen/pm_game_audio.h"
#include "sim/pvp/hand/graphics.h"
#include <chrono>
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <cstdlib>
using namespace pvz;
using J=nlohmann::json;
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
int main(int argc,char**argv){
 if(argc!=2||!std::getenv("PVP_USERDATA"))return 2;
 auto out=u8p(argv[1]);std::filesystem::create_directories(out);J report;int failures=0;
 auto save=[&]{std::ofstream f(out/"report.json");f<<report.dump(2);};
 try {SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;pg::install_pygame();init_pvp_modules();pm_app::init();
 V cb=V::func([&](const Args&A){if(A.pos[1].num()!=3)return V::none();V app=A.pos[0],pg=getattr(app,SY("pg")),r=getattr(app,SY("renderer")),state=getattr(app,SY("state"));
 auto run=[&](const char*name,auto body){try{body();report[name]["passed"]=true;}catch(const std::exception&e){++failures;report[name]["passed"]=false;report[name]["error"]=e.what();}save();};
 run("art_and_audio",[&]{
   report["art_and_audio"]["asset_dir"]=py_str(getattr(r,SY("asset_dir")));
   for(const char*name:{"石化火炬","石化火炬-蓝火","篮球"}){V art=callm(r,SY("artwork"),Args{V(name)});report["art_and_audio"][name]=!art.is_none();require(!art.is_none(),"missing artwork");callm(getattr(pg,SY("image")),SY("save"),Args{art,V(p8(out/u8p(std::string(name)+".png")))});}
   V audio=getattr(app,SY("game_audio"));require(callm(audio,SY("play"),Args{SV("投篮")}).truthy(),"basketball sound did not play");
   report["art_and_audio"]["channels"]=getattr(audio,SY("channels")).len();callm(audio,SY("stop_effects"),Args{});
 });
 J scenario={{"seed",301},{"decks",{{"plant",{"plant:向日葵","plant:豌豆射手"}},{"zombie",{"zombie:脑光墓碑","zombie:投篮车僵尸","zombie:飞贼僵尸"}}}}};
 auto h=battle_from_scenario(scenario);
 auto b=as<pm_native_battle::C_NativeBattle>(h.battle);
 run("frozen_pixel_cache",[&]{
   V img=gfx::make_image("canvas",64,64);callm(img,SY("fill"),Args{V::nums({220,40,15,255})});
   V pixels=py::native_hook("graphics.recorded_image_pixels",Args{img});
   auto start=std::chrono::steady_clock::now();int shared=0;
   for(int i=0;i<100;++i){V frozen=callm(img,SY("frozen"),Args{});V got=py::native_hook("graphics.recorded_image_pixels",Args{frozen});if(got.box==pixels.box)++shared;}
   report["frozen_pixel_cache"]["milliseconds"]=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
   report["frozen_pixel_cache"]["shared_pixels"]=shared;
   require(shared==100,"frozen images discarded their materialized pixel cache");
   V frozen=callm(img,SY("frozen"),Args{});callm(img,SY("fill"),Args{V::nums({5,90,250,255})});
   V now=py::native_hook("graphics.recorded_image_pixels",Args{img}),old=py::native_hook("graphics.recorded_image_pixels",Args{frozen});
   require(callm(now,SY("get_at"),Args{V::nums({0,0})})!=callm(old,SY("get_at"),Args{V::nums({0,0})}),"mutating original changed frozen pixels");
 });
 run("duo_reference",[&]{
   V old_view=getattr(app,SY("view")),old_mode=getattr(app,SY("mode")),old_peer=getattr(app,SY("peer_id"));
   auto restore=py::finally([&]{setattr(app,SY("view"),old_view);setattr(app,SY("mode"),old_mode);setattr(app,SY("peer_id"),old_peer);setitem(state,SV("screen"),SV("home"));});
   V decks=py_dict({{SV("plant"),V::list({SV("plant:火炬树桩")})},{SV("plant2"),V::list({SV("plant:豌豆射手")})},{SV("zombie"),V::list()},{SV("zombie2"),V::list()}});
   V terrain=pm_maps::new_MapSnapshot(Args({rd(b->a_map,SV("map_id")),rd(b->a_map,SV("seed")),rd(b->a_map,SV("generator_revision")),rd(b->a_map,SV("tiles"))},{{SY("tile_size"),b->a_tile},{SY("spawns"),rd(b->a_map,SV("spawns"))},{SY("environment"),rd(b->a_map,SV("environment"))}}));
   V view=py_dict({{SV("mode"),SV("duo")},{SV("phase"),SV("picking")},{SV("current_side"),SV("plant")},{SV("current_seat"),SV("plant2")},{SV("members"),py_dict({{SV("test-peer"),SV("plant2")}})},{SV("decks"),decks},{SV("bans"),V::list()},{SV("rules"),b->a_rules},{SV("map"),callm(terrain,SY("to_dict"),Args{})}});
   setattr(app,SY("view"),view);setattr(app,SY("mode"),SV("guest"));setattr(app,SY("peer_id"),SV("test-peer"));
   callm(app,SY("action"),Args{V::tuple({SV("draft_reference")})});require(rd(state,SV("advice_seat"))==SV("plant2"),"reference did not open current seat");
   V advice=rd(state,SV("draft_advice")),deck=rd(advice,SV("deck"));require(py::in(SV("plant:豌豆射手"),deck),"own locked card missing");require(!py::in(SV("plant:火炬树桩"),deck),"teammate unique card recommended");
   report["duo_reference"]["summary"]=py_str(rd(advice,SV("summary")));require(py::m_get(advice,SV("ai"),V(false)).truthy(),"AI evaluator fell back to heuristics");
   callm(app,SY("render"),Args{});V seats=V::set();for(const auto&control:getattr(r,SY("controls")).items()){V action=control.idx(1);if(action.len()==2&&action.idx(0)==SV("draft_reference"))callm(seats,SY("add"),Args{action.idx(1)});}
   require(seats.len()==4,"not all four seat tabs rendered");report["duo_reference"]["deck"]=J::parse(dump(deck));
   callm(getattr(pg,SY("image")),SY("save"),Args{getattr(r,SY("screen")),V(p8(out/"duo-reference.png"))});
 });
 V world=pm_world_view::new_WorldView(Args{pg,h.bridge,getattr(r,SY("asset_dir"))});V screen=getattr(r,SY("screen"));setitem(state,SV("zoom"),V(.65));
 auto render=[&]{V snap=callm(h.battle,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));setattr(world,SY("local_pixels"),getattr(b->a_recorder,SY("latest_pixels")));callm(world,SY("render"),Args{screen,snap,callm(screen,SY("get_rect"),Args{}),SV("plant"),state});return snap;};
 run("basketball_and_bungee",[&]{
   double tile=b->a_tile.num();V rows=rd(b->a_g,SV("ditu")),empty=rd(b->a_g,SV("kong"));int row=-1,col=0;
   for(int y=3;y<int(rows.len())-1&&row<0;++y)for(int x=12;x<int(rows.idx(y).len())-12;++x)if(rd(rows.idx(y).idx(x),SV("方块"))==SV("空")&&!py::in(rd(rows.idx(y+1).idx(x),SV("方块")),empty)){row=y;col=x;break;}
   require(row>=0,"no ground cell");double x=(col+.5)*tile,y=(row+1)*tile;
   V avatar=rd(b->a_hero_states,SV("plant"));py::set_slice(rd(avatar,SV("玩家位置")),V::none(),V::none(),V::nums({x,y,0,0}));
   V cart=b->m_spawn(Args{SV("zombie:投篮车僵尸"),SV("zombie"),V(x+5*tile),V(y),V(-1)});V native=rd(b->a__native_objects,rd(cart,SV("id")));
   setitem(native,SV("出场"),V(500));setitem(native,SV("投篮"),V(119));setitem(native,SV("篮球cd"),V(300));
   int balls=0,ball_commands=0;J samples=J::array();
   for(int t=0;t<30;++t){callm(h.battle,SY("step"),Args{V(1)});V snap=render();int count=0,commands=0;
     for(const auto&e:rd(b->a_g,SV("实体")).items())if(py::m_get(e,SV("名"))==SV("篮球")){++count;if(t==0)report["basketball_and_bungee"]["ball"]=dump(e);}
     for(const auto&c:rd(rd(snap,SV("native_frame")),SV("commands")).items())if(dump(c).find("world:篮球")!=std::string::npos)++commands;
     balls=std::max(balls,count);ball_commands=std::max(ball_commands,commands);samples.push_back({{"tick",t},{"balls",count},{"commands",commands},{"render_error",py_str(getattr(world,SY("native_error")))}});
     if(t==0||t==10)callm(getattr(pg,SY("image")),SY("save"),Args{screen,V(p8(out/("basketball-"+std::to_string(t)+".png")))});
   }
   report["basketball_and_bungee"]["samples"]=samples;require(balls>0,"cart produced no basketball");require(ball_commands>0,"basketball has no native draw command");
   b->m_spawn(Args{SV("plant:向日葵"),SV("plant"),V(x+tile),V(y),V(1)});b->m_spawn(Args{SV("zombie:飞贼僵尸"),SV("zombie"),V(x+tile),V(y),V(-1)});
   for(int t=0;t<65;++t){callm(h.battle,SY("step"),Args{V(1)});render();require(!getattr(world,SY("native_error")).truthy(),"bungee drawing failed");if(t==1||t==60)callm(getattr(pg,SY("image")),SY("save"),Args{screen,V(p8(out/("bungee-"+std::to_string(t)+".png")))});}
   report["basketball_and_bungee"]["rope_width"]=rd(b->a_g,SV("xianbi")).num();
 });
 run("legacy_replay_hash",[&]{
   V snapshot=callm(h.battle,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
   V legacy=py::deepcopy(snapshot);int ropes=0;
   for(const auto&c:rd(rd(legacy,SV("native_frame")),SV("commands")).items())if(py::m_get(c,SV("primitive"))==SV("line")){setitem(rd(c,SV("args")),V(3),V::none());++ropes;}
   require(ropes>0,"missing legacy rope fixture");
   V expected=pm_catalog::f_digest(Args{legacy}),recording=py_dict({{SV("format"),SV("pvz-pvp-replay-1")},{SV("build"),SV("1.6.0.72-native.20261104")}});
   require(pm_replay::f_matches_state_hash(Args{h.battle,expected,recording}).truthy(),"legacy presentation rejected");
   require(pm_replay::f_matches_state_hash(Args{h.battle,pm_replay::f_state_hash(Args{h.battle}),recording}).truthy(),"new digest rejected");
   V hero=rd(rd(legacy,SV("players")),SV("plant"));setitem(hero,SV("hp"),rd(hero,SV("hp"))-V(1));
   require(!pm_replay::f_matches_state_hash(Args{h.battle,pm_catalog::f_digest(Args{legacy}),recording}).truthy(),"combat tampering accepted");
   setitem(recording,SV("build"),SV("unrelated"));require(!pm_replay::f_matches_state_hash(Args{h.battle,expected,recording}).truthy(),"unrelated build accepted");
 });
 run("render_error_survives_empty_layer",[&]{V snap=callm(h.battle,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));V frame=py::copy(rd(snap,SV("native_frame")));
   setitem(frame,SV("commands"),V::list({py_dict({{SV("op"),SV("primitive")},{SV("primitive"),SV("line")},{SV("args"),V::list({V::tuple({V(0),V(0),V(0)}),V::tuple({V(0),V(0)}),V::tuple({V(5),V(5)}),V::none()})},{SV("kwargs"),V::dict()}})}));setitem(snap,SV("native_frame"),frame);
   callm(world,SY("render"),Args{screen,snap,callm(screen,SY("get_rect"),Args{}),SV("plant"),state});require(getattr(world,SY("native_error")).truthy(),"later empty layer hid render error");render();require(!getattr(world,SY("native_error")).truthy(),"error did not clear next healthy frame");
 });
 run("audio_initialization_recovery",[&]{
   V old_audio=getattr(app,SY("game_audio")),mixer=getattr(pg,SY("mixer")),init=getattr(mixer,SY("init"));
   callm(old_audio,SY("close"),Args{});callm(getattr(old_audio,SY("sounds")),SY("clear"),Args{});callm(mixer,SY("quit"),Args{});
   auto restore=py::finally([&]{pg::module_of(mixer)->set_property(SY("init"),init);if(!callm(mixer,SY("get_init"),Args{}).truthy())init.call(Args{});});
   pg::module_of(mixer)->set_property(SY("init"),V::func([](const Args&)->V{throw PyError("error","simulated audio device startup failure");}));
   V recovering=pm_game_audio::new_GameAudio(Args{pg,getattr(old_audio,SY("root"))});require(getattr(recovering,SY("channels")).len()==0,"failed mixer unexpectedly has channels");
   pg::module_of(mixer)->set_property(SY("init"),init);setattr(recovering,SY("retry_at"),V(0));
   callm(recovering,SY("update"),Args{V::dict(),py_dict({{SV("screen"),SV("home")},{SV("focused"),V(true)},{SV("music"),V(false)}})});
   report["audio_initialization_recovery"]["mixer_initialized"]=callm(mixer,SY("get_init"),Args{}).truthy();
   report["audio_initialization_recovery"]["channels"]=getattr(recovering,SY("channels")).len();
   require(getattr(recovering,SY("channels")).len()==16,"channels not restored after startup failure");
   require(callm(recovering,SY("play"),Args{SV("投篮")}).truthy(),"sound unavailable after recovery");callm(recovering,SY("close"),Args{});
 });
 callm(h.battle,SY("close"),Args{});setattr(app,SY("running"),V(false));return V::none();});pm_app::f_run(Args({},{{SY("auto_test"),cb}}));
 }catch(const std::exception&e){report["fatal"]=e.what();++failures;}report["failures"]=failures;save();return failures?1:0;
}
