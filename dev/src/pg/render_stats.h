#pragma once
#include <cstdint>
namespace pvz::pg {
struct RenderStats72 {uint64_t surface_allocations=0,allocated_bytes=0,blits=0,blit_pixels=0,direct_scales=0,avoided_copy_bytes=0;};
RenderStats72 render_stats72();
void reset_render_stats72();
int set_render_reference72(int value);
}
