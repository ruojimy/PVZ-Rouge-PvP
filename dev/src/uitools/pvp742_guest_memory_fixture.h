#pragma once
// Real guest receive / snapshot / view ownership, without sockets or rendering.
#include "pg/pg.h"
#include "core/alloc.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/typed_battle.h"
#include "ui/gen/pm_app.h"
#include "ui/gen/pm_room.h"
#include "ui/gen/pm_network.h"
#include "ui/gen/pm_adaptive_pacing.h"
#include "ui/hand/texture74_internal.h"
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>
#if defined(_WIN32)
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"psapi.lib")
#else
#include <unistd.h>
#endif
namespace pvz::guest_memory_audit {
using J=nlohmann::json;
inline void require(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
inline J json(const V& v){return J::parse(dump(v));}
inline uint64_t private_bytes(){
#if defined(_WIN32)
 PROCESS_MEMORY_COUNTERS_EX p{};p.cb=sizeof(p);if(GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&p),sizeof(p)))return p.PrivateUsage;
#else
 FILE* f=std::fopen("/proc/self/statm","r");unsigned long pages=0,resident=0;if(f){int n=std::fscanf(f,"%lu %lu",&pages,&resident);std::fclose(f);if(n==2)return uint64_t(resident)*uint64_t(sysconf(_SC_PAGESIZE));}
#endif
 return 0;
}
inline J allocator(const SmallAllocatorStats& s){return {{"legacy",s.legacy},{"slab_bytes",s.slab_bytes},{"slab_count",s.slab_count},{"cross_thread_frees",s.cross_thread_frees},{"central_blocks",s.central_blocks},{"central_reused_blocks",s.central_reused_blocks},{"thread_cache_flushes",s.thread_cache_flushes}};}
struct Sample {const char* phase="message";size_t completed=0;uint64_t live=0,peak=0,private_memory=0;double seconds=0;SmallAllocatorStats small;};
// The sole replacement for the network is recv(): it supplies valid encoded
// bytes in the same 64-KiB chunks as the real socket. All parsers and queues below
// remain the generated production implementations.
struct ReplaySocket:PyObj {
 const std::string* frame=nullptr;size_t offset=0;
 const char* type_name()const override{return "SnapshotAuditSocket";}
 V method(Sym n)override{
  if(n==SY("recv"))return V::func([this](const Args& a){const size_t count=std::min<size_t>(size_t(a.pos.at(0).num()),frame->size()-offset);std::string bytes=frame->substr(offset,count);offset+=count;return V::bytes(bytes);});
  if(n==SY("close")||n==SY("setblocking"))return V::func([](const Args&){return V::none();});
  return V();
 }
};
struct Receiver {
 V transport,connection;
 std::shared_ptr<pm_network::C_ClientTransport> client;
 std::shared_ptr<ReplaySocket> socket;
 Receiver(){
  client=std::make_shared<pm_network::C_ClientTransport>();transport=V::inst(client);pm_network::initcv_ClientTransport(client.get());
  client->m__init_base(Args{V::none(),SV("memory-audit"),pm_network::MAX_FRAME_BYTES,V(2),V(30),V(10),V(30)});
  client->a_peer_id=SV("guest");client->a_spectator=V(false);client->a__in_seq=V(0);client->a__out_seq=V(0);client->a_state=SV("connected");
  client->m__ready(Args{SV("server"),V(true)});
 }
 void open(){socket=std::make_shared<ReplaySocket>();connection=pm_network::new__Connection(Args{V::inst(socket),pm_network::MAX_FRAME_BYTES});setattr(connection,SY("ready"),V(true));client->a__conn=connection;}
 void drain_outgoing(){(void)py::iter_list(callm(transport,SY("_pop_commands"),Args{}));}
 void produce(const std::string& frame){
  drain_outgoing();socket->frame=&frame;socket->offset=0;
  while(socket->offset<frame.size())client->m__read(Args{connection});
   require(py::len(getattr(getattr(connection,SY("decoder")),SY("buffer"))).num()==0,"FrameDecoder retained incomplete bytes");
 }
 void close(){drain_outgoing();client->a__conn=V::none();connection=V::none();socket.reset();}
};
// V handoff remains under the real GIL. Only plain integers / condition state
// cross the std::condition_variable while the main thread releases that lock.
struct Channel {
 Receiver& receiver;const std::vector<std::string>& frames;std::thread worker;
 std::mutex lock;std::condition_variable cv;int requested=-1,ready=-1,next_ticket=0;size_t requested_frame=0;bool stop=false;std::string error;
 Channel(Receiver& r,const std::vector<std::string>& bytes):receiver(r),frames(bytes){
  worker=std::thread([this]{int served=-1;bool opened=false;
   for(;;){int ticket;size_t index;{std::unique_lock guard(lock);cv.wait(guard,[&]{return stop||requested!=served;});if(stop)break;ticket=requested;index=requested_frame;}
    gil::acquire();try{if(!opened){receiver.open();opened=true;}receiver.produce(frames.at(index));}
    catch(const std::exception& e){std::lock_guard guard(lock);error=e.what();}gil::release();
    {std::lock_guard guard(lock);served=ticket;ready=ticket;}cv.notify_all();
   }
   gil::acquire();try{if(opened)receiver.close();}catch(...){}gil::release();
  });
 }
 void produce(size_t index){
  const int ticket=++next_ticket;
  {std::lock_guard guard(lock);requested_frame=index;requested=ticket;}cv.notify_all();
  {gil::Release release;std::unique_lock guard(lock);cv.wait(guard,[&]{return ready==ticket||!error.empty();});}
  require(error.empty(),error);
 }
 void finish(){if(!worker.joinable())return;{std::lock_guard guard(lock);stop=true;}cv.notify_all();{gil::Release release;worker.join();}}
 ~Channel(){finish();}
};
}
