// Original native_multiworker.py classes staged by stage_snapshot47.py, then
// adapted for the standalone thread backend, idempotent shutdown and error release.
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include "sim/pvp/dynamic_bindings.h"
#include "sim/pvp/shim/pm_native_multiworker.h"
namespace pvz { namespace py { inline void init_deps_native_snapshot_worker() { pm_native_multiworker::init(); } } }
namespace pvz { namespace pm_native_snapshot_worker {
V _clock;
V KERNELS;
// f_pack_snapshot_kernel: hand-written (src/sim/pvp/hand)
// f_pack_snapshot_profile: hand-written (src/sim/pvp/hand)
V f_process_backend_supported(const Args& A) {
    return V(false);
    return V::none();
}

V f_executable_worker_supported(const Args& A) {
    return V(false);
    return V::none();
}

bool C_WorkerFailure::isa(const char* c) const { std::string s(c); return s == "WorkerFailure" || s == "object"; }
V* C_WorkerFailure::slot(Sym name) {
    return nullptr;
}
V C_WorkerFailure::method(Sym name) {
    if (name == SY("__native_type__")) { V metadata=V::func([](const Args&) { return pm_native_snapshot_worker::cls_WorkerFailure(); }); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }
    if (name == SY("__native_slot_names__")) return V::func([](const Args&) { return V::tuple({}); });
    return V();
}
bool C_WorkerFailure::call_method(Sym name, const Args& A, V& out) {
    return false;
}
V new_WorkerFailure(const Args& A) { return py::make_exc(SV("WorkerFailure"), A, "RuntimeError"); }
V cls_WorkerFailure() { static V c = [] { V c = py::class_value(SV("WorkerFailure"), [](const Args& A) { return new_WorkerFailure(A); }); c.box->fattrs.emplace_back(Sym("__module__"), SV("pvp.native_snapshot_worker")); return c; }(); return c; }
bool C__Future::isa(const char* c) const { std::string s(c); return s == "_Future" || s == "object"; }
V* C__Future::slot(Sym name) {
    static const SymIndex idx_({SY("_event"), SY("_result"), SY("_error"), SY("_cancelled")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return nullptr;
    switch (k_) {
        case 0: return &a__event;
        case 1: return &a__result;
        case 2: return &a__error;
        case 3: return &a__cancelled;
    }
    return nullptr;
}
V C__Future::method(Sym name) {
    if (name == SY("__native_type__")) { V metadata=V::func([](const Args&) { return pm_native_snapshot_worker::cls__Future(); }); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }
    if (name == SY("__native_slot_names__")) return V::func([](const Args&) { return V::tuple({SV("_event"), SV("_result"), SV("_error"), SV("_cancelled")}); });
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls__Future(), name, self()); replacement.has()) return replacement;
    static const SymIndex idx_({SY("__init__"), SY("done"), SY("result"), SY("cancel")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return V();
    auto sp = std::static_pointer_cast<C__Future>(shared_from_this());
    switch (k_) {
        case 0: { V method=V::func([sp](const Args& A) { return sp->m___init__(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 1: { V method=V::func([sp](const Args& A) { return sp->m_done(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 2: { V method=V::func([sp](const Args& A) { return sp->m_result(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 3: { V method=V::func([sp](const Args& A) { return sp->m_cancel(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
    }
    return V();
}
bool C__Future::call_method(Sym name, const Args& A, V& out) {
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls__Future(), name, self()); replacement.has()) { out = replacement.call(A); return true; }
    static const SymIndex idx_({SY("__init__"), SY("done"), SY("result"), SY("cancel")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return false;
    switch (k_) {
        case 0: out = m___init__(A); return true;
        case 1: out = m_done(A); return true;
        case 2: out = m_result(A); return true;
        case 3: out = m_cancel(A); return true;
    }
    return false;
}
V C__Future::m___init__(const Args& A) {
    a__event = py::stdlib_call(SV("threading.Event"), Args{});
    a__result = V::none();
    a__error = V::none();
    a__cancelled = V(false);
    return V::none();
}

V C__Future::m_done(const Args& A) {
    return callm(a__event, SY("is_set"), Args{});
    return V::none();
}

V C__Future::m_result(const Args& A) {
    V L_timeout = (A.size() > 0 || A.has_kw(SY("timeout"))) ? A.get(0, SY("timeout"), nullptr) : V(V::none());
    if (!(callm(a__event, SY("wait"), Args{L_timeout})).truthy()) {
        py::raise(py::make_exc(SV("TimeoutError"), Args{SV("job timed out")}, ""));
    }
    if (!py_is(a__error, V::none())) {
        py::raise(a__error);
    }
    return a__result;
    return V::none();
}

V C__Future::m_cancel(const Args& A) {
    a__cancelled = V(true);
    return V::none();
}

void initcv__Future(C__Future* p) {

}
V new__Future(const Args& A) {
    init();
    auto p = std::make_shared<C__Future>();
    V self = V::inst(p);
    initcv__Future(p.get());
    callm(self, SY("__init__"), A);
    return self;
}
V cls__Future() { static V c = [] { V c = py::class_value(SV("_Future"), [](const Args& A) { return new__Future(A); }); c.box->fattrs.emplace_back(Sym("__module__"), SV("pvp.native_snapshot_worker")); c.box->fattrs.emplace_back(Sym("__new__"), V::func([](const Args& A) { if (A.pos.size() != 1 || !py_is(A.pos[0], cls__Future())) throw PyError("TypeError", "native __new__ requires its exact class"); auto p = std::make_shared<C__Future>(); initcv__Future(p.get()); return V::inst(p); })); c.box->fattrs.emplace_back(Sym("__init__"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Future>([](pm_native_snapshot_worker::C__Future* self, const Args& args) { return self->pm_native_snapshot_worker::C__Future::m___init__(args); }, A); })); c.box->fattrs.emplace_back(Sym("done"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Future>([](pm_native_snapshot_worker::C__Future* self, const Args& args) { return self->pm_native_snapshot_worker::C__Future::m_done(args); }, A); })); c.box->fattrs.emplace_back(Sym("result"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Future>([](pm_native_snapshot_worker::C__Future* self, const Args& args) { return self->pm_native_snapshot_worker::C__Future::m_result(args); }, A); })); c.box->fattrs.emplace_back(Sym("cancel"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Future>([](pm_native_snapshot_worker::C__Future* self, const Args& args) { return self->pm_native_snapshot_worker::C__Future::m_cancel(args); }, A); })); for (auto& item : c.box->fattrs) if (item.second.t == V::FUNC) item.second.box->fattrs.emplace_back(Sym("__native_declared_method__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_class_dispatch__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_static_methods__"), V::set({SV("__new__")})); return c; }(); return c; }
bool C__Executor::isa(const char* c) const { std::string s(c); return s == "_Executor" || s == "object"; }
V* C__Executor::slot(Sym name) {
    static const SymIndex idx_({SY("_queue"), SY("_threads")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return nullptr;
    switch (k_) {
        case 0: return &a__queue;
        case 1: return &a__threads;
    }
    return nullptr;
}
V C__Executor::method(Sym name) {
    if (name == SY("__native_type__")) { V metadata=V::func([](const Args&) { return pm_native_snapshot_worker::cls__Executor(); }); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }
    if (name == SY("__native_slot_names__")) return V::func([](const Args&) { return V::tuple({SV("_queue"), SV("_threads")}); });
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls__Executor(), name, self()); replacement.has()) return replacement;
    static const SymIndex idx_({SY("__init__"), SY("_loop"), SY("submit"), SY("shutdown")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return V();
    auto sp = std::static_pointer_cast<C__Executor>(shared_from_this());
    switch (k_) {
        case 0: { V method=V::func([sp](const Args& A) { return sp->m___init__(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 1: { V method=V::func([sp](const Args& A) { return sp->m__loop(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 2: { V method=V::func([sp](const Args& A) { return sp->m_submit(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 3: { V method=V::func([sp](const Args& A) { return sp->m_shutdown(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
    }
    return V();
}
bool C__Executor::call_method(Sym name, const Args& A, V& out) {
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls__Executor(), name, self()); replacement.has()) { out = replacement.call(A); return true; }
    static const SymIndex idx_({SY("__init__"), SY("_loop"), SY("submit"), SY("shutdown")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return false;
    switch (k_) {
        case 0: out = m___init__(A); return true;
        case 1: out = m__loop(A); return true;
        case 2: out = m_submit(A); return true;
        case 3: out = m_shutdown(A); return true;
    }
    return false;
}
V C__Executor::m___init__(const Args& A) {
    V L_workers = A.get(0, SY("workers"), nullptr, "__init__");
    V L_name = A.get(1, SY("name"), nullptr, "__init__");
    V L_max_pending = (A.size() > 2 || A.has_kw(SY("max_pending"))) ? A.get(2, SY("max_pending"), nullptr) : V(V(0.0));
    V L_queue;
    V L_thread;
    L_queue = py::stdlib_module(SV("queue"));
    a__queue = callm(L_queue, SY("Queue"), Args({}, {{SY("maxsize"), L_max_pending}}));
    a__threads = [&]() -> V { V out_ = V::list(); V L_index; { V it1_ = py::iter_list(py::range((int64_t)(py::max_it(V::list({V(1.0), py::int_(L_workers)}), py::Key(), V())).num())); for (size_t i1_ = 0; i1_ < it1_.len(); ++i1_) { L_index = it1_.idx(int64_t(i1_)); out_.append(py::stdlib_call(SV("threading.Thread"), Args({}, {{SY("target"), method(SY("_loop"))}, {SY("name"), py::percent(SV("%s-%d"), V::tuple({L_name, L_index}))}, {SY("daemon"), V(true)}}))); }}return out_; }();
    { V it2_ = py::iter_list(a__threads);
    for (size_t i2_ = 0; i2_ < it2_.len(); ++i2_) {
        L_thread = it2_.idx(int64_t(i2_)); 
        (void)(callm(L_thread, SY("start"), Args{}));
    }}
    return V::none();
}

V C__Executor::m__loop(const Args& A) {
    V L_args;
    V L_exc;
    V L_function;
    V L_future;
    V L_item;
    while (true) {
        L_item = callm(a__queue, SY("get"), Args{});
        if (py_is(L_item, V::none())) {
            return V::none();
        }
        { V ut1_ = py::as_seq(L_item); L_future = ut1_.idx(0); L_function = ut1_.idx(1); L_args = ut1_.idx(2); } 
        if ((pvz::getattr(L_future, SY("_cancelled"))).truthy()) {
            pvz::setattr(L_future, SY("_error"), py::make_exc(SV("RuntimeError"), Args{SV("job cancelled")}, ""));
        } else {
            try {
                pvz::setattr(L_future, SY("_result"), (L_function).call([&]() -> Args { Args expanded_; { V spread_=py::iter_list(L_args); for(const V& item_:spread_.items())expanded_.pos.push_back(item_); } auto keyword_=[&](Sym key_,const V& value_){ for(const auto& present_:expanded_.kw)if(present_.first==key_)throw PyError("TypeError","multiple values for keyword argument "+key_.str());expanded_.kw.emplace_back(key_,value_); }; return expanded_; }()));
            } catch (PyError& exc_) {
                if (exc_.matches("BaseException")) {
                    L_exc = py::exc_value(exc_);
                    pvz::setattr(L_future, SY("_error"), L_exc);
                }
                else throw;
            } catch (const std::exception& error) {
                pvz::setattr(L_future, SY("_error"), py::make_exc(SV("RuntimeError"), Args{V(error.what())}, ""));
            }
        }
        L_exc.del();
        L_item.del();
        L_function.del();
        L_args.del();
        (void)(callm(pvz::getattr(L_future, SY("_event")), SY("set"), Args{}));
        L_future.del();
    }
    return V::none();
}

V C__Executor::m_submit(const Args& A) {
    if (closed_) throw PyError("WorkerFailure", "worker executor is closed");
    V L_function = A.get(0, SY("function"), nullptr, "submit");
    V L_args = A.rest(1);
    V L_future;
    V L_queue;
    L_future = pm_native_snapshot_worker::new__Future(Args{});
    if ((pvz::getattr(a__queue, SY("maxsize"))).truthy()) {
        L_queue = py::stdlib_module(SV("queue"));
        try {
            (void)(callm(a__queue, SY("put_nowait"), Args{V::tuple({L_future, L_function, L_args})}));
        } catch (PyError& exc_) {
            if (exc_.matches("Full")) {
                py::raise(py::make_exc(SV("WorkerFailure"), Args{SV("worker queue capacity exceeded")}, "RuntimeError"));
            }
            else throw;
        }
    } else {
        (void)(callm(a__queue, SY("put"), Args{V::tuple({L_future, L_function, L_args})}));
    }
    return L_future;
    return V::none();
}

V C__Executor::m_shutdown(const Args& A) {
    V L_wait = (A.size() > 0 || A.has_kw(SY("wait"))) ? A.get(0, SY("wait"), nullptr) : V(V(true));
    V L__;
    V L_thread;
    if (!closed_) { closed_ = true;
    { V it1_ = py::iter_list(a__threads);
    for (size_t i1_ = 0; i1_ < it1_.len(); ++i1_) {
        L__ = it1_.idx(int64_t(i1_)); 
        (void)(callm(a__queue, SY("put"), Args{V::none()}));
    }}
    }
    if ((L_wait).truthy()) {
        { V it2_ = py::iter_list(a__threads);
        for (size_t i2_ = 0; i2_ < it2_.len(); ++i2_) {
            L_thread = it2_.idx(int64_t(i2_)); 
            (void)(callm(L_thread, SY("join"), Args{}));
        }}
    }
    return V::none();
}

void initcv__Executor(C__Executor* p) {

}
V new__Executor(const Args& A) {
    init();
    auto p = std::make_shared<C__Executor>();
    V self = V::inst(p);
    initcv__Executor(p.get());
    callm(self, SY("__init__"), A);
    return self;
}
V cls__Executor() { static V c = [] { V c = py::class_value(SV("_Executor"), [](const Args& A) { return new__Executor(A); }); c.box->fattrs.emplace_back(Sym("__module__"), SV("pvp.native_snapshot_worker")); c.box->fattrs.emplace_back(Sym("__new__"), V::func([](const Args& A) { if (A.pos.size() != 1 || !py_is(A.pos[0], cls__Executor())) throw PyError("TypeError", "native __new__ requires its exact class"); auto p = std::make_shared<C__Executor>(); initcv__Executor(p.get()); return V::inst(p); })); c.box->fattrs.emplace_back(Sym("__init__"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Executor>([](pm_native_snapshot_worker::C__Executor* self, const Args& args) { return self->pm_native_snapshot_worker::C__Executor::m___init__(args); }, A); })); c.box->fattrs.emplace_back(Sym("_loop"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Executor>([](pm_native_snapshot_worker::C__Executor* self, const Args& args) { return self->pm_native_snapshot_worker::C__Executor::m__loop(args); }, A); })); c.box->fattrs.emplace_back(Sym("submit"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Executor>([](pm_native_snapshot_worker::C__Executor* self, const Args& args) { return self->pm_native_snapshot_worker::C__Executor::m_submit(args); }, A); })); c.box->fattrs.emplace_back(Sym("shutdown"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C__Executor>([](pm_native_snapshot_worker::C__Executor* self, const Args& args) { return self->pm_native_snapshot_worker::C__Executor::m_shutdown(args); }, A); })); for (auto& item : c.box->fattrs) if (item.second.t == V::FUNC) item.second.box->fattrs.emplace_back(Sym("__native_declared_method__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_class_dispatch__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_static_methods__"), V::set({SV("__new__")})); return c; }(); return c; }
bool C_SnapshotPackWorker::isa(const char* c) const { std::string s(c); return s == "SnapshotPackWorker" || s == "object"; }
V* C_SnapshotPackWorker::slot(Sym name) {
    static const SymIndex idx_({SY("mode"), SY("backend_kind"), SY("max_bytes"), SY("executor"), SY("backend"), SY("pending"), SY("_inflight"), SY("frozen_byte_limit"), SY("inflight_limit"), SY("profile_detail"), SY("profile_phases"), SY("telemetry")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return nullptr;
    switch (k_) {
        case 0: return &a_mode;
        case 1: return &a_backend_kind;
        case 2: return &a_max_bytes;
        case 3: return &a_executor;
        case 4: return &a_backend;
        case 5: return &a_pending;
        case 6: return &a__inflight;
        case 7: return &a_frozen_byte_limit;
        case 8: return &a_inflight_limit;
        case 9: return &a_profile_detail;
        case 10: return &a_profile_phases;
        case 11: return &a_telemetry;
    }
    return nullptr;
}
V C_SnapshotPackWorker::method(Sym name) {
    if (name == SY("__native_type__")) { V metadata=V::func([](const Args&) { return pm_native_snapshot_worker::cls_SnapshotPackWorker(); }); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }
    if (name == SY("__native_slot_names__")) return V::func([](const Args&) { return V::tuple({SV("mode"), SV("backend_kind"), SV("max_bytes"), SV("executor"), SV("backend"), SV("pending"), SV("_inflight"), SV("frozen_byte_limit"), SV("inflight_limit"), SV("profile_detail"), SV("profile_phases"), SV("telemetry")}); });
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls_SnapshotPackWorker(), name, self()); replacement.has()) return replacement;
    static const SymIndex idx_({SY("__init__"), SY("_reap_inputs"), SY("_pack"), SY("busy"), SY("_pack_deliver"), SY("submit"), SY("completed"), SY("forget"), SY("close")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return V();
    auto sp = std::static_pointer_cast<C_SnapshotPackWorker>(shared_from_this());
    switch (k_) {
        case 0: { V method=V::func([sp](const Args& A) { return sp->m___init__(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 1: { V method=V::func([sp](const Args& A) { return sp->m__reap_inputs(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 2: { V method=V::func([sp](const Args& A) { return sp->m__pack(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 3: { V method=V::func([sp](const Args& A) { return sp->m_busy(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 4: { V method=V::func([sp](const Args& A) { return sp->m__pack_deliver(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 5: { V method=V::func([sp](const Args& A) { return sp->m_submit(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 6: { V method=V::func([sp](const Args& A) { return sp->m_completed(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 7: { V method=V::func([sp](const Args& A) { return sp->m_forget(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
        case 8: { V method=V::func([sp](const Args& A) { return sp->m_close(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); return method; }
    }
    return V();
}
bool C_SnapshotPackWorker::call_method(Sym name, const Args& A, V& out) {
    if (V replacement = py::class_method_override(pm_native_snapshot_worker::cls_SnapshotPackWorker(), name, self()); replacement.has()) { out = replacement.call(A); return true; }
    static const SymIndex idx_({SY("__init__"), SY("_reap_inputs"), SY("_pack"), SY("busy"), SY("_pack_deliver"), SY("submit"), SY("completed"), SY("forget"), SY("close")});
    const int k_ = idx_.find(name);
    if (k_ < 0) return false;
    switch (k_) {
        case 0: out = m___init__(A); return true;
        case 1: out = m__reap_inputs(A); return true;
        case 2: out = m__pack(A); return true;
        case 3: out = m_busy(A); return true;
        case 4: out = m__pack_deliver(A); return true;
        case 5: out = m_submit(A); return true;
        case 6: out = m_completed(A); return true;
        case 7: out = m_forget(A); return true;
        case 8: out = m_close(A); return true;
    }
    return false;
}
V C_SnapshotPackWorker::m___init__(const Args& A) {
    V L_mode = (A.size() > 0 || A.has_kw(SY("mode"))) ? A.get(0, SY("mode"), nullptr) : V(V::none());
    V L_max_bytes = (A.size() > 1 || A.has_kw(SY("max_bytes"))) ? A.get(1, SY("max_bytes"), nullptr) : V(((V(8.0) * V(1024.0)) * V(1024.0)));
    L_mode = callm((py_is(L_mode, V::none()) ? V(py::m_get(py::stdlib_attr(SV("os"), SV("environ")), SV("PVP_NET_PACK_WORKER"), SV("process"))) : V(L_mode)), SY("lower"), Args{});
    if (((L_mode == SV("process")) && !(callm(pm_native_snapshot_worker::module_ns(), SY("process_backend_supported"), Args{})).truthy())) {
        L_mode = ((callm(pm_native_snapshot_worker::module_ns(), SY("executable_worker_supported"), Args{})).truthy() ? V(SV("process")) : V(SV("thread")));
    }
    a_mode = L_mode;
    a_backend_kind = V::none();
    a_max_bytes = L_max_bytes;
    a_executor = pm_native_snapshot_worker::new__Executor(Args({V(1.0), SV("pvp-pack-worker")}, {{SY("max_pending"), V(16.0)}}));
    a_backend = V::none();
    a_pending = py_dict({});
    a__inflight = py_dict({});
    a_frozen_byte_limit = ((V(32.0) * V(1024.0)) * V(1024.0));
    a_inflight_limit = V(16.0);
    a_profile_detail = V(false);
    a_profile_phases = callm(pm_native_snapshot_worker::module_ns(), SY("PhaseProfiler"), Args({}, {{SY("limit"), V(600.0)}, {SY("rolling"), V(true)}}));
    a_telemetry = py_dict({{SV("submitted"), V(0.0)}, {SV("completed"), V(0.0)}, {SV("busy_skips"), V(0.0)}, {SV("fallbacks"), V(0.0)}, {SV("freeze_ms"), V(0.0)}, {SV("pack_ms"), V(0.0)}});
    (void)(callm(a_telemetry, SY("update"), Args({}, {{SY("frozen_bytes"), V(0.0)}, {SY("peak_frozen_bytes"), V(0.0)}, {SY("inflight_items"), V(0.0)}, {SY("frozen_byte_limit"), a_frozen_byte_limit}, {SY("inflight_item_limit"), a_inflight_limit}, {SY("capacity_declines"), V(0.0)}})));
    return V::none();
}

V C_SnapshotPackWorker::m__reap_inputs(const Args& A) {
    a__inflight = [&]() -> V { V out_ = V::dict(); V L_future; V L_size; { auto it1_ = py::items_vec(a__inflight); for (size_t i1_ = 0; i1_ < it1_.size(); ++i1_) { L_future = it1_[i1_].first; L_size = it1_[i1_].second; if (!(!(callm(L_future, SY("done"), Args{})).truthy())) continue; out_.at(L_future) = L_size; }}return out_; }();
    pvz::setitem(a_telemetry, SV("frozen_bytes"), py::sum_it(callm(a__inflight, SY("values"), Args{})));
    pvz::setitem(a_telemetry, SV("inflight_items"), py::len(a__inflight));
    return V::none();
}

V C_SnapshotPackWorker::m__pack(const Args& A) {
    V L_data = A.get(0, SY("data"), nullptr, "_pack");
    V L_profiled = (A.size() > 1 || A.has_kw(SY("profiled"))) ? A.get(1, SY("profiled"), nullptr) : V(V(false));
    V L_task;
    L_task = ((L_profiled).truthy() ? V(SV("pack_snapshot_profile")) : V(SV("pack_snapshot")));
    // Native standalone has no CPython process-worker protocol. Constructor
    // selects the actual thread backend, including the default process request.
    if (a_mode == SV("process")) throw PyError("NotImplementedError", "native process worker protocol");
    a_backend_kind = SV("thread");
    return (rd(pm_native_snapshot_worker::KERNELS, L_task)).call(Args{L_data});
    return V::none();
}

V C_SnapshotPackWorker::m_busy(const Args& A) {
    V L_peer = A.get(0, SY("peer"), nullptr, "busy");
    return V(py::in(L_peer, a_pending));
    return V::none();
}

V C_SnapshotPackWorker::m__pack_deliver(const Args& A) {
    V L_data = A.get(0, SY("data"), nullptr, "_pack_deliver");
    V L_delivery = A.get(1, SY("delivery"), nullptr, "_pack_deliver");
    V L_profiled = (A.size() > 2 || A.has_kw(SY("profiled"))) ? A.get(2, SY("profiled"), nullptr) : V(V(false));
    V L_encoded;
    V L_raw_length;
    V L_result;
    V L_started;
    L_started = (pm_native_snapshot_worker::_clock).call(Args{});
    L_result = ((L_profiled).truthy() ? V(callm(self(), SY("_pack"), Args{L_data, V(true)})) : V(callm(self(), SY("_pack"), Args{L_data})));
    { V ab1_ = a_telemetry; V ak1_ = SV("pack_ms"); pvz::setitem(ab1_, ak1_, py::iadd(rd(ab1_, ak1_), (((pm_native_snapshot_worker::_clock).call(Args{}) - L_started) * V(1000.0)))); }
    { V ut2_ = py::as_seq(py::slice(L_result, V::none(), V(2.0))); L_encoded = ut2_.idx(0); L_raw_length = ut2_.idx(1); } 
    if ((!py_is(L_delivery, V::none()) && (L_raw_length > a_max_bytes))) {
        py::raise(py::make_exc(SV("ValueError"), Args{SV("权威快照超出大小限制")}, ""));
    }
    if (!py_is(L_delivery, V::none())) {
        (void)(callm(L_delivery, SY("publish"), Args{py_dict({{SV("type"), SV("room_snapshot")}, {SV("encoding"), SV("zlib-json")}, {SV("data"), L_encoded}})}));
    }
    return L_result;
    return V::none();
}

V C_SnapshotPackWorker::m_submit(const Args& A) {
    if (closed_) return V(false);
    V L_peer = A.get(0, SY("peer"), nullptr, "submit");
    V L_key = A.get(1, SY("key"), nullptr, "submit");
    V L_value = A.get(2, SY("value"), nullptr, "submit");
    V L_delivery = (A.size() > 3 || A.has_kw(SY("delivery"))) ? A.get(3, SY("delivery"), nullptr) : V(V::none());
    V L_data;
    V L_future;
    V L_marshal;
    V L_started;
    L_marshal = py::stdlib_module(SV("marshal"));
    if (py::in(L_peer, a_pending)) {
        { V ab1_ = a_telemetry; V ak1_ = SV("busy_skips"); pvz::setitem(ab1_, ak1_, py::iadd(rd(ab1_, ak1_), V(1.0))); }
        return V(true);
    }
    (void)(callm(self(), SY("_reap_inputs"), Args{}));
    if ((py::len(a__inflight) >= a_inflight_limit)) {
        { V ab2_ = a_telemetry; V ak2_ = SV("capacity_declines"); pvz::setitem(ab2_, ak2_, py::iadd(rd(ab2_, ak2_), V(1.0))); }
        return V(false);
    }
    L_started = (pm_native_snapshot_worker::_clock).call(Args{});
    try {
        L_data = callm(L_marshal, SY("dumps"), Args{L_value});
    } catch (PyError& exc_) {
        if (exc_.matches("ValueError")) {
            return V(false);
        }
        else throw;
    }
    { V ab3_ = a_telemetry; V ak3_ = SV("freeze_ms"); pvz::setitem(ab3_, ak3_, py::iadd(rd(ab3_, ak3_), (((pm_native_snapshot_worker::_clock).call(Args{}) - L_started) * V(1000.0)))); }
    if (((py::len(L_data) + rd(a_telemetry, SV("frozen_bytes"))) > a_frozen_byte_limit)) {
        { V ab4_ = a_telemetry; V ak4_ = SV("capacity_declines"); pvz::setitem(ab4_, ak4_, py::iadd(rd(ab4_, ak4_), V(1.0))); }
        return V(false);
    }
    try {
        L_future = callm(a_executor, SY("submit"), Args{method(SY("_pack_deliver")), L_data, L_delivery, a_profile_detail});
    } catch (PyError& exc_) {
        if (exc_.matches("WorkerFailure")) {
            { V ab5_ = a_telemetry; V ak5_ = SV("capacity_declines"); pvz::setitem(ab5_, ak5_, py::iadd(rd(ab5_, ak5_), V(1.0))); }
            return V(false);
        }
        else throw;
    }
    pvz::setitem(a__inflight, L_future, py::len(L_data));
    (void)(callm(self(), SY("_reap_inputs"), Args{}));
    pvz::setitem(a_telemetry, SV("peak_frozen_bytes"), py::max_it(V::list({rd(a_telemetry, SV("peak_frozen_bytes")), rd(a_telemetry, SV("frozen_bytes"))}), py::Key(), V()));
    pvz::setitem(a_pending, L_peer, V::tuple({L_key, L_future}));
    { V ab6_ = a_telemetry; V ak6_ = SV("submitted"); pvz::setitem(ab6_, ak6_, py::iadd(rd(ab6_, ak6_), V(1.0))); }
    return V(true);
    return V::none();
}

V C_SnapshotPackWorker::m_completed(const Args& A) {
    V L_encoded;
    V L_future;
    V L_key;
    V L_name;
    V L_peer;
    V L_raw_length;
    V L_ready;
    V L_result;
    V L_value;
    (void)(callm(self(), SY("_reap_inputs"), Args{}));
    L_ready = V::list({});
    { V it1_ = py::iter_list(py::list_it(callm(a_pending, SY("items"), Args{})));
    for (size_t i1_ = 0; i1_ < it1_.len(); ++i1_) {
        { V ut2_ = py::as_seq(it1_.idx(int64_t(i1_))); L_peer = ut2_.idx(0); { V ut3_ = py::as_seq(ut2_.idx(1)); L_key = ut3_.idx(0); L_future = ut3_.idx(1); } } 
        if (!(callm(L_future, SY("done"), Args{})).truthy()) {
            continue;
        }
        pvz::delitem(a_pending, L_peer);
        L_result = callm(L_future, SY("result"), Args{});
        { V ut4_ = py::as_seq(py::slice(L_result, V::none(), V(2.0))); L_encoded = ut4_.idx(0); L_raw_length = ut4_.idx(1); } 
        if ((py::len(L_result) > V(2.0))) {
            { auto it5_ = py::items_vec(rd(L_result, V(2.0)));
            for (size_t i5_ = 0; i5_ < it5_.size(); ++i5_) {
                L_name = it5_[i5_].first; L_value = it5_[i5_].second; 
                (void)(callm(a_profile_phases, SY("record"), Args{L_name, L_value}));
            }}
        }
        if ((L_raw_length > a_max_bytes)) {
            py::raise(py::make_exc(SV("ValueError"), Args{SV("权威快照超出大小限制")}, ""));
        }
        { V ab6_ = a_telemetry; V ak6_ = SV("completed"); pvz::setitem(ab6_, ak6_, py::iadd(rd(ab6_, ak6_), V(1.0))); }
        (void)(py::m_append(L_ready, V::tuple({L_peer, L_key, py_dict({{SV("type"), SV("room_snapshot")}, {SV("encoding"), SV("zlib-json")}, {SV("data"), L_encoded}})})));
    }}
    return L_ready;
    return V::none();
}

V C_SnapshotPackWorker::m_forget(const Args& A) {
    V L_peer = (A.size() > 0 || A.has_kw(SY("peer"))) ? A.get(0, SY("peer"), nullptr) : V(V::none());
    V L_entry;
    V L_name;
    { V it1_ = py::iter_list((!py_is(L_peer, V::none()) ? V(V::list({L_peer})) : V(py::list_it(a_pending))));
    for (size_t i1_ = 0; i1_ < it1_.len(); ++i1_) {
        L_name = it1_.idx(int64_t(i1_)); 
        L_entry = callm(a_pending, SY("pop"), Args{L_name, V::none()});
        if (!py_is(L_entry, V::none())) {
            (void)(callm(rd(L_entry, V(1.0)), SY("cancel"), Args{}));
        }
    }}
    (void)(callm(self(), SY("_reap_inputs"), Args{}));
    return V::none();
}

V C_SnapshotPackWorker::m_close(const Args& A) {
    if (closed_) return V::none();
    closed_ = true;
    (void)(callm(self(), SY("forget"), Args{}));
    (void)(callm(a_executor, SY("shutdown"), Args({}, {{SY("wait"), V(true)}})));
    (void)(callm(a__inflight, SY("clear"), Args{}));
    (void)(callm(self(), SY("_reap_inputs"), Args{}));
    if (!py_is(a_backend, V::none())) {
        (void)(callm(a_backend, SY("close"), Args{}));
        a_backend = V::none();
    }
    return V::none();
}

void initcv_SnapshotPackWorker(C_SnapshotPackWorker* p) {

}
V new_SnapshotPackWorker(const Args& A) {
    init();
    auto p = std::make_shared<C_SnapshotPackWorker>();
    V self = V::inst(p);
    initcv_SnapshotPackWorker(p.get());
    callm(self, SY("__init__"), A);
    return self;
}
V cls_SnapshotPackWorker() { static V c = [] { V c = py::class_value(SV("SnapshotPackWorker"), [](const Args& A) { return new_SnapshotPackWorker(A); }); c.box->fattrs.emplace_back(Sym("__module__"), SV("pvp.native_snapshot_worker")); c.box->fattrs.emplace_back(Sym("__new__"), V::func([](const Args& A) { if (A.pos.size() != 1 || !py_is(A.pos[0], cls_SnapshotPackWorker())) throw PyError("TypeError", "native __new__ requires its exact class"); auto p = std::make_shared<C_SnapshotPackWorker>(); initcv_SnapshotPackWorker(p.get()); return V::inst(p); })); c.box->fattrs.emplace_back(Sym("__init__"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m___init__(args); }, A); })); c.box->fattrs.emplace_back(Sym("_reap_inputs"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m__reap_inputs(args); }, A); })); c.box->fattrs.emplace_back(Sym("_pack"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m__pack(args); }, A); })); c.box->fattrs.emplace_back(Sym("busy"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m_busy(args); }, A); })); c.box->fattrs.emplace_back(Sym("_pack_deliver"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m__pack_deliver(args); }, A); })); c.box->fattrs.emplace_back(Sym("submit"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m_submit(args); }, A); })); c.box->fattrs.emplace_back(Sym("completed"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m_completed(args); }, A); })); c.box->fattrs.emplace_back(Sym("forget"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m_forget(args); }, A); })); c.box->fattrs.emplace_back(Sym("close"), V::func([](const Args& A) { return py::unbound_call<pm_native_snapshot_worker::C_SnapshotPackWorker>([](pm_native_snapshot_worker::C_SnapshotPackWorker* self, const Args& args) { return self->pm_native_snapshot_worker::C_SnapshotPackWorker::m_close(args); }, A); })); for (auto& item : c.box->fattrs) if (item.second.t == V::FUNC) item.second.box->fattrs.emplace_back(Sym("__native_declared_method__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_class_dispatch__"), V(true)); c.box->fattrs.emplace_back(Sym("__native_static_methods__"), V::set({SV("__new__")})); return c; }(); return c; }
static bool inited_ = false;
void init() {
    if (inited_) return;
    inited_ = true;
    py::note_module_loaded("pvp.native_snapshot_worker");
    py::init_deps_native_snapshot_worker();
    pm_native_snapshot_worker::_clock = py::stdlib_attr(SV("time"), SV("perf_counter"));
    pm_native_snapshot_worker::KERNELS = py_dict({{SV("pack_snapshot"), V::func(pm_native_snapshot_worker::f_pack_snapshot_kernel)}, {SV("pack_snapshot_profile"), V::func(pm_native_snapshot_worker::f_pack_snapshot_profile)}});
}
static V modattr_(Sym n) {
    init();
    const std::string& s = n.str();
    if (s == "_clock") return pm_native_snapshot_worker::_clock;
    if (s == "KERNELS") return pm_native_snapshot_worker::KERNELS;
    if (s == "pack_snapshot_kernel") return V::func(f_pack_snapshot_kernel);
    if (s == "pack_snapshot_profile") return V::func(f_pack_snapshot_profile);
    if (s == "process_backend_supported") return V::func(f_process_backend_supported);
    if (s == "executable_worker_supported") return V::func(f_executable_worker_supported);
    if (s == "WorkerFailure") return cls_WorkerFailure();
    if (s == "_Future") return cls__Future();
    if (s == "_Executor") return cls__Executor();
    if (s == "SnapshotPackWorker") return cls_SnapshotPackWorker();
    if (s == "PhaseProfiler") return pm_native_multiworker::cls_PhaseProfiler();
    if (s == "os") return py::stdlib(SV("os"));
    if (s == "threading") return py::stdlib(SV("threading"));
    if (s == "time") return py::stdlib(SV("time"));
    return V();
}
static V modwrite_(const Args& A) {
    init();
    const std::string& s = A.pos.at(0).str();
    if (s == "_clock") { pm_native_snapshot_worker::_clock = A.pos.at(1); return V(true); }
    if (s == "KERNELS") { pm_native_snapshot_worker::KERNELS = A.pos.at(1); return V(true); }
    return V(false);
}
V module_ns() { static const bool reg_ = (py::register_module_attrs("native_snapshot_worker", modattr_), py::register_native_hook("module.write.native_snapshot_worker", modwrite_), true); (void)reg_; init(); return py::module_ns(SV("native_snapshot_worker")); }
}}  // namespace pvz::pm_native_snapshot_worker
