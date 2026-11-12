#pragma once
#include "sim/typed/room_wire.h"
#include <atomic>
#include <map>
#include <mutex>
#include <set>
#include <unordered_map>
namespace pvz::typed72 {
struct RoomTransportMetrics {
    size_t received_bytes=0,sent_bytes=0,receive_block_peak=0,decoder_retained_peak=0,socket_output_peak=0;
    size_t command_bytes_peak=0,event_bytes_peak=0,command_items_peak=0,event_items_peak=0;
    size_t control_items_peak=0,control_overflows=0,coalesced_snapshots=0;
};
struct RoomTransportCommand {std::string peer;WireObject payload;};
// Owns only cold transport messages. A queue never retains NativeWorld or V.
class RoomTransportQueues {
public:
    explicit RoomTransportQueues(size_t maximum):maximum_(maximum){}
    std::atomic<bool> stopped=false;
    bool send(const std::string&,const WireObject&,std::optional<uint64_t> generation={});
    bool spectator(const std::string&,const WireObject&,bool full);
    void ready(const std::string&,bool);
    void role(const std::string&,bool);
    void erase_peer(const std::string&);
    uint64_t generation(const std::string&)const;
    bool is_spectator(const std::string&)const;
    size_t pending(const std::string&)const;
    std::vector<RoomTransportCommand> take_commands();
    void discard_commands();
    void emit(WireObject);
    std::vector<WireObject> poll(size_t limit=100);
    void close();
    WireObject statistics()const;
    void received(size_t block,size_t retained);
    void sent(size_t bytes);
    void output(const std::string&,size_t bytes);
    void control_size(size_t);
    void control_overflow();
private:
    struct Command {std::string peer,raw;uint64_t generation;};
    struct Event {WireObject value;size_t bytes;};
    struct Pending {std::string peer,raw;bool full;};
    size_t maximum_,command_bytes_=0,event_bytes_=0;
    mutable std::mutex mutex_;
    std::deque<Command> commands_;
    std::deque<Event> events_;
    std::vector<Pending> spectator_;
    std::set<std::string> ready_;
    std::unordered_map<std::string,uint64_t> generations_;
    std::unordered_map<std::string,size_t> peer_bytes_,output_bytes_;
    std::unordered_map<std::string,bool> roles_;
    RoomTransportMetrics metrics_;
    void uncharge(const Command&);
};
} // namespace pvz::typed72
