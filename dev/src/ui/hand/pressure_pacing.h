#pragma once
#include "sim/pvp/pvprt.h"
#include "core/function_profile.h"
namespace pvz::pressure741 {
// One policy for desktop and Android. Only platform power hints remain separate.
void observe(const V& app,double elapsed,double work);
double now();
// Measure update + snapshot publication separately from drawing, at the UI boundary.
void record_advance(const V& app,double cost);
// UI remains bounded outside battle; active authority credits elapsed wall time
// into the room's fixed-step accumulator instead of discarding every >250ms frame.
double service_delta(const V& app,double milliseconds);
double authority_delta(const V& app,double seconds);
void reset_wall_clock(const V& app);
class FrameServiceScope {
    V state_,previous_;
public:
    explicit FrameServiceScope(const V& app);
    ~FrameServiceScope();
};
bool command_refresh_needed(const V& app,const V& command_type);
}
