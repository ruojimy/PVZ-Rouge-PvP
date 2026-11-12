#include "sim/pvp/hand/original_namespace.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "data/datastore.h"
#include "sim/pvp/shim/pm_native_assets.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
#include "core/fsutil.h"
namespace pvz { V runtime_table_value(const nlohmann::json&);V fn_加载图(Match&,const Args&);V fn_加载原图(Match&,const Args&); }
namespace pvz { namespace pm_native_assets {
namespace {
struct AssetImagePaths : PyObj {
    V image;std::filesystem::path directory;
    const char* type_name()const override{return "NativeAssetImagePaths";}
    V property(Sym name,bool& found)override{if(name==Sym("load")){found=false;return V();}found=true;return pvz::getattr(image,name);}
    V method(Sym name)override{
        if(name!=Sym("load"))return V();auto owner=std::static_pointer_cast<AssetImagePaths>(shared_from_this());
        return V::func([owner](const Args& input){Args actual=input;std::string source=py::str(actual.pos.at(0)).str();std::replace(source.begin(),source.end(),'\\','/');
            actual.pos[0]=V(p8(owner->directory/u8p(source).filename()));return callm(owner->image,Sym("load"),actual);});
    }
};
}

// Dictionary namespaces use the actual original loader and real SDL surfaces.
// The ordinary match recording path keeps its existing baked PvP composition.
static V load_dictionary_original_assets(const Args& A) {
    V mapping=A.pos.at(0);
    static const V default_tile(48),no_patch=V::none();
    V tile=A.get(3,Sym("tile"),&default_tile),patch=A.get(4,Sym("patch"),&no_patch);
    if(tile.t!=V::NUM || !std::isfinite(tile.num()) || std::trunc(tile.num())!=tile.num() || tile.num()<16 || tile.num()>128)throw PyError("ValueError","Native tile must be 16..128 integer pixels");
    invoke_compiled_original_namespace(mapping,[&](Match& world){
        if(pvz::hasattr(world.pygame,Sym("g")))throw PyError("ValueError","Load native atlases before installing NamespaceGraphics");
        for(const char* name:{"加载游戏","变图","纯换色","不纯换色","换蓝色","换黑白","换金色","c"})
            if(!world.has_global(V(name)) || !py::callable(world.global(V(name))).truthy())world.global(V(name))=bind_compiled_original_function(mapping,V(name));
        auto view=std::make_shared<MatchNS>();view->G=&world;view->setattr(Sym("__original_raw_asset_io__"),V(true));
        Args io=A;io.pos.at(0)=V::inst(view);f_load_original_assets(io);
        V old_width=world.总宽,old_panorama=world.生成近景;
        world.总宽=tile*V(20);if(!world.总高.has())world.总高=V(640);
        world.生成近景=V::func([](const Args&){return V::none();});
        {
            auto restore=py::finally([&]{world.总宽=old_width;if(old_panorama.has())world.生成近景=old_panorama;else world.生成近景.del();});
            // Retain a verified source binding if supplied by the fixture. It
            // executes real C++ under the unchanged reference invocation gate.
            world.加载游戏.call(Args{});
        }
        return V::none();
    });
        if(!patch.is_none()) {
            for(const char* name:{"__pvz_sb_patch_star_atlas","__pvz_sb_patch_stone_assets","__pvz_sb_patch_tripea_assets","__pvz_sb_patch_pumpkin_armor_assets","__pvz_sb_patch_plant_zombie_assets"}) {
                V helper=py::m_get(patch,V(name));if(!py::callable(helper).truthy())throw PyError("ValueError",std::string("Original patch asset helper missing: ")+name);
                helper.call(Args{mapping});
            }
            // Exactly the original late-added plant/hero/head state variants.
            V atlas=rd(mapping,V("图集"));
            for(const auto& entry:pm_catalog::CARDS.kv()) {
                V card=entry.second,name=rd(card,V("name"));
                if(rd(card,V("side"))!=V("plant") || rd(card,V("category"))!=V("plant") || !atlas.contains(name))continue;
                for(V suffixes=V::tuple({V("-受伤"),V("-黑白")});const V& suffix:suffixes.items())if(!atlas.contains(name+suffix)) {
                    V raw=rd(mapping,V("加载原图")).call(Args{V("图片/")+name+V(".png")});
                    V recolored=suffix==V("-受伤")?rd(mapping,V("纯换色")).call(Args{raw,rd(mapping,V("纯白色"))}):rd(mapping,V("换黑白")).call(Args{raw});
                    V size=callm(rd(atlas,name),Sym("get_size"),Args{});atlas.at(name+suffix)=rd(mapping,V("变图")).call(Args{recolored,size.idx(0),size.idx(1)});
                }
            }
            for(V skins=V::tuple({V("疯狂戴夫"),V("僵尸戴夫")});const V& skin:skins.items())if(atlas.contains(skin) && !atlas.contains(skin+V("-冰冻"))) {
                V raw=rd(mapping,V("加载原图")).call(Args{V("图片/")+skin+V(".png")}),size=callm(rd(atlas,skin),Sym("get_size"),Args{});
                atlas.at(skin+V("-冰冻"))=rd(mapping,V("变图")).call(Args{rd(mapping,V("不纯换色")).call(Args{raw,rd(mapping,V("蓝色"))}),size.idx(0),size.idx(1)});
            }
            V keys=V::set();
            for(const auto& entry:pm_catalog::CARDS.kv())if(rd(entry.second,V("side"))==V("zombie"))py::set_add(keys,rd(patch,V("__pvz_sb_plant_zombie_head_key")).call(Args{rd(entry.second,V("name"))}));
            py::set_add(keys,rd(patch,V("__pvz_sb_K_FUMESHROOM_ZOMBIE_THUNDER_HEAD")));
            for(V ordered_keys=py::sorted_it(keys,py::Key(),false);const V& key:ordered_keys.items())if(atlas.contains(key)) {
                V variants=V::tuple({V::tuple({V("-受伤"),V("纯换色"),V("纯白色")}),V::tuple({V("-冰冻"),V("不纯换色"),V("蓝色")}),V::tuple({V("-灰烬"),V("纯换色"),V("纯黑色")}),V::tuple({V("-魅惑"),V("不纯换色"),V("紫色")})});
                for(const V& row:variants.items())if(!atlas.contains(key+row.idx(0)))atlas.at(key+row.idx(0))=rd(mapping,row.idx(1)).call(Args{callm(rd(atlas,key),Sym("copy"),Args{}),rd(mapping,row.idx(2))});
            }
        }
        return py_dict({{V("tile"),rd(mapping,V("比"))},{V("plk"),rd(mapping,V("plk"))},{V("world_assets"),V(double(rd(mapping,V("图集")).len()))},{V("ui_assets"),V(double(rd(mapping,V("ui图集")).len()))},{V("source"),V("compiled original 加载游戏")},{V("patch_assets"),V(!patch.is_none())},{V("menu_panorama_generated"),V(false)}});
}

V f_load_original_assets(const Args& A) {
    if(A.pos.at(0).t==V::DICT)return load_dictionary_original_assets(A);
    Match& world=match_of(A.pos.at(0));
    // Seed only absent original literal inputs, with tuple/set/dictionary types.
    // This is static source data, never an atlas/render or gameplay result.
    for(auto& [name,value]:data::module("_original_asset_literals").items())if(!world.has_global(V(name)))world.global(V(name))=runtime_table_value(value);
    for(const char* name:{"math","copy","random","time"})if(!world.has_global(V(name)))world.global(V(name))=py::stdlib_module(V(name));
    if(!pvz::getattr(A.pos.at(0),Sym("__original_raw_asset_io__"),V(false)).truthy())gfx::install_atlases(world);
    // 加载游戏 sets xianbi = int(比/17) with the other asset globals (画线 uses it for bungee
    // ropes). The atlas path above bypasses that loader, so the asset step sets it here; a
    // bare NativeRuntime (no assets loaded) has none, as in CPython.
    world.xianbi=py::int_(world.比/V(17.0));
    // Headless recipe execution has no SDL pixel backend. Its baked atlas path
    // is retained; a real linked pixel namespace installs the original IO bodies.
    if(py::has_native_hook("graphics.materialize_image") && world.pygame.has() && !world.pygame.is_none()) {
        if(pvz::getattr(world.pygame,Sym("__graphics_metrics__"),V::none()).is_dict())throw PyError("ValueError","Load native atlases before installing the recording namespace");
        auto image=std::make_shared<AssetImagePaths>();image->image=pvz::getattr(world.pygame,Sym("image"));image->directory=u8p(py::str(A.pos.at(2)).str());
        auto io=std::make_shared<Match>();io->pygame=py_dict({{V("image"),V::inst(image)},{V("transform"),pvz::getattr(world.pygame,Sym("transform"))}});
        world.加载图=V::func([io](const Args& args){return fn_加载图(*io,args);});
        world.加载原图=V::func([io](const Args& args){return fn_加载原图(*io,args);});
    }
    return py_dict({{SV("tile"),V(48.0)}});
}
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_native_assets
