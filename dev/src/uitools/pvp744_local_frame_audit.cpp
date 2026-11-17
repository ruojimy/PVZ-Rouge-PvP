#include "pvp742_guest_memory_fixture.h"
#include "ui/gen/pm_world_view.h"
using namespace pvz;
using namespace pvz::guest_memory_audit;
namespace {
V value(const J& j){return py::json_loads(V(j.dump()));}
V local_snapshot(const V& b){typed72app::LocalPresentationScope scope(b);return callm(b,SY("snapshot"),Args{V(false),V(false)});}
J expand(const V& f){J out=json(callm(rd(f,SV("_typed_local_frame")),SY("project"),Args{}));out.erase("command_count");return out;}
}
int main(int argc,char** argv){
    if(argc!=2||!std::getenv("PVP_USERDATA"))return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J checks=J::array();int failed=0;
    auto test=[&](const char* name,auto fn){J row={{"name",name}};try{row["evidence"]=fn();row["passed"]=true;}catch(const std::exception& e){row["passed"]=false;row["error"]=e.what();++failed;}checks.push_back(row);std::cout<<row.dump()<<std::endl;};
    auto h=battle_from_scenario({{"seed",744},{"night",true},{"durable_heroes",true}});
    V enemy=rd(getattr(h.battle,SY("avatars")),SV("zombie"));setitem(enemy,SV("玩家位置"),value({2280,864,0,0}));setitem(enemy,SV("黄油"),V(1000000.));
    V b=typed72app::wrap_battle(h.battle);typed72app::start_battle_session(b);
    for(const auto& [key,x]:std::vector<std::pair<std::string,double>>{{"plant:抓人草",2136.},{"plant:向日葵",1896.},{"plant:豌豆射手",1944.}})
        require(!callm(b,SY("spawn"),Args{V(key),SV("plant"),V(x),V(864),V(1)}).is_none(),"spawn failed");
    for(double x:{1656.,1704.,1752.,1800.,1848.,1992.,2040.,2088.})
        require(!callm(b,SY("spawn"),Args{SV("plant:抓人草"),SV("plant"),V(x),V(864),V(1)}).is_none(),"dense root spawn failed");
    callm(b,SY("step"),Args{V(180)});
    V local=local_snapshot(b),lazy=rd(local,SV("native_frame"));
    V full=callm(b,SY("snapshot"),Args{V(true),V(false)}),full_frame=rd(full,SV("native_frame"));
    setitem(local,SV("map"),rd(full,SV("map")));
    test("local_frame_is_lazy_public_protocol_stays_complete",[&]{
        require(json(full)["pvp70"]["tentacles"].size()>=6,"fixture did not produce dense grabber heads");
        require(lazy.find(SV("_typed_local_frame"))&&rd(lazy,SV("commands")).len()==0,"no private lazy frame");
        require(!full_frame.find(SV("_typed_local_frame"))&&rd(full_frame,SV("commands")).len()>10,"public protocol changed");
        const J stats=json(callm(b,SY("backend_audit"),Args{}));require(stats["local_frame"]["commands_projected"]==0,"private frame eagerly projected");
        return stats["local_frame"];
    });
    V world=pm_world_view::new_WorldView(Args{pg::pygame_module(),h.bridge});
    V screen=pg::new_surface(960,640,true),rect=value({19,13,900,600});
    V app=pm_app::new_Application(Args{pg::pygame_module(),screen,h.bridge});texture74::initialize(app);
    auto render=[&](const V& snap,const V& settings){callm(screen,SY("fill"),Args{value({20,30,40,255})});callm(world,SY("render"),Args{screen,snap,rect,SV("plant"),settings,V::none(),V(true)});require(!getattr(world,SY("native_error")).truthy(),"WorldView rendering error: "+py_str(getattr(world,SY("native_error"))));return texture74::pixels(screen);};
    test("real_world_pixels_layers_clipping_zoom_and_offsets",[&]{
        int cases=0;
        for(double zoom:{.55,1.,1.75})for(double camera:{2136.,3000.}){
            V settings=value({{"zoom",zoom},{"world_quality","native"},{"replay_camera",{camera,800.}}});
            auto reference=render(full,settings);require(reference==render(local,settings),"lazy world pixels differ");++cases;
        }
        V shifted_full=py::dict_of(full),shifted_local=py::dict_of(local),offset=value({{"hero:plant",{-8.25,3.5}},{"hero:zombie",{9.,0.}}});
        setitem(shifted_full,SV("_visual_offsets"),offset);setitem(shifted_local,SV("_visual_offsets"),offset);
        V settings=value({{"zoom",1.25},{"world_quality","native"},{"replay_camera",{2136.,800.}}});
        require(render(shifted_full,settings)==render(shifted_local,settings),"interpolated offsets differ");
        const J stats=json(callm(b,SY("backend_audit"),Args{}));require(stats["local_frame"]["commands_projected"].get<int>()>0&&stats["local_frame"]["commands_culled"].get<int>()>0,"renderer did not consume/cull typed commands");
        callm(pg::image_module(),SY("save"),Args{screen,V(p8(u8p(argv[1]).parent_path()/"local-frame-world.png"))});
        return J{{"pixel_comparisons",cases+1},{"local_frame",stats["local_frame"]}};
    });
    test("outro_hide_and_fallen_hero_materialize_only_on_request",[&]{
        const J hero=json(full)["players"]["plant"];
        V settings=value({{"zoom",1.25},{"world_quality","native"},{"replay_camera",{hero["x"],hero["y"]}},{"outro_hide","hero:plant"}});
        require(render(full,settings)==render(local,settings),"hidden hero differs");
        std::vector<uint32_t> reference;
        for(const V& snap:{full,local}){render(snap,settings);require(callm(world,SY("draw_fallen_hero"),Args{screen,snap,SV("hero:plant"),V(75)}).truthy(),"fallen body missing");auto pixels=texture74::pixels(screen);if(reference.empty())reference=std::move(pixels);else require(pixels==reference,"fallen hero pixels differ");}
        return J{{"pixels_equal",true}};
    });
    test("full_fallback_matches_protocol_and_held_version_survives",[&]{
        const J old=json(full_frame);require(expand(lazy)==old,"full fallback schema changed");
        const J rng=json(callm(getattr(getattr(b,SY("engine")),SY("rng")),SY("getstate"),Args{}));
        for(int i=0;i<10;++i)render(local,value({{"world_quality","native"},{"replay_camera",{2136.,800.}}}));
        require(json(callm(getattr(getattr(b,SY("engine")),SY("rng")),SY("getstate"),Args{}))==rng,"render consumed battle RNG");
        callm(b,SY("step"),Args{V(1)});V next=local_snapshot(b);require(!py_is(rd(next,SV("native_frame")),lazy),"new tick retained old frame");
        require(expand(lazy)==old,"held native frame mutated");
        return J{{"held_frame_immutable",true},{"rng_unchanged_by_render",true}};
    });
    test("material_override_and_original_restore_match",[&]{
        const J empty={{"format","pvz-texture-pack-v1"},{"name","original"},{"entries",J::object()}};
        texture74::activate(empty);
        const J hero=json(full)["players"]["plant"];
        const V settings=value({{"world_quality","native"},{"replay_camera",{hero["x"],hero["y"]}}});
        const auto original=render(local,settings);
        const auto* resource=texture74::resource("world:疯狂戴夫");require(resource,"hero resource missing");
        std::vector<uint32_t> pixels(size_t(resource->w)*resource->h,0x2080f0ff);
        J pack=empty;pack["entries"]["world:疯狂戴夫"]={{"width",resource->w},{"height",resource->h},{"png",texture74::b64(texture74::png_encode(texture74::surface(resource->w,resource->h,pixels)))}};
        texture74::activate(pack);const auto decorated=render(local,settings);
        require(decorated!=original,"material fixture did not change visible hero pixels");
        require(decorated==render(full,settings),"material override differs between paths");
        texture74::activate(empty);require(render(local,settings)==original,"material restore left stale pixels");
        return J{{"custom_and_restore_equal",true}};
    });
    callm(b,SY("close"),Args{});callm(h.battle,SY("close"),Args{});
    std::ofstream(u8p(argv[1]))<<J{{"passed",failed==0},{"checks",checks}}.dump(2);return failed?1:0;
}
