// Minimal stand-in for <SDL.h> used ONLY by the headless AI build when no real SDL2 is
// available (build/ai-nn/CMakeLists.txt, AI_NN_SDL=shim). The typed kernel needs SDL in exactly
// one place: NativeArtStore::pixels() scales RGBA32 sprites with SDL_SoftStretch
// (sim/typed/native_art.cpp). This header declares just the four entry points used there;
// sdl_shim.cpp implements the nearest-neighbour stretch of SDL 2.28-2.30 (SDL_stretch.c).
// The shipped game never uses this file.
#pragma once
#include <cstdint>
extern "C" {
typedef uint8_t Uint8;
typedef uint32_t Uint32;
struct SDL_Rect {int x,y,w,h;};
struct SDL_Surface {int w,h,pitch;void* pixels;};
enum : Uint32 {SDL_PIXELFORMAT_RGBA32=0x16762004u};   // SDL_PIXELFORMAT_ABGR8888 on little-endian
SDL_Surface* SDL_CreateRGBSurfaceWithFormatFrom(void* pixels,int width,int height,int depth,int pitch,Uint32 format);
void SDL_FreeSurface(SDL_Surface* surface);
int SDL_SoftStretch(SDL_Surface* src,const SDL_Rect* srcrect,SDL_Surface* dst,const SDL_Rect* dstrect);
const char* SDL_GetError(void);
// Number of SDL_SoftStretch calls so far in this process (evidence for docs/ai-nn).
unsigned long long pvz_sdl_shim_stretch_calls(void);
}
