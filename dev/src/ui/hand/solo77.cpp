#include "ui/hand/solo77.h"
#include "ui/hand/texture_pack.h"
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
        pm_catalog::init();pm_pve::init();pm_team_maps::init();Pools p;
        const auto entries=pm_team_maps::f_bundled_index(Args{});
        for(const auto& entry:entries.items())p.team_maps.push_back("custom:"+py_str(rd(entry,V("id"))));
        auto eligible=zombies(24);
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
std::string map_label(const Campaign& c){
    static const auto names=[]{
        std::map<std::string,std::string> result;
        const auto entries=pm_team_maps::f_bundled_index(Args{});
        for(const auto& e:entries.items())result.emplace("custom:"+py_str(rd(e,V("id"))),py_str(rd(e,V("name"))));
        return result;
    }();
    const auto where=names.find(c.map);
    return (where==names.end()?c.map:where->second)+(c.rain?" · 雨天":"");
}
void migrate_map(Campaign& c,bool coop){
    c.cooperative=coop;
    if(c.visited_maps.empty()&&!c.map.empty())c.visited_maps.push_back(c.map);
    if(c.zombie()&&!has(c.defenders,"plant:睡莲"))c.defenders.push_back("plant:睡莲");
}
bool night(const Campaign& c){return c.zombie()?c.stage%2==0:c.stage%4==3||c.stage%8==0;}
int terrain_seed(const Campaign& c){
    std::seed_seq sequence{c.seed,c.stage,c.attempt};unsigned value;
    sequence.generate(&value,&value+1);return int(value&0x3fffffff);
}
V terrain(const V& bridge,const Campaign& c){
    struct Preview {int seed=-1;std::string map;bool night=false,rain=false;V snapshot;};
    static Preview cache;const int seed=terrain_seed(c);
    if(cache.seed!=seed||cache.map!=c.map||cache.night!=night(c)||cache.rain!=c.rain){
        const auto snapshot=c.map.starts_with("custom:")?pm_team_maps::f_bundled_snapshot(Args{V(c.map.substr(7))}):
            pm_maps::f_build_snapshot(Args({bridge,V(c.map),V(seed)},{{SY("solo_variant"),V(true)},{SY("weather"),V(c.rain?"rain":"clear")}}));
        auto map=callm(snapshot,SY("to_dict"),Args{});
        callm(map,SY("pop"),Args{V("terrain_hash"),V::none()});
        setitem(map,V("seed"),V(seed));
        setitem(rd(map,V("environment")),V("night"),V(night(c)));
        cache={seed,c.map,night(c),c.rain,pm_team_maps::f_team_snapshot(Args{pm_maps::C_MapSnapshot::m_from_dict(Args{map})})};
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
        std::ifstream file(path,std::ios::binary);const auto record=J::parse(file);value.c=record.get<Campaign>();
        migrate_map(value.c,false);
        if(value.c.mode!=mode||value.c.stage<1||value.c.stage>(value.c.zombie()?19:24))throw std::runtime_error("单机存档模式或关卡无效");
        auto& c=value.c;
        if(!record.contains("clear_difficulty")&&(c.stage>1||c.complete))c.clear_difficulty=1;
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
void write_save(const std::filesystem::path& path,const J& record){
    std::filesystem::create_directories(path.parent_path());
    auto temp=path;temp+=".tmp";
    {std::ofstream out(temp,std::ios::binary|std::ios::trunc);out.exceptions(std::ios::failbit|std::ios::badbit);out<<record.dump(1);out.close();}
#ifdef _WIN32
    if(!MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("无法替换单机存档");
#else
    std::filesystem::rename(temp,path);
#endif
}
void save(){
    write_save(current.path,J(current.c));current.exists=true;
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
V selector_art(const SoloPage& page,const std::string& name,int x,int y,int w,int h){
    struct Cached { V source,scaled; int w=0,h=0; };
    static std::map<std::string,Cached> cache;
    const auto rect=page.hitbox(V::tuple({V(x),V(y),V(w),V(h)}));
    if(w<1||h<1)return rect;
    V art=texture74::artwork((name=="主界面"?"bg:":"ui:")+name);
    if(art.is_none())art=texture74::artwork("world:"+name);
    if(art.is_none())art=callm(getattr(pm_menu_view::f__world(Args{page.r}),SY("art")),SY("raw"),Args{V(name)});
    if(art.is_none())return rect;
    auto& cached=cache[name];
    if(!py_is(cached.source,art)||cached.w!=w||cached.h!=h){
        const auto bounds=callm(art,SY("get_bounding_rect"),Args{});
        const double cw=getattr(bounds,SY("w")).num(),ch=getattr(bounds,SY("h")).num();
        if(cw<1||ch<1)return rect;
        const double scale=std::min(w/cw,h/ch);
        const auto cropped=callm(art,SY("subsurface"),Args{bounds});
        const auto size=V::tuple({V(std::max(1,int(std::round(cw*scale)))),V(std::max(1,int(std::round(ch*scale))))});
        cached={art,callm(getattr(getattr(page.r,SY("pg")),SY("transform")),SY("scale"),Args{cropped,size}),w,h};
    }
    const auto dest=callm(cached.scaled,SY("get_rect"),Args({},{{SY("center"),getattr(rect,SY("center"))}}));
    callm(getattr(page.r,SY("screen")),SY("blit"),Args{cached.scaled,dest});return dest;
}
void draw_modes(const SoloPage& p){
    pm_menu_view::f__backdrop(Args{p.r});
    const auto screen=getattr(p.r,SY("screen"));
    const int w=int(callm(screen,SY("get_width"),Args{}).num());
    const int h=int(callm(screen,SY("get_height"),Args{}).num());
    auto rect=[](int x,int y,int w,int h){return V::tuple({V(x),V(y),V(w),V(h)});};
    const int logo=std::min(h/4,std::clamp(h/5,97,145));
    selector_art(p,"主界面",(w-logo*4/3)/2,8,logo*4/3,logo);
    const int card_h=std::min({330,(h-logo-96),w*79/180});
    const int card_w=std::max(1,card_h*36/79);
    const int gap=std::min(card_w*44/100,std::max(0,(w-card_w*4)/5));
    const int left=(w-card_w*4-gap*3)/2,top=logo+32;
    const std::array<std::string,4> covers{"选块","新游戏","抽奖模式","我是僵尸"};
    const std::array<std::string,4> titles{"合作模式","单人闯关","抽奖模式","我是僵尸"};
    const std::array<V,4> actions{V::tuple({V("coop_lobby")}),act("adventure"),act("open","lottery"),act("open","izombie")};
    static std::array<double,4> hover{};
    const auto now=std::chrono::steady_clock::now();static auto last=now;
    const double step=std::clamp(std::chrono::duration<double>(now-last).count()*7.,0.,1.);last=now;
    for(size_t i=0;i<covers.size();++i){
        const int x=left+int(i)*(card_w+gap);
        const bool active=p.over(rect(x,top-card_h/45,card_w,card_h+card_h/45));
        hover[i]+=std::clamp((active?1.:0.)-hover[i],-step,step);
        const int y=top-int(hover[i]*card_h/45);
        const auto drawn=selector_art(p,covers[i],x,y,card_w,card_h);
        const int bx=int(getattr(drawn,SY("x")).num()),by=int(getattr(drawn,SY("y")).num());
        const int bw=int(getattr(drawn,SY("w")).num()),bh=int(getattr(drawn,SY("h")).num());
        if(i==0){
            p.image("向日葵",rect(bx+bw/8,by+bh*43/100,bw*3/8,bw*3/8));
            p.image("豌豆射手",rect(bx+bw/2,by+bh*43/100,bw*3/8,bw*3/8));
        }
        pm_menu_view::f__center(Args{p.r,V(titles[i]),rect(bx+bw/8,by+bh*7/100,bw-2*(bw/8),bh/9),
            V(std::clamp(bw/7,10,20)),active?pm_menu_view::GOLD:pm_menu_view::PAPER});
        p.hit(drawn,actions[i]);
    }
    p.plaque("返回菜单","返回主界面",.45,9.8,act("home"));
}
std::string stage_title(const Campaign& c){
    return std::string(c.zombie()?"我是僵尸 · 第 ":"抽奖模式 · 第 ")+std::to_string(c.stage)+(c.zombie()?" 场":" 天");
}
} // namespace
V shop_rect(const V& stage,const V& item,const V& x,const V& y){
    const V kind=get(item,"kind");
    if(get(item,"key")==V("brain"))
        return callm(stage,SY("rect"),Args{x+V(.1875),y+V(.25),V(1.125),V(1.0625)});
    const double width=kind==V("secret")?1.1625:.975;
    const double height=kind==V("secret")?1.2:kind==V("sun")?1.35:1.3125;
    return callm(stage,SY("rect"),Args{x,y,V(width),V(height)});
}
V seat_rally(const V& app,const V& view){
    const auto battle=get(view,"battle"),points=get(battle,"rally_points");
    if(points.is_dict()){
        const auto seat=callm(app,SY("local_seat"),Args{V("zombie")});
        return get(points,py_str(seat).c_str());
    }
    return get(battle,"rally_point");
}
namespace {
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
        auto base=shop_rect(p.stage,items.idx(i),V(x),V(y));
        const bool hover=p.over(base);if(hover)focus=offer.key;
        const auto box=shop_rect(p.stage,items.idx(i),V(x),V(y-(hover?.12:0)));
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
double animation_time(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
void claim_animation(V s,const Campaign& c,const std::string& key){
    const auto at=std::find(c.rewards.begin(),c.rewards.end(),key);
    if(at==c.rewards.end())return;
    const auto i=at-c.rewards.begin();
    setitem(s,V("solo78_claim"),V(key));setitem(s,V("solo78_claim_start"),V(animation_time()));
    setitem(s,V("solo78_claim_x"),V(c.rewards.size()==1?10.:c.rewards.size()==2?7.+6*i:6.+4*i));
}
bool draw_claim(const SoloPage& p,V s,const Campaign& c){
    const auto key=get(s,"solo78_claim");if(!key.truthy())return false;
    const double elapsed=animation_time()-get(s,"solo78_claim_start").num();
    if(elapsed>=.65&&(has(c.owned,py_str(key))||elapsed>3.)){
        callm(s,SY("pop"),Args{V("solo78_claim")});return false;
    }
    const double t=std::clamp(elapsed/.65,0.,1.),ease=t*t*(3.-2.*t);
    const double start=get(s,"solo78_claim_x").num()-.56;
    p.packet(py_str(key),p.rect(start+(1.1-start)*ease,3.-2.85*ease,1.46-.49*ease,1.97-.66*ease));
    return true;
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
void draw_run(const SoloPage& p,V s,const Campaign& c,bool coop,bool host){
    const char* back=coop?"返回房间":"返回模式选择";
    const double bottom=getattr(p.stage,SY("rows")).num()-1.5;
    if(!c.rewards.empty()){draw_rewards(p,c,s);p.plaque("返回菜单",back,.4,bottom,act("modes"));return;}
    if(c.complete){
        p.image(c.clear_difficulty==4?"金杯":"银杯",p.rect(8.7,2.6,2.6,2.6));
        const V color=c.clear_difficulty==4?pm_menu_view::GOLD:c.clear_difficulty==2?V::tuple({V(255),V(96),V(96)}):p.white;
        pm_pve_ui::f_label(Args{p.r,V(c.zombie()?"三个黄金脑子已摧毁":"已通过全部 24 天"),p.pos(7.4,5.6),color,V(int(p.fs.num()*1.3)),p.black});
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
        p.label(map_label(c)+" · 卡槽 "+std::to_string(c.deck.size())+"/"+std::to_string(c.slots())+" · 金币 $"+std::to_string(c.coins),9.1,2.52);
        if(!c.zombie()&&(focus=="plant:模仿者"||focus=="plant:咖啡豆")){
            const bool copy=focus=="plant:模仿者";
            auto lines=V::list({V(copy?"随机模仿者":"咖啡豆"),V(copy?"从本模式全部合资格植物与僵尸中抽取。":"唤醒一株休眠植物，可重复使用。"),V(copy?"冷却 2 秒。Boss 关只抽植物。":"冷却 2 秒。")});
            pm_pve_ui::f_detail_panel(Args{p.r,p.stage,lines,p.rect(9.1,3.45,10.35,4.5),V("pve_detail_scroll"),s,p.fs});
        }else if(has(c.owned,focus))p.detail(focus,p.rect(9.1,3.45,10.35,4.5),s);
        else p.label(c.zombie()?(c.stage==19?"摧毁三个黄金脑子":"摧毁三个脑子"):(c.stage%8==0?"Boss 关 · 模仿者只抽植物":"随机模仿者每 2 秒可部署一次"),9.1,3.55);
        const char* difficulty=c.difficulty==4?"末日 ×4":c.difficulty==2?"极难 ×2":"一般 ×1";
        if(!coop||host)callm(p.r,SY("button"),Args({V(difficulty),p.rect(16.1,2.3,3.2,.72),act("solo_difficulty")},{{SY("size"),p.fs}}));
        if(c.zombie())p.plaque("返回菜单", "本关植物与秘籍",9.2,8.15,act("defenders"));
        if(!c.deck.empty())p.plaque("开始干","开始作战",16.5,bottom,act("start"));
    }
    p.plaque("走啦","戴夫的商店",9.6,bottom,act("shop"));p.plaque("返回菜单",back,13.05,bottom,act("modes"));
    if(!coop||host)p.plaque("返回菜单","重新开始",.4,bottom,act("confirm_reset"));
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
    setitem(p,V("pvp78_run"),V(std::to_string(c.seed)));
    setitem(getattr(room,SY("rules")),V("pvp78_health"),V(c.difficulty));
    setitem(p,V("pvp77_zombie_deck"),enemy);setattr(room,SY("pve"),p);
    if(c.zombie())setitem(getattr(room,SY("members")),V("host"),V("zombie"));
    setattr(room,SY("on_pve_result"),getattr(app,SY("pve_result")));setattr(room,SY("replay_enabled"),V(false));
    callm(room,SY("_start_pve"),Args{});++c.attempt;save();
    screen(getattr(app,SY("state")),"room");callm(app,SY("refresh"),Args{});
}
}
namespace {
V pack(const J& value){return py::json_loads(V(value.dump()));}
J unpack(const V& value){return J::parse(py_str(py::stdlib_call(SV("json.dumps"),Args{value})));}
bool special_coop(const V& pve){return get(pve,"campaign78_seats").is_dict();}
V local_room_view(const V& app){
    const auto room=getattr(app,SY("room"));
    if(room.truthy()&&getattr(app,SY("mode"))!=V("guest"))return getattr(room,SY("pve"),V::none());
    return get(getattr(app,SY("view")),"pve");
}
V own_seat(const V& app){
    const auto room=getattr(app,SY("room")),peer=getattr(app,SY("peer_id"));
    if(room.truthy()&&getattr(app,SY("mode"))!=V("guest"))return callm(room,SY("side_for"),Args{peer});
    return get(get(getattr(app,SY("view")),"members"),py_str(peer).c_str());
}
Campaign seat_campaign(const V& pve,const V& seat){return unpack(rd(get(pve,"campaign78_seats"),seat)).get<Campaign>();}
void store_seats(const V& room,const V& seats){
    auto pve=getattr(room,SY("pve"));
    const auto path=u8p(py_str(getattr(room,SY("_campaign78_path"))));
    write_save(path,unpack(seats));setitem(pve,V("campaign78_seats"),seats);
    for(const auto& [seat,row]:py::items_vec(seats)){
        const auto c=unpack(row).get<Campaign>();
        setitem(get(pve,"decks"),seat,list(c.deck));
        setitem(get(pve,"seat_slots"),seat,V(c.slots()));
        setitem(get(pve,"seat_start_sun"),seat,V(150+25*c.sun_bought));
    }
}
void setup_coop_board(const V& room){
    auto p=getattr(room,SY("pve")),rules=getattr(room,SY("rules"));
    const bool zombie=get(p,"pvp77_mode")==V("izombie");
    const auto c=seat_campaign(p,V(zombie?"zombie":"plant"));
    const auto other=seat_campaign(p,V(zombie?"zombie2":"plant2"));
    setitem(p,V("day"),V(c.stage));setitem(p,V("pvp77_stage"),V(c.stage));
    setitem(p,V("seed"),V(terrain_seed(c)));setitem(p,V("pvp78_run"),V(std::to_string(c.seed)));
    setitem(p,V("deck"),list(zombie?c.plant_secrets:c.deck));
    setitem(p,V("slots"),V(std::max(c.slots(),other.slots())));
    setitem(p,V("unlocked"),list(c.owned));
    setitem(p,V("pvp77_defenders"),list(c.defenders));
    setitem(p,V("pvp77_plants"),list(campaign_pools().random_plants));
    setitem(p,V("pvp77_zombies"),list(campaign_pools().random_zombies));
    setitem(p,V("pvp77_zombie_deck"),zombie?list(c.deck):pvp76r2::coop_zombie_secrets(V(std::to_string(c.seed)),V(1),V(c.stage)));
    setitem(rules,V("pvp78_coop_campaign"),V(true));
    setitem(rules,V("pvp77_battle_seed"),V(terrain_seed(c)));
    setitem(rules,V("pvp77_start_brain"),V(150+25*c.sun_bought));setitem(rules,V("pvp78_start_brain2"),V(150+25*other.sun_bought));
    setattr(room,SY("map"),terrain(getattr(room,SY("bridge")),c));setattr(room,SY("map_id"),V(c.map));setattr(room,SY("seed"),V(terrain_seed(c)));
}
}
bool draw_coop(const V& app,const V& r,const V& view){
    const auto pve=get(view,"pve");if(!special_coop(pve))return false;
    const bool zombie=get(pve,"pvp77_mode")==V("izombie"),ended=get(view,"phase")==V("result");
    const auto state=getattr(app,SY("state")),mine=own_seat(app);
    const auto players=get(view,"members",V::dict()),ready=get(view,"confirmed",V::dict());
    const SoloPage p(app,r,false);
    auto first=seat_campaign(pve,V(zombie?"zombie":"plant"));
    callm(r,SY("start"),Args{V(""),V("")});backdrop(r,first);
    p.label(zombie?"合作我是僵尸":"合作抽奖",.65,.45,1.35);
    const auto profiles=get(view,"player_profiles",V::dict());
    for(int i=0;i<2;++i){
        const auto seat=V(zombie?(i?"zombie2":"zombie"):(i?"plant2":"plant"));
        V peer;for(const auto& [id,place]:py::items_vec(players))if(place==seat)peer=id;
        const double x=.55+i*4.5;const auto c=seat_campaign(pve,seat);
        auto box=p.rect(x,1.65,4.25,3.7);callm(r,SY("native_frame"),Args{V("选卡板"),box,V(8)});
        callm(r,SY("icon"),Args{V(zombie?"僵尸戴夫":"疯狂戴夫"),p.rect(x+.24,2.02,1.25,2.)});
        p.label(peer.truthy()?py_str(get(get(profiles,py_str(peer).c_str()),"name",V("戴夫"))):"待加入",x+1.52,2.1,1,2.4);
        p.label(std::to_string(i+1)+" 号席 · "+std::to_string(c.deck.size())+" 张",x+1.52,2.85,.82,2.5);
        const auto connected=get(view,"connected",V::dict());
        const bool online=peer.truthy()&&get(connected,py_str(peer).c_str(),V(true)).truthy();
        const bool prepared=online&&get(ready,py_str(seat).c_str()).truthy();
        const char* status=!peer.truthy()?"空位":!online?"已断线":prepared?"已准备":"待准备";
        const V color=prepared?V::tuple({V(120),V(240),V(120)}):online?pm_menu_view::GOLD:p.white;
        pm_pve_ui::f_label(Args{r,V(status),p.pos(x+1.52,3.48),color,p.fs,p.black});
        if(get(view,"can_kick").truthy()&&peer.truthy()&&peer!=V("host"))
            callm(r,SY("button"),Args{V("请出"),p.rect(x+.5,4.45,2.95,.6),V::tuple({V("kick"),peer})});
        if(get(view,"can_change_role").truthy()&&!mine.truthy()&&!peer.truthy())
            callm(r,SY("button"),Args{V("入座"),p.rect(x,5.6,4.2,.68),V::tuple({V("spectator_role"),V("player"),seat})});
    }
    if(get(view,"can_change_role").truthy()&&mine.truthy())
        callm(r,SY("button"),Args{V("转为观战"),p.rect(.55,5.6,4.2,.68),V::tuple({V("spectator_role"),V("spectator")})});
    p.label(map_label(first)+" · "+stage_title(first),9.9,1.9,1.05,9.);
    if(ended)p.label(get(get(view,"result"),"winner")==V(zombie?"zombie":"plant")?"本关通过":"本关失败",9.9,2.7,1.1);
    if(get(state,"token").truthy()){
        p.label("邀请码 "+py_str(get(state,"token")),9.9,3.6,1.,6.7);
        callm(r,SY("button"),Args{V("复制邀请码"),p.rect(16.,3.42,3.2,.7),V::tuple({V("copy_relay_code")})});
    }
    const auto endpoints=get(state,"endpoints",V::list());
    if(get(state,"network_mode")==V("direct")&&endpoints.len()){
        const int index=int(get(state,"endpoint_index",V(0)).num())%int(endpoints.len());
        p.label(py_str(endpoints.idx(index)),9.9,4.54,1.,9.);
        callm(r,SY("button"),Args{V("切换地址"),p.rect(9.9,5.2,3,.68),V::tuple({V("endpoint"),V(1)})});
        callm(r,SY("button"),Args{V("复制地址"),p.rect(13.3,5.2,3,.68),V::tuple({V("copy_address")})});
    }
    if(mine.truthy()){
        p.plaque("走啦","选卡 · 商店",10.1,8.65,V::tuple({V("pve_open")}));
        p.plaque("开始干",ended?"准备下一关":"确认作战",16.35,8.65,V::tuple({V("pve_start")}));
    }
    p.plaque("返回菜单","离开房间",.45,8.65,V::tuple({V("leave")}));
    callm(r,SY("button"),Args{V("聊天"),p.rect(4.8,9.45,2.5,.72),V::tuple({V("chat_open")})});
    p.label(py_str(get(state,"message",V(""))),.65,7.1,1,18.8);
    return true;
}
void init_coop(const V& app){
    const auto state=getattr(app,SY("state")),room=getattr(app,SY("room"));
    const auto mode=get(state,"coop78_variant");
    if((mode!=V("lottery")&&mode!=V("izombie"))||!room.truthy()||getattr(room,SY("mode"))!=V("coop"))return;
    if(special_coop(getattr(room,SY("pve"))))return;
    const bool zombie=mode==V("izombie");
    const auto folder=u8p(py_str(callm(app,SY("campaign_path"),Args{}))).parent_path();
    const auto path=folder/("coop_"+py_str(mode)+"_v78.json");
    J saved;
    if(std::filesystem::exists(path)){std::ifstream in(path,std::ios::binary);saved=J::parse(in);}
    else{
        Campaign c;c.start(py_str(mode),fresh_seed(),campaign_pools(),true);
        saved[zombie?"zombie":"plant"]=c;saved[zombie?"zombie2":"plant2"]=c;
    }
    for(auto& row:saved){auto c=row.get<Campaign>();migrate_map(c,true);row=c;}
    auto pve=py_dict({{V("campaign78_seats"),pack(saved)},{V("pvp77_mode"),mode},{V("decks"),V::dict()},
        {V("seat_slots"),V::dict()},{V("seat_start_sun"),V::dict()},{V("start_sun"),V(150)},
        {V("max_zombies"),get(getattr(room,SY("rules")),"pve_max_zombies",V(40))}});
    setattr(room,SY("_campaign78_path"),V(p8(path)));setattr(room,SY("pve"),pve);
    if(zombie){
        const auto members=getattr(room,SY("members"));
        for(const auto& [peer,seat]:py::items_vec(members))setitem(members,peer,V(seat==V("plant2")?"zombie2":"zombie"));
    }
    callm(room,SY("_reset_selection"),Args{});
    store_seats(room,get(pve,"campaign78_seats"));setup_coop_board(room);
}
V coop_ready(const V& room,const V& peer){
    const auto p=getattr(room,SY("pve")),seat=callm(room,SY("side_for"),Args{peer});
    if(!seat.truthy())return V("旁观者不能准备");
    const auto c=seat_campaign(p,seat);
    if(c.complete)return V("本轮已经通关");
    if(!c.rewards.empty())return V("请先领取上一关奖励");
    if(c.deck.empty())return V("请先选择卡组");
    for(const auto& [other,_]:py::items_vec(get(p,"campaign78_seats")))if(seat_campaign(p,other).stage!=c.stage)return V("等待队友领取奖励");
    return V("");
}
V coop_command(const V& room,const V& peer,const V& payload){
    const auto p=getattr(room,SY("pve")),op=get(payload,"type");
    if(!special_coop(p))return V::none();
    if(op==V("fill_ai")||op==V("pve_deck")||op==V("coop_buy")||op==V("coop_reward")||op==V("coop_skip")||op==V("coop_reset_deck")||op==V("coop_gift"))return V("请使用本模式的备战界面");
    if(op!=V("campaign78"))return V::none();
    const auto operation=get(payload,"operation"),seat=callm(room,SY("side_for"),Args{peer});
    if(!seat.truthy())return V("仅入座玩家可以调整备战");
    const auto phase=getattr(room,SY("phase"));
    if(phase!=V("config")&&phase!=V("result"))return V("请在备战时操作");
    const auto key=py_str(get(payload,"key",V("")));
    auto c=seat_campaign(p,seat);
    if(get(payload,"stage")!=V(c.stage)||get(payload,"match")!=V(c.last_result))return V("关卡已更新，请重新打开备战");
    std::string error;
    if(operation==V("restart")){
        if(peer!=V("host"))return V("只有房主可重新开始");
        const auto mode=c.mode;c.start(mode,fresh_seed(),campaign_pools(),true);
        auto seats=V::dict();
        for(const auto& [id,_]:py::items_vec(get(p,"campaign78_seats")))setitem(seats,id,pack(J(c)));
        store_seats(room,seats);callm(room,SY("_reset_selection"),Args{});setup_coop_board(room);
        return V("");
    }
    if(operation==V("deck"))error=c.toggle(campaign_pools(),key);
    else if(operation==V("buy"))error=c.buy(key);
    else if(operation==V("reward")){
        if(!has(c.rewards,key))return V("奖励已经领取或无效");c.reward(campaign_pools(),key);
    }else if(operation==V("prepare")){
        if(phase==V("result")&&peer!=V("host"))return V("等待房主准备下一关");
        const auto ready=coop_ready(room,peer);if(ready.truthy())return ready;
        if(phase==V("result"))callm(room,SY("_reset_selection"),Args{});
        setup_coop_board(room);
        return callm(room,SY("command"),Args{peer,py_dict({{V("type"),V("confirm_map")},{V("terrain_hash"),getattr(getattr(room,SY("map")),SY("terrain_hash"))},{V("revision"),getattr(room,SY("revision"))}})});
    }else if(operation==V("gift")){
        int amount=0;
        if(key.empty()||key.size()>9||key.find_first_not_of("0123456789")!=std::string::npos)return V("请输入正整数金币数量");
        amount=std::stoi(key);if(amount<=0||amount>c.coins)return V("金币不足");
        const auto mate=V(c.zombie()?(seat==V("zombie")?"zombie2":"zombie"):(seat==V("plant")?"plant2":"plant"));
        auto other=seat_campaign(p,mate);if(other.coins>1000000000-amount)return V("队友金币已达上限");
        c.coins-=amount;other.coins+=amount;
        auto seats=py::dict_of(get(p,"campaign78_seats"));setitem(seats,seat,pack(J(c)));setitem(seats,mate,pack(J(other)));
        store_seats(room,seats);setattr(room,SY("revision"),getattr(room,SY("revision"))+V(1));return V("");
    }else return V("未知备战操作");
    if(!error.empty())return V(error);
    auto seats=py::dict_of(get(p,"campaign78_seats"));
    setitem(seats,seat,pack(J(c)));store_seats(room,seats);
    setitem(getattr(room,SY("confirmed")),seat,V(false));setattr(room,SY("revision"),getattr(room,SY("revision"))+V(1));
    return V("");
}
void result_receipt(const V& room,const V& result){
    const auto p=getattr(room,SY("pve"));
    const auto mode=getattr(room,SY("mode"));
    if(!p.is_dict()||(mode!=V("coop")&&mode!=V("pve")))return;
    const auto run=get(p,"pvp78_run",get(p,"coop_run_id",V("")));
    setitem(result,V("pve_day"),get(p,"day"));
    const std::string key=(mode==V("coop")?"coop_":"solo_")+py_str(get(p,"pvp77_mode",V("adventure")));
    setitem(result,V("campaign78"),py_dict({{V("mode"),V(key)},{V("run"),run},
        {V("match"),getattr(room,SY("match_id"))},{V("members"),getattr(room,SY("match_members"))},
        {V("factor"),getattr(room,SY("_pvp78_match_grade"),get(getattr(room,SY("rules")),"pvp78_health",V(1)))},
        {V("seconds"),getattr(room,SY("_pvp78_seconds"),V(0))}}));
}
void start_coop_attempt(const V& room){
    const auto pve=getattr(room,SY("pve"));
    if(special_coop(pve)){
        auto states=get(pve,"campaign78_seats");
        auto seats=py::dict_of(states);
        for(const auto& [seat,row]:py::items_vec(states)){
            auto c=unpack(row).get<Campaign>();++c.attempt;
            setitem(seats,seat,pack(J(c)));
        }
        store_seats(room,seats);
    }else{
        auto progress=getattr(room,SY("coop_progress"));
        setattr(progress,SY("terrain_attempt"),getattr(progress,SY("terrain_attempt"),V(0))+V(1));
        callm(progress,SY("save"),Args{});
    }
}
void settle_coop(const V& room,const V& result){
    const auto p=getattr(room,SY("pve"));auto seats=py::dict_of(get(p,"campaign78_seats"));
    const auto match=py_str(getattr(room,SY("match_id")));
    for(const auto& [seat,row]:py::items_vec(seats)){
        auto c=unpack(row).get<Campaign>();if(c.last_result==match)continue;
        setitem(getattr(room,SY("confirmed")),seat,V(false));
        const int coins=int(get(get(result,"seat_coins"),py_str(seat).c_str(),V(0)).num());
        const int diamonds=int(get(get(result,"seat_diamonds"),py_str(seat).c_str(),V(0)).num());
        c.difficulty=int(get(get(result,"campaign78"),"factor",get(getattr(room,SY("rules")),"pvp78_health",V(1))).num());
        c.finish(campaign_pools(),match,get(result,"winner")==V(c.zombie()?"zombie":"plant"),coins,diamonds);
        setitem(seats,seat,pack(J(c)));
    }
    store_seats(room,seats);
}
bool adventure_rain(const V& campaign){
    return rainy_stage(int(getattr(campaign,SY("seed")).num()),int(getattr(campaign,SY("day")).num()));
}
V adventure_map(const V& campaign){
    const auto day=int(getattr(campaign,SY("day")).num());
    return V(map_for_stage(original_maps(),py_str(getattr(campaign,SY("seed"))),day));
}
V classic_map(const V& app,const V& day,const V& coop){
    const auto map=pm_pve::f_map_for_day(Args{day,coop});
    if(!coop.truthy())return map;
    const auto room=getattr(app,SY("room"),V::none());
    const auto pve=get(getattr(app,SY("view"),V::none()),"pve");
    auto run=get(pve,"coop_run_id");
    if(room.truthy()&&getattr(app,SY("mode"))!=V("guest")){
        const auto progress=getattr(room,SY("coop_progress"),V::none());
        if(progress.truthy())run=getattr(progress,SY("run_id"));
    }
    if(!run.truthy())return map;
    const auto id=map_for_stage(campaign_pools().team_maps,py_str(run),int(day.num()));
    return V::tuple({V("team"),V(id.substr(7)),map.idx(2)});
}
V classic_seed(const V& room,const V& campaign,const V& day){
    if(!room.truthy()||getattr(room,SY("mode"))!=V("coop")){
        const auto history=getattr(campaign,SY("history"));
        if(history.len())return get(history.idx(-1),"attempt_seed",getattr(campaign,SY("seed"))+day);
        return getattr(campaign,SY("seed"))+day;
    }
    const auto progress=getattr(room,SY("coop_progress"));
    const auto run=py_str(getattr(progress,SY("run_id")));
    std::vector<uint32_t> words(run.begin(),run.end());
    words.push_back(uint32_t(day.num()));
    words.push_back(uint32_t(getattr(progress,SY("terrain_attempt"),V(0)).num()));
    std::seed_seq sequence(words.begin(),words.end());unsigned value;
    sequence.generate(&value,&value+1);
    return V(int(value&0x3fffffff));
}
void configure_adventure(const V& room,const V& campaign){
    Campaign layout;
    layout.mode="adventure";layout.map=py_str(adventure_map(campaign));layout.rain=adventure_rain(campaign);
    layout.stage=int(getattr(campaign,SY("day")).num());
    layout.seed=int(getattr(campaign,SY("seed")).num());
    layout.attempt=fresh_seed();
    setattr(room,SY("map"),terrain(getattr(room,SY("bridge")),layout));
    setattr(room,SY("map_id"),V(layout.map));setattr(room,SY("seed"),V(terrain_seed(layout)));
    const auto rules=getattr(room,SY("rules")),pve=getattr(room,SY("pve"));
    setitem(rules,V("pvp78_adventure"),V(true));
    setitem(pve,V("pvp78_run"),V(std::to_string(layout.seed)));
    setitem(pve,V("coop_zombie_secrets"),pvp76r2::coop_zombie_secrets(V(std::to_string(layout.seed)),V(1),V(layout.stage)));
}
void difficulty_buttons(const V& app,const V& r,const V& stage,const V& x,const V& y,const V& width,const V& fs){
    const auto state=getattr(app,SY("state")),room=getattr(app,SY("room"));
    const bool entry=get(state,"screen")==V("coop_entry");
    const bool guest=getattr(app,SY("mode"))==V("guest");
    const auto view=getattr(app,SY("view"));
    const auto source=guest?get(view,"rules"):room.truthy()&&!entry?getattr(room,SY("rules")):state;
    const auto factor=get(source,"pvp78_health",V(1));
    if(entry){
        const auto variant=get(state,"coop78_variant",V("adventure"));
        const auto box=callm(stage,SY("rect"),Args{V(x.num()),V(y.num()+1.30),V(4.9),V(.48)});
        const char* label=variant==V("izombie")?"合作我是僵尸":variant==V("lottery")?"合作抽奖":"常规合作";
        callm(r,SY("button"),Args({V(label),box,act("variant")},{{SY("size"),fs}}));
    }
    const std::array<const char*,3> captions{"一般 ×1","极难 ×2","末日 ×4"};
    // The entry page also has a create button on the right of this row.
    const double space=entry?4.9:width.num(),w=space/3.;
    for(int i=0;i<3;++i){
        const auto box=callm(stage,SY("rect"),Args{V(x.num()+w*i),V(y.num()+.7),V(w-.08),V(.57)});
        callm(r,SY("button"),Args({V(captions[i]),box,act("difficulty",std::to_string(1<<i))},{{SY("selected"),V(factor==V(1<<i))},{SY("size"),V(std::max(10,int(fs.num())-2))}}));
    }
}
namespace {
struct RecordBook {
    std::filesystem::path path;
    J data=J::object();
    void load(const V& app){
        const auto file=u8p(py_str(callm(app,SY("campaign_path"),Args{}))).parent_path()/"campaign_records_v78.json";
        if(file==path)return;
        J next=J::object();
        if(std::filesystem::exists(file)){
            std::ifstream input(file,std::ios::binary);next=J::parse(input);
            if(!next.is_object())throw std::runtime_error("闯关战绩存档格式错误");
        }
        data=std::move(next);path=file;
    }
};
RecordBook records;
}
void observe_result(const V& app,const V& view){
    const auto result=get(view,"result"),receipt=get(result,"campaign78");
    if(!receipt.is_dict())return;
    const auto member=get(receipt,"members");
    if(!get(member,py_str(getattr(app,SY("peer_id"))).c_str()).truthy())return;
    const std::string mode=py_str(get(receipt,"mode")),run=py_str(get(receipt,"run")),match=py_str(get(receipt,"match"));
    const bool zombie=mode.ends_with("izombie");
    const int day=int(get(result,"pve_day",V(0)).num()),last=zombie?19:24;
    if(run.empty()||match.empty()||day<1||day>last)return;
    records.load(app);
    const auto key=mode+"/"+run;
    if(records.data.contains("runs")&&records.data["runs"].contains(key)&&
       records.data["runs"][key]["matches"].contains(match))return;
    auto next=records.data;
    auto& progress=next["runs"][key];
    const double seconds=std::max(0.,get(receipt,"seconds",V(0)).num());
    progress["matches"][match]=true;
    progress["seconds"]=progress.value("seconds",0.)+seconds;
    if(get(result,"winner")==V(zombie?"zombie":"plant")){
        const int factor=int(get(receipt,"factor",V(1)).num());
        auto& cleared=progress["cleared"][std::to_string(day)];
        cleared=cleared.is_number_integer()?std::min(cleared.get<int>(),factor):factor;
        if(day==last&&progress["cleared"].size()==size_t(last)&&!progress.value("complete",false)){
            int grade=4;for(const auto& level:progress["cleared"])grade=std::min(grade,level.get<int>());
            auto& award=next["awards"][mode][std::to_string(grade)];
            if(award.is_null())award=J::object();
            award["count"]=award.value("count",0)+1;
            award["seconds"]=award.value("seconds",0.)+progress["seconds"].get<double>();
            progress["complete"]=true;
        }
    }
    write_save(records.path,next);records.data=std::move(next);
}
void profile_button(const V& app){
    const auto r=getattr(app,SY("renderer")),sz=callm(getattr(r,SY("screen")),SY("get_size"),Args{});
    button(r,"闯关奖杯与用时",260,int(sz.idx(1).num())-90,190,42,act("records"));
}
void draw_records(const SoloPage& p){
    static constexpr std::array ids{"coop_adventure","coop_lottery","coop_izombie","solo_adventure","solo_lottery","solo_izombie"};
    static constexpr std::array names{"常规合作","合作抽奖","合作我是僵尸","单人闯关","抽奖模式","我是僵尸"};
    const auto awards=records.data.value("awards",J::object());
    for(size_t i=0;i<ids.size();++i){
        const double y=2.+i*1.12;
        p.label(names[i],.8,y);
        const auto mode=awards.value(ids[i],J::object());
        for(int k=0;k<3;++k){
            const int factor=1<<k;const auto data=mode.value(std::to_string(factor),J::object());
            const int count=data.value("count",0),seconds=int(data.value("seconds",0.));
            const double x=4.2+k*5.15;
            const char* level=k==2?"末日":k==1?"极难":"一般";
            auto color=k==2?pm_menu_view::GOLD:k==1?V::tuple({V(255),V(96),V(96)}):p.white;
            if(count)p.image(k==2?"金杯":"银杯",p.rect(x,y-.1,.62,.62));
            const auto caption=std::string(level)+" "+std::to_string(count)+"次  "+std::to_string(seconds/3600)+"时"+std::to_string(seconds/60%60)+"分"+std::to_string(seconds%60)+"秒";
            pm_pve_ui::f_label(Args{p.r,V(caption),p.pos(x+.66,y),color,V(std::max(11,int(p.fs.num()*.83))),p.black,V(int(getattr(p.stage,SY("u")).num()*4.45))});
        }
    }
    p.plaque("返回菜单","返回玩家存档",.5,9.7,act("profile"));
}
bool result(const V& app,const V& r){
    auto room=getattr(app,SY("room"));if(!room.truthy())return false;
    if(special_coop(getattr(room,SY("pve"))))return true;
    auto mode=get(getattr(room,SY("pve")),"pvp77_mode");if(!mode.truthy())return false;
    observe_result(app,py_dict({{V("result"),r}}));
    open(app,py_str(mode));const bool win=get(r,"winner")==V(current.c.zombie()?"zombie":"plant");
    current.c.finish(campaign_pools(),py_str(getattr(room,SY("match_id"))),win,int(get(r,"coins",V(0)).num()),int(get(r,"diamond_coins",V(0)).num()));
    save();const auto state=getattr(app,SY("state"));
    if(win){setitem(state,V("solo78_after_curtain"),getattr(room,SY("match_id")));screen(state,"room");}
    else screen(state,"solo_run");
    return true;
}
bool action(const V& app,const V& input){
    if(!input.len())return false;
    const auto kind=input.idx(0);
    if(kind==V("pve_back")&&get(getattr(app,SY("state")),"pvp78_adventure").truthy()&&get(getattr(app,SY("state")),"pve_return")==V("solo_modes"))return action(app,act("modes"));
    if(kind!=V("solo77")&&kind!=V("pve_open")&&kind!=V("pve_start")&&kind!=V("confirm_map")&&kind!=V("fill_ai")&&kind!=V("coop_lobby"))return false;
    const auto state=getattr(app,SY("state"));
    if(get(state,"pvp78_adventure").truthy()&&(kind==V("coop_lobby")||(kind==V("solo77")&&input.len()>1&&(input.idx(1)==V("open")||input.idx(1)==V("home"))))){
        setitem(state,V("pvp78_adventure"),V(false));setattr(app,SY("_campaign"),V::none());
    }
    if(kind==V("coop_lobby")){
        const auto key="coop78_level_"+py_str(get(state,"coop78_variant",V("adventure")));
        setitem(state,V("pvp78_health"),get(state,key.c_str(),V(1)));
    }
    const auto pve=local_room_view(app);
    const bool coop=special_coop(pve);
    if(kind!=V("solo77")&&!coop)return false;
    if(kind==V("fill_ai")&&coop)return true;
    V s=getattr(app,SY("state"));auto op=kind==V("solo77")?py_str(input.idx(1)):py_str(kind),arg=input.len()>2?py_str(input.idx(2)):"";
    try{
        if(op=="variant"){
            auto mode=get(s,"coop78_variant");
            const auto next=mode==V("lottery")?V("izombie"):mode==V("izombie")?V("adventure"):V("lottery");
            setitem(s,V("coop78_variant"),next);
            setitem(s,V("pvp78_health"),get(s,("coop78_level_"+py_str(next)).c_str(),V(1)));return true;
        }
        if(coop){
            const auto seat=own_seat(app);
            if(op=="modes"||op=="home"){screen(s,"room");return true;}
            if(op=="confirm_reset"){if(getattr(app,SY("peer_id"))==V("host"))screen(s,"solo_reset");return true;}
            if(!seat.truthy())return true;
            const auto c=seat_campaign(pve,seat);
            const auto send=[&](const std::string& action){
                const auto error=callm(app,SY("command"),Args{py_dict({{V("type"),V("campaign78")},{V("operation"),V(action)},{V("key"),V(arg)},{V("stage"),V(c.stage)},{V("match"),V(c.last_result)}}),seat});
                if(error.truthy())callm(app,SY("message"),Args{error});return !error.truthy();
            };
            if(op=="pve_open"||op=="run"){screen(s,"solo_run");return true;}
            if(op=="reset"){if(send("restart"))screen(s,"room");return true;}
            if(op=="solo_difficulty"){
                if(getattr(app,SY("mode"))==V("guest"))return true;
                const auto room=getattr(app,SY("room"));const auto f=get(getattr(room,SY("rules")),"pvp78_health",V(1));
                return action(app,act("difficulty",f==V(4)?"1":f==V(2)?"4":"2"));
            }
            if(op=="start"||op=="pve_start"||op=="confirm_map"){
                if(!send("prepare"))return true;
                screen(s,"room");return true;
            }
            if(op=="inspect_buy"||op=="inspect_reward"){
                if(get(s,"solo_detail")!=V(arg)){setitem(s,V("solo_detail"),V(arg));setitem(s,V("pve_detail_scroll"),V(0));return true;}
                if(get(s,"solo78_claim").truthy())return true;
                if(send(op=="inspect_buy"?"buy":"reward")&&op=="inspect_reward"){screen(s,"solo_run");claim_animation(s,c,arg);}return true;
            }
            if(op=="gift"){send("gift");return true;}
            if(op=="deck"||op=="reward"||op=="buy"){setitem(s,V("solo_detail"),V(arg));send(op);return true;}
        }
        if(op=="records"){records.load(app);screen(s,"solo_records");}
        else if(op=="profile")screen(s,"profile");
        else if(op=="solo_difficulty"){
            if(current.c.complete)return true;
            current.c.difficulty=current.c.difficulty==1?2:current.c.difficulty==2?4:1;save();
        }else if(op=="difficulty"){
            if(getattr(app,SY("mode"))==V("guest"))return true;
            const int factor=std::stoi(arg);
            if(factor!=1&&factor!=2&&factor!=4)return true;
            const auto key=get(s,"pvp78_adventure").truthy()?std::string("adventure78_level"):
                "coop78_level_"+py_str(get(s,"coop78_variant",V("adventure")));
            setitem(s,V(key),V(factor));setitem(s,V("pvp78_health"),V(factor));
            auto room=getattr(app,SY("room"));
            if(room.truthy()&&getattr(room,SY("phase"))==V("config")){
                setitem(getattr(room,SY("rules")),V("pvp78_health"),V(factor));
                setattr(room,SY("_pve_setup"),V::none());
                setattr(room,SY("revision"),getattr(room,SY("revision"))+V(1));
                auto confirmed=getattr(room,SY("confirmed"));
                for(const auto& [seat,_]:py::items_vec(confirmed))setitem(confirmed,seat,V(false));
                callm(app,SY("refresh"),Args{});
            }
        }
        else if(op=="modes"){
            if(get(s,"pvp78_adventure").truthy()){
                callm(app,SY("close_room"),Args{});setattr(app,SY("_campaign"),V::none());
                setitem(s,V("pvp78_adventure"),V(false));
            }
            screen(s,"solo_modes");
        }
        else if(op=="home")screen(s,"home");
        else if(op=="adventure"){
            callm(app,SY("close_room"),Args{});
            setattr(app,SY("_campaign"),V::none());
            setitem(s,V("pvp78_adventure"),V(true));
            setitem(s,V("pvp78_health"),get(s,"adventure78_level",V(1)));
            const auto path=callm(app,SY("campaign_path"),Args{});
            if(!callm(path,SY("exists"),Args{}).truthy()){
                const auto c=pm_pve::new_Campaign(Args{V(fresh_seed()),V(true)});
                callm(c,SY("save"),Args{path});setattr(app,SY("_campaign"),c);
            }
            callm(app,SY("pve_action"),Args{V::tuple({V("pve_open")})});
            callm(getattr(app,SY("personal_campaign")),SY("restrict_coop"),Args{});
            setitem(s,V("pve_return"),V("solo_modes"));
        }
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
            else if(has(current.c.rewards,arg)&&!get(s,"solo78_claim").truthy()){
                claim_animation(s,current.c,arg);current.c.reward(campaign_pools(),arg);save();screen(s,"solo_run");
            }
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
    if(tab=="room"&&get(s,"solo78_after_curtain").truthy()){
        const auto room=getattr(app,SY("room"));
        if(room.truthy()&&getattr(room,SY("phase"))==V("result")&&get(s,"solo78_after_curtain")==getattr(room,SY("match_id"))){
            callm(s,SY("pop"),Args{V("solo78_after_curtain")});screen(s,"solo_run");tab="solo_run";
        }
    }
    if(!tab.starts_with("solo_"))return false;
    auto r=getattr(app,SY("renderer"));auto sz=callm(getattr(r,SY("screen")),SY("get_size"),Args{});
    int w=int(sz.idx(0).num()),h=int(sz.idx(1).num());
    const auto pve=local_room_view(app);
    const bool coop=special_coop(pve)&&own_seat(app).truthy();
    Campaign remote;if(coop){remote=seat_campaign(pve,own_seat(app));remote.difficulty=int(get(get(getattr(app,SY("view")),"rules"),"pvp78_health",V(1)).num());}
    const auto& c=coop?remote:current.c;
    if(tab=="solo_records"){callm(r,SY("start"),Args{V("闯关奖杯与通关总时长"),V("")});draw_records(SoloPage(app,r,false));return true;}
    if(tab=="solo_modes"||tab=="solo_run"||tab=="solo_shop"||tab=="solo_reset"){
        const SoloPage page(app,r,tab=="solo_shop");
        callm(r,SY("start"),Args{V(""),V("")});
        if(tab=="solo_modes"){draw_modes(page);return true;}
        if(tab=="solo_shop"){
            draw_shop(page,s,c);
            if(coop&&c.coins>0){
                const int amount=std::min(100,c.coins);
                callm(r,SY("button"),Args{V("赠给队友 $"+std::to_string(amount)),page.rect(3.4,.52,3.5,.7),act("gift",std::to_string(amount))});
            }
            return true;
        }
        backdrop(r,c);
        if(tab=="solo_reset"){
            page.label("重新开始将替换这个模式的进度",6.7,3.5,1.35);
            page.plaque("返回菜单","继续原进度",5.5,6.6,act("run"));
            page.plaque("开始干","确认重新开始",11.5,6.6,act("reset",c.mode));
        }else if(!draw_claim(page,s,c))draw_run(page,s,c,coop,getattr(app,SY("mode"))!=V("guest"));
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
