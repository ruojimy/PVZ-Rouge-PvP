// User-rule expectations and real-engine integration for the 72 change set.
// Rendering additionally compares the retained 71 scalar paths byte for byte.
#include "pg/pg.h"
#include "pg/render_stats.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "core/save_upgrade72.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_native_content.h"
#include "sim/pvp/gen/pm_native_targets.h"
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_zombie_secrets.h"
#include "ui/gen/pm_ui_data.h"
#include "ui/gen/pm_hud.h"
#include "ui/gen/pm_draft_advisor.h"
#include "ui/gen/pm_room.h"
#include "ui/gen/pm_replay.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <stdexcept>
#include <cmath>
#include <cstdlib>

using namespace pvz;
namespace {
using json=nlohmann::json;
void require(bool yes,const std::string& text){if(!yes)throw std::runtime_error(text);}
void number(double actual,double expected,const std::string& text){require(std::abs(actual-expected)<1e-8,text+": "+std::to_string(actual)+" != "+std::to_string(expected));}
V dict(std::initializer_list<std::pair<V,V>> data){return py_dict(data);}
V pos(double x,double y){return V::nums({x,y,0,0});}
V card(const char* key,V secrets=V::list()){return pm_catalog::f_actual_card(Args{V(key),secrets});}
std::string bytes(const std::filesystem::path& p){std::ifstream f(p,std::ios::binary);return std::string(std::istreambuf_iterator<char>(f),{});}
void write(const std::filesystem::path& p,const std::string& text){std::filesystem::create_directories(p.parent_path());std::ofstream f(p,std::ios::binary);f<<text;}
struct MatchCase {
    BattleHandle h;
    pm_native_battle::C_NativeBattle* b;
    MatchCase(bool duo=false) {
        json decks={{"plant",{"plant:向日葵","plant:豌豆射手","plant:模仿者","secret:肆意模仿","plant:大喷菇","secret:雷霆"}},
                    {"zombie",{"zombie:脑光墓碑","zombie:普通僵尸","zombie:墓碑吞噬者僵尸","zsecret:玉米卷","zsecret:石更！","zsecret:狂暴","zsecret:最后攻势"}}};
        if(duo){decks["plant2"]={"plant:双子向日葵","plant:豌豆射手"};decks["zombie2"]={"zombie:脑光墓碑","zombie:普通僵尸"};}
        h=battle_from_scenario({{"seed",301},{"mode",duo?"duo":"duel"},{"decks",decks},{"clear_cooldowns",true}});
        b=as<pm_native_battle::C_NativeBattle>(h.battle);require(b,"NativeBattle type");
        for(auto& item:py::items_vec(b->a_players))setitem(item.second,SV("resource"),V(10000));
    }
    ~MatchCase(){try{callm(h.battle,SY("close"),Args{});}catch(...) {}}
    V spawn(const char* key,const char* side,double x,double y){return b->m_spawn(Args{V(key),V(side),V(x),V(y),V(1)});}
    V native(const V& unit){return rd(b->a__native_objects,rd(unit,SV("id")));}
    pm_native_content::C_NativeContent* content(){return as<pm_native_content::C_NativeContent>(b->a_content);}
    pm_zombie_secrets::C_ZombieSecrets* secrets(){return as<pm_zombie_secrets::C_ZombieSecrets>(b->a_zsecrets);}
};
std::pair<int,int> ground_cell(MatchCase& match) {
    V rows=rd(match.b->a_g,SV("ditu")),empty=rd(match.b->a_g,SV("kong"));
    for(int y=2;y<int(rows.len())-1;++y)for(int x=8;x<int(rows.idx(y).len())-8;++x)
        if(rd(rows.idx(y).idx(x),SV("方块"))==SV("空") && !empty.contains(rd(rows.idx(y+1).idx(x),SV("方块"))))return {y,x};
    throw std::runtime_error("No ground fixture cell");
}
void pixels_equal(const V& a,const V& b,const std::string& label) {
    auto x=pg::surf(a),y=pg::surf(b);require(x->w()==y->w() && x->h()==y->h(),label+" dimensions");
    for(int row=0;row<x->h();++row)require(std::memcmp(static_cast<char*>(x->s->pixels)+row*x->s->pitch,static_cast<char*>(y->s->pixels)+row*y->s->pitch,size_t(x->w())*4)==0,label+" row "+std::to_string(row));
}
void seed_pixels(V v,int salt) {
    auto s=pg::surf(v);
    for(int y=0;y<s->h();++y){auto row=reinterpret_cast<uint32_t*>(static_cast<char*>(s->s->pixels)+y*s->s->pitch);
        for(int x=0;x<s->w();++x)row[x]=uint32_t((x*67+y*19+salt)%256)<<24|uint32_t((x*11+salt)%256)<<16|uint32_t((y*31+salt)%256)<<8|uint32_t((x+y*7+salt)%256);}
}
}

int main(int argc,char** argv) {
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");py::g_real_clock=true;
    std::filesystem::path output=argc>1?u8p(argv[1]):std::filesystem::path("test_results/pvp72-conformance.json");
    auto scratch=std::filesystem::absolute(output).parent_path()/"conformance-userdata";
#ifdef _WIN32
    _putenv_s("PVP_USERDATA",p8(scratch).c_str());_putenv_s("SDL_VIDEODRIVER","dummy");_putenv_s("SDL_AUDIODRIVER","dummy");
#endif
    json results=json::array();int failures=0;
    auto run=[&](const char* name,const std::function<void()>& test){
        auto begin=std::chrono::steady_clock::now();std::string error;
        try{test();}catch(const std::exception& e){error=e.what();}catch(...){error="Unknown exception";}
        if(!error.empty())++failures;
        results.push_back({{"name",name},{"outcome",error.empty()?"PASS":"FAIL"},{"detail",error},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()}});
        printf("%s %s %s\n",error.empty()?"PASS":"FAIL",name,error.c_str());fflush(stdout);
    };
    try{pg::install_pygame();init_pvp_modules();}catch(const std::exception& e){printf("INIT FAIL %s\n",e.what());return 2;}
    run("catalog_user_values",[]{
        struct Expected{const char* id;double cost,hp,cd;};
        for(auto row:std::initializer_list<Expected>{{"plant:原始土豆地雷",-1,18,-1},{"plant:萝卜伞",100,36,-1},{"plant:寒冰辣椒",150,-1,-1},{"plant:双子向日葵",90,-1,-1},{"zombie:橄榄球僵尸",175,-1,-1},{"zombie:毁灭菇僵尸",250,-1,60},{"zombie:辣椒僵尸",175,-1,48},{"zombie:墓碑吞噬者僵尸",225,300,-1}}){
            V c=card(row.id);if(row.cost>=0)number(rd(c,SV("cost")).num(),row.cost,row.id);if(row.hp>=0)number(rd(c,SV("hp")).num(),row.hp,row.id);if(row.cd>=0)number(rd(c,SV("cooldown")).num(),row.cd,row.id);
        }
        number(rd(card("zombie:飞贼僵尸",V::list({SV("zsecret:空输")})),SV("cost")).num(),100,"airdrop cost");
        require(rd(pm_catalog::RULES,SV("ruleset"))==SV("pvp72"),"ruleset fingerprint");
    });
    run("spawn_hp_and_half_health_bites",[]{
        MatchCase m;auto c=m.content();V unit=m.spawn("zombie:墓碑吞噬者僵尸","zombie",500,960),z=m.native(unit);
        number(rd(z,SV("血量")).num(),300,"gravebuster spawn HP");number(c->m_plant_bite(Args{z}).num(),3,"full-health bite");
        setitem(z,SV("血量"),V(150));number(c->m_plant_bite(Args{z}).num(),6,"half-health bite");
        setitem(z,SV("血量"),V(150.001));number(c->m_plant_bite(Args{z}).num(),3,"above-half bite");
        V mine=m.spawn("plant:原始土豆地雷","plant",800,960);number(rd(m.native(mine),SV("植物血")).num(),18,"primal mine deployed HP");
    });
    run("additive_movement_and_fixed_motion",[]{
        V z=dict({{SV("移速"),V(40)},{SV("_pvp_base_speed"),V(40)}});
        pm_zombie_secrets::f_scale_speed(Args{z,SV("大运"),V(1.)});pm_zombie_secrets::f_scale_speed(Args{z,SV("海陆空"),V(.25)});pm_zombie_secrets::f_scale_speed(Args{z,SV("玉米卷"),V(.75)});
        number(rd(z,SV("移速")).num(),120,"bonuses sum to +200%");
        require(!pm_zombie_secrets::f_scale_speed(Args{z,SV("玉米卷"),V(.75)}).truthy(),"repeat taco rejected");
        MatchCase m;V live=m.native(m.spawn("zombie:墓碑吞噬者僵尸","zombie",600,960));
        pm_zombie_secrets::f_scale_speed(Args{live,SV("玉米卷"),V(.75)});
        V ns=pvz::getattr(m.b->a_patch,SY("ns"));
        call(rd(ns,SV("__pvz_sb_enforce_plant_zombie_motion")),Args{m.b->a_g,live,dict({{SV("move_speed"),V(40)}})});
        number(rd(live,SV("移速")).num(),std::max(1.,40*rd(m.b->a_g,SV("plk")).num())*1.75,"fixed-speed plant zombie retains taco");
    });
    run("thunder_and_garlic_contact_stun",[]{
        MatchCase m;V biter=dict({{SV("僵尸"),SV("普通僵尸")},{SV("眩晕"),V(0)}});
        m.content()->m_flyer_bite_effect(Args{biter,dict({{SV("植物"),SV("雷蘑菇")}})});number(rd(biter,SV("眩晕")).num(),250,"one second thunder stun");
        V parrot=dict({{SV("_pvp_content"),SV("海盗鹦鹉")},{SV("眩晕"),V(0)}});
        m.content()->m_flyer_bite_effect(Args{parrot,dict({{SV("植物"),SV("大蒜")}})});number(rd(parrot,SV("眩晕")).num(),125,"existing garlic stun");
    });
    run("imitater_negative_price_hud_and_deploy",[]{
        MatchCase m;V player=rd(m.b->a_players,SV("plant"));setitem(player,SV("last_copy_card"),SV("plant:向日葵"));
        V shown=pm_hud::f_battle_card(Args{SV("plant:模仿者"),player,V::dict()});number(rd(shown,SV("cost")).num(),-50,"HUD negative sun price");
        V changed=pm_hud::f_battle_card(Args{SV("plant:模仿者"),player,V::dict(),V(false),SV("plant:豌豆射手")});number(rd(changed,SV("cost")).num(),-40,"explicit copy target price");
        bool deployed=false;double before=rd(player,SV("resource")).num();
        for(int row=1;row<23 && !deployed;++row)for(int col=8;col<60 && !deployed;++col){
            V plan=m.b->m_placement(Args{SV("plant"),SV("plant:模仿者"),V((col+.5)*48),V((row+.5)*48),V::none(),SV("plant:向日葵")});
            if(plan.idx(0).truthy())continue;
            number(rd(plan.idx(1),SV("charge")).num(),-50,"authoritative negative charge");
            V error=m.b->m_deploy(Args{SV("plant"),SV("plant:模仿者"),V((col+.5)*48),V((row+.5)*48),V::none(),SV("plant:向日葵")});
            require(!error.truthy(),"negative-price deploy: "+py_str(error));deployed=true;
        }
        require(deployed,"legal copy placement exists");number(rd(player,SV("resource")).num(),before+50,"negative price credits sun once");
    });
    run("chili_750_finite_packet_and_no_repeat",[]{
        MatchCase m;V native=m.native(m.spawn("zombie:普通僵尸","zombie",600,960));setitem(native,SV("血量"),V(1000));setitem(native,SV("防具血量"),V(0));
        auto targets=as<pm_native_targets::C_NativeTargets>(m.b->a_targets);
        V source=dict({{SV("植物"),SV("火爆辣椒")},{SV("_pvp_owner"),SV("plant")},{SV("_pvp_id"),SV("test:chili")}});
        V roster=rd(m.b->a_g,SV("僵尸"));int index=-1;for(int i=0;i<int(roster.len());++i)if(py_is(roster.idx(i),native))index=i;
        require(index>=0,"chili victim registered");
        py::WithGuard context(targets->m_context(Args{SV("zombie"),SV("plant"),SV("plants"),source}));
        targets->m__ash_damage(Args{V(index)});number(rd(native,SV("血量")).num(),250,"750-point packet");
        targets->m__ash_damage(Args{V(index)});number(rd(native,SV("血量")).num(),250,"same explosion not repeated");
        V hero=targets->m_hero_proxy(Args{SV("zombie")});roster.append(hero);int hi=int(roster.len())-1;
        double before=rd(rd(m.b->a_hero_states,SV("zombie")),SV("玩家血量")).num();
        targets->m__ash_damage(Args{V(hi)});number(rd(rd(m.b->a_hero_states,SV("zombie")),SV("玩家血量")).num(),before-16,"chili hero packet 16");
        targets->m__ash_damage(Args{V(hi)});number(rd(rd(m.b->a_hero_states,SV("zombie")),SV("玩家血量")).num(),before-16,"same hero explosion capped once");
    });
    run("charmed_dave_priority_and_path_blocker",[]{
        MatchCase m;V source=m.native(m.spawn("zombie:普通僵尸","zombie",300,960));setitem(source,SV("魅惑"),V(250));
        setitem(rd(m.b->a_hero_states,SV("zombie")),SV("玩家位置"),pos(900,960));
        V blocker=m.native(m.spawn("zombie:普通僵尸","zombie",550,960));
        V offpath=m.native(m.spawn("zombie:普通僵尸","zombie",320,700));
        V chosen=m.content()->m_nearest(Args{source});require(py_is(chosen,blocker),"passing zombie blocks Dave pursuit");
        setitem(blocker,SV("血量"),V(0));chosen=m.content()->m_nearest(Args{source});require(chosen.get(SV("_pvp_hero"))==SV("zombie"),"Dave chosen over closer off-path zombie");
        for(int i=0;i<40;++i){setitem(offpath,SV("位置"),pos(320+(i*79)%900,700+(i*47)%350));
            V native=m.content()->m_nearest(Args{source}),dynamic=m.content()->m_nearest_dynamic(Args{source});require(py_is(native,dynamic),"typed and dynamic target identity "+std::to_string(i));}
    });
    run("stone_knockdown_guard_and_team_last_stand",[]{
        MatchCase m(true);V avatar=rd(m.b->a_hero_states,SV("zombie"));setitem(avatar,SV("玩家倒地"),V(1));number(m.b->m__hero_damage_factor(Args{SV("zombie")}).num(),.75,"stone down protection");
        setitem(avatar,SV("玩家倒地"),V(0));number(m.b->m__hero_damage_factor(Args{SV("zombie")}).num(),1,"stone standing factor");
        m.secrets()->m_hero_amount(Args{SV("zombie"),avatar,V(1000)});require(m.secrets()->m_team_last_stand(Args{}).truthy(),"team last stand active");
        require(m.secrets()->m_berserk(Args{}).truthy(),"last stand enables rage");
        V player=rd(m.b->a_players,SV("zombie2"));setitem(player,SV("resource"),V(10000));
        auto error=m.b->m_placement(Args{SV("zombie2"),SV("zombie:脑光墓碑"),V(1000),V(900)}).idx(0);
        require(error.truthy(),"team last stand applies producer restriction to teammate");
    });
    run("duo_ai_subsidy_clock",[]{
        MatchCase m(true);m.b->a_ai_subsidy_seats=V::tuple({SV("plant2")});V player=rd(m.b->a_players,SV("plant2"));double before=rd(player,SV("resource")).num();
        m.b->a_time=V(7.999);m.b->m__ai_subsidy(Args{});number(rd(player,SV("resource")).num(),before,"no early subsidy");
        m.b->a_time=V(8);m.b->m__ai_subsidy(Args{});number(rd(player,SV("resource")).num(),before+25,"8-second subsidy");
        m.b->a_time=V(48);m.b->m__ai_subsidy(Args{});number(rd(player,SV("resource")).num(),before+150,"2v2 subsidy remains 25 at 48 seconds");
        m.b->m__ai_subsidy(Args{});number(rd(player,SV("resource")).num(),before+150,"subsidy not double-paid");
    });
    run("taco_feeds_each_live_friendly_unit_once",[]{
        MatchCase m;setitem(rd(m.b->a_hero_states,SV("zombie")),SV("玩家位置"),pos(500,960));
        V one=m.native(m.spawn("zombie:普通僵尸","zombie",510,960)),two=m.native(m.spawn("zombie:普通僵尸","zombie",600,960));
        m.secrets()->m__taco(Args{SV("zombie")});m.secrets()->m__taco(Args{SV("zombie")});
        number(rd(rd(one,SV("_pvp_zs_speed")),SV("玉米卷")).num(),.75,"first taco");number(rd(rd(two,SV("_pvp_zs_speed")),SV("玉米卷")).num(),.75,"second taco skips fed unit");
        auto speed=rd(one,SV("移速")).num();m.secrets()->m__taco(Args{SV("zombie")});number(rd(one,SV("移速")).num(),speed,"all-fed roster receives no repeat buff");
    });
    run("duo_repeatable_ban_protection_and_shared_grave",[]{
        MatchCase m(true);V room=pm_room::new_Room(Args{m.h.bridge});auto r=as<pm_room::C_Room>(room);r->a_mode=SV("duo");
        r->a_decks=dict({{SV("plant"),V::list({SV("plant:向日葵")})},{SV("plant2"),V::list({SV("plant:向日葵")})},{SV("zombie"),V::list({SV("zombie:脑光墓碑")})},{SV("zombie2"),V::list({SV("zombie:脑光墓碑")})}});
        require(!r->m__team_feasible(Args{SV("plant"),r->a_decks,V::list()}).truthy(),"repeatable economy card is legal for both teammates");
        V action=dict({{SV("side"),SV("zombie")},{SV("category"),SV("plant")}});
        require(r->m__ban_problem(Args{action,SV("plant:向日葵")}).truthy(),"second-round ban cannot invalidate locked teammate card");
        auto cell=ground_cell(m);double x=(cell.second+.5)*48,y=(cell.first+1)*48;
        V grave=m.spawn("zombie:脑光墓碑","zombie",x,y);
        V plan=m.b->m_placement(Args{SV("zombie2"),SV("zombie:普通僵尸"),V(x),V(y),rd(grave,SV("id"))});
        require(!plan.idx(0).truthy(),"teammate can deploy from shared grave: "+py_str(plan.idx(0)));
    });
    run("shell_root_death_preserves_land_and_air_plants",[]{
        MatchCase m;auto cell=ground_cell(m);double x=(cell.second+.5)*48,y=(cell.first+1)*48;
        V body=m.native(m.spawn("plant:豌豆射手","plant",x,y)),root=m.native(m.spawn("plant:抓人草","plant",x,y));
        V attacker=dict({{SV("僵尸"),SV("巨人僵尸")},{SV("_pvp_owner"),SV("zombie")}});
        auto targets=as<pm_native_targets::C_NativeTargets>(m.b->a_targets);
        {py::WithGuard context(targets->m_context(Args{SV("plant"),SV("zombie"),SV("zombies"),attacker}));
            call(rd(m.b->a_g,SV("扁死")),Args{V(cell.first),V(cell.second)});call(rd(m.b->a_g,SV("扁死")),Args{V(cell.first),V(cell.second)});}
        require(!body.contains(SV("死")),"crushing root does not kill inner body");
        m.b->m_step(Args{V(1)});require(rd(body,SV("植物血")).num()>0 && !body.contains(SV("死")),"land body survives root maintenance");
        V air=m.native(m.spawn("plant:芦笋战机","plant",x+144,y-240));
        V shell=m.native(m.spawn("plant:抓人草","plant",x+144,y-240));setitem(shell,SV("植物血"),V(0));setitem(shell,SV("死"),V(0));
        m.b->m_step(Args{V(1)});require(rd(air,SV("植物血")).num()>0 && !air.contains(SV("死")),"air plant survives root death without ground support");
    });
    run("flyer_visual_center_and_route_interception",[]{
        MatchCase m;m.b->a_command=SV("attack");auto cell=ground_cell(m);double x=(cell.second+.5)*48,y=(cell.first+1)*48;
        V target=m.native(m.spawn("plant:豌豆射手","plant",x,y));V parrot=m.native(m.spawn("zombie:海盗鹦鹉","zombie",x,y));
        V point=m.content()->m_point(Args{target});V center=m.content()->m_point(Args{parrot});double half=rd(parrot,SV("位置")).idx(1).num()-center.idx(1).num();
        V position=pos(point.idx(0).num(),point.idx(1).num()+half);setitem(parrot,SV("位置"),position);setitem(parrot,SV("_pvp_content_position_before"),py::copy(position));
        m.content()->a_last_zombie=parrot;m.content()->m_finish_zombie(Args{});
        V after=m.content()->m_point(Args{parrot});number(after.idx(0).num(),point.idx(0).num(),"parrot visual center X");number(after.idx(1).num(),point.idx(1).num(),"parrot visual center Y");
        V goal=dict({{SV("位置"),pos(x+600,y)}});V blocked=m.content()->m_route_target(Args{parrot,goal,V::list({target})});require(py_is(blocked,target),"plant intercepts flight route");
    });
    run("deck_roundtrip_second_seat_and_old_version",[&]{
        auto file=scratch/"decks.json";V decks=dict({{SV("plant2"),V::list({SV("plant:向日葵"),SV("plant:豌豆射手")})},{SV("zombie2"),V::list({SV("zombie:脑光墓碑"),SV("zombie:普通僵尸")})}});
        pm_ui_data::f_save_decks(Args{V(p8(file)),decks});V read=pm_ui_data::f_load_decks(Args{V(p8(file)),V::list({SV("plant:豌豆射手")})});
        require(rd(read,SV("plant2")).len()==1 && read.contains(SV("zombie2")),"seat2 save and banned-card filtering");
        pm_ui_data::f_save_decks(Args{V(p8(file)),decks});require(std::filesystem::exists(file.parent_path()/"decks.json.previous"),"previous deck backed up");
        json old={{"format","pvp-decks-1"},{"rules_hash","71"},{"catalog_hash","71"},{"decks",{{"plant",{"plant:向日葵"}}}}};write(file,old.dump());
        require(pm_ui_data::f_load_decks(Args{V(p8(file))}).contains(SV("plant")),"old schema migrates by stable card ID");
        V eight=V::list({SV("plant:向日葵"),SV("plant:豌豆射手"),SV("plant:坚果"),SV("plant:土豆地雷"),SV("plant:大蒜"),SV("plant:萝卜伞"),SV("plant:寒冰射手"),SV("plant:双发射手")});
        pm_ui_data::f_save_decks(Args{V(p8(file)),dict({{SV("plant2"),eight}}),dict({{SV("plant_slots"),V(8)}})});
        require(rd(pm_ui_data::f_load_decks(Args{V(p8(file))}),SV("plant2")).len()==8,"extra-slot room saves all eight cards");
    });
    run("save_upgrade_preserves_files_and_is_idempotent",[&]{
        auto root=scratch/"upgrade-fixture";write(root/"settings.json","{\"volume\":0.37}");write(root/u8p("maps/自定义.json"),"{\"map\":71}");
        auto before=bytes(root/"settings.json");backup_native_save72(root);
        json marker=json::parse(bytes(root/"native-save-version.json"));auto backup=u8p(marker.at("backup").get<std::string>());
        require(bytes(root/"settings.json")==before && bytes(backup/"settings.json")==before,"settings preserved and backed up");
        require(bytes(root/u8p("maps/自定义.json"))==bytes(backup/u8p("maps/自定义.json")),"custom map bytes inherited");
        auto stamp=bytes(root/"native-save-version.json");backup_native_save72(root);require(bytes(root/"native-save-version.json")==stamp,"upgrade idempotent");
    });
    run("r22_advisor_uses_current_evaluator",[]{
        MatchCase m;V map=pm_maps::f_build_snapshot(Args{m.h.bridge,SV("家院"),V(301)});
        V view=dict({{SV("map"),callm(map,SY("to_dict"),Args{})},{SV("rules"),pm_catalog::RULES},{SV("decks"),dict({{SV("plant"),V::list({SV("plant:向日葵"),SV("plant:豌豆射手"),SV("plant:坚果"),SV("plant:土豆地雷"),SV("plant:大蒜"),SV("plant:萝卜伞")})},{SV("zombie"),V::list({SV("zombie:脑光墓碑"),SV("zombie:普通僵尸")})}})}});
        V result=pm_draft_advisor::f_recommend_ai(Args{view,SV("plant")});require(result.get(SV("ai"),V(false)).truthy(),"r22 evaluator did not run: "+py_str(result.get(SV("summary"))));
        require(rd(result,SV("deck")).len()==7,"advisor legal completion size");
    });
    run("simd_blit_pixels_all_alpha_clipping_and_alias",[]{
        for(bool dstalpha:{false,true})for(bool srcalpha:{false,true})for(int alpha:{-2,-1,0,99,255})for(int key:{0,1}) {
            V source=pg::new_surface(31,17,srcalpha),a=pg::new_surface(35,23,dstalpha),b=pg::new_surface(35,23,dstalpha);
            seed_pixels(source,7);seed_pixels(a,19);seed_pixels(b,19);auto s=pg::surf(source);s->alpha=alpha;s->has_colorkey=key;s->colorkey=0x00074c07;
            SDL_Rect clip{2,1,28,19};SDL_SetClipRect(pg::surf(a)->s,&clip);SDL_SetClipRect(pg::surf(b)->s,&clip);
            pg::set_render_reference72(1);pg::blit(pg::surf(a),s,-1,3,nullptr,0);
            pg::set_render_reference72(0);pg::blit(pg::surf(b),s,-1,3,nullptr,0);pixels_equal(a,b,"alpha/clip blit");
        }
        V a=pg::new_surface(25,10,false),b=pg::new_surface(25,10,false);seed_pixels(a,19);seed_pixels(b,19);
        pg::set_render_reference72(1);pg::blit(pg::surf(a),pg::surf(a),2,1,nullptr,0);pg::set_render_reference72(0);pg::blit(pg::surf(b),pg::surf(b),2,1,nullptr,0);pixels_equal(a,b,"alias blit");
        pg::set_render_reference72(-1);
    });
    run("direct_scale_dest_identity_and_pixel_contract",[]{
        V transform=pg::transform_module();
        for(bool alpha:{false,true})for(bool clip:{false,true})for(int key:{0,1}) {
            V source=pg::new_surface(31,17,alpha),a=pg::new_surface(53,29,alpha),b=pg::new_surface(53,29,alpha);seed_pixels(source,7);seed_pixels(a,29);seed_pixels(b,29);
            if(key){pg::surf(source)->has_colorkey=true;pg::surf(source)->colorkey=0xff070707;SDL_SetColorKey(pg::surf(source)->s,SDL_TRUE,0xff070707);}
            if(clip){SDL_Rect rect{2,3,45,19};SDL_SetClipRect(pg::surf(a)->s,&rect);SDL_SetClipRect(pg::surf(b)->s,&rect);}
            pg::set_render_reference72(1);V ra=callm(transform,SY("scale"),Args{source,V::nums({53,29}),a});
            pg::set_render_reference72(0);V rb=callm(transform,SY("scale"),Args{source,V::nums({53,29}),b});require(py_is(ra,a) && py_is(rb,b),"destination object identity");pixels_equal(a,b,"scale");
        }
        V pa=pg::new_surface(80,40,true),pb=pg::new_surface(80,40,true);seed_pixels(pa,41);seed_pixels(pb,41);
        V sa=callm(pa,SY("subsurface"),Args{V::nums({0,0,31,17})}),sb=callm(pb,SY("subsurface"),Args{V::nums({0,0,31,17})});
        V da=callm(pa,SY("subsurface"),Args{V::nums({5,3,31,17})}),db=callm(pb,SY("subsurface"),Args{V::nums({5,3,31,17})});
        pg::set_render_reference72(1);callm(transform,SY("scale"),Args{sa,V::nums({31,17}),da});
        pg::set_render_reference72(0);callm(transform,SY("scale"),Args{sb,V::nums({31,17}),db});pixels_equal(pa,pb,"overlapping parent surfaces");
        pg::set_render_reference72(-1);
    });
    json report={{"build",data::get("__init__","BUILD")},{"rules_hash",pm_catalog::f_rules_hash(Args{}).str()},{"catalog_hash",pm_catalog::f_catalog_hash(Args{}).str()},
        {"passed",failures==0},{"counts",{{"PASS",results.size()-failures},{"FAIL",failures}}},{"results",results}};
    write(output,report.dump(2,' ',false,json::error_handler_t::replace));printf("REPORT %s\n",p8(output).c_str());fflush(nullptr);
    std::_Exit(failures?1:0);
}
