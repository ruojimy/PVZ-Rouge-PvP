#include "sim/typed/native_art.h"
#include "core/pymath.h"
#include <SDL.h>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
namespace pvz::typed72 {
namespace {
std::shared_ptr<SpritePixels> empty(int width,int height) {
    if(width<0||height<0||uint64_t(width)*uint64_t(height)>size_t(-1)/sizeof(Color))throw std::length_error("native art size");
    auto p=std::make_shared<SpritePixels>();p->width=width;p->height=height;p->pixels.resize(size_t(width)*height);return p;
}
void blend(Color& target,const Color& source,int modulation) {
    if(modulation==-2){target=source;return;}
    const int a=modulation<0?source[3]:int(source[3])*std::clamp(modulation,0,255)/255;
    if(a==255){target=source;return;}
    if(!target[3]){target=source;target[3]=uint8_t(a);return;}
    for(size_t i=0;i<3;++i)target[i]=uint8_t((((int(source[i])-int(target[i]))*a+source[i])>>8)+target[i]);
    target[3]=uint8_t(a+target[3]-a*int(target[3])/255);
}
std::pair<int,int> rotation_size(int width,int height,double input) {
    // Current recorded-image metadata rounds to float, independently of the
    // full-precision surface renderer. Keep both contracts explicit.
    const double angle=float(input);
    if(std::fmod(angle,90.)==0.)return int64_t(angle/90.)%2?std::pair{height,width}:std::pair{width,height};
    const double r=angle*.01745329251994329,c=std::cos(r),s=std::sin(r);
    return {int(std::fabs(c*width)+std::fabs(s*height)),int(std::fabs(s*width)+std::fabs(c*height))};
}
const std::array<const char*,5> states{"","-受伤","-冰冻","-灰烬","-魅惑"};
}
NativeArt NativeArtStore::asset(std::string key,SpritePixels data) {
    if(data.width<0||data.height<0||data.pixels.size()!=size_t(data.width)*data.height)throw std::invalid_argument("native asset pixels");
    auto out=std::make_shared<NativeArtImage>();out->width=data.width;out->height=data.height;
    auto recipe=std::make_shared<NativeArtRecipe>();recipe->key=std::move(key);out->recipe=recipe;
    out->pixels=std::make_shared<const SpritePixels>(std::move(data));return out;
}
NativeArt NativeArtStore::find(const std::string& name)const{const auto i=atlas.find(name);return i==atlas.end()?NativeArt{}:i->second;}
NativeArt NativeArtStore::register_asset(const std::string& name,const NativeArt& image) {
    auto out=asset("world:"+name,*materialize(image));atlas[name]=out;return out;
}
FrozenArt NativeArtStore::freeze(const NativeArt& image){return image?std::make_shared<const NativeArtImage>(*image):FrozenArt{};}
NativeArt NativeArtStore::copy(const NativeArt& image){return image?std::make_shared<NativeArtImage>(*image):NativeArt{};}
std::pair<int,int> NativeArtStore::rotated_size(int width,int height,double degrees){return rotation_size(width,height,degrees);}
NativeArt NativeArtStore::canvas(int width,int height,int flags) {
    auto out=std::make_shared<NativeArtImage>();out->width=width;out->height=height;out->pixel_alpha=(flags&65536)!=0;
    auto recipe=std::make_shared<NativeArtRecipe>();recipe->kind=NativeArtRecipe::Kind::canvas;recipe->flags=flags;out->recipe=recipe;
    // Most native canvases only record strokes and are never sampled by combat.
    // pixels()/materialize() already create exactly this transparent payload on demand.
    static const bool lazy=[]{const char* p=std::getenv("PVP742_LAZY_CANVAS");return !p||*p!='0';}();
    if(!lazy)out->pixels=empty(width,height);return out;
}
NativeArt NativeArtStore::transformed(const NativeArt& image,NativeArtRecipe recipe,int width,int height) {
    if(!image)throw std::invalid_argument("missing native art");
    auto out=std::make_shared<NativeArtImage>();out->width=width;out->height=height;out->alpha=image->alpha;out->pixel_alpha=image->pixel_alpha;
    recipe.source=freeze(image);out->recipe=std::make_shared<const NativeArtRecipe>(std::move(recipe));return out;
}
NativeArt NativeArtStore::scale(const NativeArt& image,int width,int height) {
    if(width<0||height<0)throw std::invalid_argument("negative art scale");
    NativeArtRecipe r;r.kind=NativeArtRecipe::Kind::scale;return transformed(image,std::move(r),width,height);
}
NativeArt NativeArtStore::flip(const NativeArt& image,bool horizontal,bool vertical) {
    NativeArtRecipe r;r.kind=NativeArtRecipe::Kind::flip;r.flip_x=horizontal;r.flip_y=vertical;
    return transformed(image,std::move(r),image->width,image->height);
}
NativeArt NativeArtStore::rotate(const NativeArt& image,double degrees) {
    if(!std::isfinite(degrees))throw std::invalid_argument("nonfinite art rotation");
    NativeArtRecipe r;r.kind=NativeArtRecipe::Kind::rotate;r.angle=degrees;
    const auto [width,height]=rotation_size(image->width,image->height,degrees);return transformed(image,std::move(r),width,height);
}
void NativeArtStore::blit(const NativeArt& destination,const NativeArt& overlay,Point point) {
    if(!destination||!overlay)throw std::invalid_argument("missing blit image");
    NativeArtRecipe r;r.kind=NativeArtRecipe::Kind::blit;r.source=freeze(destination);r.overlay=freeze(overlay);r.destination=point;
    destination->recipe=std::make_shared<const NativeArtRecipe>(std::move(r));destination->pixels.reset();
}
const SpritePixels& NativeArtStore::pixels(const FrozenArt& image) {
    if(!image)throw std::invalid_argument("missing native pixels");
    if(image->pixels)return *image->pixels;
    const auto& r=*image->recipe;auto out=empty(image->width,image->height);
    if(r.kind==NativeArtRecipe::Kind::canvas){image->pixels=out;return *out;}
    if(r.kind==NativeArtRecipe::Kind::asset)throw std::logic_error("cold asset missing pixel payload");
    const auto& source=pixels(r.source);const int sw=source.width,sh=source.height,w=out->width,h=out->height;
    if(r.kind==NativeArtRecipe::Kind::scale) {
        if(w&&h&&sw&&sh) {
            // Use the very same SDL_SoftStretch entrypoint as current V/hand.
            using Surface=std::unique_ptr<SDL_Surface,decltype(&SDL_FreeSurface)>;
            Surface src(SDL_CreateRGBSurfaceWithFormatFrom(const_cast<Color*>(source.pixels.data()),sw,sh,32,sw*4,SDL_PIXELFORMAT_RGBA32),SDL_FreeSurface);
            Surface dst(SDL_CreateRGBSurfaceWithFormatFrom(out->pixels.data(),w,h,32,w*4,SDL_PIXELFORMAT_RGBA32),SDL_FreeSurface);
            if(!src||!dst||SDL_SoftStretch(src.get(),nullptr,dst.get(),nullptr))throw std::runtime_error(SDL_GetError());
        }
    }else if(r.kind==NativeArtRecipe::Kind::flip) {
        for(int y=0;y<h;++y)for(int x=0;x<w;++x)out->pixels[size_t(y)*w+x]=source.at(r.flip_x?w-1-x:x,r.flip_y?h-1-y:y);
    }else if(r.kind==NativeArtRecipe::Kind::blit) {
        out->pixels=source.pixels;const auto& overlay=pixels(r.overlay);
        // Current V/hand Surface::blit floors float destinations (surface.cpp iv).
        const int left=int(std::floor(r.destination.x)),top=int(std::floor(r.destination.y));
        for(int y=std::max(0,top);y<std::min(h,top+overlay.height);++y)
            for(int x=std::max(0,left);x<std::min(w,left+overlay.width);++x)
                blend(out->pixels[size_t(y)*w+x],overlay.at(x-left,y-top),r.overlay->alpha);
    }else if(r.kind==NativeArtRecipe::Kind::rotate) {
        const double angle=r.angle;
        double a=std::fmod(angle,360.);if(a<0)a+=360.;
        if(std::fmod(angle,90.)==0.) {
            const int turns=int(a/90.)%4;
            for(int y=0;y<h;++y)for(int x=0;x<w;++x) {
                int sx=x,sy=y;
                if(turns==1){sx=sw-1-y;sy=x;}else if(turns==2){sx=sw-1-x;sy=sh-1-y;}else if(turns==3){sx=y;sy=sh-1-x;}
                out->pixels[size_t(y)*w+x]=source.at(sx,sy);
            }
        }else {
            const double rad=angle*.01745329251994329,s=std::sin(rad),c=std::cos(rad);
            const int dw=int(std::max({std::fabs(c*sw+s*sh),std::fabs(c*sw-s*sh),std::fabs(-c*sw+s*sh),std::fabs(-c*sw-s*sh)}));
            const int dh=int(std::max({std::fabs(s*sw+c*sh),std::fabs(s*sw-c*sh),std::fabs(-s*sw+c*sh),std::fabs(-s*sw-c*sh)}));
            // Recorded image dimensions and materialized surface dimensions
            // have separate owning sources in current V/hand.
            out=empty(dw,dh);
            const int64_t isin=int64_t(s*65536.),icos=int64_t(c*65536.);
            const int64_t ax=int64_t(dw)*32768-int64_t(c*(int64_t(dw-1)*32768));
            const int64_t ay=int64_t(dh)*32768-int64_t(s*(int64_t(dw-1)*32768));
            for(int y=0;y<dh;++y) {
                int64_t dx=ax+isin*(dh/2-y)+int64_t(sw-dw)*32768;
                int64_t dy=ay-icos*(dh/2-y)+int64_t(sh-dh)*32768;
                for(int x=0;x<dw;++x,dx+=icos,dy+=isin)if(dx>=0&&dy>=0&&dx<int64_t(sw)*65536&&dy<int64_t(sh)*65536)
                    out->pixels[size_t(y)*dw+x]=source.at(int(dx>>16),int(dy>>16));
            }
        }
    }else throw std::logic_error("unsupported native image recipe");
    image->pixels=out;return *out;
}
std::shared_ptr<const SpritePixels> NativeArtStore::materialize(const NativeArt& image) {
    if(!image)throw std::invalid_argument("missing native pixels");
    if(!image->pixels){const auto frozen=freeze(image);pixels(frozen);image->pixels=frozen->pixels;}
    return image->pixels;
}
std::optional<NativeArtBox> NativeArtStore::bounds(const NativeArt& image,int threshold) {
    if(!image)return {};const auto held=materialize(image);const auto& p=*held;NativeArtBox box{p.width,p.height,-1,-1};
    for(int y=0;y<p.height;++y)for(int x=0;x<p.width;++x)if(p.at(x,y)[3]>=threshold){box.left=std::min(box.left,x);box.top=std::min(box.top,y);box.right=std::max(box.right,x);box.bottom=std::max(box.bottom,y);}
    return box.right<0?std::nullopt:std::optional(box);
}
std::optional<int> NativeArtStore::painted_top(const NativeArt& image,int threshold) {
    if(!image)return {};const auto held=materialize(image);const auto& p=*held;
    for(int y=0;y<p.height;++y)for(int x=0;x<p.width;++x)if(p.at(x,y)[3]>threshold)return y;return {};
}
std::optional<std::string> NativeArtStore::art_key(const FrozenArt& image) {
    if(!image)return {};auto node=image;
    for(int i=0;i<8&&node;++i){if(node->recipe->kind==NativeArtRecipe::Kind::asset)return node->recipe->key;node=node->recipe->source;}return {};
}
std::string NativeArtStore::atlas_name(const std::string& key){return key.starts_with("world:")?key.substr(6):key;}
double NativeArtStore::factor(const std::string& unit)const{const auto i=factors.find(unit);return i==factors.end()?1.:i->second;}
double NativeArtStore::rider_lift(const std::string& unit)const{const auto i=rider_lifts.find(unit);return i==rider_lifts.end()?0.:i->second;}
NativeArt NativeArtStore::shrink(const NativeArt& image,double factor)const {
    if(!image||factor==1.)return image;
    const int width=std::max(1,int(py::round0(image->width*factor))),height=std::max(1,int(py::round0(image->height*factor)));
    auto small=scale(image,width,height),out=canvas(image->width,image->height);
    blit(out,small,{std::floor(double(image->width-width)/2.),double(image->height-height)});return out;
}
void NativeArtStore::install_scale(const std::map<std::string,double>& sizes,double tile) {
    factors.clear();rider_lifts.clear();
    for(const auto& [unit,tiles]:sizes) {
        factors[unit]=tiles/2.;const auto base=find(unit);if(!base||base->height<=0)continue;
        const double s=tiles*tile/base->height;if(s>=1.)continue;
        for(const std::string part:{"","-身","-首","-帧0","-帧1","-帧2","-帧3","-身0","-身1","-身2","-身3","-首0","-首1","-首2","-首3"})for(const auto suffix:states) {
            const auto name=unit+part+suffix;const auto before=find(name);if(!before)continue;
            const auto after=shrink(before,s);atlas[name]=after;
            if(name==unit){const auto a=painted_top(before),b=painted_top(after);if(a&&b)rider_lifts[unit]=double(*b-*a);}
        }
    }
    for(const std::string armor:{"路障","铁桶","橄榄球头盔","黑路障","黑铁桶","黑橄榄球头盔"})for(const auto suffix:states) {
        const auto name=armor+suffix;const auto image=find(name);if(image)atlas["小鬼僵尸-"+name]=shrink(image,factor("小鬼僵尸"));
    }
}
}
