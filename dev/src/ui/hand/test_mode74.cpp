#include "ui/hand/test_mode74.h"
#include "pg/pg.h"
#include "ui/gen/pm_ui_data.h"
#include "core/resource_paths.h"
#include "core/fsutil.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/typed72_app/typed_battle.h"
#include <nlohmann/json.hpp>
#include <map>
#include <algorithm>
namespace pvz::test74 {
void register_sounds(const V& files){for(auto name:{"NPC_Hit_1","NPC_Hit_2","NPC_Killed_1","NPC_Killed_2","Roar_0","eow_dig"}){std::string key=std::string("terraria_")+name;setitem(files,V(key),py::stdlib_call(V("pathlib.Path"),Args{V(p8(native_workspace()/"extract"/"assets"/"terraria"/(key+".wav")))}));}}
V boss_camera(const V& camera,const V& battle,const V& settings,bool replay,const V& hero){
 if(camera.is_none()||replay||!py::m_get(settings,V("test74_boss_camera"),V(true)).truthy())return camera;
 auto test=py::m_get(battle,V("test_mode"),V::dict());
 bool boss=py::m_get(py::m_get(py::m_get(battle,V("team"),V::dict()),V("waves"),V::dict()),V("boss_active"),V(false)).truthy();for(const auto& u:py::m_get(test,V("npcs"),V::list()).items()){
  const auto type=py::m_get(py::m_get(u,V("terraria"),V::dict()),V("type"),V(0)).num();
  if((type==4||type==13||type==35)&&py::m_get(u,V("血量"),V(0)).num()>0.){boss=true;break;}
 }
 if(!boss)return camera;
 const auto rect=camera.idx(3);const double w=getattr(rect,SY("w")).num(),h=getattr(rect,SY("h")).num();
 const double old=camera.idx(2).num(),tile=py::m_get(py::m_get(battle,V("native_frame"),V::dict()),V("tile"),V(48)).num();
 const double scale=std::min(old,h/(500.*tile/16.));
 if(hero.is_none())return camera;
 // Keep the normal horizontal follow. Original hover offsets require sky above
 // the PvZ map; this is a camera change only, without changing AI or hit boxes.
 // The card bars occupy the upper viewport. Reserve sky beyond the 200-pixel
 // hover offset plus the 83-pixel half-sprite and ordinary movement overshoot.
 const double center=camera.idx(0).num()+w/old*.5,top=rd(hero,V("y")).num()-h/scale*.80;
 return V::tuple({V(center-w/scale*.5),V(top),V(scale),rect,camera.idx(4)});
}
V replay_rules(const V& rules){auto copy=py::dict_of(rules);auto flag=py::m_get(copy,V("local_test_mode"),V::none());if(isinstance(flag,"bool"))callm(copy,SY("pop"),Args{V("local_test_mode")});return copy;}
namespace {
using J=nlohmann::json;
struct Panel {std::string side="plant",tab="cards",focus,query,unit_id,number="10000",notice;int slot=0,page=0;} panel;
struct Npc {int id,w,h;const char* name;int hp,damage,defense;};
const Npc npcs[]={{4,110,166,"克苏鲁之眼",2800,15,12},{5,20,32,"克苏鲁之仆",8,12,0},{13,46,90,"世界吞噬者",150,22,2},{14,46,90,"世界吞噬者体节",150,13,4},{15,46,90,"世界吞噬者尾节",150,11,8},{35,114,132,"骷髅王",4400,32,10},{36,58,78,"骷髅王之手",600,20,14}};
bool main_npc(int id){return id==4||id==13||id==35;}
V val(const J& j){return py::json_loads(V(j.dump()));}
V st(const V& a){return getattr(a,SY("state"));}
std::string screen(const V& a){return py_str(py::m_get(st(a),V("screen"),V("")));}
bool enabled(const V& a){const auto room=getattr(a,SY("room"),V::none());return getattr(a,SY("mode"),V::none())==V("local")&&!room.is_none()&&py::m_get(getattr(room,SY("rules")),V("local_test_mode"),V(false)).truthy();}
V command(const std::string& op,const V& data=V::none()){return V::tuple({V("test74"),V(op),data});}
void text(const V& r,const std::string& s,int x,int y,int size=16,int width=0){Args a{V(s),V::tuple({V(x),V(y)}),V::tuple({V(45),V(49),V(40)}),V(size)};if(width)a.kw.emplace_back(SY("max_width"),V(width));callm(r,SY("text"),a);}
void button(const V& r,const std::string& s,int x,int y,int w,int h,const std::string& op,const V& data=V::none(),bool selected=false){callm(r,SY("button"),Args({V(s),V::tuple({V(x),V(y),V(w),V(h)}),command(op,data)},{{SY("size"),V(15)},{SY("selected"),V(selected)}}));}
void send(const V& a,J data){Args args{V(panel.side),V("test_mode")};for(const auto& [k,v]:data.items())args.kw.emplace_back(Sym(k),val(v));V error=callm(a,SY("input"),args);panel.notice=error.truthy()?py_str(error):"已应用";}
V player(const V& a){const auto view=getattr(a,SY("view"));const auto battle=py::m_get(view,V("battle"),py_dict({}));return py::m_get(py::m_get(battle,V("players"),py_dict({})),V(panel.side),py_dict({}));}
void fill_deck(const V& app,bool saved){
    const V side(panel.side),view=getattr(app,SY("view"));
    const V cards=saved?py::m_get(pm_ui_data::f_load_decks(Args{getattr(getattr(app,SY("settings_path")),SY("parent"))/V("decks.json"),py::m_get(view,V("bans"),V::list())}),side,V::list()):
        py::m_get(callm(app,SY("draft_advice"),Args{side,side}),V("deck"),V::list());
    auto current=callm(py::m_get(player(app),V("deck"),V::list()),SY("copy"),Args{});
    while(current.len()<13)current.append(V(""));
    int added=0;
    for(const auto& key:cards.items()){
        if(!key.truthy()||py::in(key,current))continue;
        size_t slot=0;while(slot<13&&current.idx(slot).truthy())++slot;if(slot==13)break;
        auto error=callm(app,SY("input"),Args({side,V("test_mode")},{{SY("op"),V("card")},{SY("slot"),V(int(slot))},{SY("card"),key}}));
        if(error.truthy())throw std::runtime_error(py_str(error));
        setitem(current,V(int(slot)),key);++added;
    }
    panel.notice=added?"已补入 "+std::to_string(added)+" 张卡":saved?"没有可补入的已存卡牌":"没有可补入的参考卡牌";
}
void close(const V& a){panel.focus.clear();setitem(st(a),V("screen"),V("room"));callm(a,SY("_sync_text_input"),Args{});}
}
void catalog(){static bool initialized=false;if(initialized)return;pm_catalog::init();auto base=rd(pm_catalog::CARDS,V("zombie:普通僵尸"));for(const auto& n:npcs){if(n.id==5)continue; /* PvP75: zombie:克苏鲁之仆 is a regular card */auto card=callm(base,SY("copy"),Args{});const std::string key=std::string("zombie:")+n.name;for(const char* f:{"id","base_id","resolved_id"})setitem(card,V(f),V(key));setitem(card,V("name"),V(n.name));setitem(card,V("family"),V(n.name));setitem(card,V("native_source"),V(n.name));setitem(card,V("asset"),V(std::string("terraria/NPC_")+std::to_string(n.id)));setitem(card,V("behavior"),V("terraria"));setitem(card,V("cost"),V(0));setitem(card,V("cooldown"),V(0));setitem(card,V("hp"),V(n.hp));setitem(card,V("damage"),V(n.damage));setitem(card,V("defense"),V(n.defense));setitem(card,V("selectable"),V(false));setitem(card,V("spawn_only"),V(true));setitem(card,V("pvp_regular_unit"),V(true));setitem(card,V("description"),V("本地测试模式可召唤；合作第 8/16/24 关对应 Boss 战。普通模式数值。对植物、戴夫伤害除以 10，对魅惑僵尸保持原值。"));setitem(pm_catalog::CARDS,V(key),card);}initialized=true;}
V original_asset(const std::string& key){if(key.starts_with("world:terraria/Gore_")){const auto id=key.substr(20);for(int allowed:{2,6,7,8,9,10,24,25,26,27,28,29,54,55,56,57})if(id==std::to_string(allowed)){static std::map<std::string,V> gore;auto it=gore.find(key);if(it!=gore.end())return it->second;auto art=callm(pg::image_module(),SY("load"),Args{V(p8(native_workspace()/"extract"/"assets"/"terraria"/("Gore_"+id+".png")))});art=callm(art,SY("convert_alpha"),Args{});gore[key]=art;return art;}return V::none();}if(key=="world:terraria/Arm_Bone"){static V bone;if(!bone.has()){bone=callm(pg::image_module(),SY("load"),Args{V(p8(native_workspace()/"extract"/"assets"/"terraria"/"Arm_Bone.png"))});bone=callm(bone,SY("convert_alpha"),Args{});}return bone;}if(!key.starts_with("world:terraria/NPC_"))return V::none();const std::string suffix=key.substr(19);const Npc* npc=nullptr;for(const auto& n:npcs)if(suffix==std::to_string(n.id))npc=&n;if(!npc)return V::none();static std::map<int,V> sheets;auto it=sheets.find(npc->id);if(it!=sheets.end())return it->second;auto path=native_workspace()/"extract"/"assets"/"terraria"/("NPC_"+std::to_string(npc->id)+".png");V sheet=callm(pg::image_module(),SY("load"),Args{V(p8(path))});sheet=callm(sheet,SY("convert_alpha"),Args{});sheets[npc->id]=sheet;return sheet;}
bool icon(const V& screen,const std::string& name,const V& rect,bool flip){const Npc* npc=nullptr;for(const auto& n:npcs)if(name==n.name||name==std::string("terraria/NPC_")+std::to_string(n.id))npc=&n;if(!npc||npc->id==5)return false; /* PvP75: the 克苏鲁之仆 card face is 图片/克苏鲁之仆.png */auto sheet=original_asset("world:terraria/NPC_"+std::to_string(npc->id));auto crop=callm(sheet,SY("subsurface"),Args{V::tuple({V(0),V(0),V(npc->w),V(npc->h)})});int w=int(rect.idx(2).num()),h=int(rect.idx(3).num());double factor=std::min(double(w)/npc->w,double(h)/npc->h);V art=callm(pg::transform_module(),SY("scale"),Args{crop,V::tuple({V(std::max(1,int(npc->w*factor))),V(std::max(1,int(npc->h*factor)))})});if(flip)art=callm(pg::transform_module(),SY("flip"),Args{art,V(true),V(false)});callm(screen,SY("blit"),Args{art,V::tuple({rect.idx(0),rect.idx(1)})});return true;}
bool action(const V& app,const V& input){if(input.is_none()||!input.len()||input.idx(0)!=V("test74"))return false;const auto op=py_str(input.idx(1));const auto data=input.len()>2?input.idx(2):V::none();
 try{catalog();if(op=="start"){
  auto room=getattr(app,SY("room"),V::none());if(getattr(app,SY("mode"))!=V("local")||room.is_none()||getattr(room,SY("phase"))!=V("config"))throw std::runtime_error("请在本地演练配置中开始测试");
  if(getattr(room,SY("mode"),V("duel"))!=V("duel"))throw std::runtime_error("测试模式使用本地双方对局");
  setitem(getattr(room,SY("rules")),V("local_test_mode"),V(true));setattr(room,SY("decks"),val({{"plant",J::array()},{"zombie",J::array()}}));callm(room,SY("_start_battle"),Args{});typed72app::start_battle_session(getattr(room,SY("battle")));
  for(const char* side:{"plant","zombie"}){auto peer=callm(app,SY("peer_for"),Args{V(side)});auto payload=py_dict({{V("type"),V("loaded")},{V("loading_id"),getattr(room,SY("loading_id"))},{V("terrain_hash"),getattr(getattr(room,SY("map")),SY("terrain_hash"))}});auto error=callm(room,SY("command"),Args{peer,payload});if(error.truthy())throw std::runtime_error(py_str(error));}
  panel=Panel{};callm(app,SY("refresh"),Args{});setitem(st(app),V("screen"),V("room"));return true;
 }
 if(!enabled(app))return true;
 if(op=="open"){callm(app,SY("release_inputs"),Args{});panel.tab=py_str(data);panel.notice.clear();panel.focus.clear();setitem(st(app),V("screen"),V("test74"));}
 else if(op=="close")close(app);
 else if(op=="side"){panel.side=py_str(data);panel.page=0;}
 else if(op=="tab"){panel.tab=py_str(data);panel.focus.clear();}
 else if(op=="reference"||op=="saved")fill_deck(app,op=="saved");
 else if(op=="slot")panel.slot=int(data.num());
 else if(op=="page")panel.page=std::max(0,panel.page+int(data.num()));
 else if(op=="focus"){panel.focus=py_str(data);callm(app,SY("_sync_text_input"),Args{});}
 else if(op=="card")send(app,{{"op","card"},{"slot",panel.slot},{"card",py_str(data)}});
 else if(op=="unit_pick"){panel.unit_id=py_str(data);panel.notice="已选择单位 "+panel.unit_id;}
 else if(op=="unit_hp"||op=="unit_defense"){size_t end=0;double n=std::stod(panel.number,&end);if(end!=panel.number.size())throw std::runtime_error("请输入完整数字");send(app,{{"op","unit"},{"id",panel.unit_id},{"field",op=="unit_hp"?"hp":"defense"},{"value",n}});}
 else if(op=="number"){panel.number=py_str(data);}
 else if(op=="economy"||op=="health"){size_t end=0;double n=std::stod(panel.number,&end);if(end!=panel.number.size())throw std::runtime_error("请输入完整数字");send(app,{{"op",op},{"value",n}});}
 else if(op=="clear")send(app,{{"op","clear"},{"what",py_str(data)}});
 else if(op=="cooldowns")send(app,{{"op","cooldowns"}});
 else if(op=="zero_cooldown")send(app,{{"op","zero_cooldown"}}); // PvP75: toggles 0 cooldown for the selected side only
 else if(op=="night")send(app,{{"op","daylight"},{"night",data.truthy()}});
 }catch(const std::exception& e){panel.notice=e.what();callm(app,SY("message"),Args{V(panel.notice)});}return true;
}
bool draw(const V& app){if(screen(app)!="test74")return false;if(!enabled(app)){close(app);return false;}catalog();auto r=getattr(app,SY("renderer"));auto surface=getattr(r,SY("screen"));auto* s=pg::surf(surface);int w=s->w(),h=s->h();SDL_FillRect(s->s,nullptr,SDL_MapRGB(s->s->format,232,236,216));setattr(r,SY("controls"),V::list());
 text(r,"本地测试模式",24,18,26);button(r,"返回对局",w-145,15,120,36,"close");button(r,"选卡",24,62,100,34,"tab",V("cards"),panel.tab=="cards");button(r,"作弊器",132,62,100,34,"tab",V("cheats"),panel.tab=="cheats");button(r,"植物方",260,62,110,34,"side",V("plant"),panel.side=="plant");button(r,"僵尸方",380,62,110,34,"side",V("zombie"),panel.side=="zombie");
 if(panel.tab=="cards"){const auto deck=py::m_get(player(app),V("deck"),V::list());int columns=std::min(7,std::max(4,(w-48)/130)),cw=(w-48)/columns;for(int i=0;i<13;++i){std::string name="空";if(i<int(deck.len())&&deck.idx(i).truthy()){auto card=py::m_get(pm_catalog::CARDS,deck.idx(i),py_dict({}));name=py_str(py::m_get(card,V("name"),deck.idx(i)));}button(r,std::to_string(i+1)+" · "+name,24+(i%columns)*cw,112+(i/columns)*40,cw-5,35,"slot",V(i),panel.slot==i);}
  int top=112+((13+columns-1)/columns)*40;button(r,"参考阵容补齐",24,top,145,32,"reference");button(r,"已存阵容补齐",178,top,145,32,"saved");top+=38;button(r,"搜索："+panel.query,24,top,w-205,34,"focus",V("query"),panel.focus=="query");button(r,"清空此槽",w-170,top,146,34,"card",V(""));
  std::vector<std::string> keys;auto raw=J::parse(dump(pm_catalog::CARDS));for(const auto& [key,c]:raw.items()){bool boss=false;for(const auto& n:npcs)if(main_npc(n.id)&&key==std::string("zombie:")+n.name)boss=true;if(c.value("side",std::string{})!=panel.side||(!c.value("selectable",false)&&!boss))continue;const std::string name=c.value("name",key);if(!panel.query.empty()&&name.find(panel.query)==std::string::npos)continue;keys.push_back(key);}
  const int cols=std::max(3,(w-48)/190),rows=std::max(1,(h-top-125)/49),per=rows*cols,pages=std::max(1,int((keys.size()+per-1)/per));panel.page=std::min(panel.page,pages-1);int bw=(w-48)/cols;for(int j=0;j<per&&panel.page*per+j<int(keys.size());++j){const auto& key=keys[panel.page*per+j];const auto& c=raw.at(key);button(r,c.value("name",key),24+(j%cols)*bw,top+45+(j/cols)*49,bw-6,43,"card",V(key));}
  button(r,"上一页",24,h-70,100,32,"page",V(-1));text(r,std::to_string(panel.page+1)+" / "+std::to_string(pages),135,h-64);button(r,"下一页",220,h-70,100,32,"page",V(1));text(r,"先选卡槽，再选卡牌；立即生效，已有单位保留。",340,h-64,14,w-365);
 }else if(panel.tab=="units"){text(r,"选择场上单位后设置属性；Boss 的防御随原版阶段变化。",24,115,17,w-48);button(r,"输入数值："+panel.number,24,150,300,36,"focus",V("number"));button(r,"设单位血量",335,150,150,36,"unit_hp");button(r,"设僵尸防御",495,150,150,36,"unit_defense");button(r,"返回作弊器",660,150,145,36,"tab",V("cheats"));auto view=getattr(app,SY("view"));auto battle=py::m_get(view,V("battle"),py_dict({}));auto units=py::m_get(battle,V("units"),V::list());const int rows=std::max(1,(h-295)/44),per=rows*2,pages=std::max(1,(int(units.len())+per-1)/per);panel.page=std::min(panel.page,pages-1);for(int j=0;j<per&&panel.page*per+j<int(units.len());++j){auto unit=units.idx(panel.page*per+j);auto id=py_str(py::m_get(unit,V("id")));auto card=py::m_get(unit,V("card"),py_dict({}));std::string name=card.is_dict()?py_str(py::m_get(card,V("name"),V(id))):py_str(card);button(r,id+" · "+name+" · HP "+py_str(py::m_get(unit,V("hp"))),24+(j%2)*(w-48)/2,202+(j/2)*44,(w-60)/2,38,"unit_pick",V(id),panel.unit_id==id);}button(r,"上一页",24,h-70,100,32,"page",V(-1));button(r,"下一页",135,h-70,100,32,"page",V(1));text(r,std::to_string(panel.page+1)+" / "+std::to_string(pages),250,h-64);
 }else{auto p=player(app);text(r,"当前经济："+py_str(py::m_get(p,V("resource"),V(0)))+"    血量："+py_str(py::m_get(p,V("hp"),V(0)))+" / "+py_str(py::m_get(p,V("max_hp"),V(0))),24,115,19);button(r,"输入数值："+panel.number,24,155,330,38,"focus",V("number"),panel.focus=="number");button(r,"设为经济",370,155,145,38,"economy");button(r,"设为血量",525,155,145,38,"health");
  int x=24;for(const char* n:{"0","40","1000","10000","1000000"}){button(r,n,x,210,110,34,"number",V(n));x+=120;}{const bool zero=py::m_get(p,V("test_zero_cooldown"),V(false)).truthy();button(r,zero?"该方0冷却：开（点此恢复）":"该方0冷却：关（点此开启）",24,270,230,40,"zero_cooldown",V::none(),zero);}button(r,"修改场上单位血量 / 防御",270,270,310,40,"tab",V("units"));
  button(r,"清理全部植物",24,335,210,42,"clear",V("plants"));button(r,"清理全部僵尸",245,335,210,42,"clear",V("zombies"));button(r,"清理双方单位",466,335,210,42,"clear",V("all"));button(r,"改为夜晚",24,405,160,38,"night",V(true));button(r,"改为白天",195,405,160,38,"night",V(false));text(r,"原版机制：眼球白天退场；骷髅王白天狂暴。清场包含 Boss 部件与召唤物。",24,465,15,w-48);text(r,"血量超过当前上限时同步提高上限。其余对局规则照常运行。",24,495,15,w-48);
 }
 if(!panel.notice.empty())text(r,panel.notice,24,h-28,14,w-48);return true;
}
void overlay(const V& app){if(screen(app)!="room"||!enabled(app))return;auto room=getattr(app,SY("room"));if(getattr(room,SY("phase"))!=V("battle"))return;auto r=getattr(app,SY("renderer"));auto* s=pg::surf(getattr(r,SY("screen")));button(r,"测试选卡",s->w()/2-116,162,110,32,"open",V("cards"));button(r,"作弊器",s->w()/2+6,162,110,32,"open",V("cheats"));}
bool sync_text_input(const V& app){if(screen(app)!="test74")return false;const bool active=!panel.focus.empty();if(active){SDL_StartTextInput();SDL_Rect rect{24,155,330,38};SDL_SetTextInputRect(&rect);}else SDL_StopTextInput();setattr(app,SY("_text_input_active"),V(active));return true;}
bool event(const V& app,const V& e){if(screen(app)!="test74")return false;int type=int(getattr(e,SY("type")).num());if(type==SDL_TEXTINPUT){auto& value=panel.focus=="number"?panel.number:panel.query;if(!panel.focus.empty()&&value.size()<100)value+=py_str(getattr(e,SY("text")));panel.page=0;return true;}if(type==SDL_KEYUP)return true;if(type!=SDL_KEYDOWN)return false;int key=int(getattr(e,SY("key")).num());if(key==SDLK_ESCAPE){close(app);return true;}if(key==SDLK_RETURN){panel.focus.clear();sync_text_input(app);return true;}auto& value=panel.focus=="number"?panel.number:panel.query;if(!panel.focus.empty()){if(key==SDLK_BACKSPACE&&!value.empty()){size_t pos=value.size()-1;while(pos&&((unsigned char)value[pos]&0xc0)==0x80)--pos;value.resize(pos);}else if(key==SDLK_a&&(int(getattr(e,SY("mod"),V(0)).num())&KMOD_CTRL))value.clear();panel.page=0;}return true;}
}
