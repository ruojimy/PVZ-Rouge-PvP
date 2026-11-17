#pragma once
#include "sim/pvp/pvprt.h"
#include "core/function_profile.h"
namespace pvz::pressure741 {
// One policy for desktop and Android. Only platform power hints remain separate.
void observe(const V& app,double elapsed,double work);
double now();
// Legacy update + publication estimator, retained for the default A/B control.
void record_advance(const V& app,double cost);
// Optional scheduler experiment. Budget checks happen only after a whole room
// step. Always return actual completed steps, including early battle termination.
V advance_steps(const V& room,const V& requested);
V presentation_snapshot(const V& app,const V& include_map);
class AdvanceScope {
    V app_,battle_;
    double started_,updated_=0.,sim_before_=0.,time_before_=0.;
public:
    explicit AdvanceScope(const V& app);
    void updated();
    void refreshed();
};
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
