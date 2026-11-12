#include "sim/typed/room_transport.h"
#include <iostream>
#include <optional>
using namespace pvz::typed72;
namespace {
using J=WireObject;
RoomTransportOptions options(const J& j){
    RoomTransportOptions o;o.identity=j.value("identity",o.identity);o.room_code=j.value("room_code",std::string{});o.max_frame_bytes=j.value("max_frame_bytes",o.max_frame_bytes);
    o.heartbeat_interval=j.value("heartbeat",o.heartbeat_interval);o.idle_timeout=j.value("idle",o.idle_timeout);o.handshake_timeout=j.value("handshake",o.handshake_timeout);o.reconnect_timeout=j.value("reconnect",o.reconnect_timeout);o.connect_timeout=j.value("connect",o.connect_timeout);o.reconnect_delay=j.value("retry",o.reconnect_delay);
    o.spectator=j.value("spectator",false);o.allow_spectators=j.value("allow_spectators",true);o.relay_spectator=j.value("relay_spectator",false);o.request_player=j.value("request_player",false);o.max_peers=j.value("max_peers",o.max_peers);o.max_spectators=j.value("max_spectators",o.max_spectators);
    if(j.contains("session_id")&&!j["session_id"].is_null())o.session_id=j["session_id"].get<std::string>();if(j.contains("token")&&!j["token"].is_null())o.token=j["token"].get<std::string>();return o;
}
J run(const J& j,std::optional<RoomTransport>& transport){
    const auto op=j.at("op").get<std::string>();
    if(op=="init"){
        if(transport)transport->close();transport.reset();const auto o=options(j.value("options",J::object()));
        if(j.at("mode")=="server")transport=RoomTransport::server(j.value("host",std::string("127.0.0.1")),j.value("port",uint16_t(0)),o);
        else transport=RoomTransport::client(parse_room_endpoint(j.at("endpoint").get<std::string>()),o);return true;
    }
    if(op=="endpoint"){const auto e=parse_room_endpoint(j.at("value").get<std::string>(),j.value("port",uint16_t(24561)));return J::array({e.host,e.port});}
    if(!transport)throw std::logic_error("transport not initialized");
    if(op=="poll")return transport->poll(j.value("limit",size_t(100)));
    if(op=="send")return transport->send(j.value("peer",std::string("server")),j.at("payload"),j.contains("generation")?std::optional<uint64_t>(j["generation"].get<uint64_t>()):std::nullopt);
    if(op=="spectator")return transport->send_spectator(j.at("peer"),j.at("payload"),j.value("full",false));
    if(op=="generation")return transport->generation(j.value("peer",std::string("server")));
    if(op=="pending")return transport->pending_bytes(j.value("peer",std::string("server")));
    if(op=="statistics")return transport->statistics();
    if(op=="role")return transport->set_peer_role(j.at("peer"),j.at("spectator"));
    if(op=="allow_spectators"){transport->set_allow_spectators(j.at("value"));return true;}
    if(op=="max_peers"){transport->set_max_peers(j.at("value"));return true;}
    if(op=="release")return transport->release_peer(j.at("peer"));
    if(op=="reject")return transport->reject_peer(j.at("peer"),j.at("message"));
    if(op=="close"){transport->close();return true;}
    throw std::invalid_argument("unknown operation");
}
}
int main(){std::optional<RoomTransport> transport;std::string line;while(std::getline(std::cin,line))try{std::cout<<run(J::parse(line),transport).dump()<<std::endl;}catch(const std::exception& e){std::cout<<J({{"error",e.what()}}).dump()<<std::endl;}return 0;}
