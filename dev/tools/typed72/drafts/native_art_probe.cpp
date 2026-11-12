// Direct current V/hand pixel and metadata oracle in a test executable only.
#include "sim/typed/native_art.h"
#include "sim/typed/expansion_art.h"
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_native_expansion.h"
#include "sim/pvp/gen/pm_native_scale.h"
#include <fstream>
#include <iostream>
using namespace pvz;
using namespace pvz::typed72;
using J=nlohmann::json;
namespace {
struct ReferenceArt {V pixels,recorded;};
J encode(const V& value) {
    if(!value.has()||value.is_none())return nullptr;
    if(value.is_str())return value.str();if(value.is_num())return value.num();if(value.t==V::BOOL)return value.truthy();
    if(value.is_dict()){J out=J::object();for(const auto& [k,v]:py::items_vec(value))out[k.str()]=encode(v);return out;}
    J out=J::array();for(const auto& v:py::iter_list(value).items())out.push_back(encode(v));return out;
}
V point(int a,int b){return V::nums({double(a),double(b)});}
J snapshot(const NativeArt& art) {
    const auto held=NativeArtStore::materialize(art);const auto& pixels=*held;
    return {{"size",{art->width,art->height}},{"pixels_size",{pixels.width,pixels.height}},{"pixels",pixels.pixels}};
}
J snapshot(const ReferenceArt& art) {
    const auto* surface=pg::surf(art.pixels);J colors=J::array();
    for(int y=0;y<surface->h();++y)for(int x=0;x<surface->w();++x) {
        const auto* pixel=reinterpret_cast<const uint32_t*>(static_cast<const uint8_t*>(surface->s->pixels)+size_t(y)*surface->s->pitch)+x;
        uint8_t r,g,b,a;SDL_GetRGBA(*pixel,surface->s->format,&r,&g,&b,&a);colors.push_back({r,g,b,a});
    }
    return {{"size",encode(callm(art.recorded,SY("get_size"),Args{}))},{"pixels_size",{surface->w(),surface->h()}},{"pixels",colors}};
}
void run(const J& input,J& actual,J& expected) {
    NativeArtStore store;std::vector<NativeArt> typed;std::vector<ReferenceArt> original;
    const V pg=pg::pygame_module(),recorded_pg=gfx::make_pygame();
    for(const auto& asset:input.at("assets")) {
        std::cerr<<"asset "<<asset.at("name")<<'\n';
        SpritePixels p;p.width=asset.at("width");p.height=asset.at("height");p.pixels=asset.at("pixels").get<std::vector<Color>>();
        typed.push_back(store.asset("world:"+asset.at("name").get<std::string>(),p));
        V pixels=pg::new_surface(p.width,p.height,true);auto* surface=pg::surf(pixels);
        for(int y=0;y<p.height;++y)for(int x=0;x<p.width;++x) {
            const auto color=p.at(x,y);
            auto* target=reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(surface->s->pixels)+size_t(y)*surface->s->pitch)+x;
            *target=SDL_MapRGBA(surface->s->format,color[0],color[1],color[2],color[3]);
        }
        original.push_back({pixels,gfx::make_image("world:"+asset.at("name").get<std::string>(),p.width,p.height)});
    }
    actual=J::array();expected=J::array();
    for(const auto& op:input.at("operations")) {
        std::cerr<<"operation "<<op.dump()<<'\n';
        const auto kind=op.at("op").get<std::string>();const size_t i=op.value("image",size_t(0));
        const auto before=typed.at(i);const auto prior=original.at(i);J ta,va;
        if(kind=="seat") {
            const auto other=op.at("plate").get<size_t>();const auto armor=op.at("armor").get<std::string>();
            const auto seat=ExpansionArt::seat(armor,before,typed.at(other));ta=seat?J{seat->x,seat->y}:J(nullptr);
            va=encode(pm_native_expansion::f_headgear_seat(Args{V("head"),V(armor),prior.pixels,original.at(other).pixels}));
        }else if(kind=="box") {
            const auto box=NativeArtStore::bounds(before,op.value("threshold",8));ta=box?J{box->left,box->top,box->right,box->bottom}:J(nullptr);
            V r=callm(prior.pixels,SY("get_bounding_rect"),Args{V(op.value("threshold",8))});
            const int x=int(getattr(r,SY("x")).num()),y=int(getattr(r,SY("y")).num()),w=int(getattr(r,SY("width")).num()),h=int(getattr(r,SY("height")).num());
            va=w&&h?J{x,y,x+w-1,y+h-1}:J(nullptr);
        }else {
            NativeArt next;ReferenceArt next_v;
            if(kind=="copy") {next=NativeArtStore::copy(before);next_v={callm(prior.pixels,SY("copy"),Args{}),callm(prior.recorded,SY("copy"),Args{})};}
            else if(kind=="scale") {
                const int w=op.at("width"),h=op.at("height");next=NativeArtStore::scale(before,w,h);
                next_v={callm(getattr(pg,SY("transform")),SY("scale"),Args{prior.pixels,point(w,h)}),callm(getattr(recorded_pg,SY("transform")),SY("scale"),Args{prior.recorded,point(w,h)})};
            }else if(kind=="flip") {
                const bool x=op.at("x"),y=op.at("y");next=NativeArtStore::flip(before,x,y);
                next_v={callm(getattr(pg,SY("transform")),SY("flip"),Args{prior.pixels,V(x),V(y)}),callm(getattr(recorded_pg,SY("transform")),SY("flip"),Args{prior.recorded,V(x),V(y)})};
            }else if(kind=="rotate") {
                const double angle=op.at("angle");next=NativeArtStore::rotate(before,angle);
                next_v={callm(getattr(pg,SY("transform")),SY("rotate"),Args{prior.pixels,V(angle)}),callm(getattr(recorded_pg,SY("transform")),SY("rotate"),Args{prior.recorded,V(angle)})};
            }else if(kind=="shrink") {
                const double factor=op.at("factor");next=store.shrink(before,factor);
                next_v={pm_native_scale::f_shrink(Args{pg,prior.pixels,V(factor)}),pm_native_scale::f_shrink(Args{recorded_pg,prior.recorded,V(factor)})};
            }else if(kind=="blit") {
                next=NativeArtStore::copy(before);next_v={callm(prior.pixels,SY("copy"),Args{}),callm(prior.recorded,SY("copy"),Args{})};
                const auto target=op.at("overlay").get<size_t>();const double x=op.at("point").at(0),y=op.at("point").at(1);
                NativeArtStore::blit(next,typed.at(target),{x,y});const V p=V::nums({x,y});
                callm(next_v.pixels,SY("blit"),Args{original.at(target).pixels,p});callm(next_v.recorded,SY("blit"),Args{original.at(target).recorded,p});
            }else if(kind=="alpha") {
                before->alpha=op.at("value").is_null()?-2:op.at("value").get<int>();
                const V alpha=op.at("value").is_null()?V::none():V(op.at("value").get<int>());
                callm(prior.pixels,SY("set_alpha"),Args{alpha});callm(prior.recorded,SY("set_alpha"),Args{alpha});next=before;next_v=prior;
            }else throw std::invalid_argument("native art fixture operation");
            typed.push_back(next);original.push_back(next_v);ta=snapshot(next);va=snapshot(next_v);
        }
        actual.push_back(ta);expected.push_back(va);
    }
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=4)throw std::invalid_argument("usage: native_art72_probe inputs actual expected");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");
        SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);
        pg::install_pygame();init_pvp_modules();
        std::ifstream input(argv[1]);std::ofstream actual(argv[2]),expected(argv[3]);std::string line;
        while(std::getline(input,line))if(!line.empty()){J a,b;run(J::parse(line),a,b);actual<<a.dump()<<'\n';expected<<b.dump()<<'\n';}
        return actual&&expected?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
