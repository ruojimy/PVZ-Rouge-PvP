#pragma once
#include "sim/typed/room_transport_queue.h"
#include <memory>
namespace pvz::typed72 {
struct RoomTransportOptions {
    WireObject identity={{"protocol",1},{"build","development"},{"rules_hash",""}};
    std::string room_code;
    size_t max_frame_bytes=1024*1024;
    double heartbeat_interval=2.,idle_timeout=8.,handshake_timeout=5.,reconnect_timeout=20.,connect_timeout=5.,reconnect_delay=.5;
    bool spectator=false,allow_spectators=true,relay_spectator=false,request_player=false;
    size_t max_peers=1,max_spectators=4;
    std::optional<std::string> session_id,token;
};
struct RoomEndpoint {std::string host;uint16_t port=24561;};
RoomEndpoint parse_room_endpoint(std::string_view endpoint,uint16_t default_port=24561);
// Sockets, DNS, handshakes and reconnect run on the owned native worker.
// Only these immutable JSON messages cross the I/O boundary; simulation
// commands are decoded once by CommandCodec on the room owner thread.
class RoomTransport {
public:
    static RoomTransport server(std::string host,uint16_t port,RoomTransportOptions={});
    static RoomTransport client(RoomEndpoint,RoomTransportOptions={});
    RoomTransport(RoomTransport&&)noexcept=default;
    RoomTransport& operator=(RoomTransport&&)noexcept;
    ~RoomTransport();
    bool send(const std::string&,const WireObject&,std::optional<uint64_t> generation={});
    bool send_spectator(const std::string&,const WireObject&,bool full_snapshot=false);
    std::vector<WireObject> poll(size_t limit=100);
    uint64_t generation(const std::string&)const;
    size_t pending_bytes(const std::string&)const;
    WireObject statistics()const;
    void set_max_peers(size_t);
    void set_allow_spectators(bool);
    std::string set_peer_role(const std::string&,bool);
    bool release_peer(const std::string&);
    bool reject_peer(const std::string&,std::string message);
    void close();
private:
    struct Impl;std::shared_ptr<Impl> impl_;
    explicit RoomTransport(std::shared_ptr<Impl> impl):impl_(std::move(impl)){}
};
} // namespace pvz::typed72
