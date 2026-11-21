// PvP75 actual-UI audit: local test-mode battle through the real Application, its
// world clicks (激光豆 aim / fire / stop / cancel), the range hint, and screenshots of
// the new cards (激光豆 beam, 巴豆 gas, 盾卫僵尸 shield, 克苏鲁之仆).
#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "ui/hand/test_mode74.h"
#include "ui/hand/pvp75_ui.h"
#include "ui/gen/pm_app.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "core/render_cache.h"
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
namespace {
void need(bool condition,const std::string& why){if(!condition)throw std::runtime_error(why);}
J json(const V& v){return J::parse(dump(v));}
V val(const J& j){return py::json_loads(V(j.dump()));}
struct Driver {
    V app;std::filesystem::path out;J evidence=J::object();
    V room()const{return getattr(app,SY("room"));}
    V battle()const{return getattr(room(),SY("battle"));}
    J view()const{return json(getattr(app,SY("view")));}
    void frame(int steps=1){for(int i=0;i<steps;++i)callm(battle(),SY("step"),Args{});callm(app,SY("refresh"),Args{});callm(app,SY("render"),Args{});}
    void shot(const std::string& name){callm(pg::image_module(),SY("save"),Args{getattr(app,SY("surface")),V(p8(out/u8p(name+".png")))});}
    std::string input(const std::string& side,const std::string& type,std::vector<std::pair<Sym,V>> kw={}){
        return py_str(callm(app,SY("input"),Args(ArgVec{V(side),V(type)},std::move(kw))));
    }
    void cheat(const std::string& side,J data){
        std::vector<std::pair<Sym,V>> kw;for(auto& [k,v]:data.items())kw.push_back({Sym(k),val(v)});
        auto e=input(side,"test_mode",std::move(kw));need(e.empty()||e=="None",side+" test_mode: "+e);
    }
    J players(){return view()["battle"]["players"];}
    J units(){auto u=view()["battle"]["units"];J out=J::array();if(u.is_object())for(auto& [k,v]:u.items())out.push_back(v);else out=u;return out;}
    J find(const std::string& card){J best;for(const auto& u:units())if(u.value("card_id",std::string{})==card&&u.value("hp",0.)>0.)best=u;return best;}
    V screen(double x,double y){return callm(getattr(getattr(app,SY("renderer")),SY("world")),SY("point"),Args{V(x),V(y)});}
    void click(double x,double y,bool right=false){press(x,y,right);}
    // The real pointer path (pointer_down, a few frames, pointer_up), as a mouse click arrives.
    void press(double x,double y,bool right=false){const V s=screen(x,y);callm(app,SY("pointer_down"),Args{s,V(right?3.:1.)});frame(3);callm(app,SY("pointer_up"),Args{s,V(right?3.:1.)});frame(1);}
    void side(const std::string& s){setitem(getattr(app,SY("state")),V("active_side"),V(s));}
    // Roof maps: a flower pot first, then the plant in the cell above it (near the Dave).
    std::string potted(const std::string& card,double x,double y,int facing,int only=0){
        std::string last="no cell";
        for(int dx=0;dx<=12;++dx)for(int sign:{1,-1}){if(only&&sign!=only)continue;
            const double cx=x+sign*dx*48.;
            auto e=input("plant","deploy",{{SY("card"),V("plant:花盆")},{SY("x"),V(cx)},{SY("y"),V(y-24.)},{SY("facing"),V(facing)}});
            if(!(e.empty()||e=="None"))continue;
            frame(2);last=input("plant","deploy",{{SY("card"),V(card)},{SY("x"),V(cx)},{SY("y"),V(y-24.-48.)},{SY("facing"),V(facing)}});
            if(last.empty()||last=="None"){evidence[card]={cx,y-72.};frame(2);return {};}
        }
        return last;
    }
    // First accepted deploy among nearby cells (plants need a supported cell).
    std::string deploy(const std::string& seat,const std::string& card,double x,double y,int facing,std::vector<std::pair<Sym,V>> extra={}){
        std::string last;
        for(int ring=0;ring<=24;++ring)for(int dx=-ring;dx<=ring;++dx)for(int dy=-8;dy<=12;++dy){if(std::abs(dx)!=ring)continue;
            auto kw=extra;kw.push_back({SY("card"),V(card)});kw.push_back({SY("x"),V(x+dx*48.)});kw.push_back({SY("y"),V(y+dy*48.)});kw.push_back({SY("facing"),V(facing)});
            last=input(seat,"deploy",kw);if(last.empty()||last=="None"){evidence[card]={x+dx*48.,y+dy*48.};frame(2);return {};}
        }
        return last;
    }
};
}
int main(int argc,char** argv){
    if(argc<2)return 2;auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output);
    env_set_u8("PVP_USERDATA",p8(output/"userdata"));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J results=J::array();int failed=0;std::string error;
    pm_app::init();callm(pg::display_module(),SY("set_mode"),Args{V::tuple({V(1280),V(800)})});int done=0;
    V cb=V::func([&](const Args& args){
        auto app=args.pos.at(0);int frame_no=int(args.pos.at(1).num());if(frame_no>4)return V(true);if(frame_no!=0)return V(false);
        Driver d{app,output};
        auto check=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}results.push_back(row);std::cerr<<row.dump()<<std::endl;};
        try{
            callm(app,SY("create"),Args{V(true)});callm(app,SY("render"),Args{});
            test74::action(app,V::tuple({V("test74"),V("start")}));need(getattr(d.room(),SY("phase"))==V("battle"),"test mode did not start");
            for(const char* s:{"plant","zombie"}){d.cheat(s,{{"op","economy"},{"value",99999.}});d.cheat(s,{{"op","health"},{"value",100000.}});}
            int slot=0;for(const char* c:{"plant:激光豆","plant:巴豆","plant:三叶草","plant:杨桃"})d.cheat("plant",{{"op","card"},{"slot",slot++},{"card",c}});
            d.cheat("plant",{{"op","card"},{"slot",slot++},{"card","plant:花盆"}});
            slot=0;for(const char* c:{"zombie:脑光墓碑","zombie:盾卫僵尸","zombie:克苏鲁之仆","zombie:雪橇车小队","zombie:普通僵尸"})d.cheat("zombie",{{"op","card"},{"slot",slot++},{"card",c}});
            d.cheat("plant",{{"op","cooldowns"}});d.cheat("zombie",{{"op","cooldowns"}});
            d.side("plant");d.frame(300); // both Daves have landed; the camera follows the plant Dave
        }catch(const std::exception& e){error=e.what();}
        if(error.empty()){
        const J p=d.players();const double px=p["plant"]["x"],py=p["plant"]["y"];
        check("deploy_new_cards",[&]()->J{
            // Left of the camera centre, so that 8-10 cells to its right stay on screen.
            auto e=d.potted("plant:激光豆",px-6.*48.,py,1,-1);need(e.empty(),"激光豆 deploy: "+e);
            e=d.deploy("zombie","zombie:脑光墓碑",px+12.*48.,py-24.,-1);need(e.empty(),"grave deploy: "+e);
            d.cheat("plant",{{"op","cooldowns"}});
            auto grave=d.find("zombie:脑光墓碑");need(!grave.is_null(),"grave missing");
            e=d.deploy("zombie","zombie:盾卫僵尸",px+12.*48.,py-24.,-1,{{SY("grave"),V(grave["id"].get<std::string>())}});need(e.empty(),"盾卫 deploy: "+e);
            e=d.input("zombie","deploy",{{SY("card"),V("zombie:克苏鲁之仆")},{SY("x"),V(px+8.*48.)},{SY("y"),V(py-6.*48.)},{SY("facing"),V(-1)}});need(e.empty()||e=="None","仆从 deploy: "+e);
            d.frame(30);d.shot("01-deployed");
            need(!d.find("plant:激光豆").is_null()&&!d.find("zombie:盾卫僵尸").is_null()&&!d.find("zombie:克苏鲁之仆").is_null(),"units missing");
            return J{{"laser",d.find("plant:激光豆")["id"]},{"guard",d.find("zombie:盾卫僵尸")["id"]}};
        });
        check("laser_real_pointer_hits_whole_sprite",[&]()->J{
            d.side("plant");d.frame(1);auto bean=d.find("plant:激光豆");need(!bean.is_null(),"no bean");
            // The servant hunts the nearest plant: keep the 6 HP bean alive through the sweep.
            d.cheat("plant",{{"op","unit"},{"id",bean["id"]},{"field","hp"},{"value",100000.}});
            const double bx=bean["x"],by=bean["y"];J rows=J::array();int misses=0;
            for(double dy=-44.;dy<=12.;dy+=8.)for(double dx:{-18.,0.,18.}){
                d.press(bx+dx,by+dy);const bool hit=d.players()["plant"].contains("laser_aim")&&d.players()["plant"]["laser_aim"].is_object();
                rows.push_back({dx,dy,hit});if(!hit)++misses;if(hit)d.input("plant","laser_cancel");d.frame(1);
            }
            d.shot("01b-real-pointer");
            need(misses==0,"pointer clicks on the bean missed: "+rows.dump()+" bean="+bean.dump().substr(0,300));
            return rows;
        });
        check("laser_aim_ring_fire_stop",[&]()->J{
            d.side("plant");d.frame(1);auto bean=d.find("plant:激光豆");need(!bean.is_null(),"no bean");
            const double bx=bean["x"],by=bean["y"];
            // Holding a card, a click on the bean drops the card and aims (the cob cannon rule).
            setitem(getattr(app,SY("state")),V("selected_card"),V("plant:巴豆"));
            d.click(bx,by-20.);d.frame(1);
            {const V s=d.screen(bx,by-20.);const V w=callm(getattr(app,SY("renderer")),SY("world_point"),Args{s});
             need(!py::m_get(getattr(app,SY("state")),V("selected_card")).truthy(),"card still held after aiming: bean="+bean.dump()+" screen="+dump(s)+" world="+dump(w)+
                 " at="+dump(pvp75_ui::laser_at(app,w.truthy()?w.idx(0):V(0.),w.truthy()?w.idx(1):V(0.)))+" side="+py_str(py::m_get(getattr(app,SY("state")),V("active_side")))+" msg="+py_str(py::m_get(getattr(app,SY("state")),V("message"))));}
            auto aim=d.players()["plant"]["laser_aim"];need(aim.is_object(),"no laser_aim after clicking the bean");
            need(pvp75_ui::laser_aiming(app),"UI does not see the aim");
            d.shot("02-laser-aim-ring");
            // Out of range cancels the aim (too close, 3 cells).
            d.click(bx+3.*48.,by-30.);d.frame(1);need(d.players()["plant"]["laser_aim"].is_null(),"too-close click kept the aim");
            d.click(bx,by-20.);d.frame(1);d.click(bx,by-20.,true);d.frame(1);need(d.players()["plant"]["laser_aim"].is_null(),"right click did not cancel");
            d.click(bx,by-20.);d.frame(1);
            auto guard=d.find("zombie:盾卫僵尸");const double gx=guard["x"],gy=guard["y"];
            const V fire=d.screen(bx+8.6*48.,by-20.);const V fire_world=callm(getattr(app,SY("renderer")),SY("world_point"),Args{fire});
            d.click(bx+8.6*48.,by-20.);d.frame(40);
            need(d.players()["plant"]["laser_aim"].is_null(),"aim kept after firing: screen="+dump(fire)+" world="+dump(fire_world)+" msg="+py_str(py::m_get(getattr(app,SY("state")),V("message"))));
            d.shot("03-laser-beam");
            auto hit=d.find("zombie:盾卫僵尸");
            d.frame(150);d.shot("04-guard-shield");
            d.click(bx,by-20.);d.frame(30);d.shot("05-laser-stopped");
            return J{{"aim",aim},{"guard_before",guard["hp"]},{"guard_after",hit.is_null()?J(nullptr):hit["hp"]}};
        });
        check("test_zero_cooldown_toggle",[&]()->J{
            auto cd=[&](const char* key){const auto p=d.players()["zombie"];const auto c=p.value("cooldowns",J::object());const double t=d.view()["battle"].value("time",0.);return c.contains(key)?c[key].get<double>()-t:0.;};
            const auto deploy=[&](){return d.input("zombie","deploy",{{SY("card"),V("zombie:克苏鲁之仆")},{SY("x"),V(px+8.*48.)},{SY("y"),V(py-6.*48.)},{SY("facing"),V(-1)}});};
            d.cheat("zombie",{{"op","zero_cooldown"}});d.frame(1);need(d.players()["zombie"].value("test_zero_cooldown",false),"flag not published");
            need(d.players()["plant"].value("test_zero_cooldown",false)==false,"plant side changed too");
            for(int i=0;i<3;++i){auto e=deploy();need(e.empty()||e=="None","zero-cooldown deploy "+std::to_string(i)+": "+e);d.frame(1);need(cd("zombie:克苏鲁之仆")<=0.,"cooldown started while 0 cooldown");}
            d.cheat("zombie",{{"op","zero_cooldown"}});d.frame(1);need(!d.players()["zombie"].value("test_zero_cooldown",false),"flag kept after switching off");
            auto e=deploy();need(e.empty()||e=="None","normal deploy: "+e);d.frame(1);const double left=cd("zombie:克苏鲁之仆");
            need(left>18.&&left<=20.01,"normal cooldown not restored: "+std::to_string(left));
            return J{{"cooldown_after_off",left}};
        });
        check("replay_normalize_same_pixels",[&]()->J{
            // DrawReplay.surface of a pure transform chain vs its normalised copy (alpha 255 inside,
            // outer alpha set at blit time): identical pixels, alpha and composite on a backdrop.
            const V pgm=pg::pygame_module();const V image=getattr(pgm,SY("image"));
            const auto bytes=[&](const V& s){return py_str(callm(image,SY("tobytes"),Args{s,V("RGBA")}));};
            std::map<std::string,V> assets;
            for(bool srcalpha:{true,false}){
                V s=pg::new_surface(37,29,srcalpha);
                callm(s,SY("fill"),Args{V::tuple({V(40),V(160),V(70),V(255)})});
                callm(s,SY("fill"),Args{V::tuple({V(200),V(30),V(90),V(120)}),V::tuple({V(3),V(4),V(20),V(9)})});
                callm(s,SY("fill"),Args{V::tuple({V(10),V(10),V(220),V(30)}),V::tuple({V(15),V(12),V(18),V(14)})});
                callm(s,SY("fill"),Args{V::tuple({V(0),V(0),V(0),V(0)}),V::tuple({V(0),V(20),V(9),V(9)})});
                assets[srcalpha?"world:audit-srcalpha":"world:audit-plain"]=s;
            }
            const V resolver=V::func([&](const Args& a){const auto i=assets.find(py_str(a.pos.at(0)));return i==assets.end()?V::none():i->second;});
            const V replay=pm_native_animation::new_DrawReplay(Args{pgm,resolver});
            const auto level=[&](J image,J alpha){return J{{"image",std::move(image)},{"alpha",alpha},{"colorkey",nullptr},{"size",{37,29}}};};
            int compared=0,quantised=0;
            for(const char* key:{"world:audit-srcalpha","world:audit-plain"})for(double angle:{5.25,-7.5,0.,90.,5.3})for(J alpha:{J(nullptr),J(88),J(255)}){
                J asset=level({{"op","asset"},{"key",key},{"size",{37,29}}},alpha);
                J flip=level({{"op","flip"},{"source",asset},{"args",{true,false}}},alpha);
                J rot=level({{"op","rotate"},{"source",flip},{"args",{angle}}},alpha);
                const V desc=val(rot);V outer;bool applied=false;const V norm=native_replay_normalize(desc,outer,applied);
                need(applied,"pure chain not normalised");
                const double expect=std::round(angle*4.)/4.;
                need(json(norm)["image"]["args"][0].get<double>()==expect,"angle not quantised");
                if(expect!=angle){++quantised;continue;}  // 5.3 -> 5.25: a deliberate sub-pixel change
                const V a=callm(replay,SY("surface"),Args{desc});const V b=callm(replay,SY("surface"),Args{norm});callm(b,SY("set_alpha"),Args{outer});
                need(bytes(a)==bytes(b),std::string("pixels differ: ")+key+" "+std::to_string(angle));
                need(dump(callm(a,SY("get_alpha"),Args{}))==dump(callm(b,SY("get_alpha"),Args{})),"surface alpha differs");
                for(const V& backdrop_color:{V::tuple({V(255),V(255),V(255)}),V::tuple({V(20),V(40),V(60)})}){
                    V x=pg::new_surface(80,80,false),y=pg::new_surface(80,80,false);
                    callm(x,SY("fill"),Args{backdrop_color});callm(y,SY("fill"),Args{backdrop_color});
                    callm(x,SY("blit"),Args{a,V::tuple({V(5),V(7)})});callm(y,SY("blit"),Args{b,V::tuple({V(5),V(7)})});
                    need(bytes(x)==bytes(y),"composited pixels differ");
                }
                ++compared;
            }
            // Composite recipes (blit) are never normalised.
            J base=level({{"op","asset"},{"key","world:audit-plain"},{"size",{37,29}}},88);
            J composite=level({{"op","blit"},{"source",base},{"overlay",base},{"dest",{0,0}},{"area",nullptr},{"flags",0}},88);
            V outer;bool applied=true;native_replay_normalize(val(composite),outer,applied);need(!applied,"composite recipe normalised");
            return J{{"compared",compared},{"quantised",quantised}};
        });
        check("croton_gas",[&]()->J{
            d.side("plant");d.frame(1);auto guard=d.find("zombie:盾卫僵尸");
            const double gx=guard.is_null()?px+10.*48.:guard["x"].get<double>(),gy=guard.is_null()?py:guard["y"].get<double>();
            d.cheat("plant",{{"op","cooldowns"}});auto e=d.potted("plant:巴豆",gx-96.,gy,1,-1);need(e.empty(),"巴豆 deploy: "+e);
            // The plant Dave teleports onto the bean so that the camera watches the bite.
            {const auto bean=d.find("plant:巴豆");need(!bean.is_null(),"巴豆 missing");const auto t=d.input("plant","teleport",{{SY("target"),V(bean["id"].get<std::string>())}});d.evidence["teleport"]=t;d.frame(60);}
            // Zombies start on "follow Dave"; the attack command sends them at the plants.
            {const auto mode=d.view()["battle"].value("command",std::string{});if(mode!="attack")d.input("zombie","command");d.frame(1);need(d.view()["battle"].value("command",std::string{})=="attack","attack command not set");}
            bool gas=false;for(int i=0;i<400&&!gas;++i){d.frame(5);if(d.find("plant:巴豆").is_null()){gas=true;}}
            d.frame(8);d.shot("06-croton-gas");d.frame(25);d.shot("07-croton-gas-late");d.frame(40);d.shot("08-guard-after");
            need(gas,"巴豆 was never bitten: positions="+d.evidence.dump()+" guard="+d.find("zombie:盾卫僵尸").dump().substr(0,200));
            return J{{"bitten",gas},{"positions",d.evidence}};
        });
        }
        ++done;setattr(app,SY("running"),V(false));return V(true);
    });
    pm_app::f_run(Args({},{{SY("auto_test"),cb}}));
    J result={{"positions",nullptr},{"checks",results},{"failures",failed},{"setup_error",error},{"driver_ran",done}};
    std::ofstream(output/"results.json")<<result.dump(2);std::cerr<<result.dump()<<std::endl;
    return (failed||!error.empty()||done!=1)?1:0;
}
