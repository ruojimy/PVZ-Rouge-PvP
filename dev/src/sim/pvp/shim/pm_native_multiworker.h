// Shim for modkit/pvp/native_multiworker.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_native_multiworker {
void init();
V cls_JobSystem();
V new_CandidateIndex(const Args& A);
V cls_CandidateIndex();
V cls_SnapshotPackWorker();
V f_pack_snapshot_kernel(const Args& A);
V f_pack_snapshot_profile(const Args& A);
V cls_PhaseProfiler();
V new_PhaseProfiler(const Args& A);
V f_native_kernel_status(const Args& A);
V f_configured_workers(const Args& A);
V f_fastpath_enabled(const Args& A);
}}  // namespace pvz::pm_native_multiworker
