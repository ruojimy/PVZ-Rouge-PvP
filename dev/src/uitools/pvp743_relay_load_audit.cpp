// One private, bounded native relay session. Never records room credentials.
#include "pvp742_guest_memory_fixture.h"
#include "ui/gen/pm_relay.h"
using namespace pvz;using namespace pvz::guest_memory_audit;
using Clock=std::chrono::steady_clock;
double seconds(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}
void relax(){gil::Release release;std::this_thread::sleep_for(std::chrono::milliseconds(2));}
double percentile(std::vector<double> values,double p){if(values.empty())return -1;std::sort(values.begin(),values.end());return values[size_t((values.size()-1)*p)];}
int main(int argc,char**argv){if(argc!=4)return 2;V server,client;J report;try{
 SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();pm_relay::init();
 std::ifstream input(argv[2]);J source;input>>source;V expected=py::json_loads(V(source.dump()));
 V identity=py_dict({{V("protocol"),V(1)},{V("build"),V("t24-native-private-probe")},{V("rules_hash"),V("fixture")},{V("catalog_hash"),V("fixture")}});
 server=pm_relay::new_RelayHostTransport(Args({V(argv[3])},{{SY("identity"),identity},{SY("public"),V(false)},{SY("allow_spectators"),V(false)},{SY("max_spectators"),V(1)},{SY("heartbeat_interval"),V(.5)},{SY("idle_timeout"),V(15)}}));
 auto* relay=as<pm_relay::C_RelayHostTransport>(server);auto setup=Clock::now();
 auto check_errors=[&](const V& transport){V events=callm(transport,SY("poll"),Args{V(4096)});for(const V& event:events.items())if(py::m_get(event,V("type"))==V("error"))throw std::runtime_error("relay error code: "+py_str(py::m_get(event,V("code"))));return events;};
 while(relay->a_code.is_none()){check_errors(server);relax();require(seconds(setup)<15,"private relay registration timeout");}
 client=pm_relay::new_RelayClientTransport(Args({V(argv[3])},{{SY("identity"),identity},{SY("room_code"),relay->a_code},{SY("heartbeat_interval"),V(.5)},{SY("idle_timeout"),V(15)}}));
 while(getattr(client,SY("state"))!=V("connected")){check_errors(server);check_errors(client);relax();require(seconds(setup)<30,"private relay handshake timeout");}
 V peer=getattr(client,SY("peer_id")),inner=relay->a_inner;int offered=0,received=0,commands=0,acks=0,skips=0,last=0;std::vector<double> ages,rtts;J transport_errors=J::array();uint64_t private_before=private_bytes(),private_peak=private_before;auto start=Clock::now();double next_snapshot=0,next_input=0;
 auto service=[&]{double now=seconds(start);
  V host_events=check_errors(server);for(const V& event:host_events.items())if(py::m_get(event,V("type"))==V("message")){V payload=rd(event,V("payload"));if(py::m_get(payload,V("type"))==V("audit_input")){setitem(payload,V("type"),V("audit_ack"));require(callm(inner,SY("send"),Args{peer,payload}).truthy(),"relay ACK admission failed");}}
  V client_events=check_errors(client);for(const V& event:client_events.items())if(py::m_get(event,V("type"))==V("message")){V payload=rd(event,V("payload"));V kind=py::m_get(payload,V("type"));if(kind==V("room_snapshot")){int tick=int(rd(payload,V("audit_tick")).num());require(tick>last,"relay snapshot order changed");last=tick;require(rd(payload,V("data"))==rd(expected,V("data")),"relay snapshot bytes changed");if(!received)require(json(pm_app::f_unpack_snapshot(Args{payload}))==json(pm_app::f_unpack_snapshot(Args{expected})),"native receiver decoded different Room state");++received;ages.push_back(now*1000-rd(payload,V("audit_emitted_ms")).num());}else if(kind==V("audit_ack")){require(rd(payload,V("seq"))==V(++acks),"relay command ACK order changed");rtts.push_back(now*1000-rd(payload,V("sent_ms")).num());}}
 };
 while(seconds(start)<20){double now=seconds(start);if(now>=next_snapshot){next_snapshot=now+.2;double pending=callm(inner,SY("pending_bytes"),Args{peer}).num();if(pending>96*1024)++skips;else{V payload=py::json_loads(V(source.dump()));setitem(payload,V("audit_tick"),V(++offered));setitem(payload,V("audit_emitted_ms"),V(now*1000));setitem(payload,V("snapshot_stream"),V::list({V("private-dense-room"),V("battle"),V(1)}));setitem(payload,V("map_included"),V(offered==1));require(callm(inner,SY("send"),Args{peer,payload}).truthy(),"relay snapshot admission failed");}}
  if(now>=next_input){next_input=now+.5;require(callm(client,SY("send"),Args{py_dict({{V("type"),V("audit_input")},{V("seq"),V(++commands)},{V("sent_ms"),V(now*1000)}})}).truthy(),"relay input admission failed");}service();private_peak=std::max(private_peak,private_bytes());relax();}
 auto tail=Clock::now();while((acks<commands||last<offered)&&seconds(tail)<8){service();relax();}
 report={{"passed",true},{"public_room",false},{"server_configuration_changed",false},{"duration_seconds",20},{"target_snapshot_hz",5},{"offered",offered},{"received",received},{"final_tick",last},{"backlog_skips",skips},{"commands",commands},{"acks",acks},{"snapshot_age_p50_ms",percentile(ages,.5)},{"snapshot_age_p95_ms",percentile(ages,.95)},{"input_rtt_p95_ms",percentile(rtts,.95)},{"private_before",private_before},{"private_peak",private_peak},{"host_transport",json(callm(inner,SY("statistics"),Args{}))},{"client_transport",json(callm(client,SY("statistics"),Args{}))},{"scope","Actual native RelayHostTransport/RelayClientTransport and bounded snapshot decode through one private public-cloud lane. Fixed real 300-unit Room snapshot at bounded 5Hz; both endpoints on this PC; not physical-device or server-capacity acceptance."}};
 require(acks==commands&&last==offered&&received>=80,"private relay completion denominator not met");
 }catch(const std::exception&e){report["passed"]=false;report["error"]=e.what();}
 if(client.has())try{callm(client,SY("close"),Args{});}catch(...){}if(server.has())try{callm(server,SY("close"),Args{});}catch(...){}
 std::ofstream(argv[1],std::ios::binary)<<report.dump(2);std::cout<<report.dump()<<'\n';return report.value("passed",false)?0:1;
}
