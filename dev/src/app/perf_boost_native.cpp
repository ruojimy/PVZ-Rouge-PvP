// PvP73: native port of modkit/android/perf_boost.py (PvP71) - the Android performance provider
// behind pvp.perf_hooks. Installed only on Android (see main.cpp); a PC build never installs one.
//
// Diagnostics (always, 2 Hz, sysfs/procfs reads only): the game thread's core and whether it is a
// big core, that core's current/max frequency, the thermal status, the authority's slow-motion scale.
// Requests (setting "性能申请", default on; PVP_PERF_BOOST=0/1 overrides):
//   1. an ADPF performance hint session on the game thread (API 33 NDK, resolved with dlsym so the
//      APK keeps its minimum SDK), fed with every frame's measured work against a 60 fps budget;
//   2. the game thread bound to the big cores (never the whole process);
//   3. 30 fps presentation while the local authority is slowed (scale < 0.9); time is never skipped.
// Every failure is recorded in `errors` and never affects play.
#include "sim/pvp/pvprt.h"
#include "core/fsutil.h"
#include "ui/gen/pm_perf_hooks.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <vector>
#ifdef __ANDROID__
#include <dlfcn.h>
#include <sched.h>
#include <unistd.h>
#include <sys/syscall.h>
#endif
namespace pvz {
namespace {
constexpr double SAMPLE_SECONDS=.5, SLOW_SCALE=.9;
constexpr int64_t FRAME_BUDGET_NS=16666667;
const char* THERMAL_NAMES[]={"无","轻微","中等","严重","危急","紧急","关机"};
double now_s(){using namespace std::chrono;return duration<double>(steady_clock::now().time_since_epoch()).count();}
std::string read_text(const std::string& path){std::ifstream in(path,std::ios::binary);std::string s;std::getline(in,s);return s;}
long read_long(const std::string& path){const auto s=read_text(path);try{return s.empty()?-1:std::stol(s);}catch(...){return -1;}}

struct NativePerfBoost final : PyObj {
    std::string userdata;bool enabled=true;std::string setting_source="default";
    std::map<int,long> topology;std::vector<int> big;
    int64_t frames=0;double work=0.,window_work=0.;int64_t window_frames=0;
    double next_sample=0.,started=now_s();bool slow=false,local=true;
    int core=-1;long core_khz=-1,core_max=-1;int thermal=-1;double scale=1.,cost_ratio=0.;
    std::deque<std::string> errors;std::vector<int> affinity;std::string affinity_error,session_error;
    std::vector<std::pair<double,bool>> toggles;
#ifdef __ANDROID__
    pid_t tid=pid_t(syscall(SYS_gettid));
    void* hint_session=nullptr;void* thermal_manager=nullptr;
    using GetManager=void*(*)();using CreateSession=void*(*)(void*,const int32_t*,size_t,int64_t);
    using Report=int(*)(void*,int64_t);using Close=void(*)(void*);
    using AcquireThermal=void*(*)();using ThermalStatus=int(*)(void*);
    Report report_fn=nullptr;Close close_fn=nullptr;ThermalStatus thermal_fn=nullptr;
    void* libandroid=dlopen("libandroid.so",RTLD_NOW);
#endif
    const char* type_name() const override {return "NativePerfBoost";}
    NativePerfBoost(std::string data):userdata(std::move(data)){
        for(int cpu=0;cpu<64;++cpu){
            const std::string base="/sys/devices/system/cpu/cpu"+std::to_string(cpu);
            if(!std::filesystem::exists(base))continue;
            topology[cpu]=read_long(base+"/cpufreq/cpuinfo_max_freq");
        }
        big=big_cores();
        std::string forced;
        if(env_u8("PVP_PERF_BOOST",forced)&&(forced=="0"||forced=="1")){enabled=forced=="1";setting_source="env";}
        else{const auto text=read_text(userdata+"/perf-boost.json");
            if(!text.empty()){enabled=text.find("false")==std::string::npos;setting_source="setting";}}
#ifdef __ANDROID__
        if(libandroid){
            if(auto acquire=reinterpret_cast<AcquireThermal>(dlsym(libandroid,"AThermal_acquireManager")))thermal_manager=acquire();
            thermal_fn=reinterpret_cast<ThermalStatus>(dlsym(libandroid,"AThermal_getCurrentThermalStatus"));
        }
#endif
        if(enabled)apply();
    }
    std::vector<int> big_cores()const{
        std::vector<long> tiers;for(const auto& [cpu,freq]:topology)if(freq>0&&std::find(tiers.begin(),tiers.end(),freq)==tiers.end())tiers.push_back(freq);
        std::sort(tiers.rbegin(),tiers.rend());if(tiers.size()<2)return {};
        std::vector<int> chosen;for(const auto& [cpu,freq]:topology)if(freq==tiers[0])chosen.push_back(cpu);
        if(chosen.size()<2){chosen.clear();for(const auto& [cpu,freq]:topology)if(freq>=tiers[1])chosen.push_back(cpu);}
        return chosen.size()<topology.size()?chosen:std::vector<int>{};
    }
    void failed(const std::string& where,const std::string& what){errors.push_back(where+": "+what);if(errors.size()>20)errors.pop_front();}
    void apply(){start_hint();bind(big,true);}
    void release(){
#ifdef __ANDROID__
        if(hint_session&&close_fn)close_fn(hint_session);hint_session=nullptr;
        if(!affinity.empty()){std::vector<int> all;for(const auto& [cpu,f]:topology)all.push_back(cpu);bind(all,false);affinity.clear();}
#endif
    }
    void start_hint(){
#ifdef __ANDROID__
        if(hint_session)return;
        if(!libandroid){session_error="no libandroid";return;}
        auto get=reinterpret_cast<GetManager>(dlsym(libandroid,"APerformanceHint_getManager"));
        auto create=reinterpret_cast<CreateSession>(dlsym(libandroid,"APerformanceHint_createSession"));
        report_fn=reinterpret_cast<Report>(dlsym(libandroid,"APerformanceHint_reportActualWorkDuration"));
        close_fn=reinterpret_cast<Close>(dlsym(libandroid,"APerformanceHint_closeSession"));
        if(!get||!create||!report_fn){session_error="ADPF unavailable (API < 33)";return;}
        void* manager=get();if(!manager){session_error="no performance hint manager";return;}
        const int32_t tids[1]={int32_t(tid)};
        hint_session=create(manager,tids,1,FRAME_BUDGET_NS);
        session_error=hint_session?"":"createSession returned null";
#else
        session_error="not Android";
#endif
    }
    void bind(const std::vector<int>& cores,bool record){
        if(cores.empty()){if(record)affinity_error="homogeneous or unknown cores";return;}
#ifdef __ANDROID__
        cpu_set_t set;CPU_ZERO(&set);for(int c:cores)CPU_SET(c,&set);
        if(sched_setaffinity(tid,sizeof(set),&set)!=0){affinity_error="sched_setaffinity errno "+std::to_string(errno);return;}
        if(record){affinity=cores;affinity_error.clear();}
#else
        (void)record;
#endif
    }
    void sample(const V& app,double now){
#ifdef __ANDROID__
        const auto stat=read_text("/proc/self/task/"+std::to_string(tid)+"/stat");
        const auto close=stat.rfind(')');
        if(close!=std::string::npos){
            std::vector<std::string> f;std::string tok;for(size_t i=close+2;i<=stat.size();++i){if(i==stat.size()||stat[i]==' '){if(!tok.empty())f.push_back(tok);tok.clear();}else tok+=stat[i];}
            if(f.size()>36)try{core=std::stoi(f[36]);}catch(...){}
        }
        if(core>=0){const std::string base="/sys/devices/system/cpu/cpu"+std::to_string(core)+"/cpufreq/";core_khz=read_long(base+"scaling_cur_freq");core_max=read_long(base+"cpuinfo_max_freq");}
        if(thermal_fn&&thermal_manager)thermal=thermal_fn(thermal_manager);
#endif
        (void)app;(void)now;
    }
    V frame(const Args& a){
        const V app=a.get(0,Sym("app"),nullptr);const double w=a.get(1,Sym("work_seconds"),nullptr).num();
        ++frames;work+=w;window_work+=w;++window_frames;
#ifdef __ANDROID__
        if(hint_session&&report_fn&&report_fn(hint_session,std::max<int64_t>(1,int64_t(w*1e9)))!=0){failed("hint_report","rejected");hint_session=nullptr;}
#endif
        // Local authority pacing (a guest's slow-motion belongs to its host).
        local=true;scale=1.;cost_ratio=0.;
        const V mode=pvz::getattr(app,Sym("mode"),V::none());
        if(mode.is_str()&&py_str(mode)=="guest")local=false;
        else{const V room=pvz::getattr(app,Sym("room"),V::none());
            if(!room.is_none()&&!pvz::getattr(room,Sym("battle"),V::none()).is_none()){
                const V pacing=pvz::getattr(room,Sym("pacing"),V::none());
                if(!pacing.is_none()){scale=pvz::getattr(pacing,Sym("scale"),V(1.)).num();cost_ratio=pvz::getattr(pacing,Sym("ratio"),V(0.)).num();}}}
        slow=local&&scale<SLOW_SCALE;
        const double t=now_s();if(t>=next_sample){next_sample=t+SAMPLE_SECONDS;sample(app,t);}
        return V::none();
    }
    V status_line()const{
        if(core<0)return V("");
        const bool is_big=std::find(big.begin(),big.end(),core)!=big.end();
        char text[160];std::snprintf(text,sizeof text,"核%d(%s) %.1f/%.1fGHz 温控%s%s",core,big.empty()?"同构":is_big?"大":"小",
            core_khz>0?core_khz/1e6:0.,core_max>0?core_max/1e6:0.,thermal>=0&&thermal<7?THERMAL_NAMES[thermal]:"?",enabled?"":" 申请关");
        return V(std::string(text));
    }
    V report()const{
        V d=V::dict();d.at(V("provider"))=V("native-perf-boost-73");d.at(V("enabled"))=V(enabled);d.at(V("setting_source"))=V(setting_source);
        V cores=V::list();for(int c:big)cores.append(V(double(c)));d.at(V("big_cores"))=cores;
        V aff=V::list();for(int c:affinity)aff.append(V(double(c)));d.at(V("affinity"))=aff;d.at(V("affinity_error"))=V(affinity_error);
        d.at(V("hint_session"))=V(session_error.empty());d.at(V("hint_error"))=V(session_error);
        d.at(V("frames"))=V(double(frames));d.at(V("mean_work_ms"))=V(frames?work*1000./double(frames):0.);
        d.at(V("core"))=V(double(core));d.at(V("core_khz"))=V(double(core_khz));d.at(V("core_max_khz"))=V(double(core_max));
        d.at(V("thermal"))=V(double(thermal));d.at(V("slow"))=V(slow);d.at(V("scale"))=V(scale);d.at(V("cost_ratio"))=V(cost_ratio);
        V errs=V::list();for(const auto& e:errors)errs.append(V(e));d.at(V("errors"))=errs;
        V tg=V::list();for(const auto& [t,on]:toggles){V row=V::dict();row.at(V("at"))=V(t);row.at(V("enabled"))=V(on);tg.append(row);}d.at(V("toggles"))=tg;
        return d;
    }
    void set_boost(bool flag){
        if(flag==enabled)return;enabled=flag;setting_source="setting";toggles.emplace_back(std::round((now_s()-started)*10.)/10.,flag);
        std::ofstream out(u8p(userdata+"/perf-boost.json"),std::ios::binary);out<<"{\"enabled\": "<<(flag?"true":"false")<<"}";
        if(flag)apply();else release();
    }
    V method(Sym name) override {
        auto self=std::static_pointer_cast<NativePerfBoost>(shared_from_this());
        if(name==Sym("frame"))return V::func([self](const Args& a){return self->frame(a);});
        if(name==Sym("frame_rate"))return V::func([self](const Args& a){static const V sixty(60.);const V d=a.get(0,Sym("default"),&sixty);return self->enabled&&self->slow?V(30.):d;});
        if(name==Sym("status_line"))return V::func([self](const Args&){return self->status_line();});
        if(name==Sym("report"))return V::func([self](const Args&){return self->report();});
        if(name==Sym("boost_enabled"))return V::func([self](const Args&){return V(self->enabled);});
        if(name==Sym("set_boost"))return V::func([self](const Args& a){self->set_boost(a.get(0,Sym("flag"),nullptr).truthy());return V::none();});
        if(name==Sym("failed"))return V::func([self](const Args& a){self->failed("hook",a.size()?py_str(py::str(a.pos[0])):"?");return V::none();});
        return V();
    }
};
}
// Installs the provider into pvp.perf_hooks (Android only; returns false elsewhere).
bool install_native_perf_boost(const std::string& userdata){
#ifdef __ANDROID__
    try{pm_perf_hooks::f_install(Args{V::inst(std::make_shared<NativePerfBoost>(userdata))});return true;}
    catch(const std::exception&){return false;}
#else
    (void)userdata;return false;
#endif
}
} // namespace pvz
