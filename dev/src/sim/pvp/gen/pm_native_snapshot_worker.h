// Adapted original native_multiworker.py classes; see worker provenance47.json.
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_native_snapshot_worker {
V module_ns();
void init();
extern V _clock;
extern V KERNELS;
V f_pack_snapshot_kernel(const Args& A);
V f_pack_snapshot_profile(const Args& A);
V f_process_backend_supported(const Args& A);
V f_executable_worker_supported(const Args& A);
struct C_WorkerFailure;
V new_WorkerFailure(const Args& A);
V cls_WorkerFailure();
struct C__Future;
V new__Future(const Args& A);
V cls__Future();
struct C__Executor;
V new__Executor(const Args& A);
V cls__Executor();
struct C_SnapshotPackWorker;
V new_SnapshotPackWorker(const Args& A);
V cls_SnapshotPackWorker();
struct C_WorkerFailure : PyObj {
    const char* type_name() const override { return "WorkerFailure"; }
    bool isa(const char* c) const override;
    V* slot(Sym name) override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& A, V& out) override;
    V self_v() { return self(); }
};
struct C__Future : PyObj {
    V a__event;
    V a__result;
    V a__error;
    V a__cancelled;
    const char* type_name() const override { return "_Future"; }
    bool isa(const char* c) const override;
    V* slot(Sym name) override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& A, V& out) override;
    V self_v() { return self(); }
    virtual V m___init__(const Args& A);
    virtual V m_done(const Args& A);
    virtual V m_result(const Args& A);
    virtual V m_cancel(const Args& A);
};
void initcv__Future(C__Future* p);
struct C__Executor : PyObj {
    bool closed_ = false;
    V a__queue;
    V a__threads;
    const char* type_name() const override { return "_Executor"; }
    bool isa(const char* c) const override;
    V* slot(Sym name) override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& A, V& out) override;
    V self_v() { return self(); }
    virtual V m___init__(const Args& A);
    virtual V m__loop(const Args& A);
    virtual V m_submit(const Args& A);
    virtual V m_shutdown(const Args& A);
};
void initcv__Executor(C__Executor* p);
struct C_SnapshotPackWorker : PyObj {
    bool closed_ = false;
    V a_mode;
    V a_backend_kind;
    V a_max_bytes;
    V a_executor;
    V a_backend;
    V a_pending;
    V a__inflight;
    V a_frozen_byte_limit;
    V a_inflight_limit;
    V a_profile_detail;
    V a_profile_phases;
    V a_telemetry;
    const char* type_name() const override { return "SnapshotPackWorker"; }
    bool isa(const char* c) const override;
    V* slot(Sym name) override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& A, V& out) override;
    V self_v() { return self(); }
    virtual V m___init__(const Args& A);
    virtual V m__reap_inputs(const Args& A);
    virtual V m__pack(const Args& A);
    virtual V m_busy(const Args& A);
    virtual V m__pack_deliver(const Args& A);
    virtual V m_submit(const Args& A);
    virtual V m_completed(const Args& A);
    virtual V m_forget(const Args& A);
    virtual V m_close(const Args& A);
};
void initcv_SnapshotPackWorker(C_SnapshotPackWorker* p);
}}  // namespace pvz::pm_native_snapshot_worker
