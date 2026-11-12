// Serial equal-pixel microbench; it is not a phone FPS or 4-AI benchmark.
#include "pg/pg.h"
#include "pg/render_stats.h"
#include "core/gil.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <cstdio>
#include <cstdlib>
using namespace pvz;
int main(int argc,char** argv) {
    SDL_SetMainReady();gil::init();pg::install_pygame();
    int frames=argc>1?std::atoi(argv[1]):120;if(frames<1 || frames>10000)return 2;
    V screen=pg::new_surface(2174,981,false),sprite=pg::new_surface(96,96,true),world=pg::new_surface(1200,700,false);
    auto s=pg::surf(sprite);
    for(int y=0;y<s->h();++y){auto line=reinterpret_cast<uint32_t*>(static_cast<char*>(s->s->pixels)+y*s->s->pitch);for(int x=0;x<s->w();++x)line[x]=uint32_t((x*43+y*17)%256)<<24|uint32_t(x*2)<<16|uint32_t(y*2)<<8|uint32_t(x+y);}
    auto transform=pg::transform_module();V size=V::nums({2174,981});
    for(int i=0;i<3;++i){pg::blit(pg::surf(screen),s,100,100,nullptr,0);callm(transform,SY("scale"),Args{world,size,screen});}
    pg::reset_render_stats72();auto start=std::chrono::steady_clock::now();
    for(int frame=0;frame<frames;++frame)for(int i=0;i<120;++i)pg::blit(pg::surf(screen),s,(i*151)%2050,(i*83)%860,nullptr,0);
    auto mixed=std::chrono::steady_clock::now();
    for(int frame=0;frame<frames;++frame)callm(transform,SY("scale"),Args{world,size,screen});
    auto end=std::chrono::steady_clock::now();auto counters=pg::render_stats72();
    nlohmann::json report={{"frames",frames},{"canvas",{2174,981}},{"sprite_count",120},{"sprite_size",{96,96}},
        {"reference",std::getenv("PVZ72_REFERENCE")!=nullptr},{"blit_seconds",std::chrono::duration<double>(mixed-start).count()},
        {"scale_seconds",std::chrono::duration<double>(end-mixed).count()},
        {"surface_allocations",counters.surface_allocations},{"allocated_bytes",counters.allocated_bytes},
        {"direct_scales",counters.direct_scales},{"avoided_copy_bytes",counters.avoided_copy_bytes}};
    printf("BENCH_RENDER %s\n",report.dump().c_str());fflush(nullptr);std::_Exit(0);
}
