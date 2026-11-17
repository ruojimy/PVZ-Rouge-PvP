// Deterministic video export from the production Session and WorldView renderer.
// Only the fixture / presentation lives here. No alternative boss simulation.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_world_view.h"
#include "ui/gen/pm_rendering.h"
#include "ui/gen/pm_game_audio.h"
#include "ui/hand/test_mode74.h"
#include <fstream>
#include <iostream>
#include <cstdio>
#include <cmath>
using namespace pvz;using J=nlohmann::json;using Session=typed72app::Session;
namespace {
V value(const J& j){return py::json_loads(V(j.dump()));}
void need(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
struct AudioCapture:pm_game_audio::C_GameAudio {
 double time=0.;J events=J::array();
 V m_play(const Args& a)override{auto name=a.pos[0];if(!a_files.contains(name))return V(false);events.push_back({{"time",time},{"name",py_str(name)},{"file",py_str(rd(a_files,name))},{"gain",a.pos[1].num()},{"pan",a.pos[2].num()}});return V(true);}
 V m__music(const Args&)override{return V::none();}
};
void text_at(const V& renderer,const std::string& text,int x,int y,int size,J color={232,236,240}){callm(renderer,SY("text"),Args{V(text),value({x,y}),value(color),V(size)});}
struct Encoder {
 FILE* pipe=nullptr;
 Encoder(const std::filesystem::path& ff,const std::filesystem::path& file){
  std::wstring command=L"\"\""+ff.wstring()+L"\" -hide_banner -loglevel error -y -f rawvideo -pixel_format bgra -video_size 1280x720 -framerate 30 -i pipe:0 -an -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -movflags +faststart \""+file.wstring()+L"\"\"";
  pipe=_wpopen(command.c_str(),L"wb");need(pipe,"cannot open video encoder");
 }
 void frame(const V& screen){auto* s=pg::surf(screen)->s;need(s->format->format==SDL_PIXELFORMAT_ARGB8888,"unexpected capture format");for(int y=0;y<s->h;++y)need(fwrite(static_cast<unsigned char*>(s->pixels)+size_t(y)*s->pitch,1,size_t(s->w)*4,pipe)==size_t(s->w)*4,"video encoder pipe closed");}
 void close(){if(pipe){auto p=pipe;pipe=nullptr;need(_pclose(p)==0,"video encoder failed");}}
 ~Encoder(){if(pipe)_pclose(pipe);}
};
}
int main(int argc,char** argv){
 try{
  if(argc<4)return 2;auto output=std::filesystem::absolute(u8p(argv[1])),ff=std::filesystem::absolute(u8p(std::string(argv[2])=="bundled"?"视频制作工具与记忆/runtime/ffmpeg/ffmpeg.exe":argv[2]));const std::string chapter=argv[3];int seconds=chapter=="eye"?47:chapter=="worm"?36:43;if(argc>4)seconds=std::min(seconds,std::stoi(argv[4]));
  std::filesystem::create_directories(output);env_set_u8("PVP_USERDATA",p8(output/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");env_set_u8("PVP_FONT","C:/Windows/Fonts/msyh.ttc");
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();callm(pg::pygame_module(),SY("init"),Args{});V screen=callm(pg::display_module(),SY("set_mode"),Args{value({1280,720})});test74::catalog();
  J scenario={{"fixture_flat",true},{"seed",744},{"mode","duel"},{"night",true},{"weather","clear"},{"durable_heroes",true},{"decks",{{"plant",J::array()},{"zombie",J::array()}}},{"rules",{{"deathmatch_seconds",100000.},{"local_test_mode",true}}}};
  auto h=battle_from_scenario(scenario);auto terrain=getattr(h.battle,SY("map"));auto cold=typed72app::export_cold(h.battle,744.);cold.cold["battle"]["rules"]["local_test_mode"]=true;auto s=Session::create(std::move(cold),"boss-video");callm(h.battle,SY("close"),Args{});
  auto assets=callm(h.bridge,SY("combat_payload"),Args{}).idx(2);auto world=pm_world_view::new_WorldView(Args{pg::pygame_module(),h.bridge}),renderer=pm_rendering::new_Renderer(Args{pg::pygame_module(),screen,h.bridge,assets});
  auto audio=std::make_shared<AudioCapture>();pm_game_audio::initcv_GameAudio(audio.get());V audio_value=V::inst(audio);audio->m___init__(Args{pg::pygame_module(),assets});
  V settings=value({{"zoom",1.},{"world_quality","native"}}),audio_state=value({{"screen","room"},{"active_side","plant"},{"sound",true},{"volume",.75},{"focused",true},{"music",false}});
  int64_t seq=0;J interventions=J::array(),timeline=J::array();auto input=[&](std::string side,J p){p["seq"]=++seq;need(s->command(side,p).empty(),"demo input rejected: "+p.dump());};
  auto cheat=[&](J p,double at){interventions.push_back({{"time",at},{"command",p}});p["type"]="test_mode";input("zombie",p);};
  input("plant",{{"type","test_mode"},{"op","health"},{"value",1000000.}});s->fixture_set_avatar("plant",{{"玩家位置",{1800.,960.,0.,0.}}});s->fixture_set_avatar("zombie",{{"玩家位置",{3100.,960.,0.,0.}},{"_pvp_butter",1000000.}});
  const std::string name=chapter=="eye"?"克苏鲁之眼":chapter=="worm"?"世界吞噬者":"骷髅王";
  auto spawned=s->spawn("zombie:"+name,"zombie",chapter=="worm"?2300.:2150.,chapter=="worm"?1050.:420.,-1.,false);need(bool(spawned),"boss spawn failed");const auto boss_id=*spawned;std::vector<std::string> original;
  auto initial=s->native_view();for(const auto& u:initial["g"]["僵尸"])original.push_back(u["_pvp_id"]);
  Encoder encoder(ff,output/(chapter+"-silent.mp4"));V previous_camera=V::none();bool freeze_camera=false;J previous_phase=nullptr;
  for(int frame=0;frame<seconds*30;++frame){const double t=frame/30.;
   if(chapter=="eye"){
    if(frame==20*30)cheat({{"op","unit"},{"id",boss_id},{"field","hp"},{"value",1399.}},t);
    if(frame==43*30)cheat({{"op","unit"},{"id",boss_id},{"field","hp"},{"value",0.}},t);
   }else if(chapter=="worm"){
    if(frame==12*30)cheat({{"op","unit"},{"id",original.at(33)},{"field","hp"},{"value",0.}},t);
    if(frame==23*30)for(int index:{16,49})cheat({{"op","unit"},{"id",original.at(index)},{"field","hp"},{"value",0.}},t);
    if(frame==33*30){auto current=s->native_view();for(const auto& u:current["g"]["僵尸"])cheat({{"op","unit"},{"id",u["_pvp_id"]},{"field","hp"},{"value",0.}},t);}
   }else{
    if(frame==25*30){auto current=s->native_view();for(const auto& u:current["g"]["僵尸"])if(u["terraria"]["type"]==36){cheat({{"op","unit"},{"id",u["_pvp_id"]},{"field","hp"},{"value",0.}},t);break;}}
    if(frame==35*30)cheat({{"op","daylight"},{"night",false}},t);
    if(frame==40*30)cheat({{"op","unit"},{"id",boss_id},{"field","hp"},{"value",0.}},t);
   }
   // Recorded movement inputs, not teleports: give the attacks a moving target.
   if(frame%120==0){int direction=(frame/120)%4==1?1:(frame/120)%4==2?-1:0;input("plant",{{"type","move"},{"move",direction},{"jump",false}});}
   s->step();auto snap=s->snapshot(true,true);need(snap["result"].is_null(),"demo match ended early");auto units=snap["test_mode"]["npcs"];J boss=nullptr;int heads=0,hands=0,servants=0;double total_hp=0.;
   for(const auto& u:units){if(u["_pvp_id"]==boss_id)boss=u;int type=u["terraria"]["type"];heads+=type==13;hands+=type==36;servants+=type==5;total_hp+=u["血量"].get<double>();}
   const bool has_boss=chapter=="worm"?heads>0:!boss.is_null();
   if(!has_boss&&!freeze_camera&&!previous_camera.is_none()){const auto c=previous_camera;setitem(settings,V("zoom"),V(c.idx(2).num()*48./64.));setitem(settings,V("replay_camera"),value({c.idx(0).num()+1280./c.idx(2).num()/2.,c.idx(1).num()+620./c.idx(2).num()/2.}));freeze_camera=true;}
   setitem(terrain,V("tiles"),value(s->map_tiles()));if(snap.contains("map")&&snap["map"].contains("environment"))setitem(terrain,V("environment"),value(snap["map"]["environment"]));callm(screen,SY("fill"),Args{value({14,20,28})});
   callm(world,SY("render"),Args{screen,value(snap),value({0,76,1280,620}),V("plant"),settings,terrain,V(freeze_camera)});
   need(!getattr(world,SY("native_error")).truthy(),py_str(getattr(world,SY("native_error"))));previous_camera=getattr(world,SY("camera"));need(!previous_camera.is_none(),"world not rendered");
   std::string phase,note;
   if(chapter=="eye"){
    int a=boss.is_null()?-1:int(boss["terraria"]["ai"][0].get<double>()),b=boss.is_null()?0:int(boss["terraria"]["ai"][1].get<double>());
    phase=a<0?"主体死亡 · 仆从仍独立存活":a==1?"变身：加速旋转":a==2?"变身：减速旋转":std::string(a==3?"第二阶段 · ":"第一阶段 · ")+(b==0?"悬停追踪":"连续三次冲刺");
    note=t>=43?"测试操作：将主体血量设为 0，观察死亡碎片与存活仆从":t>=20?"测试操作：20 秒时血量调至 1399 / 2800，触发半血变身":"普通难度：悬停时召唤仆从，随后进行三次冲刺";
   }else if(chapter=="worm"){
    phase="独立链条 "+std::to_string(heads)+"  |  存活体节 "+std::to_string(units.size());
    note=t>=33?"测试操作：清空各体节血量，观察独立死亡反馈":t>=23?"测试操作：再击杀两个中段体节，观察多条短链独立追击":t>=12?"测试操作：击杀中间体节；前链变尾，后链变头":"67 个独立体节；钻地、出土、跟随转向与地形遮挡";
   }else{
    int a=boss.is_null()?-1:int(boss["terraria"]["ai"][1].get<double>());
    phase=a<0?"头部死亡 · 剩余手臂随之消失":a==1?"旋转追击 · 防御降至 0":a==2?"白天狂暴 · 伤害 / 防御 9999":"悬停 · 双手独立攻击";
    if(hands==1&&a==0)phase="悬停 · 剩余单手继续攻击";
    note=t>=40?"测试操作：清空头部血量，观察头与手的死亡反馈":t>=35?"测试操作：切换白天，观察狂暴追击":t>=25?"测试操作：击杀一只手；头部生命不扣除":"普通难度：双手错拍上抬、下砸、外拉、横扫；头部悬停 / 旋转循环";
   }
   SDL_Rect top{0,0,1280,76},bottom{0,636,1280,84};SDL_FillRect(pg::surf(screen)->s,&top,0xff101923);SDL_FillRect(pg::surf(screen)->s,&bottom,0xff101923);
   text_at(renderer,name,24,13,29,{245,221,158});text_at(renderer,phase,265,20,22);
   const std::string stats=chapter=="worm"?"总生命 "+std::to_string(int(total_hp)):"主体生命 "+std::to_string(boss.is_null()?0:int(boss["血量"].get<double>()))+"  |  "+(chapter=="eye"?"仆从 "+std::to_string(servants):"手臂 "+std::to_string(hands));
   text_at(renderer,stats,24,50,16,{173,188,204});text_at(renderer,"当前移植版本 · 测试模式",960,19,18,{173,188,204});
   text_at(renderer,note,24,649,21);text_at(renderer,"平地测试场  |  戴夫加血以持续观察  |  实际游戏速度 1×",24,684,16,{173,188,204});char clock[32];std::snprintf(clock,sizeof(clock),"%02d:%02d / %02d:%02d",frame/1800,(frame/30)%60,seconds/60,seconds%60);text_at(renderer,clock,1090,684,16,{173,188,204});
   SDL_Rect progress{0,716,int(1280.*(frame+1)/(seconds*30.)),4};SDL_FillRect(pg::surf(screen)->s,&progress,0xffd8b970);
   audio->time=t;audio->m_update(Args{value({{"battle",snap},{"map",J::parse(dump(terrain))},{"phase","battle"},{"match_id",chapter}}),audio_state});
   encoder.frame(screen);
   J state={{"phase",phase},{"heads",heads},{"hands",hands},{"servants",servants}};
   if(state!=previous_phase||frame%30==0){timeline.push_back({{"time",t},{"state",state},{"boss",boss},{"dave",snap["players"]["plant"]}});previous_phase=state;}
   if(frame%150==0||frame==20*30||frame==23*30+15||frame==35*30||frame==43*30)callm(pg::image_module(),SY("save"),Args{screen,V(p8(output/(chapter+"-"+std::to_string(frame)+".png")))});
   if(frame%300==0)std::cerr<<chapter<<" "<<frame/30<<" / "<<seconds<<std::endl;
  }
  encoder.close();std::ofstream(output/(chapter+"-events.json"))<<J{{"chapter",chapter},{"boss",name},{"fps",30},{"seconds",seconds},{"audio",audio->events},{"interventions",interventions},{"timeline",timeline},{"source","production typed Session + production WorldView; offline fixed-step capture"}}.dump(2);return 0;
 }catch(const std::exception& e){std::cerr<<"capture error: "<<e.what()<<std::endl;return 1;}
}
