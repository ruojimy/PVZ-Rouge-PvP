#include "pvp742_guest_memory_fixture.h"
#include "sim/typed72_app/unit_projection.h"
#include "sim/typed/room_public_codec.h"
#include "ui/gen/pm_hud.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;
namespace {
V value(const J& j){return py::json_loads(V(j.dump()));}
V local_snapshot(const V& b){typed72app::LocalPresentationScope scope(b);return callm(b,SY("snapshot"),Args{V(false),V(false)});}
J counts(const V& s){
    J out={{"graves",0},{"damaged_graves",0},{"scarecrows",0}};
    for(const auto& u:json(rd(s,SV("units"))))if(u["side"]=="zombie"&&u["hp"].get<double>()>0.){
        if(u["card_id"]=="zombie:稻草人")out["scarecrows"]=out["scarecrows"].get<int>()+1;
        if(u["behavior"]=="grave"){
            out["graves"]=out["graves"].get<int>()+1;
            if(u["hp"].get<double>()<u["max_hp"].get<double>())out["damaged_graves"]=out["damaged_graves"].get<int>()+1;
        }
    }
    return out;
}
}
int main(int argc,char** argv){
    if(argc!=2||!std::getenv("PVP_USERDATA")||!std::getenv("PVP744_STATE_VIEW")||!std::getenv("PVP744_VERIFY_STATE"))return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J checks=J::array();int failed=0;
    auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
    test("unit_wire_parity_optional_fields_charm_seats_and_barrel",[&]{
        using namespace typed72;
        int cases=0;
        for(Seat side:{Seat::plant,Seat::zombie,Seat::plant2,Seat::zombie2})for(int mask=0;mask<8;++mask){
            auto card=std::make_shared<RoomPublicCard>();card->id="zombie:滚桶僵尸";card->behavior="grave";card->flying=true;
            RoomPublishedUnit u;u.card=card;u.id="audit:unit";u.side=side;u.original_owner=Seat::zombie;
            u.position={-1.25,864};u.velocity={2.5,-3.5};u.hp=12;u.max_hp=30;u.armor_hp=4;u.armor_max=9;u.w=30;u.h=50;
            u.mobile=true;u.burrowed=true;u.temporary=true;u.awake=false;u.floating=true;u.frozen=true;u.slowed=true;u.buttered=true;u.stunned=true;
            u.production_rate=.75;u.mature=true;u.torch_blue=true;u.drowsy=true;u.drowsy_level=2;u.poison_level=3;u.facing=-1;
            if(mask&1){u.copy_card="plant:抓人草";u.seat=Seat::zombie2;u.secret_speed={{"speed",.5},{"fire",1.25}};}
            if(mask&2)u.first_soldier_ready=bool(mask&1);
            u.orphan_barrel=mask&4;
            J c={{"id",card->id},{"name","滚桶僵尸"},{"asset","滚桶僵尸"},{"side","zombie"}};
            const J reference=encode_public_unit(u,typed72::WireObject(c));
            if(u.orphan_barrel){c["name"]="滚桶";c["asset"]="滚桶";}
            require(json(typed72app::project_public_unit(u,value(c)))==reference,"unit wire schema/value drift");++cases;
        }
        return J{{"cases",cases}};
    });
    for(const std::string mode:{"duel","duo","coop","pve"})test(("real_session_parity_"+mode).c_str(),[&]{
        J scenario={{"seed",744},{"mode",mode},{"night",true},{"durable_heroes",true}};
        if(mode=="coop"||mode=="pve"){scenario["campaign_deck"]=true;scenario["director"]={{"day",1},{"seed",301}};}
        auto h=battle_from_scenario(scenario);V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
        for(const auto& [key,x]:std::vector<std::pair<std::string,double>>{{"plant:向日葵",1896.},{"plant:向日葵",1944.},{"plant:抓人草",2136.}})
            require(!callm(b,SY("spawn"),Args{V(key),SV("plant"),V(x),V(864),V(1)}).is_none(),"spawn fixture failed");
        V s=local_snapshot(b);
        require(s.find(SV("_local_hud")),"missing local HUD summary");
        require(json(rd(s,SV("_local_hud")))==counts(s),"summary differs from old scan");
        const J held=json(rd(s,SV("units")));const J before=json(callm(b,SY("backend_audit"),Args{}))["state_view"];
        for(int i=0;i<6;++i)local_snapshot(b);
        require(json(callm(b,SY("backend_audit"),Args{}))["state_view"]==before,"idle rebuilt state");
        callm(b,SY("resource"),Args{SV("plant"),V(25),V(1900),V(864),SV("audit")});
        V next=local_snapshot(b);
        require(rd(next,SV("tick"))==rd(s,SV("tick")),"same tick fixture advanced");
        require(rd(next,SV("resources")).len()>rd(s,SV("resources")).len(),"same tick mutation stale");
        callm(b,SY("step"),Args{V(15)});next=local_snapshot(b);
        require(json(rd(s,SV("units")))==held,"old unit rows mutated after step");
        require(json(rd(next,SV("_local_hud")))==counts(next),"stepped HUD stale");
        V public_view=callm(b,SY("snapshot"),Args{V(true),V(true)});
        const auto keys=[](const V& v){std::vector<std::string> out;for(const auto& p:py::items_vec(v))out.push_back(py_str(p.first));return out;};
        require(keys(rd(next,SV("players")))==keys(rd(public_view,SV("players"))),"player draw order changed");
        require(!public_view.find(SV("_local_hud")),"private HUD leaked to public snapshot");
        require(!rd(public_view,SV("native_frame")).find(SV("_typed_local_frame")),"private frame leaked");
        // The public copy must not alias private local rows, cards or players.
        const J expected_units=json(rd(next,SV("units")));
        auto row=rd(rd(public_view,SV("units")),V(0));setitem(row,SV("hp"),V(-999));setitem(rd(row,SV("card")),SV("name"),SV("mutated"));
        const J after_public=json(rd(local_snapshot(b),SV("units")));
        require(after_public==expected_units,"public copy corrupted local state: "+J::diff(expected_units,after_public).dump());
        const J stats=json(callm(b,SY("backend_audit"),Args{}))["state_view"];
        require(stats["cards_resolved"].get<int>()<stats["units_projected"].get<int>(),"card deduplication did not run");
        callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});return stats;
    });
    test("hud_price_and_feedback_match_scan_across_lifecycle",[&]{
        V tracker_a=pm_hud::new_FeedbackTracker(Args{}),tracker_b=pm_hud::new_FeedbackTracker(Args{});
        int cases=0;
        for(int phase=0;phase<4;++phase){
            J units=J::array({{{"id","grave"},{"side","zombie"},{"behavior","grave"},{"hp",phase==2?0:10},{"max_hp",phase==1?20:10},{"card_id","zombie:稻草人"}},
                {{"id","charmed"},{"side","plant"},{"behavior","grave"},{"hp",30},{"max_hp",30},{"card_id","zombie:稻草人"}}});
            if(phase==3)units=J::array();
            V battle=value({{"tick",phase},{"time",phase*1.},{"units",units},{"players",{{"zombie",{{"stats",{{"producer_lost",phase>1?1:0}}}}}}}});
            V fast=py::dict_of(battle);setitem(fast,SV("_local_hud"),value(counts(battle)));
            V player=value({{"secrets",{"zsecret:鸦群"}}});
            require(json(pm_hud::f_battle_card(Args{SV("zombie:乌鸦"),player,battle}))==json(pm_hud::f_battle_card(Args{SV("zombie:乌鸦"),player,fast})),"crow cost differs");
            V va=V::dict(),vb=V::dict();setitem(va,SV("battle"),battle);setitem(vb,SV("battle"),fast);
            for(const char* side:{"plant","zombie"}){require(callm(tracker_a,SY("update"),Args{va,V(side)})==callm(tracker_b,SY("update"),Args{vb,V(side)}),"feedback text differs");++cases;}
        }
        return J{{"cases",cases},{"death_charm_damage_empty_covered",true}};
    });
    if(std::getenv("PVP744_METADATA_VIEW")){
        const auto plain=[](const V& snap){V v=py::dict_of(snap);if(v.find(SV("native_frame")))v.erase(SV("native_frame"));if(v.find(SV("_local_hud")))v.erase(SV("_local_hud"));return json(v);};
        test("private_graph_edits_cannot_corrupt_public_snapshot",[&]{
            auto h=battle_from_scenario({{"seed",744},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
            callm(b,SY("spawn"),Args{SV("plant:向日葵"),SV("plant"),V(1900),V(864),V(1)});callm(b,SY("step"),Args{V(1)});
            V local=local_snapshot(b);const J expected=plain(local);
            V hero=rd(rd(local,SV("players")),SV("plant"));setitem(hero,SV("resource"),V(-999));rd(hero,SV("deck")).append(SV("private-only"));
            setitem(rd(hero,SV("cooldowns")),SV("private-only"),V(123));
            rd(rd(local,SV("native_placement_state")),SV("plants")).append(V::dict());
            setitem(rd(rd(local,SV("units")),V(0)),SV("hp"),V(-888));
            const J held_private=plain(local);
            V pub=callm(b,SY("snapshot"),Args{V(false),V(false)});
            require(plain(pub)==expected,"private edits escaped to public graph");
            setitem(rd(rd(pub,SV("players")),SV("plant")),SV("resource"),V(-777));
            require(plain(local)==held_private,"public edit changed held private graph");
            callm(b,SY("step"),Args{V(1)});V next=local_snapshot(b);
            require(rd(rd(rd(next,SV("players")),SV("plant")),SV("resource")).num()>=0.,"private edit reached Session");
            require(plain(local)==held_private,"new state mutated held private graph");
            J stats=json(callm(b,SY("backend_audit"),Args{}))["metadata_view"];
            require(stats["private_adoptions"].get<int>()>0&&stats["public_rebuilds"].get<int>()>0,"ownership branches not covered");
            callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});return stats;
        });
        test("placement_shapes_sleep_vines_air_and_resources",[&]{
            auto h=battle_from_scenario({{"seed",744},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
            double x=1704.;for(const char* name:{"plant:南瓜头","plant:花盆","plant:抓人草","plant:阳光藤蔓","plant:忧郁藤蔓","plant:旋转芜菁","plant:芦笋战机","plant:大喷菇"}){
                require(!callm(b,SY("spawn"),Args{V(name),SV("plant"),V(x),V(864),V(1)}).is_none(),std::string("spawn failed: ")+name);x+=48.;
            }
            callm(b,SY("resource"),Args{SV("plant"),V(25),V(1900),V(864),SV("audit")});V s=local_snapshot(b);
            const J placement=json(rd(s,SV("native_placement_state")));int air=0,vines=0,sleep=0;
            for(const auto& p:placement["plants"]){air+=p.value("air",false);vines+=p.value("vine",false);sleep+=p.value("睡觉",false);}
            require(air>=2&&vines>=3&&sleep>=1,"placement fixture missing variants");
            require(rd(s,SV("resources")).len()>0,"resource sink not covered");
            callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});return J{{"air",air},{"vines",vines},{"sleep",sleep}};
        });
        test("same_tick_player_metadata_edits_refresh_and_detach",[&]{
            auto h=battle_from_scenario({{"seed",744},{"durable_heroes",true}});V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
            V first=local_snapshot(b);const J held=plain(first);
            V p=rd(getattr(b,SY("players")),SV("plant"));setitem(p,SV("resource"),V(1234));setitem(p,SV("teleport_ready_at"),V(88));setitem(p,SV("seq"),V(27));
            setitem(p,SV("input"),value({{"move",-1}}));setitem(rd(p,SV("cooldowns")),SV("plant:向日葵"),V(42));
            setitem(rd(p,SV("stats")),SV("spent"),V(567));
            V next=local_snapshot(b);J player=json(rd(rd(next,SV("players")),SV("plant")));
            require(rd(first,SV("tick"))==rd(next,SV("tick")),"metadata edit advanced battle");
            require(player["resource"]==1234&&player["teleport_ready_at"]==88&&player["seq"]==27&&player["input"]["move"]==-1&&player["cooldowns"]["plant:向日葵"]==42&&player["stats"]["spent"]==567,"player metadata stale");
            require(plain(first)==held,"live players edited held snapshot");
            callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});return J{{"same_tick",true},{"fields",6}};
        });
    }
    std::ofstream(u8p(argv[1]))<<J{{"passed",failed==0},{"checks",checks}}.dump(2);return failed?1:0;
}
