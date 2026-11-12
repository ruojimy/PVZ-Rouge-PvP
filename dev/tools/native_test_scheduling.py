"""Memory-aware parallel native modules with per-worker growth reservations."""
import concurrent.futures
import ctypes
import os
import time

MIB = 1024*1024


def memory_snapshot():
    if os.name != 'nt':
        return None  # Unknown host headroom: fall back to one worker.
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
                    ('total_phys','avail_phys','total_commit','avail_commit','total_virtual','avail_virtual','reserved')]
    status = MemoryStatus();status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return dict(physical_available=status.avail_phys,commit_available=status.avail_commit)


def process_private_bytes(process):
    if os.name != 'nt' or process is None:
        return 0
    class Counters(ctypes.Structure):
        _fields_ = [('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in
                    ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    try:
        counters = Counters();counters.cb = ctypes.sizeof(counters)
        function = ctypes.windll.psapi.GetProcessMemoryInfo
        function.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        if function(int(process._handle),ctypes.byref(counters),counters.cb):
            return counters.private
    except (AttributeError,OSError,ValueError):
        pass
    return 0


def can_start(snapshot, running_usage, budget, reserve):
    if snapshot is None:
        return not running_usage
    headroom = min(snapshot['physical_available'],snapshot['commit_available'])
    growth = sum(max(0,budget-used) for used in running_usage)
    return headroom >= reserve+growth+budget


def run_modules(modules, work, max_workers, worker_memory_mib, reserve_mib,
                processes, on_event, probe=memory_snapshot):
    """Run pending modules as soon as both CPU slots and memory are available.

    The budget is an estimate, not an OS hard limit. Observed larger workers
    increase it for subsequent admissions. Running tests are not terminated
    merely because another application consumes memory.
    """
    budget = worker_memory_mib*MIB;reserve = reserve_mib*MIB
    pending = iter(modules);next_module = next(pending,None)
    results = {};running = {};peak_workers = peak_private = peak_processes = 0
    last_wait_message = last_sample = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        while next_module is not None or running:
            for future in list(running):
                if future.done():
                    module = running.pop(future);results[module] = future.result()
                    on_event(dict(event='finished',module=module,running=len(running)))
            active = processes()
            process_count=sum(process.poll() is None for process in active.values())
            peak_processes=max(peak_processes,process_count)
            usage = [process_private_bytes(active.get(module)) for module in running.values()]
            peak_private = max([peak_private]+usage)
            budget = max(budget,(peak_private*115+99)//100)
            snapshot = probe()
            if time.monotonic()-last_sample>=5:
                on_event(dict(event='memory_sample',running=len(running),native_processes=process_count,
                              memory=snapshot,worker_budget_bytes=budget,reserve_bytes=reserve))
                last_sample=time.monotonic()
            if next_module is not None and len(running)<max_workers and can_start(snapshot,usage,budget,reserve):
                module = next_module;future = pool.submit(work,module);running[future] = module
                peak_workers = max(peak_workers,len(running))
                on_event(dict(event='started',module=module,running=len(running),memory=snapshot,
                              worker_budget_bytes=budget,reserve_bytes=reserve))
                next_module = next(pending,None)
                continue
            if next_module is not None and len(running)<max_workers and time.monotonic()-last_wait_message>=30:
                on_event(dict(event='waiting_for_memory',running=len(running),memory=snapshot,
                              worker_budget_bytes=budget,reserve_bytes=reserve))
                last_wait_message = time.monotonic()
            if running:
                concurrent.futures.wait(running,timeout=0.5,return_when=concurrent.futures.FIRST_COMPLETED)
            elif next_module is not None:
                time.sleep(0.5)
    return [results[module] for module in modules],dict(max_workers=max_workers,peak_workers=peak_workers,peak_native_processes=peak_processes,
            initial_worker_memory_mib=worker_memory_mib,final_worker_budget_bytes=budget,
            peak_observed_worker_private_bytes=peak_private,memory_reserve_mib=reserve_mib,
            memory_metric='minimum of available physical memory and available system commit; reserve unallocated worker growth')
