// Test-only probes call the production codec, worker, queues and OS threads.
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include "sim/pvp/hand/native_marshal.h"
#include <nlohmann/json.hpp>
#include <thread>
#include <cmath>
namespace pvz::cpptests {
namespace {
using json=nlohmann::json;
std::string hex(const std::string& bytes) {
    static const char* digits="0123456789abcdef"; std::string out;
    for(unsigned char c:bytes){out+=digits[c>>4];out+=digits[c&15];}return out;
}
std::string unhex(const std::string& text) {
    if(text.size()%2)throw PyError("ValueError","odd probe hex");std::string out;
    auto digit=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw PyError("ValueError","bad probe hex");};
    for(size_t i=0;i<text.size();i+=2)out+=char(digit(text[i])*16+digit(text[i+1]));return out;
}
json shape(const V& v) {
    if(v.is_none())return json::array({"none"});
    if(v.t==V::BOOL)return json::array({"bool",v.truthy()});
    if(v.is_num()) {
        if(!std::isfinite(v.num()))return json::array({"number",std::isnan(v.num())?"nan":v.num()<0?"-inf":"inf"});
        if(v.num()==0&&std::signbit(v.num()))return json::array({"number","-0"});
        return json::array({"number",v.num()});
    }
    if(v.t==V::STR)return json::array({v.byt?"bytes":"str",v.byt?hex(v.str()):v.str()});
    json items=json::array();
    if(v.t==V::LIST||v.t==V::TUPLE){for(const V& item:v.items())items.push_back(shape(item));return json::array({v.t==V::LIST?"list":"tuple",items});}
    if(v.t==V::DICT){for(const auto& item:v.kv())items.push_back(json::array({shape(item.first),shape(item.second)}));return json::array({"dict",items});}
    throw PyError("TypeError","unsupported probe shape");
}
V invoke(const V& object,const char* name,const Args& a={}) {return callm(object,Sym(name),a);}
struct WorkerGuard {
    V worker,gate;
    ~WorkerGuard(){try{if(gate.has())invoke(gate,"set");if(worker.has())invoke(worker,"close");}catch(...) {}}
};
}
json snapshot_contract(const json& spec) {
    json report;
    if(spec.contains("marshal")) {
        report["marshal"]=json::array();
        for(const auto& row:spec["marshal"]) {
            json result={{"name",row.at("name")}};
            try {
                V decoded=py::native_marshal_loads(Args{V::bytes(unhex(row.at("hex")))});
                result["shape"]=shape(decoded);
                result["encoded"]=hex(py::native_marshal_dumps(Args{decoded}).str());
                if(row.value("alias",false))result["alias"]=decoded.idx(0).box.get()==decoded.idx(1).box.get();
                if(row.value("wire",false)) {
                    V packed=pm_native_snapshot_worker::f_pack_snapshot_kernel(Args{py::native_marshal_dumps(Args{decoded})});
                    V profiled=pm_native_snapshot_worker::f_pack_snapshot_profile(Args{py::native_marshal_dumps(Args{decoded})});
                    result["wire"]=packed.idx(0).str();result["raw_length"]=packed.idx(1).num();
                    result["profile_exact"]=py_eq(packed,py::slice(profiled,V::none(),V(2)));
                    result["timings"]=json::parse(py::stdlib_call(V("json.dumps"),Args{profiled.idx(2)}).str());
                }
            }catch(const PyError& e){result["error"]=e.kind;}
            report["marshal"].push_back(result);
        }
        report["encode_rejections"]=json::array();
        V cycle=V::list();cycle.append(cycle);
        V ordered=py::stdlib_call(V("collections.OrderedDict"),Args{});
        V badkey=V::dict();badkey.at(V::tuple({V(1)}))=V(2);
        for(V value:{cycle,ordered,badkey,V::func([](const Args&){return V::none();})}) {
            try{py::native_marshal_dumps(Args{value});report["encode_rejections"].push_back("ACCEPTED");}
            catch(const PyError& e){report["encode_rejections"].push_back(e.kind);}
        }
        cycle.items().clear();
    }
    if(spec.value("worker",false)) {
        auto event=[](){return py::stdlib_call(V("threading.Event"),Args{});};
        auto new_worker=[](){return pm_native_snapshot_worker::new_SnapshotPackWorker(Args{});};
        auto telemetry=[](const V& w){return json::parse(py::stdlib_call(V("json.dumps"),Args{pvz::getattr(w,Sym("telemetry"))}).str());};
        // No test real-thread flag is required: verify actual C++ thread IDs.
        const auto main_id=std::this_thread::get_id();std::thread::id pack_id;
        V started=event(),gate=event();WorkerGuard guard{new_worker(),gate};
        V w=guard.worker, original=pvz::getattr(w,Sym("_pack")), observed;
        pvz::setattr(w,Sym("_pack"),V::func([&](const Args& a){
            pack_id=std::this_thread::get_id();invoke(started,"set");invoke(gate,"wait",Args{V(5)});
            observed=py::native_marshal_loads(Args{a.pos.at(0)});return original.call(a);
        }));
        V state=py_dict({{V("payload"),V(std::string(1024,'a'))},{V("nested"),V::list({V(1),V(2)})}});
        int accepted=invoke(w,"submit",Args{V("guest"),V(0),state}).truthy()?1:0;
        bool started_ok=invoke(started,"wait",Args{V(2)}).truthy();
        V first_future=pvz::getattr(w,Sym("pending")).get(V("guest")).idx(1);
        pvz::setitem(state.get(V("nested")),V(0),V(99));
        invoke(w,"forget",Args{V("guest")});
        report["cancel_done_before_release"]=invoke(first_future,"done").truthy();
        for(int i=0;i<40;++i){if(invoke(w,"submit",Args{V("guest"),V(i+1),state}).truthy())++accepted;invoke(w,"forget",Args{V("guest")});}
        report["started"]=started_ok;report["real_os_thread"]=started_ok&&pack_id!=main_id;
        report["accepted"]=accepted;report["blocked"]=telemetry(w);
        invoke(gate,"set");invoke(w,"close");invoke(w,"close");
        report["released"]=telemetry(w);report["frozen_state"]=shape(observed);
        report["submit_after_close"]=invoke(w,"submit",Args{V("late"),V(0),state}).truthy();
        report["completion_after_cancel"]=invoke(w,"completed").len();
        // Charge the byte budget independently of the item count.
        started=event();gate=event();WorkerGuard bytes{new_worker(),gate};w=bytes.worker;
        original=pvz::getattr(w,Sym("_pack"));
        pvz::setattr(w,Sym("_pack"),V::func([&](const Args& a){invoke(started,"set");invoke(gate,"wait",Args{V(5)});return original.call(a);}));
        V data=py_dict({{V("payload"),V(std::string(4096,'b'))}});
        pvz::setattr(w,Sym("frozen_byte_limit"),V(10000));
        bool first=invoke(w,"submit",Args{V("a"),V(0),data}).truthy();invoke(started,"wait",Args{V(2)});invoke(w,"forget");
        bool second=invoke(w,"submit",Args{V("b"),V(0),data}).truthy();invoke(w,"forget");
        bool third=invoke(w,"submit",Args{V("c"),V(0),data}).truthy();
        report["byte_accepts"]=json::array({first,second,third});report["byte_blocked"]=telemetry(w);
        invoke(gate,"set");invoke(w,"close");report["byte_released"]=telemetry(w);
        // A failed pack must wake its future and release inputs; the next job runs.
        WorkerGuard errors{new_worker(),V()};w=errors.worker;
        pvz::setattr(w,Sym("_pack"),V::func([](const Args&)->V{throw PyError("ValueError","controlled snapshot pack error");}));
        invoke(w,"submit",Args{V("error"),V(0),state});
        V future=pvz::getattr(w,Sym("pending")).get(V("error")).idx(1);
        try{invoke(future,"result",Args{V(2)});report["pack_error"]="ACCEPTED";}
        catch(const PyError& e){report["pack_error"]=e.kind;}
        try{invoke(w,"completed");}catch(const PyError& e){report["completion_error"]=e.kind;}
        pvz::setattr(w,Sym("_pack"),V::func(pm_native_snapshot_worker::f_pack_snapshot_kernel));
        invoke(w,"submit",Args{V("next"),V(1),state});
        future=pvz::getattr(w,Sym("pending")).get(V("next")).idx(1);invoke(future,"result",Args{V(2)});
        report["after_error_completions"]=invoke(w,"completed").len();
        invoke(w,"close");report["error_released"]=telemetry(w);
    }
    return report;
}
}
