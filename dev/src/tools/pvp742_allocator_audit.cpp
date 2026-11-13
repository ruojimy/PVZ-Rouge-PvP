#include "core/alloc.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <new>
#include <string>
#include <thread>
#if defined(_WIN32)
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"psapi.lib")
#else
#include <unistd.h>
#endif
namespace pvz {extern void (*g_alloc_hook)(size_t);}
using J=nlohmann::json;
namespace {
constexpr size_t sizes[]={16,64,128,256,512};
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
uint64_t private_bytes(){
#if defined(_WIN32)
    PROCESS_MEMORY_COUNTERS_EX info{};info.cb=sizeof(info);
    if(GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&info),sizeof(info)))return info.PrivateUsage;
#else
    FILE* f=std::fopen("/proc/self/statm","r");unsigned long pages=0,resident=0;
    if(f){const int n=std::fscanf(f,"%lu %lu",&pages,&resident);std::fclose(f);if(n==2)return uint64_t(resident)*uint64_t(sysconf(_SC_PAGESIZE));}
#endif
    return 0;
}
void allocate(void** pointers,size_t count){
    for(size_t i=0;i<count;++i){pointers[i]=::operator new(sizes[i%5]);std::memset(pointers[i],int(i%251),sizes[i%5]);}
}
void release(void** pointers,size_t count,std::atomic<bool>& bad){
    for(size_t i=0;i<count;++i){
        auto* p=static_cast<unsigned char*>(pointers[i]);
        if((reinterpret_cast<uintptr_t>(p)&15)||p[0]!=i%251||p[sizes[i%5]-1]!=i%251)bad=true;
        ::operator delete(p);pointers[i]=nullptr;
    }
}
struct Sample {size_t completed=0;double seconds=0;uint64_t private_memory=0,live=0,peak=0;pvz::SmallAllocatorStats allocator;};
J stats(const pvz::SmallAllocatorStats& s){return {{"slab_bytes",s.slab_bytes},{"slab_count",s.slab_count},{"central_blocks",s.central_blocks},{"cross_thread_frees",s.cross_thread_frees},{"central_reused_blocks",s.central_reused_blocks},{"thread_cache_flushes",s.thread_cache_flushes},{"legacy",s.legacy}};}
struct LateDestructor {
    std::atomic<int>* completed=nullptr;
    ~LateDestructor(){if(!completed)return;const bool after_reaper=pvz::native_small_allocator_thread_cache_closed();void* p=::operator new(96,std::nothrow);if(p&&!(reinterpret_cast<uintptr_t>(p)&15)){::operator delete(p);if(after_reaper||pvz::native_small_allocator_stats().legacy)++*completed;}}
};
void contracts(){
    uint64_t current=0,peak=0;pvz::native_alloc_trace_start();
    for(size_t n:{size_t(0),size_t(1),size_t(16),size_t(512),size_t(513),size_t(8192)}){
        void* p=::operator new(n);require((reinterpret_cast<uintptr_t>(p)&15)==0,"new lost 16-byte alignment");::operator delete(p,n);
        p=::operator new[](n,std::nothrow);require(p!=nullptr,"nothrow allocation unexpectedly failed");::operator delete[](p,std::nothrow);
    }
    ::operator delete(nullptr);::operator delete[](nullptr);
    auto old=pvz::g_alloc_hook;pvz::g_alloc_hook=[](size_t){throw std::bad_alloc();};
    void* failure=::operator new(32,std::nothrow);pvz::g_alloc_hook=old;
    require(failure==nullptr,"nothrow new propagated an allocation-hook exception");
    volatile size_t too_large=SIZE_MAX;
    require(::operator new(too_large,std::nothrow)==nullptr,"allocator header size overflow was not rejected");
    pvz::native_alloc_trace_read(current,peak);require(current==0,"new/delete trace balance failed");pvz::native_alloc_trace_stop();
    std::atomic<int> late_completed=0;
    std::thread late([&]{thread_local LateDestructor late;late.completed=&late_completed;void* p=::operator new(96);::operator delete(p);});late.join();
    require(late_completed==1,"allocation after TLS cache destruction failed");
}
}
int main(int argc,char** argv){
    if(argc<3){std::cerr<<"usage: pvp742_allocator_audit output.json same|cross|retire|parallel [iterations] [batch]\n";return 2;}
    try {
        const std::string mode=argv[2];require(mode=="same"||mode=="cross"||mode=="retire"||mode=="parallel","invalid workload");
        const size_t iterations=argc>3?std::stoull(argv[3]):mode=="retire"?64:6000,batch=argc>4?std::stoull(argv[4]):128;
        require(iterations>0&&iterations<=100000&&batch>0&&batch<=16384,"workload exceeds bounded audit limits");
        contracts();
        auto** pointers=static_cast<void**>(std::calloc(batch,sizeof(void*)));require(pointers!=nullptr,"fixture pointer allocation failed");
        const size_t interval=std::max<size_t>(1,iterations/16),capacity=mode=="parallel"?68:iterations/interval+3;
        auto* samples=static_cast<Sample*>(std::calloc(capacity,sizeof(Sample)));require(samples!=nullptr,"fixture samples allocation failed");
        void** pair_pointers[4]={pointers,nullptr,nullptr,nullptr};
        if(mode=="parallel")for(size_t i=1;i<4;++i){pair_pointers[i]=static_cast<void**>(std::calloc(batch,sizeof(void*)));require(pair_pointers[i]!=nullptr,"parallel fixture pointers failed");}
        size_t sample_count=0;std::atomic<bool> bad=false;std::atomic<int> ready=0;
        const auto initial=pvz::native_small_allocator_stats();const uint64_t initial_private=private_bytes();
        pvz::native_alloc_trace_start();const auto started=std::chrono::steady_clock::now();
        const auto sample=[&](size_t n){auto& s=samples[sample_count++];s.completed=n;s.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();s.private_memory=private_bytes();pvz::native_alloc_trace_read(s.live,s.peak);s.allocator=pvz::native_small_allocator_stats();};
        sample(0);
        if(mode=="same"){
            for(size_t n=1;n<=iterations;++n){allocate(pointers,batch);release(pointers,batch,bad);if(n%interval==0||n==iterations)sample(n);}
        }else if(mode=="cross"){
            std::thread producer([&]{for(size_t n=0;n<iterations;++n){allocate(pointers,batch);ready.store(1,std::memory_order_release);while(ready.load(std::memory_order_acquire)!=2)std::this_thread::yield();ready.store(0,std::memory_order_release);}});
            for(size_t n=1;n<=iterations;++n){while(ready.load(std::memory_order_acquire)!=1)std::this_thread::yield();release(pointers,batch,bad);if(n%interval==0||n==iterations)sample(n);ready.store(2,std::memory_order_release);}producer.join();
        }else if(mode=="retire"){
            for(size_t n=1;n<=iterations;++n){std::thread worker([&]{allocate(pointers,batch);release(pointers,batch,bad);});worker.join();if(n%interval==0||n==iterations)sample(n);}
        }else{
            std::atomic<int> states[4]{};std::atomic<size_t> completed=0;std::thread producers[4],consumers[4];
            for(size_t i=0;i<4;++i){
                producers[i]=std::thread([&,i]{for(size_t n=0;n<iterations;++n){allocate(pair_pointers[i],batch);states[i].store(1,std::memory_order_release);while(states[i].load(std::memory_order_acquire)!=2)std::this_thread::yield();states[i].store(0,std::memory_order_release);}});
                consumers[i]=std::thread([&,i]{for(size_t n=0;n<iterations;++n){while(states[i].load(std::memory_order_acquire)!=1)std::this_thread::yield();release(pair_pointers[i],batch,bad);completed.fetch_add(1,std::memory_order_release);states[i].store(2,std::memory_order_release);}});
            }
            size_t next=std::max<size_t>(1,iterations/4);while(completed.load(std::memory_order_acquire)<iterations*4){const size_t n=completed.load(std::memory_order_acquire);if(n>=next&&sample_count+1<capacity){sample(n);next=n+std::max<size_t>(1,iterations/4);}std::this_thread::yield();}
            for(auto& t:producers)t.join();for(auto& t:consumers)t.join();sample(iterations*4);
        }
        uint64_t final_live=0,final_peak=0;pvz::native_alloc_trace_read(final_live,final_peak);const auto final=pvz::native_small_allocator_stats();pvz::native_alloc_trace_stop();
        const uint64_t delta=final.slab_bytes-initial.slab_bytes;uint64_t workload=0;for(size_t i=0;i<batch;++i)workload+=sizes[i%5];workload*=iterations*(mode=="parallel"?4:1);
        const bool bounded=initial.legacy||mode=="same"||delta<=std::max<uint64_t>(4*1024*1024,workload/10);
        J rows=J::array();for(size_t i=0;i<sample_count;++i){const auto& s=samples[i];rows.push_back({{"completed_batches",s.completed},{"wall_seconds",s.seconds},{"private_bytes",s.private_memory},{"requested_live_bytes",s.live},{"requested_peak_bytes",s.peak},{"allocator",stats(s.allocator)}});}
        J out={{"passed",!bad&&final_live==0&&bounded},{"workload",mode},{"iterations",iterations},{"batch",batch},{"payload_bytes_over_run",workload},{"allocator_before",stats(initial)},{"allocator_after",stats(final)},{"slab_bytes_added",delta},{"private_bytes_before",initial_private},{"private_bytes_after",private_bytes()},{"requested_final_live_bytes",final_live},{"requested_peak_bytes",final_peak},{"aligned_and_payload_intact",!bad.load()},{"new_allocator_bounded",initial.legacy?J(nullptr):J(bounded)},{"new_allocator_threshold_checked",!initial.legacy},{"samples",rows},{"scope","Independent process; requested new/delete bytes exclude slabs and foreign malloc. Windows PrivateBytes includes process commit; non-Windows fallback reports resident bytes."}};
        std::ofstream(argv[1],std::ios::binary)<<out.dump(2);std::cout<<J{{"passed",out["passed"]},{"workload",mode},{"legacy",initial.legacy},{"slab_bytes_added",delta},{"requested_final_live_bytes",final_live}}.dump()<<std::endl;
        std::free(samples);for(auto* p:pair_pointers)std::free(p);return out["passed"].get<bool>()?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
