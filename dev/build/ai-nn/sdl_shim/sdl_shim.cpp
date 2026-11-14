// See SDL.h in this directory. Full-surface RGBA32 -> RGBA32 nearest stretch, written to
// follow SDL 2.28-2.30 SDL_stretch.c (SDL_LowerSoftStretchNearest / scale_mat_nearest_4):
// 16.16 fixed-point source steps, starting half a step in. Not verified against a real SDL
// binary in the environment it was written in: compare on a machine with SDL2 before relying
// on it (docs/ai-nn/交接.md).
#include "SDL.h"
#include <atomic>
#include <new>
namespace {
std::atomic<unsigned long long> stretch_calls{0};
const char* last_error="";
}
extern "C" {
SDL_Surface* SDL_CreateRGBSurfaceWithFormatFrom(void* pixels,int width,int height,int depth,int pitch,Uint32 format){
    if(depth!=32||format!=SDL_PIXELFORMAT_RGBA32||width<0||height<0||pitch<width*4){last_error="sdl_shim: only RGBA32 surfaces";return nullptr;}
    auto* s=new(std::nothrow) SDL_Surface{width,height,pitch,pixels};
    if(!s)last_error="sdl_shim: out of memory";
    return s;
}
void SDL_FreeSurface(SDL_Surface* surface){delete surface;}
int SDL_SoftStretch(SDL_Surface* src,const SDL_Rect* srcrect,SDL_Surface* dst,const SDL_Rect* dstrect){
    ++stretch_calls;
    if(!src||!dst||srcrect||dstrect){last_error="sdl_shim: full-surface stretch only";return -1;}
    const int src_w=src->w,src_h=src->h,dst_w=dst->w,dst_h=dst->h;
    if(dst_w<=0||dst_h<=0)return 0;
    if(src_w>0xffff||src_h>0xffff||dst_w>0xffff||dst_h>0xffff){last_error="Size too large for scaling";return -1;}
    const Uint32 incy=(Uint32(src_h)<<16)/Uint32(dst_h),incx=(Uint32(src_w)<<16)/Uint32(dst_w);
    Uint32 posy=incy/2;
    for(int i=0;i<dst_h;++i){
        const int srcy=int(posy>>16);
        const auto* row=reinterpret_cast<const Uint32*>(static_cast<const Uint8*>(src->pixels)+size_t(srcy)*src->pitch);
        auto* out=reinterpret_cast<Uint32*>(static_cast<Uint8*>(dst->pixels)+size_t(i)*dst->pitch);
        posy+=incy;
        Uint32 posx=incx/2;
        for(int n=0;n<dst_w;++n){out[n]=row[posx>>16];posx+=incx;}
    }
    return 0;
}
const char* SDL_GetError(void){return last_error;}
unsigned long long pvz_sdl_shim_stretch_calls(void){return stretch_calls.load();}
}
