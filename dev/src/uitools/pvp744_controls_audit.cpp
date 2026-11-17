#include "pg/pg.h"
#include "pg/motion_sensor.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_touch.h"
#include "ui/hand/test_mode74.h"
#include "sim/typed/native_frame.h"
#include <fstream>
#include <iostream>
#include <cmath>
using namespace pvz;using J=nlohmann::json;
namespace {
void need(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
V val(const J& j){return py::json_loads(V(j.dump()));}
J json(const V& v){return J::parse(dump(v));}
V point(double x,double y){return V::tuple({V(x),V(y)});}
}
int main(int argc,char** argv){
 if(argc<2)return 2;auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output);
 env_set_u8("PVP_USERDATA",p8(output/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
 J results=J::array();int failed=0;auto check=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}results.push_back(row);std::cerr<<row.dump()<<std::endl;};
 check("motion_filter_calibration_orientation_and_gyro",[]()->J{
  for(auto orientation:{SDL_ORIENTATION_PORTRAIT,SDL_ORIENTATION_LANDSCAPE,SDL_ORIENTATION_LANDSCAPE_FLIPPED,SDL_ORIENTATION_PORTRAIT_FLIPPED}){
   pg::MotionTilt filter;std::array<double,3> flat{0,0,9.80665},tilted=flat;double sign=1.;int axis=0;
   if(orientation==SDL_ORIENTATION_LANDSCAPE){axis=1;sign=-1.;}else if(orientation==SDL_ORIENTATION_LANDSCAPE_FLIPPED)axis=1;else if(orientation==SDL_ORIENTATION_PORTRAIT_FLIPPED)sign=-1.;
   need(filter.sample(flat,{0,0,0},.016,orientation,true)==0.,"initial calibration");tilted[axis]=sign*-4.903325;tilted[2]=8.492808;
   double reading=0.;for(int i=0;i<600;++i)reading=filter.sample(tilted,{0,0,0},.016,orientation,false);
   need(std::abs(reading-30.)<.01,"screen orientation sign");need(filter.sample(tilted,{0,0,0},.016,orientation,true)==0.,"recalibration");
  }
  pg::MotionTilt filter;filter.sample({0,0,9.80665},{0,0,0},0,SDL_ORIENTATION_PORTRAIT,true);
  need(filter.sample({0,0,0},{0,1,0},.1,SDL_ORIENTATION_PORTRAIT,false)>5.,"gyro did not integrate during invalid accelerometer sample");
  need(pg::motion_sensor(Args{V(false),V(false)}).is_none(),"disabled sensor");
  const auto sensor_before=SDL_WasInit(SDL_INIT_SENSOR);
  for(int i=0;i<20;++i){pg::motion_sensor(Args{V(true),V(true)});pg::motion_sensor(Args{V(false),V(false)});}
  need(SDL_WasInit(SDL_INIT_SENSOR)==sensor_before,"sensor subsystem reference leaked across enable/disable");
  need(SDL_InitSubSystem(SDL_INIT_SENSOR)==0,"sensor subsystem fixture");pg::motion_sensor(Args{V(true),V(true)});pg::motion_sensor(Args{V(false),V(false)});
  need(SDL_WasInit(SDL_INIT_SENSOR)!=0,"closing movement sensor stole external subsystem owner");SDL_QuitSubSystem(SDL_INIT_SENSOR);
  need(SDL_WasInit(SDL_INIT_SENSOR)==sensor_before,"shared sensor subsystem reference leaked");return true;
 });
 check("bounded_visual_bursts_keep_later_units",[]()->J{
  typed72::NativeFrameRecorder recorder(4);auto sprite=typed72::NativeArtStore::canvas(2,2);recorder.begin_frame(1);
  {typed72::NativeFrameTransientScope effects(recorder);for(int i=0;i<10;++i)recorder.blit(sprite,{double(i),0.});}
  {typed72::NativeFrameScope hero(recorder,{"hero:plant",{10.,10.}});recorder.blit(sprite,{10.,10.});}
  need(recorder.size()==4&&recorder.frame().dropped_commands==7,"burst budget not bounded");need(recorder.frame().commands.back().entity==std::optional<std::string>("hero:plant"),"later hero omitted");recorder.begin_frame(2);need(recorder.frame().dropped_commands==0,"budget did not reset");return true;
 });
 check("original_boss_audio_loads_and_camera_is_test_only",[]()->J{
  callm(pg::mixer_module(),SY("init"),Args{});V files=V::dict();test74::register_sounds(files);for(const auto& pair:files.kv()){auto sound=callm(pg::mixer_module(),SY("Sound"),Args{pair.second});need(callm(sound,SY("get_length"),Args{}).num()>0.,"empty original sound");callm(sound,SY("play"),Args{});}callm(pg::mixer_module(),SY("stop"),Args{});
  auto rect=callm(pg::pygame_module(),SY("Rect"),Args{val({0,0,960,640})}),camera=V::tuple({V(0),V(0),V(1),rect,V(3456)}),hero=val({{"y",960}});
  need(test74::boss_camera(camera,V::dict(),V::dict(),false,hero)==camera,"ordinary camera changed");auto battle=val({{"test_mode",{{"npcs",J::array({{{"血量",2800},{"terraria",{{"type",4}}}}})}}}});
  need(test74::boss_camera(camera,battle,V::dict(),true,hero)==camera,"replay camera overridden");auto boss=test74::boss_camera(camera,battle,V::dict(),false,hero);need(boss.idx(2).num()<.6,"boss hover remains outside viewport");return {{"sounds",files.len()},{"boss_scale",boss.idx(2).num()}};
 });
 check("generated_controls_real_runtime_and_settings",[&]()->J{
  pm_app::init();int done=0;
  V callback=V::func([&](const Args& a){auto actual=a.pos[0];if(done++)return V(true);setattr(actual,SY("running"),V(false));
   auto screen=pg::new_surface(960,640,true),renderer=getattr(actual,SY("renderer"));setattr(renderer,SY("screen"),screen);
   auto fake=V::inst(std::make_shared<PyObj>());int jumps=0,moves=0,saves=0;J actions=J::array();
   V state=val({{"screen","room"},{"touch_mode",true},{"active_side","plant"},{"bindings",{{"plant_left",97},{"plant_right",100},{"plant_jump",119},{"zombie_left",1073741904},{"zombie_right",1073741903},{"zombie_jump",1073741906}}}});
   setattr(fake,SY("state"),state);setattr(fake,SY("pg"),pg::pygame_module());setattr(fake,SY("renderer"),renderer);setattr(fake,SY("surface"),screen);
   setattr(fake,SY("mode"),V("local"));setattr(fake,SY("held_keys"),V::set({}));setattr(fake,SY("pointer_capture"),V::none());
   setattr(fake,SY("view"),val({{"phase","battle"},{"local_sides",{"plant","zombie"}},{"battle",{{"players",{{"plant",{{"deck",J(std::vector<std::string>(13))}}}}}}}}));
   for(auto name:{"chat_guard","world_touch_can_jump"})setattr(fake,Sym(name),V::func([](const Args&){return V(false);}));
   for(auto name:{"pointer_down","pointer_up","pointer_motion","message","wheel","input"})setattr(fake,Sym(name),V::func([](const Args&){return V::none();}));
   setattr(fake,SY("jump_press"),V::func([&](const Args&){++jumps;return V::none();}));
   setattr(fake,SY("move_inputs"),V::func([&](const Args&){++moves;return V::none();}));
   setattr(fake,SY("save_settings"),V::func([&](const Args&){++saves;return V::none();}));
   setattr(fake,SY("action"),V::func([&](const Args& x){actions.push_back(json(x.pos[0]));return V::none();}));
   auto touch=pm_touch::new_TouchControls(Args{fake});auto* t=as<pm_touch::C_TouchControls>(touch);
   auto option=[&](const char* key,V v){callm(touch,SY("editor_option"),Args{V(key),v});};
   auto slots=[&](){return pm_touch::f_placed_slots(Args{V(960),V(640),state});};
   auto rect=[&](const char* slot){return rd(slots(),V(slot));};
   auto center=[&](const char* slot){auto r=rect(slot);return point(r.idx(0).num()+r.idx(2).num()/2.,r.idx(1).num()+r.idx(3).num()/2.);};
   auto down=[&](int id,V p){t->m__down(Args{V(id),p});};auto motion=[&](int id,V p){t->m__motion(Args{V(id),p});};auto up=[&](int id){t->m__up(Args{V(id),point(0,0)});};
   auto held=[&](int key){return getattr(fake,SY("held_keys")).contains(V(key));};
   down(1,center("left"));need(held(97),"legacy left hold");up(1);need(!held(97),"legacy left release");
   t->a_editor_selected=V("jump");option("shape",V(0));auto jump=rect("jump");
   need(t->m__hit(Args{point(jump.idx(0).num()+1,jump.idx(1).num()+1)}).is_none(),"circle corner captured");
   down(1,center("jump"));need(held(119)&&jumps==1,"circle center did not jump");up(1);
   option("movement",V("joystick"));auto stick=rect("joystick"),c=center("joystick");double x=c.idx(0).num(),y=c.idx(1).num(),r=stick.idx(2).num()/2.;
   down(1,c);need(!held(97)&&!held(100)&&!held(119),"stick dead zone");motion(1,point(x-r,y));need(held(97)&&!held(100),"stick left");motion(1,point(x+r,y));need(held(100)&&!held(97),"stick right release");
   motion(1,point(x,y-r));need(held(119)&&jumps==2,"up jump edge");motion(1,point(x,y-r));need(jumps==2,"held jump repeated edge");
   down(2,center("jump"));up(1);need(held(119),"stick release cancelled separate jump finger");up(2);need(!held(119)&&!held(100),"last finger release stuck");
   down(1,c);motion(1,point(x+r*.8,y-r*.8));need(!held(119),"outside 60 degree jump cone");option("jump_angle",V(120));motion(1,point(x+r*.8,y-r*.8));need(held(119),"expanded cone not honored");up(1);
   option("facing_slider",V(true));auto slider=rect("facing_slider");double sx=slider.idx(0).num(),sy=slider.idx(1).num()+10,sw=slider.idx(2).num();
   down(1,point(sx+2,sy));motion(1,point(sx+sw/2,sy));motion(1,point(sx+sw-2,sy));up(1);
   need(actions==J::array({J::array({"facing",-1}),J::array({"facing",0}),J::array({"facing",1})}),"slider order or capture");
   option("movement",V("off"));need(!pm_touch::f_visible_slots(Args{state,V(false)}).contains(V("joystick")),"off mode still interactive");need(pm_touch::f_visible_slots(Args{state,V(true)}).contains(V("joystick")),"cannot restore hidden stick");
   option("movement",V("joystick"));down(1,c);motion(1,point(x-r,y));t->m_clear(Args{});need(getattr(fake,SY("held_keys")).len()==0,"clear left movement latched");
   // Mock only sensor readings, exercising the production input arbitration.
   auto sensorpg=V::inst(std::make_shared<PyObj>());for(auto field:{"key","Rect"})setattr(sensorpg,Sym(field),getattr(pg::pygame_module(),Sym(field)));
   double tilt=-20.;bool available=true,enabled=false,calibration_requested=false;setattr(sensorpg,SY("motion_sensor"),V::func([&](const Args& q){enabled=q.pos[0].truthy();if(enabled)calibration_requested=q.pos[1].truthy();return enabled&&available?V(tilt):V::none();}));setattr(fake,SY("pg"),sensorpg);
   option("gyro",V(true));t->m__update_gyro(Args{});need(enabled&&held(97),"gyro left");tilt=20.;t->m__update_gyro(Args{});need(held(100)&&!held(97),"gyro direction change");
   down(1,c);motion(1,point(x-r,y));t->m__update_gyro(Args{});need(held(97)&&!held(100),"manual stick must win over gyro");up(1);
   setitem(state,V("focused"),V(false));t->m__update_gyro(Args{});need(!enabled&&getattr(fake,SY("held_keys")).len()==0,"focus loss did not disable gyro");setitem(state,V("focused"),V(true));available=false;t->m__update_gyro(Args{});need(getattr(fake,SY("held_keys")).len()==0&&t->a_gyro_status==V("设备无可用陀螺仪"),"missing sensor fallback");available=true;setitem(state,V("screen"),V("touch_layout"));option("calibrate",V(0));t->m__update_gyro(Args{});t->m_clear(Args{});need(t->a_gyro_calibrate.truthy(),"editor calibration request lost while controls inactive");setitem(state,V("screen"),V("room"));t->m__update_gyro(Args{});need(calibration_requested&&!t->a_gyro_calibrate.truthy(),"manual calibration did not reach sensor exactly once");t->m__update_gyro(Args{});need(!calibration_requested,"manual calibration repeated every frame");option("gyro",V(false));setattr(fake,SY("pg"),pg::pygame_module());
   // Exercise the real generated editor, including shape anchor and tap-vs-drag.
   setitem(state,V("screen"),V("touch_layout"));t->a_editor_panel=V(false);down(3,center("jump"));up(3);need(t->a_editor_panel.truthy(),"editor tap did not open options");
   t->a_editor_panel=V(false);auto before=center("jump");down(3,before);motion(3,point(before.idx(0).num()-100,before.idx(1).num()-100));up(3);auto after=center("jump");need(std::abs(after.idx(0).num()-before.idx(0).num()+100)<2.,"circle drag anchor drift");need(!t->a_editor_panel.truthy(),"drag opened options");
   t->a_editor_selected=V("joystick");t->a_editor_panel=V(true);callm(screen,SY("fill"),Args{V::tuple({V(70),V(87),V(49)})});t->m_draw_editor(Args{});callm(pg::image_module(),SY("save"),Args{screen,V(p8(output/"joystick-options.png"))});
   t->a_editor_selected=V("facing_slider");t->m_draw_editor(Args{});callm(pg::image_module(),SY("save"),Args{screen,V(p8(output/"facing-options.png"))});
   t->a_editor_panel=V(false);t->m_draw_editor(Args{});callm(pg::image_module(),SY("save"),Args{screen,V(p8(output/"layout.png"))});
   auto actualstate=getattr(actual,SY("state"));setitem(actualstate,V("touch_options"),rd(state,V("touch_options")));setitem(actualstate,V("touch_layout"),rd(state,V("touch_layout")));callm(actual,SY("save_settings"),Args{});
   setitem(actualstate,V("touch_options"),V::dict());callm(actual,SY("load_settings"),Args{});need(json(rd(actualstate,V("touch_options")))==json(rd(state,V("touch_options"))),"settings reload lost options");
   return V(true);
  });pm_app::f_run(Args({},{{SY("auto_test"),callback}}));need(done>0,"UI callback missing");return true;
 });
 std::ofstream(output/"results.json")<<J{{"failures",failed},{"checks",results}}.dump(2);return failed?1:0;
}
