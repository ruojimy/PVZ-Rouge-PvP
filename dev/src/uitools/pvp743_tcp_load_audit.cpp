// Production native transports, real TCP, an externally rate-limited peer,
// and a stalled spectator UI. The payload comes from a real dense Room fixture.
#include "pvp742_guest_memory_fixture.h"
using namespace pvz;using namespace pvz::guest_memory_audit;
using Clock=std::chrono::steady_clock;
double elapsed(Clock::time_point begin){return std::chrono::duration<double>(Clock::now()-begin).count();}
void pause(){gil::Release release;std::this_thread::sleep_for(std::chrono::milliseconds(2));}
double percentile(std::vector<double> values,double p){if(values.empty())return -1;std::sort(values.begin(),values.end());return values[size_t((values.size()-1)*p)];}
int main(int argc,char**argv){if(argc!=4)return 2;V server;std::vector<V> clients;J report;const std::string output=argv[1];const double seconds=std::stod(argv[3]);
 try{
  require(seconds>=12&&seconds<=60,"bounded test duration required");SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();pm_network::init();
  std::ifstream input(argv[2]);J source;input>>source;V packed=py::json_loads(V(source.dump()));
  V identity=py_dict({{V("protocol"),V(1)},{V("build"),V("t24-native-load")},{V("rules_hash"),V("fixture")},{V("catalog_hash"),V("fixture")}});
  server=pm_network::new_ServerTransport(Args({V("127.0.0.1"),V(0)},{{SY("identity"),identity},{SY("max_peers"),V(3)},{SY("heartbeat_interval"),V(.5)},{SY("idle_timeout"),V(15)}}));
  auto* host=as<pm_network::C_ServerTransport>(server);auto setup=Clock::now();while(host->a_address.is_none()){pause();require(elapsed(setup)<10,"server listen timeout");}
  std::ofstream(output+".server-port")<<host->a_port.num();
  int proxy_port=0;while(!proxy_port){std::ifstream ready(output+".proxy-port");ready>>proxy_port;if(proxy_port)break;pause();require(elapsed(setup)<15,"rate-limited proxy setup timeout");}
  for(int i=0;i<4;++i)clients.push_back(pm_network::new_ClientTransport(Args({V("127.0.0.1"),i==2?V(proxy_port):host->a_port},{{SY("identity"),identity},{SY("heartbeat_interval"),V(.5)},{SY("idle_timeout"),V(15)},{SY("spectator"),V(i==3)}})));
  for(const V& client:clients)while(getattr(client,SY("state"))!=V("connected")){pause();require(elapsed(setup)<25,"client handshake timeout");}
  std::vector<V> peers;for(const V& client:clients)peers.push_back(getattr(client,SY("peer_id")));
  const char* send_option=std::getenv("PVP_AUDIT_SNDBUF");const char* backlog_option=std::getenv("PVP_AUDIT_BACKLOG_BYTES");
  const int send_buffer=send_option?std::stoi(send_option):0,backlog=backlog_option?std::stoi(backlog_option):96*1024;J socket_buffers=J::array();
  V socket_module=py::stdlib_module(V("socket"));
  for(const auto& item:py::items_vec(host->a__connections)){V sock=item.first;V level=getattr(socket_module,SY("SOL_SOCKET")),option=getattr(socket_module,SY("SO_SNDBUF"));V before=callm(sock,SY("getsockopt"),Args{level,option});if(send_buffer)callm(sock,SY("setsockopt"),Args{level,option,V(send_buffer)});socket_buffers.push_back({{"before",before.num()},{"after",callm(sock,SY("getsockopt"),Args{level,option}).num()}});}
  report["socket_send_buffers"]=socket_buffers;
  std::vector<int> snapshots(4),last_tick(4,-1),skips(4),commands(4),acks(4);std::vector<std::vector<double>> ages(4),rtts(4);std::vector<double> pending_peak(4);J errors=J::array();
  uint64_t private_before=private_bytes(),private_peak=private_before;auto begin=Clock::now();double publish=0,command=0;int tick=0;double spectator_event_peak=0;
  auto consume=[&](int i,double now){
   V events=callm(clients[i],SY("poll"),Args{V(4096)});
   for(const V& event:events.items()){
    V type=py::m_get(event,V("type"));if(type==V("error")||type==V("disconnected"))errors.push_back(json(event));
    if(type!=V("message"))continue;V payload=rd(event,V("payload"));V kind=py::m_get(payload,V("type"));
    if(kind==V("room_snapshot")){int current=int(rd(payload,V("audit_tick")).num());require(current>last_tick[i],"snapshot tick regressed");last_tick[i]=current;++snapshots[i];ages[i].push_back(now*1000-rd(payload,V("audit_emitted_ms")).num());}
    else if(kind==V("audit_ack")){require(rd(payload,V("seq"))==V(++acks[i]),"command ACK lost or reordered");rtts[i].push_back(now*1000-rd(payload,V("sent_ms")).num());}
   }
  };
  auto service_host=[&]{V host_events=callm(server,SY("poll"),Args{V(4096)});for(const V& event:host_events.items()){V type=py::m_get(event,V("type"));if(type==V("error")||type==V("disconnected"))errors.push_back(json(event));if(type!=V("message"))continue;V payload=rd(event,V("payload"));if(py::m_get(payload,V("type"))==V("audit_input")){setitem(payload,V("type"),V("audit_ack"));require(callm(server,SY("send"),Args{rd(event,V("peer_id")),payload}).truthy(),"native ACK admission failed");}}};
  while(elapsed(begin)<seconds){double now=elapsed(begin);
   if(now>=publish){publish=now+.05;++tick;for(int i=0;i<4;++i){double pending=callm(server,SY("pending_bytes"),Args{peers[i]}).num();pending_peak[i]=std::max(pending_peak[i],pending);if(i<3&&pending>backlog){++skips[i];continue;}
     V payload=py::json_loads(V(source.dump()));setitem(payload,V("audit_tick"),V(tick));setitem(payload,V("audit_emitted_ms"),V(now*1000));setitem(payload,V("snapshot_stream"),V::list({V("dense-300"),V("battle"),V(1)}));setitem(payload,V("map_included"),V(tick==1));
     bool sent=i==3?callm(server,SY("send_spectator"),Args{peers[i],payload,V(tick==1)}).truthy():callm(server,SY("send"),Args{peers[i],payload}).truthy();if(!sent)++skips[i];
   }}
   if(now>=command){command=now+.5;for(int i=0;i<3;++i){V message=py_dict({{V("type"),V("audit_input")},{V("seq"),V(++commands[i])},{V("sent_ms"),V(now*1000)}});require(callm(clients[i],SY("send"),Args{message}).truthy(),"native input admission failed");}}
   service_host();
   for(int i=0;i<4;++i)if(i!=3||now<3||now>8)consume(i,now);
   spectator_event_peak=std::max(spectator_event_peak,as<pm_network::C_ClientTransport>(clients[3])->a__event_bytes.num());private_peak=std::max(private_peak,private_bytes());pause();
  }
  // Drain the bounded slow lane so command receipt is an actual observation.
  auto tail=Clock::now();while(elapsed(tail)<12){service_host();bool done=true;for(int i=0;i<4;++i){consume(i,elapsed(begin));if(i<3&&acks[i]!=commands[i])done=false;}if(done)break;pause();}
  J rows=J::array();for(int i=0;i<4;++i){rows.push_back({{"peer",i},{"role",i==3?"spectator":i==2?"rate_limited_player":"player"},{"snapshots",snapshots[i]},{"last_tick",last_tick[i]},{"backlog_skips",skips[i]},{"snapshot_age_p50_ms",percentile(ages[i],.5)},{"snapshot_age_p95_ms",percentile(ages[i],.95)},{"snapshot_age_max_ms",percentile(ages[i],1)},{"input_acks",acks[i]},{"input_commands",commands[i]},{"input_rtt_p95_ms",percentile(rtts[i],.95)},{"pending_bytes_peak",pending_peak[i]},{"transport",json(callm(clients[i],SY("statistics"),Args{}))}});}
  report={{"passed",true},{"duration_seconds",seconds},{"socket_send_buffers",socket_buffers},{"test_send_buffer_override",send_buffer},{"test_backlog_bytes",backlog},{"offered_ticks",tick},{"payload_bytes",source.dump().size()},{"peers",rows},{"private_before",private_before},{"private_peak",private_peak},{"spectator_event_peak_bytes",spectator_event_peak},{"host_transport",json(callm(server,SY("statistics"),Args{}))},{"scope","Actual native TCP transports; fixed real 300-unit Room payload; three player peers, one rate-limited proxy lane, and a spectator UI paused for five seconds. Does not measure simulation/rendering/device/WAN capacity."}};
  for(int i=0;i<4;++i){require(snapshots[i]>=3,"receiver did not receive snapshots");if(i<3)require(acks[i]==commands[i],"input acknowledgements incomplete");}
  require(errors.empty(),"transport error/disconnect: "+errors.dump());require(pending_peak[0]<256*1024&&pending_peak[1]<256*1024,"fast peers inherited slow peer backlog");
 }catch(const std::exception&e){report["passed"]=false;report["error"]=e.what();}
 for(auto& client:clients)try{callm(client,SY("close"),Args{});}catch(...){}if(server.has())try{callm(server,SY("close"),Args{});}catch(...){}
 std::ofstream(output,std::ios::binary)<<report.dump(2);std::cout<<report.dump()<<'\n';return report.value("passed",false)?0:1;
}
