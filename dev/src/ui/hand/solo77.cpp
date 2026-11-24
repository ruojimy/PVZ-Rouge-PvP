#include "ui/hand/solo77.h"
#include "sim/pvp/hand/solo_campaign77.h"
#include "sim/pvp/hand/pvp76r2_coop.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_pve.h"
#include "core/fsutil.h"
#include "sim/pvp/hand/graphics.h"
#include "ui/gen/pm_pve_ui.h"
#include "ui/gen/pm_menu_view.h"
#include <chrono>
#include <random>
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_team_maps.h"
#include <array>
#include <algorithm>

#include <fstream>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
namespace pvz::solo77 {
namespace {
using J=nlohmann::json;
V get(const V& v,const char* key,V def=V::none()){return v.is_dict()?py::m_get(v,V(key),def):def;}
V list(const Keys& keys){V out=V::list();for(const auto& k:keys)out.append(V(k));return out;}
Keys keys(const V& seq){Keys r;for(size_t i=0;i<seq.len();++i)r.push_back(py_str(seq.idx(i)));return r;}
bool has(const Keys& v,const std::string& k){return std::find(v.begin(),v.end(),k)!=v.end();}
V card(const std::string& k){return get(pm_catalog::CARDS,k.c_str(),V::dict());}
std::string name(const std::string& k){return k=="brain"?"初始脑光 +25":k=="sun"?"初始阳光 +25":k=="slot"?"增加卡槽":py_str(get(card(k),"name",V(k)));}
Keys zombies(int day,V terrain=V::none()){
    Keys out;auto pool=pm_pve::f_zombie_pool(Args{V(day),terrain,V(true)});
    for(size_t i=0;i<pool.len();++i)out.push_back(py_str(pool.idx(i).idx(0)));return out;
}
}
const Pools& campaign_pools(){
    static const Pools data=[]{
        pm_catalog::init();pm_pve::init();Pools p;auto eligible=zombies(24);
        for(const auto& [id,row]:py::items_vec(pm_catalog::CARDS)){
            auto k=py_str(id);if(!get(row,"selectable",V(true)).truthy()||!pm_pve::f_campaign_card_allowed(Args{id,V(true)}).truthy())continue;
            auto cat=py_str(get(row,"category"));if(cat=="derived")continue;
            const V dep=get(row,"dependency");Card c{k,dep.truthy()?py_str(dep):"",cat=="secret",int(get(row,"cost",V(0)).num())};
            if(k.starts_with("plant:")||k.starts_with("secret:")){
                if(!has({"plant:石块","plant:模仿者","secret:肆意模仿"},k))p.plants.push_back(c);
                if(cat=="tool"||c.secret||k=="plant:模仿者"||k=="plant:花盆"||k=="plant:睡莲"||k=="plant:咖啡豆")continue;
                p.random_plants.push_back(k);
                if(!has({"plant:激光豆","plant:玉米加农炮","plant:墓碑吞噬者"},k))p.defenders.push_back(k);
            }else if(has(eligible,k)){
                p.random_zombies.push_back(k);
                if(k!="zombie:克苏鲁之仆")p.zombies.push_back(c);
            }else if(k=="zombie:飞贼僵尸"||pvp76r2::coop_secret_allowed(k))p.zombies.push_back(c);
        }
        return p;
    }();return data;
}
namespace {
int fresh_seed(){return int(py::stdlib_call(SV("secrets.randbelow"),Args{V(1<<30)}).num());}
bool night(const Campaign& c){return c.zombie()?c.stage%2==0:c.stage%4==3||c.stage%8==0;}
int terrain_seed(const Campaign& c){
    std::seed_seq sequence{c.seed,c.stage,c.attempt};unsigned value;
    sequence.generate(&value,&value+1);return int(value&0x3fffffff);
}
V terrain(const V& bridge,const Campaign& c){
    struct Preview {int seed=-1;std::string map;bool night=false;V snapshot;};
    static Preview cache;const int seed=terrain_seed(c);
    if(cache.seed!=seed||cache.map!=c.map||cache.night!=night(c)){
        auto snapshot=pm_maps::f_build_snapshot(Args({bridge,V(c.map),V(seed)},{{SY("solo_variant"),V(true)}}));
        auto map=callm(snapshot,SY("to_dict"),Args{});
        callm(map,SY("pop"),Args{V("terrain_hash"),V::none()});
        setitem(rd(map,V("environment")),V("night"),V(night(c)));
        cache={seed,c.map,night(c),pm_team_maps::f_team_snapshot(Args{pm_maps::C_MapSnapshot::m_from_dict(Args{map})})};
    }
    return cache.snapshot;
}
void backdrop(const V& r,const Campaign& c){
    pm_menu_view::f__backdrop(Args{r,V(night(c)?"黑天":"白天"),V(false)});
    auto bridge=getattr(r,SY("bridge"));if(bridge.is_none())return;
    const auto snapshot=terrain(bridge,c);
    // The terrain dictionary and renderer cache survive hover redraws.
    static V previous,tiles;
    if(!previous.has()||!py_is(previous,snapshot)){previous=snapshot;tiles=callm(snapshot,SY("to_dict"),Args{});}
    const auto screen=getattr(r,SY("screen")),rect=callm(screen,SY("get_rect"),Args{});
    const double scale=getattr(rect,SY("h")).num()/rd(tiles,V("height")).num();
    callm(pm_menu_view::f__world(Args{r}),SY("_terrain"),Args{screen,tiles,V::tuple({V(0),V(0),V(scale),rect,rd(tiles,V("width"))})});
}
struct Current {std::filesystem::path path;Campaign c;bool exists=false;};
Current current;
void save();
void open(const V& app,const std::string& mode,bool fresh=false){
    if(mode!="lottery"&&mode!="izombie")throw std::invalid_argument("未知单机模式");
    const auto path=u8p(py_str(callm(app,SY("campaign_path"),Args{}))).parent_path()/(mode+"_v77.json");
    if(!fresh&&current.path==path)return;
    Current value;value.path=path;value.exists=std::filesystem::exists(path);
    if(value.exists&&!fresh){
        std::ifstream file(path,std::ios::binary);value.c=J::parse(file).get<Campaign>();
        if(value.c.mode!=mode||value.c.stage<1||value.c.stage>(value.c.zombie()?19:24))throw std::runtime_error("单机存档模式或关卡无效");
        auto& c=value.c;
        const std::string excluded=c.zombie()?"zombie:克苏鲁之仆":"secret:肆意模仿";
        for(auto* items:{&c.owned,&c.deck,&c.rewards})std::erase(*items,excluded);
        std::erase_if(c.shop,[&](const Offer& o){return o.key==excluded;});
        if(c.zombie()){
            std::erase(c.defenders,"plant:墓碑吞噬者");
            if(c.sun_bought<6&&std::none_of(c.shop.begin(),c.shop.end(),[](const auto& o){return o.key=="brain";})){
                const int price_stage=c.stage+int(!c.rewards.empty());
                c.shop.push_back({"brain",((100*(c.sun_bought+1)*(price_stage+9)+49)/50)*5,false});
            }
            if(!c.rewards.empty()&&c.rewards.size()<3){
                if(!has(c.owned,"zombie:梯子僵尸")){std::erase(c.rewards,"zombie:梯子僵尸");c.rewards.insert(c.rewards.begin(),"zombie:梯子僵尸");}
                for(const auto& card:campaign_pools().zombies)if(c.rewards.size()<3&&!card.secret&&!has(c.owned,card.key)&&!has(c.rewards,card.key)&&(card.dependency.empty()||has(c.owned,card.dependency)))c.rewards.push_back(card.key);
            }
        }
    }else value.c.start(mode,fresh_seed(),campaign_pools());
    const bool created=fresh||!value.exists;
    current=std::move(value);
    if(created)save();
}
void save(){
    std::filesystem::create_directories(current.path.parent_path());
    auto temp=current.path;temp+=".tmp";
    {std::ofstream out(temp,std::ios::binary|std::ios::trunc);out.exceptions(std::ios::failbit|std::ios::badbit);out<<J(current.c).dump(1);out.close();}
#ifdef _WIN32
    if(!MoveFileExW(temp.c_str(),current.path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("无法替换单机存档");
#else
    std::filesystem::rename(temp,current.path);
#endif
    current.exists=true;
}
void screen(V state,const std::string& name){setitem(state,V("screen"),V(name));setitem(state,V("solo_page"),V(0));setitem(state,V("solo_detail"),V(""));setitem(state,V("solo_reward_time"),V(0));setitem(state,V("pve_detail_scroll"),V(0));}
V act(const std::string& op,const std::string& key=""){return V::tuple({V("solo77"),V(op),V(key)});}
void button(const V& r,std::string text,int x,int y,int w,int h,V action,bool selected=false){
    callm(r,SY("button"),Args({V(text),V::tuple({V(x),V(y),V(w),V(h)}),action},{{SY("selected"),V(selected)},{SY("size"),V(16)}}));
}
void note(const V& r,const std::string& s,int x,int y,int width){
    callm(r,SY("text"),Args({V(s),V::tuple({V(x),V(y)})},{{SY("size"),V(15)},{SY("max_width"),V(width)}}));
}

struct SoloPage {
    V r, stage, pointer, fs, white=V::tuple({V(255),V(255),V(255)}),black=V::tuple({V(24),V(19),V(17)});
    SoloPage(const V& app,const V& renderer,bool bottom):r(renderer),
        stage(pm_pve_ui::new_Stage(Args{r,V(bottom)})),pointer(callm(app,SY("_pointer"),Args{})),
        fs(callm(stage,SY("font"),Args{})) {}
    V rect(double x,double y,double w,double h)const{return callm(stage,SY("rect"),Args{V(x),V(y),V(w),V(h)});}
    V pos(double x,double y)const{return callm(stage,SY("pos"),Args{V(x),V(y)});}
    V hitbox(const V& box)const{return callm(getattr(r,SY("pg")),SY("Rect"),Args{box});}
    bool over(const V& box)const{return !pointer.is_none()&&callm(hitbox(box),SY("collidepoint"),Args{pointer}).truthy();}
    void hit(const V& box,const V& action)const{getattr(r,SY("controls")).append(V::tuple({hitbox(box),action}));}
    void image(const std::string& key,const V& box,V alpha=V::none())const{pm_pve_ui::f_native_image(Args{r,V(key),box,alpha});}
    void background_art(const char* key,const V& box)const{
        // The selector and shop paintings belong to the background atlas.
        V art=callm(r,SY("artwork"),Args{V(key)});
        if(art.is_none()){
            auto path=gfx::atlas_file("背景图集",key);
            if(!path.empty()){
                auto pg=getattr(r,SY("pg"));
                art=callm(getattr(pg,SY("image")),SY("load"),Args{V(path)});
                setitem(getattr(r,SY("images")),V(key),art);
            }
        }
        image(key,box);
    }
    void packet(const std::string& key,const V& box)const{callm(r,SY("seed_packet"),Args{V(key),box});}
    void label(const std::string& text,double x,double y,double scale=1,double max_tiles=9)const{
        pm_pve_ui::f_label(Args{r,V(text),pos(x,y),white,V(int(fs.num()*scale)),black,V(int(getattr(stage,SY("u")).num()*max_tiles))});
    }
    void plaque(const char* image,const std::string& text,double x,double y,const V& action)const{
        pm_pve_ui::f_plaque(Args{r,stage,V(image),V(text),V(x),V(y),action,pointer,fs});
    }
    void detail(const std::string& key,const V& box,V state)const{
        auto lines=pm_pve_ui::f_card_lines(Args{V(key)});
        pm_pve_ui::f_detail_panel(Args{r,stage,lines,box,V("pve_detail_scroll"),state,fs});
    }
};
void draw_modes(const SoloPage& p){
    pm_menu_view::f__backdrop(Args{p.r});
    const std::array<std::string,3> covers{"选块","抽奖模式","我是僵尸"};
    const std::array<std::string,3> titles{"双人合作","抽奖模式","我是僵尸"};
    const std::array<V,3> actions{V::tuple({V("coop_lobby")}),act("open","lottery"),act("open","izombie")};
    p.background_art("主界面",p.rect(8.5,.03,3,3));
    static std::array<double,3> hover{};
    const auto now=std::chrono::steady_clock::now();static auto last=now;
    const double step=std::clamp(std::chrono::duration<double>(now-last).count()*7.,0.,1.);last=now;
    for(int i=0;i<3;++i){
        const double cx=6.45+3.55*i;
        const auto hit=p.rect(cx-1.5,2.95,3,5.8);const bool active=p.over(hit);
        hover[i]+=std::clamp((active?1.:0.)-hover[i],-step,step);
        const double lift=.25*hover[i],w=2.72+.16*hover[i],h=5.3+.2*hover[i];
        p.image(covers[i],p.rect(cx-w/2,3.08-lift,w,h));
        if(i==0){
            p.image("向日葵",p.rect(cx-1.02,5.49-lift,1.,1.));
            p.image("豌豆射手",p.rect(cx+.02,5.45-lift,1.,1.));
        }
        const auto title_box=p.rect(cx-w/2+.15,3.68-lift,w-.3,.85);
        pm_menu_view::f__center(Args{p.r,V(titles[i]),title_box,V(int(p.fs.num()*1.19)),
            active?pm_menu_view::GOLD:pm_menu_view::PAPER});
        p.hit(hit,actions[i]);
    }
    p.plaque("返回菜单","返回主界面",.45,9.8,act("home"));
}
std::string stage_title(const Campaign& c){
    return std::string(c.zombie()?"我是僵尸 · 第 ":"抽奖模式 · 第 ")+std::to_string(c.stage)+(c.zombie()?" 场":" 天");
}
void draw_shop(const SoloPage& p,V s,const Campaign& c){
    callm(p.r,SY("icon"),Args{V("疯狂戴夫"),p.rect(3.6,4.3,3.6,6.9)});
    p.background_art("商店",p.rect(0,0,20,11.25));
    V items=V::list();
    for(const auto& offer:c.shop){
        const auto& k=offer.key;const char* kind=(k=="sun"||k=="brain")?"sun":k=="slot"?"slot":k.starts_with("secret:")||k.starts_with("zsecret:")?"secret":"plant";
        items.append(py_dict({{V("kind"),V(kind)},{V("key"),V(k)},{V("price"),V(offer.price)},{V("sold"),V(offer.sold)}}));
    }
    const auto positions=pm_pve_ui::f_shop_positions(Args{items});std::string focus=py_str(get(s,"solo_detail",V("")));
    for(size_t i=0;i<c.shop.size();++i){
        const auto& offer=c.shop[i];const auto point=positions.idx(i);double x=point.idx(0).num(),y=point.idx(1).num();
        auto box=p.rect(x,y,1.5,1.5);const bool hover=p.over(box);if(hover)focus=offer.key;
        if(offer.key=="brain")p.image("脑子",p.rect(x,y-(hover?.12:0),1.5,1.5));
        else pm_pve_ui::f_draw_item(Args{p.r,p.stage,items.idx(i),V(x),V(y-(hover?.12:0))});
        if(offer.sold)p.image("植物卡黑",box,V(120));
        p.label(offer.sold?"已售":"$"+std::to_string(offer.price),x,y-.5);
        p.hit(box,act("inspect_buy",offer.key));
    }
    const auto selected=std::find_if(c.shop.begin(),c.shop.end(),[&](const Offer& o){return o.key==focus;});
    if(selected!=c.shop.end()){
        V lines=card(focus).truthy()?pm_pve_ui::f_card_lines(Args{V(focus)}):V::list({V(name(focus)),V(focus=="slot"?"可多携带一张卡牌。":focus=="brain"?"每场作战初始脑光增加25。":"每场作战初始阳光增加25。")});
        lines.append(V(selected->sold?"已售":("价格 $"+std::to_string(selected->price)+(c.coins<selected->price?" · 金币不足":" · 再点商品购买"))));
        pm_pve_ui::f_detail_panel(Args{p.r,p.stage,lines,p.rect(.3,1.6,6.5,7.5),V("pve_detail_scroll"),s,p.fs});
    }
    auto back=p.rect(.5,.5,3,1);p.image(p.over(back)?"走啦-选中":"走啦",back);p.hit(back,act("run"));
    p.image("钱袋",p.rect(.1,10.65,2,.5));p.label("$"+std::to_string(c.coins),.42,10.69);
}
void draw_rewards(const SoloPage& p,const Campaign& c,V s){
    const bool zombie=c.zombie();const size_t count=c.rewards.size();
    p.label(stage_title(c)+" · 选择一张新卡",6.5,.8,1.3);
    const auto ticks=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
    if(!get(s,"solo_reward_time").truthy())setitem(s,V("solo_reward_time"),V(ticks));
    const double elapsed=ticks-get(s,"solo_reward_time").num();
    std::string focus=py_str(get(s,"solo_detail",V("")));
    for(size_t i=0;i<count;++i){
        double dest=count==1?10.:count==2?7.+6*i:6.+4*i;
        double t=std::clamp((elapsed-i*(zombie?.25:.15))/.5,0.,1.);t=1.-(1.-t)*(1.-t);
        double x=10.+(dest-10.)*t,y=12.-9.*t;
        p.image("发光"+std::to_string(1+(int(ticks*6)+int(i))%3),p.rect(x-1.3,y-.55,2.9,2.9));
        auto box=p.rect(x-.56,y,1.46,1.97);p.packet(c.rewards[i],box);
        p.label(name(c.rewards[i]),x-.63,y+2.08,1.05,3.5);
        if(p.over(box))focus=c.rewards[i];p.hit(box,act("inspect_reward",c.rewards[i]));
    }
    if(has(c.rewards,focus))p.detail(focus,p.rect(4.4,6.25,11.2,2.65),s);
    if(!get(s,"solo_detail",V("")).truthy())p.label("点卡查看，再点领取",8,9.25,1.);
}
void draw_run(const SoloPage& p,V s,const Campaign& c){
    const double bottom=getattr(p.stage,SY("rows")).num()-1.5;
    if(!c.rewards.empty()){draw_rewards(p,c,s);p.plaque("返回菜单","返回模式选择",.4,bottom,act("modes"));return;}
    if(c.complete){
        p.image("金杯",p.rect(8.7,2.6,2.6,2.6));
        p.label(c.zombie()?"三个黄金脑子已摧毁":"已通过全部 24 天",7.4,5.6,1.3);
    }else{
        const V bank=pm_pve_ui::f_seed_bank_layout(Args{p.stage,V(c.slots())});
        callm(p.r,SY("native_seed_bank"),Args{get(bank,"rect"),V(c.slots())});
        if(c.zombie())p.image("脑子",p.rect(.22,.08,.94,.88));
        p.label(std::to_string(150+25*c.sun_bought),.48,1.02);
        for(size_t i=0;i<c.deck.size();++i){p.packet(c.deck[i],get(bank,"cards").idx(i));p.hit(get(bank,"slots").idx(i),act("deck",c.deck[i]));}
        p.image("选卡板",p.rect(0,1.5,8.6,8.55));
        const int capacity=c.owned.size()>48?40:48;
        const int page=std::clamp(int(get(s,"solo_page",V(0)).num()),0,std::max(0,(int(c.owned.size())-1)/capacity));
        std::string focus=py_str(get(s,"solo_detail",V("")));
        for(int j=0;j<capacity&&page*capacity+j<int(c.owned.size());++j){
            const auto& key=c.owned[page*capacity+j];double x=.32+j%8,y=2.05+(j/8)*1.3;
            const V box=p.rect(x,y,.975,1.3125);p.packet(key,box);
            if(has(c.deck,key))p.image("植物卡黑",p.rect(x,y,1.5,1.5),V(155));
            if(p.over(box)){focus=key;pm_pve_ui::f_card_glow(Args{p.r,box});}p.hit(box,act("deck",key));
        }
        if(page)p.plaque("返回菜单","上一页",.4,8.7,act("page",std::to_string(page-1)));
        if((page+1)*capacity<int(c.owned.size()))p.plaque("开始干","下一页",4.8,8.7,act("page",std::to_string(page+1)));
        p.label(stage_title(c),9.1,1.72,1.4);
        p.label(c.map+" · 卡槽 "+std::to_string(c.deck.size())+"/"+std::to_string(c.slots())+" · 金币 $"+std::to_string(c.coins),9.1,2.52);
        if(!c.zombie()&&(focus=="plant:模仿者"||focus=="plant:咖啡豆")){
            const bool copy=focus=="plant:模仿者";
            auto lines=V::list({V(copy?"随机模仿者":"咖啡豆"),V(copy?"从本模式全部合资格植物与僵尸中抽取。":"唤醒一株休眠植物，可重复使用。"),V(copy?"冷却 2 秒。Boss 关只抽植物。":"冷却 2 秒。")});
            pm_pve_ui::f_detail_panel(Args{p.r,p.stage,lines,p.rect(9.1,3.45,10.35,4.5),V("pve_detail_scroll"),s,p.fs});
        }else if(has(c.owned,focus))p.detail(focus,p.rect(9.1,3.45,10.35,4.5),s);
        else p.label(c.zombie()?(c.stage==19?"摧毁三个黄金脑子":"摧毁三个脑子"):(c.stage%8==0?"Boss 关 · 模仿者只抽植物":"随机模仿者每 2 秒可部署一次"),9.1,3.55);
        if(c.zombie())p.plaque("返回菜单", "本关植物与秘籍",9.2,8.15,act("defenders"));
        if(!c.deck.empty())p.plaque("开始干","开始作战",16.5,bottom,act("start"));
    }
    p.plaque("走啦","戴夫的商店",9.6,bottom,act("shop"));p.plaque("返回菜单","返回模式选择",13.05,bottom,act("modes"));
    p.plaque("返回菜单","重新开始",.4,bottom,act("confirm_reset"));
}

void start(const V& app){
    auto& c=current.c;if(c.complete||!c.rewards.empty()||c.deck.empty())return;
    callm(app,SY("create_offline_host"),Args{});const V room=getattr(app,SY("room"));
    auto err=callm(room,SY("set_mode"),Args{V("pve")});if(err.truthy())throw std::runtime_error(py_str(err));
    setattr(room,SY("map"),terrain(getattr(room,SY("bridge")),c));
    setattr(room,SY("map_id"),V(c.map));
    const int battle_seed=fresh_seed();
    setattr(room,SY("seed"),V(battle_seed));
    setitem(getattr(room,SY("rules")),V("pvp77_battle_seed"),V(battle_seed));
    if(c.zombie())setitem(getattr(room,SY("rules")),V("pvp77_start_brain"),V(150+25*c.sun_bought));
    V p=py_dict({{V("day"),V(c.stage)},{V("seed"),V(battle_seed)},{V("deck"),list(c.zombie()?c.plant_secrets:c.deck)},{V("decks"),V::dict()},{V("unlocked"),list(c.owned)},{V("slots"),V(c.slots())},{V("start_sun"),V(150+25*c.sun_bought)},{V("max_zombies"),V(40)},{V("pvp77_mode"),V(c.mode)},{V("pvp77_stage"),V(c.stage)},{V("pvp77_defenders"),list(c.defenders)},{V("pvp77_plants"),list(campaign_pools().random_plants)},{V("pvp77_zombies"),list(campaign_pools().random_zombies)}});
    const V enemy=c.zombie()?list(c.deck):pvp76r2::coop_zombie_secrets(V(std::to_string(c.seed)),V(1),V(c.stage));
    setitem(p,V("pvp77_zombie_deck"),enemy);setattr(room,SY("pve"),p);
    if(c.zombie())setitem(getattr(room,SY("members")),V("host"),V("zombie"));
    setattr(room,SY("on_pve_result"),getattr(app,SY("pve_result")));setattr(room,SY("replay_enabled"),V(false));
    callm(room,SY("_start_pve"),Args{});++c.attempt;save();
    screen(getattr(app,SY("state")),"room");callm(app,SY("refresh"),Args{});
}
}
bool result(const V& app,const V& r){
    auto room=getattr(app,SY("room"));if(!room.truthy())return false;
    auto mode=get(getattr(room,SY("pve")),"pvp77_mode");if(!mode.truthy())return false;
    open(app,py_str(mode));const bool win=get(r,"winner")==V(current.c.zombie()?"zombie":"plant");
    current.c.finish(campaign_pools(),py_str(getattr(room,SY("match_id"))),win,int(get(r,"coins",V(0)).num()),int(get(r,"diamond_coins",V(0)).num()));
    save();screen(getattr(app,SY("state")),"solo_run");return true;
}
bool action(const V& app,const V& input){
    if(!input.len()||input.idx(0)!=V("solo77"))return false;
    V s=getattr(app,SY("state"));auto op=py_str(input.idx(1)),arg=input.len()>2?py_str(input.idx(2)):"";
    try{
        if(op=="modes")screen(s,"solo_modes");
        else if(op=="home")screen(s,"home");
        else if(op=="open"||op=="reset"){open(app,arg,op=="reset");screen(s,"solo_run");}
        else if(op=="confirm_reset")screen(s,"solo_reset");
        else if(op=="run")screen(s,"solo_run");
        else if(op=="start")start(app);
        else if(op=="shop")screen(s,"solo_shop");
        else if(op=="defenders"||op=="pool"){setitem(s,V("defender_pool"),V(op=="defenders"));setitem(s,V("pool_books"),V(arg=="books"));screen(s,"solo_pool");}
        else if(op=="back_pool")screen(s,get(s,"defender_pool").truthy()?"solo_run":"room");
        else if(op=="details"){setitem(s,V("solo_detail"),V(arg));setitem(s,V("screen"),V("solo_pool_detail"));}
        else if(op=="pool_list")setitem(s,V("screen"),V("solo_pool"));
        else if(op=="page")setitem(s,V("solo_page"),V(std::stoi(arg)));
        else if(op=="inspect_buy"||op=="inspect_reward"){
            const auto key=get(s,"solo_detail",V(""));
            if(key!=V(arg)){setitem(s,V("solo_detail"),V(arg));setitem(s,V("pve_detail_scroll"),V(0));}
            else if(op=="inspect_buy"){auto error=current.c.buy(arg);if(!error.empty())callm(app,SY("message"),Args{V(error)});else save();}
            else if(has(current.c.rewards,arg)){current.c.reward(campaign_pools(),arg);save();screen(s,"solo_run");}
        }
        else if(op=="buy"){auto error=current.c.buy(arg);if(!error.empty())callm(app,SY("message"),Args{V(error)});else save();}
        else if(op=="reward"){current.c.reward(campaign_pools(),arg);save();}
        else if(op=="deck"){
            setitem(s,V("solo_detail"),V(arg));setitem(s,V("pve_detail_scroll"),V(0));
            auto error=current.c.toggle(campaign_pools(),arg);
            if(error.empty())save();else callm(app,SY("message"),Args{V(error)});
        }
    }catch(const std::exception& e){callm(app,SY("message"),Args{V(std::string("无法完成操作：")+e.what())});}
    return true;
}
void pool_button(const V& r){
    const auto size=callm(getattr(r,SY("screen")),SY("get_size"),Args{});
    const int w=int(size.idx(0).num()),h=int(size.idx(1).num());
    const int width=std::clamp(w/5,126,210);
    button(r,"僵尸卡池与秘籍",(w-width)/2,h*65/100,width,38,act("pool"));
}
bool draw(const V& app){
    const auto s=getattr(app,SY("state"));auto tab=py_str(get(s,"screen"));
    if(!tab.starts_with("solo_"))return false;
    auto r=getattr(app,SY("renderer"));auto sz=callm(getattr(r,SY("screen")),SY("get_size"),Args{});
    int w=int(sz.idx(0).num()),h=int(sz.idx(1).num());const auto& c=current.c;
    if(tab=="solo_modes"||tab=="solo_run"||tab=="solo_shop"||tab=="solo_reset"){
        const SoloPage page(app,r,tab=="solo_shop");
        callm(r,SY("start"),Args{V(""),V("")});
        if(tab=="solo_modes"){draw_modes(page);return true;}
        if(tab=="solo_shop"){draw_shop(page,s,c);return true;}
        backdrop(r,c);
        if(tab=="solo_reset"){
            page.label("重新开始将替换这个模式的进度",6.7,3.5,1.35);
            page.plaque("返回菜单","继续原进度",5.5,6.6,act("run"));
            page.plaque("开始干","确认重新开始",11.5,6.6,act("reset",c.mode));
        }else draw_run(page,s,c);
        return true;
    }
    const bool defending=get(s,"defender_pool").truthy();
    callm(r,SY("start"),Args{V(defending?"本关植物与秘籍":"合作卡池"),V("")});
    if(tab=="solo_pool_detail"){
        const V key=get(s,"solo_detail");
        const V definition=card(py_str(key));
        callm(r,SY("icon"),Args{get(definition,"asset"),V::tuple({V(28),V(90),V(60),V(70)})});
        note(r,py_str(get(definition,"name",key)),104,105,w-132);
        const V effect=pm_catalog::f_describe(Args{key});
        callm(r,SY("wrapped"),Args{effect,V::tuple({V(28),V(170),V(w-56),V(h-240)}),V(16)});
        button(r,"返回卡池",20,h-56,130,38,act("pool_list"));return true;
    }
    Keys items,today,recent;std::string operation;int top=150;
    if(tab=="solo_pool"&&defending){
        const bool books=get(s,"pool_books").truthy();items=books?c.plant_secrets:c.defenders;today=items;operation="details";
        if(c.stage>1&&!items.empty())recent.push_back(items.back());
        button(r,"植物",w-246,75,108,38,act("defenders"),!books);button(r,"植物秘籍",w-126,75,108,38,act("defenders","books"),books);
        note(r,stage_title(c)+" · "+std::to_string(items.size())+" 张",24,90,w-270);
        if(items.empty())note(r,"本关尚无植物秘籍",24,150,w-48);
    }else if(tab=="solo_pool"){
        auto v=getattr(app,SY("view"));const auto p=get(v,"pve");
        const int day=int(get(p,"day",V(1)).num());items=zombies(day);auto prev=day>1?zombies(day-1):Keys{};
        for(const auto& k:items)if(!has(prev,k))recent.push_back(k);
        today=zombies(day,get(v,"map"));const auto books=keys(get(p,"coop_zombie_secrets",V::list()));
        if(get(s,"pool_books",V(false)).truthy()){items=books;recent.clear();if(day>1&&!books.empty()&&int(books.size())==day-1)recent.push_back(books.back());}
        button(r,"僵尸",w-246,75,108,38,act("pool"),!get(s,"pool_books",V(false)).truthy());button(r,"僵尸秘籍",w-126,75,108,38,act("pool","books"),get(s,"pool_books",V(false)).truthy());
        note(r,"第 "+std::to_string(day)+" 天 · 点卡查看效果",24,90,w-48);operation="details";
        if(items.empty()&&get(s,"pool_books",V(false)).truthy())note(r,"尚未获得僵尸秘籍。每通关一天，从当日合资格的秘籍中加入一张。",24,150,w-48);
    }
    const int cols=std::max(2,std::min(5,w/165)),rows=std::max(1,(h-top-122)/60),cap=rows*cols;
    const int page=std::clamp(int(get(s,"solo_page",V(0)).num()),0,std::max(0,(int(items.size())-1)/cap));
    const int width=(w-40)/cols;
    for(int i=0;i<cap&&page*cap+i<int(items.size());++i){
        const auto& k=items[page*cap+i];int x=20+(i%cols)*width,y=top+(i/cols)*60;
        auto label=name(k);if(tab=="solo_shop"){const auto& o=c.shop[page*cap+i];label+=o.sold?" 已售":" $"+std::to_string(o.price);}
        if(tab=="solo_pool"){
            if(has(recent,k))label+=" 新";
            if(!has(today,k)&&!k.starts_with("zsecret:"))label+="（候补）";
        }
        button(r,label,x+30,y,width-34,47,act(operation,k),operation=="deck"&&has(c.deck,k));
        const auto art=get(card(k),"asset");if(art.truthy())callm(r,SY("icon"),Args{art,V::tuple({V(x),V(y+4),V(31),V(38)})});
    }
    if(page)button(r,"上一页",w-208,h-102,90,34,act("page",std::to_string(page-1)));
    if((page+1)*cap<int(items.size()))button(r,"下一页",w-108,h-102,90,34,act("page",std::to_string(page+1)));
    button(r,"返回",20,h-56,90,38,act("back_pool"));
    return true;
}
}
