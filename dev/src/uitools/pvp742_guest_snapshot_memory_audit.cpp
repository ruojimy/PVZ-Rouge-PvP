#include "pvp742_guest_memory_fixture.h"
using namespace pvz;using J=nlohmann::json;using namespace pvz::guest_memory_audit;
int main(int argc,char** argv){
 if(argc<3)return 2;
 const auto output=std::filesystem::absolute(u8p(argv[1]));std::filesystem::create_directories(output.parent_path());
 const std::string mode=argv[2];const size_t iterations=argc>3?std::stoull(argv[3]):128,units=argc>4?std::stoull(argv[4]):200;
 J report;bool tracing=false;
 try{
  require(mode=="same_wire"||mode=="cross_wire","invalid workload");require(iterations>=64&&iterations<=200&&units>=10&&units<=300,"bounded workload is 64..200 messages, 10..300 units");
  env_set_u8("PVP_USERDATA",p8(output.parent_path()/u8p(output.stem().string()+"-userdata")));env_set_u8("SDL_VIDEODRIVER","dummy");env_set_u8("SDL_AUDIODRIVER","dummy");
  SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();(void)callm(pg::pygame_module(),SY("init"),Args{});init_pvp_modules();pm_network::init();
  auto source=battle_from_scenario({{"seed",742},{"decks",{{"plant",{"plant:向日葵","plant:豌豆射手","plant:抓人草","plant:芦笋战机"}},{"zombie",{"zombie:脑光墓碑","zombie:普通僵尸"}}}}});
  V room=pm_room::new_Room(Args{source.bridge,getattr(source.battle,SY("rules"))});auto* host=as<pm_room::C_Room>(room);
  setitem(host->a_members,SV("guest"),SV("zombie"));setitem(host->a_connected,SV("guest"),V(true));
  host->a_decks=V::dict();for(const auto& item:py::items_vec(getattr(source.battle,SY("players"))))setitem(host->a_decks,item.first,py::list_it(rd(item.second,SV("deck"))));
  callm(room,SY("_start_battle"),Args{});host->a_phase=SV("battle");host->a_recording=V::none();host->a_match_id=SV("snapshot-memory-audit");host->a_match_number=V(1);host->a_loaded=py_dict({{SV("plant"),V(true)},{SV("zombie"),V(true)}});
  typed72app::start_battle_session(host->a_battle);
  for(size_t i=0;i<units;++i){const char* card=i%10==0?"plant:抓人草":i%10==1?"plant:芦笋战机":"zombie:普通僵尸";callm(host->a_battle,SY("spawn"),Args{V(card),V(i%10<2?"plant":"zombie"),V(1700.+double(i%40)*12.),V(864.-double(i%3)*48.),V(i%10<2?1:-1)});}
  callm(room,SY("update"),Args{V(.04)});
  // Fixed input across independent processes: remove setup-only CPU sampling
  // and an opaque loading nonce, before constructing the shared test payload.
  host->a_pacing=pm_adaptive_pacing::new_AdaptivePacing(Args{});host->a_loading_id=SV("snapshot-memory-loading");
  V full=callm(room,SY("snapshot"),Args{SV("guest"),V(true)}),periodic=callm(room,SY("snapshot"),Args{SV("guest"),V(false)});
  const size_t actual_units=py::m_get(rd(periodic,SV("battle")),SV("units")).len();require(actual_units>=units,"snapshot lost source actors");
  V full_payload=pm_app::f_pack_snapshot(Args{full}),periodic_payload=pm_app::f_pack_snapshot(Args{periodic});
  constexpr size_t warm=8;std::vector<std::string> frames;frames.reserve(warm+iterations);
  for(size_t i=0;i<warm+iterations;++i)frames.push_back(py::bytes_data(pm_network::f_encode_frame(Args{py_dict({{SV("type"),SV("data")},{SV("seq"),V(double(i+1))},{SV("payload"),i?periodic_payload:full_payload}})})));
  const auto payload_hash=texture74::digest(json(periodic).dump());const size_t raw_bytes=json(periodic).dump().size();
  V pygame=pg::pygame_module(),screen=pg::new_surface(1280,720,true),app=pm_app::new_Application(Args{pygame,screen,source.bridge});auto* guest=as<pm_app::C_Application>(app);
  guest->a_mode=SV("guest");guest->a_peer_id=SV("guest");guest->a_game_audio=V::none();setitem(guest->a_state,SV("focused"),V(false));setitem(guest->a_state,SV("screen"),SV("room"));
  Receiver receiver;guest->a_transport=receiver.transport;std::unique_ptr<Channel> channel;
  if(mode=="same_wire")receiver.open();else channel=std::make_unique<Channel>(receiver,frames);
  auto deliver=[&](size_t index){if(channel)channel->produce(index);else receiver.produce(frames.at(index));
   callm(app,SY("poll_network"),Args({V(0)},{{SY("publish"),V(false)}}));
   require(!py::m_get(guest->a_state,SV("map_sync_error"),V(false)).truthy(),"actual guest map validation failed");require(py::m_get(guest->a_view,SV("phase"))==SV("battle"),"guest did not retain legal battle view");
   require(receiver.client->a__event_bytes.num()==0,"network queue was not drained");
  };
  for(size_t i=0;i<warm;++i)deliver(i);
  const auto expected_view=json(guest->a_view).dump();const auto expected_hash=texture74::digest(expected_view);std::string final_hash=expected_hash;bool final_equal=false;
  std::vector<Sample> samples;samples.reserve(iterations+4);const auto initial_small=native_small_allocator_stats();const uint64_t initial_private=private_bytes();const auto started=std::chrono::steady_clock::now();
  native_alloc_trace_start();tracing=true;size_t completed=0;bool stopped=false;
  auto sample=[&](const char* phase){Sample s;s.phase=phase;s.completed=completed;native_alloc_trace_read(s.live,s.peak);s.private_memory=private_bytes();s.small=native_small_allocator_stats();s.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();samples.push_back(s);native_alloc_trace_reset_peak();};sample("baseline");
  for(size_t i=0;i<iterations;++i){deliver(warm+i);++completed;sample("message");if(samples.back().private_memory>=initial_private+256ull*1024*1024){stopped=true;break;}}
  const auto held=samples.back();const auto last_sequence=receiver.client->a__in_seq.num();const size_t decoder_bytes=size_t(py::len(getattr(getattr(receiver.connection,SY("decoder")),SY("buffer"))).num());
  require(last_sequence==double(warm+completed),"receiver did not accept every framed sequence");
  // Verification temporaries die before the release samples. The persistent
  // digest buffer was reserved before tracing; exclude this verifier's peak.
  {const auto view=json(guest->a_view).dump();final_hash=texture74::digest(view);final_equal=view==expected_view;}native_alloc_trace_reset_peak();require(final_equal,"repeated snapshot changed the final guest view");
  callm(app,SY("close_room"),Args({},{{SY("graceful"),V(false)}}));sample("after_room_close");
  if(channel)channel->finish();else receiver.close();sample("after_receiver_exit");
  uint64_t final_live=0,final_peak=0;native_alloc_trace_read(final_live,final_peak);native_alloc_trace_stop();tracing=false;
  J rows=J::array();for(const auto& s:samples)rows.push_back({{"phase",s.phase},{"completed",s.completed},{"wall_seconds",s.seconds},{"requested_live_bytes",s.live},{"requested_batch_peak_bytes",s.peak},{"private_bytes",s.private_memory},{"allocator",allocator(s.small)}});
  const auto final_small=native_small_allocator_stats();
  report={{"passed",true},{"mode",mode},{"production_thread_placement",mode=="cross_wire"},{"allocator",initial_small.legacy?0:1},{"requested_messages",iterations},{"completed_messages",completed},{"warm_messages",warm},{"units",actual_units},{"queue_window",1},{"private_growth_cap_bytes",256ull*1024*1024},{"stopped_at_memory_cap",stopped},{"private_bytes_before",initial_private},{"private_bytes_after",private_bytes()},{"slab_bytes_added",final_small.slab_bytes-initial_small.slab_bytes},{"requested_held_view_bytes",held.live},{"requested_final_live_bytes",final_live},{"requested_final_batch_peak_bytes",final_peak},{"allocator_before",allocator(initial_small)},{"allocator_after",allocator(final_small)},{"snapshot_raw_bytes",raw_bytes},{"wire_frame_bytes",frames.back().size()},{"snapshot_sha256",payload_hash},{"expected_view_sha256",expected_hash},{"final_view_sha256",final_hash},{"final_snapshot_equal",final_equal},{"last_wire_sequence",last_sequence},{"decoder_retained_bytes",decoder_bytes},{"transport_statistics",json(callm(receiver.transport,SY("statistics"),Args{}))},{"samples",rows},{"scope","Real Room snapshot -> pack_snapshot -> encode_frame -> queued recv -> ClientTransport._read -> FrameDecoder -> _data/_emit -> Application.poll_network -> unpack_snapshot -> merge_view. cross_wire preserves the real receiver/UI thread split; same_wire runs the identical path on the UI thread as a control. No sockets, rendering, user saves, simulation progression during repetitions, or unbounded queue."}};
  callm(room,SY("close"),Args{});callm(source.battle,SY("close"),Args{});
 }catch(const std::exception& e){if(tracing)native_alloc_trace_stop();report={{"passed",false},{"mode",mode},{"error",e.what()}};}
 std::ofstream(output,std::ios::binary)<<report.dump(2);std::cout<<J{{"passed",report.value("passed",false)},{"mode",mode},{"completed_messages",report.value("completed_messages",size_t(0))},{"private_bytes_before",report.value("private_bytes_before",uint64_t(0))},{"private_bytes_after",report.value("private_bytes_after",uint64_t(0))},{"slab_bytes_added",report.value("slab_bytes_added",uint64_t(0))},{"error",report.value("error",std::string{})}}.dump()<<'\n';return report.value("passed",false)?0:1;
}
