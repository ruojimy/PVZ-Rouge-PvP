// Real Room snapshots and production SnapshotPackWorker; no user saves or live peers.
#include "pvp742_guest_memory_fixture.h"
#include "sim/pvp/gen/pm_native_snapshot_worker.h"
#include "sim/pvp/hand/native_marshal.h"
#include "core/snapshot_json.h"
#include <random>
using namespace pvz;using namespace pvz::guest_memory_audit;
using Clock=std::chrono::steady_clock;
double ms(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
int main(int argc,char**argv){
 if(argc!=2)return 2;J report;V worker;
 try{
  require(std::getenv("PVP_USERDATA")!=nullptr,"isolated PVP_USERDATA required");
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
  J codec=J::array();
  auto compare=[&](const char* name,const V& value){
   V frozen_value=py::native_marshal_dumps(Args{value});std::string direct;
   const bool fast=snapshot_json_from_marshal(frozen_value.str(),direct);
   V decoded=py::native_marshal_loads(Args{frozen_value});
   V expected_json=py::stdlib_call(SV("json.dumps"),Args({decoded},{{SY("ensure_ascii"),V(false)},{SY("separators"),V::tuple({V(","),V(":" )})},{SY("allow_nan"),V(false)}}));
   require(!fast||direct==expected_json.str(),std::string(name)+" direct JSON differs");
   V result=pm_native_snapshot_worker::f_pack_snapshot_kernel(Args{frozen_value});require(result.idx(0)==rd(pm_app::f_pack_snapshot(Args{value}),SV("data")),std::string(name)+" packed bytes differ");
   codec.push_back({{"name",name},{"fast",fast},{"bytes",expected_json.str().size()}});
  };
  V shared=V::list({V("中文🙂\n\t\r\"\\"),V::bytes(std::string("a\0b",3)),V::none(),V(true),V(-0.0)});
  compare("unicode_bytes_repeated_container",V::list({shared,shared,V::tuple({shared})}));
  compare("mapping_keys_compatibility",py_dict({{V(1),V("integer")},{V("1"),V("text")},{V::none(),V(7)}}));
  std::mt19937_64 random(743);V numbers=V::list({V(2147483647.),V(-2147483648.),V(9007199254740991.),V(1e16),V(1e-15),V(-0.)});
  for(int i=0;i<2048;++i){uint64_t bits=random();double number;std::memcpy(&number,&bits,8);if(std::isfinite(number))numbers.append(V(number));}
  compare("finite_numeric_boundaries_and_2048_random_bits",numbers);
  // Every malformed frozen prefix must fall back to the validating V codec.
  const auto sample=py::native_marshal_dumps(Args{shared}).str();size_t rejected=0;
  for(size_t n=0;n<sample.size();++n){std::string direct;require(!snapshot_json_from_marshal(sample.substr(0,n),direct),"truncated marshal accepted");++rejected;}
  for(const std::string& bytes:{sample+"junk",std::string("r\0\0\0\0",5),std::string("u\1\0\0\0\xff",6)}){std::string direct;require(!snapshot_json_from_marshal(bytes,direct),"invalid marshal accepted");++rejected;}
  auto source=battle_from_scenario({{"seed",743},{"durable_heroes",true}});
  V room=pm_room::new_Room(Args{source.bridge,getattr(source.battle,SY("rules"))});auto* host=as<pm_room::C_Room>(room);
  setitem(host->a_members,SV("guest"),SV("zombie"));setitem(host->a_connected,SV("guest"),V(true));
  host->a_decks=V::dict();for(const auto& item:py::items_vec(getattr(source.battle,SY("players"))))setitem(host->a_decks,item.first,py::list_it(rd(item.second,SV("deck"))));
  callm(room,SY("_start_battle"),Args{});host->a_phase=SV("battle");host->a_recording=V::none();host->a_match_id=SV("queue-audit");host->a_match_number=V(1);host->a_loading_id=SV("queue-audit-loading");
  typed72app::start_battle_session(host->a_battle);
  for(int i=0;i<300;++i)callm(host->a_battle,SY("spawn"),Args{V(i%10==0?"plant:抓人草":i%10==1?"plant:芦笋战机":"zombie:普通僵尸"),V(i%10<2?"plant":"zombie"),V(1700.+(i%40)*12.),V(864.-(i%3)*48.),V(i%10<2?1:-1)});
  host->a_pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});
  V snapshot=callm(room,SY("snapshot"),Args{SV("guest"),V(true)});
  require(py::m_get(rd(snapshot,SV("battle")),SV("units")).len()>=300,"dense fixture lost units");
  V frozen=py::native_marshal_dumps(Args{snapshot});V expected=pm_app::f_pack_snapshot(Args{snapshot});
  std::ofstream(std::filesystem::path(argv[1]).parent_path()/"room-payload.json",std::ios::binary)<<json(expected).dump();
  J stages=J::array();for(int i=0;i<6;++i){V result=pm_native_snapshot_worker::f_pack_snapshot_profile(Args{frozen});require(result.idx(0)==rd(expected,SV("data")),"kernel differs from ordinary pack_snapshot");stages.push_back(json(result.idx(2)));}
  worker=pm_native_snapshot_worker::new_SnapshotPackWorker(Args{SV("thread")});
  auto* w=as<pm_native_snapshot_worker::C_SnapshotPackWorker>(worker);w->a_profile_detail=V(true);
  J rounds=J::array();std::vector<double> stalls;uint64_t private_before=private_bytes(),private_peak=private_before;
  for(int round=0;round<8;++round){
   const auto begin=Clock::now();J submission=J::array();
   for(int peer=0;peer<3;++peer){const auto start=Clock::now();require(callm(worker,SY("submit"),Args{V("peer"+std::to_string(peer)),V(round),snapshot}).truthy(),"worker declined ordinary bounded batch");submission.push_back(ms(start));}
   int completed=0;J ages=J::array();
   while(completed<3){Clock::time_point reacquire;{gil::Release release;std::this_thread::sleep_for(std::chrono::milliseconds(1));reacquire=Clock::now();}stalls.push_back(ms(reacquire));private_peak=std::max(private_peak,private_bytes());
    V ready=callm(worker,SY("completed"),Args{});for(const V& row:ready.items()){require(row.idx(1)==V(round),"stale worker key");require(rd(row.idx(2),SV("data"))==rd(expected,SV("data")),"worker changed snapshot bytes");++completed;ages.push_back(ms(begin));}
    require(ms(begin)<15000,"worker stalled beyond deadline");
   }
   rounds.push_back({{"submit_ms",submission},{"completion_age_ms",ages},{"round_ms",ms(begin)}});
  }
  const J telemetry=json(w->a_telemetry);callm(worker,SY("close"),Args{});require(py::len(w->a__inflight).num()==0,"close retained frozen inputs");worker=V();
  std::sort(stalls.begin(),stalls.end());
  report={{"passed",true},{"codec_cases",codec},{"invalid_frozen_cases",rejected},{"units",300},{"peers",3},{"messages",24},{"private_before",private_before},{"private_peak",private_peak},{"frozen_bytes",frozen.str().size()},{"encoded_bytes",rd(expected,SV("data")).str().size()},{"payload_sha256",texture74::digest(rd(expected,SV("data")).str())},{"kernel_profiles",stages},{"rounds",rounds},{"main_thread_reacquire_p50_ms",stalls.at(stalls.size()/2)},{"main_thread_reacquire_p95_ms",stalls.at((stalls.size()-1)*95/100)},{"main_thread_reacquire_max_ms",stalls.back()},{"reacquire_samples",stalls.size()},{"worker_telemetry",telemetry},{"scope","Actual production worker with immutable real Room snapshots; three queued receivers, fixed battle state, no socket/simulation progression/rendering/device acceptance. Lock wait excludes Windows sleep/wakeup granularity."}};
  callm(room,SY("close"),Args{});callm(source.battle,SY("close"),Args{});
 }catch(const std::exception& e){if(worker.has())try{callm(worker,SY("close"),Args{});}catch(...){}report={{"passed",false},{"error",e.what()}};}
 std::ofstream(argv[1],std::ios::binary)<<report.dump(2);std::cout<<report.dump()<<'\n';return report.value("passed",false)?0:1;
}
