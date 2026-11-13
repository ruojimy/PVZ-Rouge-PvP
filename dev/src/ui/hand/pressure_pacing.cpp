#include "ui/hand/pressure_pacing.h"
#include "ui/gen/pm_adaptive_pacing.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <chrono>
namespace pvz::pressure741 {
namespace {
std::shared_ptr<pm_adaptive_pacing::C_AdaptivePacing> policy(const V& app){
    const V room=pvz::getattr(app,SY("room"),V::none());if(room.is_none())return {};
    const V pacing=pvz::getattr(room,SY("pacing"),V::none());
    return std::dynamic_pointer_cast<pm_adaptive_pacing::C_AdaptivePacing>(pacing.is_inst()?pacing.box->inst:nullptr);
}
}
double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
FrameServiceScope::FrameServiceScope(const V& app):state_(pvz::getattr(app,SY("state"))){
    previous_=py::m_get(state_,SV("frame_service_active"),V(false));setitem(state_,SV("frame_service_active"),V(true));
}
FrameServiceScope::~FrameServiceScope(){setitem(state_,SV("frame_service_active"),previous_);}
bool command_refresh_needed(const V& app,const V& request){
    static const bool enabled=[]{const char* p=std::getenv("PVP742_INPUT_REFRESH");return !p||*p!='0';}();
    if(!enabled||!request.is_dict()||py::m_get(request,SV("type"))!=SV("input"))return true;
    const V input=py::m_get(request,SV("input"));
    if(!input.is_dict()||py::m_get(input,SV("type"))!=SV("move"))return true;
    const V state=pvz::getattr(app,SY("state"));
    if(!py::m_get(state,SV("frame_service_active"),V(false)).truthy())return true;
    setitem(state,SV("deferred_move_refreshes"),V(py::m_get(state,SV("deferred_move_refreshes"),V(0.)).num()+1.));
    return false;
}
double service_delta(const V& app,double milliseconds){
    const double elapsed=milliseconds/1000.;
    if(!std::isfinite(elapsed)||elapsed<0.)return 0.;
    static const bool enabled=[]{const char* p=std::getenv("PVP742_WALL_CLOCK");return !p||*p!='0';}();
    const V state=pvz::getattr(app,SY("state")),view=pvz::getattr(app,SY("view"));
    const V mode=pvz::getattr(app,SY("mode"));
    const bool active=enabled&&(mode==SV("local")||mode==SV("host"))&&view.is_dict()&&
        py::m_get(view,SV("phase"))==SV("battle")&&!py::m_get(view,SV("paused")).truthy()&&!py::m_get(view,SV("audit_error")).truthy();
    if(!active){setitem(state,SV("wall_clock_debt"),V(0.));return std::min(.25,elapsed);}
    const double pending=std::max(0.,py::m_get(state,SV("wall_clock_debt"),V(0.)).num())+elapsed;
    const double credited=std::min(2.,pending);
    setitem(state,SV("wall_clock_debt"),V(pending-credited));
    return credited;
}
void reset_wall_clock(const V& app){
    const V state=pvz::getattr(app,SY("state"));
    setitem(state,SV("wall_clock_debt"),V(0.));
    setitem(state,SV("wall_clock_reset_pending"),V(true));
}
double authority_delta(const V& app,double seconds){
    const V state=pvz::getattr(app,SY("state"));
    // Lifecycle events are collected after the outer clock tick. Discard the
    // suspension interval at this boundary, before Room can credit it.
    if(py::m_get(state,SV("wall_clock_reset_pending"),V(false)).truthy()){
        setitem(state,SV("wall_clock_reset_pending"),V(false));
        setitem(state,SV("wall_clock_debt"),V(0.));return 0.;
    }
    if(!std::isfinite(seconds)||seconds<0.)return 0.;
    static const bool enabled=[]{const char* p=std::getenv("PVP742_WALL_CLOCK");return !p||*p!='0';}();
    const V mode=pvz::getattr(app,SY("mode"));
    return std::min(enabled&&(mode==SV("host")||mode==SV("local"))?2.:1.,seconds);
}
void record_advance(const V& app,double cost){
    auto p=policy(app);if(!p||!std::isfinite(cost)||cost<0.)return;
    p->advance_pending=false;
    const V view=pvz::getattr(app,SY("view"));if(!view.is_dict())return;
    const V battle=py::m_get(view,SV("battle"),V::none());if(!battle.is_dict())return;
    const V time=py::m_get(battle,SV("time"),V::none());if(time.is_none())return;
    const double current=time.num();if(!std::isfinite(current))return;
    p->advance_delta=p->game_time_known?std::max(0.,current-p->last_game_time):0.;
    p->last_game_time=current;p->game_time_known=true;p->advance_cost=cost;p->advance_pending=true;
}
void observe(const V& app,double elapsed,double work){
    const V state=pvz::getattr(app,SY("state"));
    const V view=pvz::getattr(app,SY("view"));
    if(!view.is_dict())return;
    const bool battle=py::m_get(view,SV("phase"))==SV("battle")&&!py::m_get(view,SV("paused")).truthy()&&!py::m_get(view,SV("audit_error")).truthy();
    const V room=pvz::getattr(app,SY("room"),V::none());
    if(room.is_none()||pvz::getattr(app,SY("mode"))==SV("guest"))return;
    auto p=policy(app);
    if(!p)return;
    p->frame_gated=true;
    static const bool enabled=[]{const char* v=std::getenv("PVP741_PRESSURE");return !v||*v!='0';}();
    if(!enabled){p->a_scale=V(1.);setitem(state,SV("pressure_interpolation"),V(false));return;}
    if(!battle){p->frame_age=p->frame_work=p->pressure_seconds=p->recovery_seconds=0.;p->advance_rate=p->game_rate=p->base_work=0.;p->advance_pending=p->game_time_known=false;p->control_target=1.;p->a_scale=V(1.);setitem(state,SV("pressure_interpolation"),V(false));return;}
    if(!std::isfinite(elapsed)||!std::isfinite(work)||elapsed<=0.||elapsed>2.||work<0.){p->advance_pending=false;return;}
    work=std::min(work,2.);
    // One long frame cannot satisfy the sustained-load gate by itself.
    const double control_dt=std::min(elapsed,.1);
    p->frame_age+=std::min(elapsed,.25);
    const double alpha=1.-std::exp(-control_dt/.8);
    p->frame_work+=(work-p->frame_work)*alpha;
    if(p->advance_pending){
        const double advance=std::clamp(p->advance_cost,0.,work);
        p->advance_rate+=(advance/elapsed-p->advance_rate)*alpha;
        p->game_rate+=(p->advance_delta/elapsed-p->game_rate)*alpha;
        p->base_work+=(work-advance-p->base_work)*alpha;
        p->advance_pending=false;
    }
    const V snapshot=py::m_get(view,SV("battle"),V::dict());
    if(!snapshot.is_dict()){p->advance_pending=false;return;}
    const V raw_frame=py::m_get(snapshot,SV("native_frame"),V::none());
    const V frame=raw_frame.is_dict()?raw_frame:V::dict();
    const bool crowded=py::len(py::m_get(snapshot,SV("units"),V::list())).num()>=60.||py::len(py::m_get(frame,SV("commands"),V::list())).num()>=250.;
    const bool overloaded=crowded&&elapsed>1./36.&&p->frame_work>.024;
    p->pressure_seconds=overloaded?p->pressure_seconds+control_dt:std::max(0.,p->pressure_seconds-control_dt*2.);
    double scale=p->a_scale.num();
    // Absolute throughput estimate: fixed drawing cost * frames/sec plus
    // measured update/publication cost * game-seconds/sec must fit the CPU.
    // Reducing an already reduced scale is never itself evidence for more slowing.
    const double native_limit=.80/std::max(.80,p->a_ratio.num());
    double target=std::clamp(native_limit,.15,1.);
    if(p->game_rate>.005&&p->advance_rate>0.){
        const double per_game=p->advance_rate/p->game_rate;
        const double achievable_frames=std::min(30.,.65/std::max(.0001,p->base_work));
        target=std::clamp(std::min(native_limit,(.90-p->base_work*achievable_frames)/per_game),.15,1.);
    }
    // Publication and drawing include work that is paid even on a frame with
    // no simulation tick. Do not turn that fixed cost into near-paused combat.
    // Deeper slowing needs measured native simulation overload, not UI pressure.
    target=std::clamp(std::max(target,std::min(.65,native_limit)),.15,1.);
    if(!crowded)target=1.;
    p->control_target=target;
    const bool recovering=!crowded||p->frame_work<.019||target>scale+.08;
    p->recovery_seconds=recovering?p->recovery_seconds+control_dt:0.;
    if(p->frame_age<5.){scale=1.;p->pressure_seconds=0.;}
    else if(p->pressure_seconds>=.8){
        if(target<scale)scale=std::max(target,scale-control_dt*(p->a_ratio.num()>1.5?.5:.18));
    }
    if(p->frame_age>=5.&&p->recovery_seconds>=2.)scale=std::min(std::max(scale,target),scale+control_dt*.12);
    p->a_scale=V(scale);
    const bool smoothing=p->frame_age>=5.&&scale<.999;
    setitem(state,SV("pressure_interpolation"),V(smoothing));
    setitem(state,SV("pressure_scale"),V(scale));
    setitem(state,SV("pressure_target"),V(target));
    setitem(state,SV("pressure_advance_cost"),V(p->game_rate>.005?p->advance_rate/p->game_rate:0.));
    setitem(state,SV("pressure_draw_ms"),V(p->base_work*1000.));
}
}
