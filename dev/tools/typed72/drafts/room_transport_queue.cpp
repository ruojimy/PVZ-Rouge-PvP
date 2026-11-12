#include "sim/typed/room_transport_queue.h"
#include <algorithm>
#include <stdexcept>
namespace pvz::typed72 {
namespace {
std::string raw(const WireObject& value,size_t maximum){const auto bytes=encode_room_frame(value,maximum);return std::string(bytes.begin()+4,bytes.end());}
RoomWireEvent event_view(const WireObject& v){return {v.value("type",std::string{}),v.value("peer_id",std::string{}),v.value("payload",WireObject::object())};}
}
bool RoomTransportQueues::send(const std::string& peer,const WireObject& payload,std::optional<uint64_t> generation){
    auto bytes=raw(payload,maximum_-128);std::lock_guard lock(mutex_);
    const auto current=generations_.find(peer);const uint64_t value=current==generations_.end()?0:current->second;
    if(stopped||!ready_.contains(peer)||(generation&&*generation!=value)||command_bytes_+bytes.size()>maximum_*4||commands_.size()>=256)return false;
    command_bytes_+=bytes.size();peer_bytes_[peer]+=bytes.size();commands_.push_back({peer,std::move(bytes),value});
    metrics_.command_bytes_peak=std::max(metrics_.command_bytes_peak,command_bytes_);metrics_.command_items_peak=std::max(metrics_.command_items_peak,commands_.size());return true;
}
bool RoomTransportQueues::spectator(const std::string& peer,const WireObject& payload,bool full){
    auto bytes=raw(payload,maximum_-128);std::lock_guard lock(mutex_);
    if(stopped||!ready_.contains(peer)||!roles_[peer])return false;
    auto it=std::find_if(spectator_.begin(),spectator_.end(),[&](const auto& p){return p.peer==peer;});
    if(it!=spectator_.end()){if(it->full&&!full)return false;it->raw=std::move(bytes);it->full=it->full||full;}
    else spectator_.push_back({peer,std::move(bytes),full});return true;
}
void RoomTransportQueues::ready(const std::string& peer,bool value){std::lock_guard lock(mutex_);if(ready_.contains(peer)!=value)++generations_[peer];if(value)ready_.insert(peer);else ready_.erase(peer);}
void RoomTransportQueues::role(const std::string& peer,bool spectator){std::lock_guard lock(mutex_);roles_[peer]=spectator;std::erase_if(spectator_,[&](const auto& p){return p.peer==peer;});}
void RoomTransportQueues::erase_peer(const std::string& peer){std::lock_guard lock(mutex_);roles_.erase(peer);output_bytes_.erase(peer);std::erase_if(spectator_,[&](const auto& p){return p.peer==peer;});}
uint64_t RoomTransportQueues::generation(const std::string& peer)const{std::lock_guard lock(mutex_);const auto it=generations_.find(peer);return it==generations_.end()?0:it->second;}
bool RoomTransportQueues::is_spectator(const std::string& peer)const{std::lock_guard lock(mutex_);const auto it=roles_.find(peer);return it!=roles_.end()&&it->second;}
size_t RoomTransportQueues::pending(const std::string& peer)const{std::lock_guard lock(mutex_);size_t total=0;for(const auto* map:{&peer_bytes_,&output_bytes_})if(const auto it=map->find(peer);it!=map->end())total+=it->second;for(const auto& p:spectator_)if(p.peer==peer)total+=p.raw.size();return total;}
void RoomTransportQueues::uncharge(const Command& c){command_bytes_-=c.raw.size();auto it=peer_bytes_.find(c.peer);if(it!=peer_bytes_.end()){if(it->second>c.raw.size())it->second-=c.raw.size();else peer_bytes_.erase(it);}}
std::vector<RoomTransportCommand> RoomTransportQueues::take_commands(){
    std::vector<Command> commands;std::vector<Pending> spectator;
    {std::lock_guard lock(mutex_);for(size_t i=0;i<64&&!commands_.empty();++i){auto c=std::move(commands_.front());commands_.pop_front();uncharge(c);if(c.generation==generations_[c.peer])commands.push_back(std::move(c));}spectator.swap(spectator_);}
    std::vector<RoomTransportCommand> result;result.reserve(commands.size()+spectator.size());for(auto& c:commands)result.push_back({std::move(c.peer),WireObject::parse(c.raw)});for(auto& c:spectator)result.push_back({std::move(c.peer),WireObject::parse(c.raw)});return result;
}
void RoomTransportQueues::discard_commands(){std::lock_guard lock(mutex_);commands_.clear();command_bytes_=0;peer_bytes_.clear();}
void RoomTransportQueues::emit(WireObject value){
    const auto size=value.dump(-1,' ',true).size();std::lock_guard lock(mutex_);
    if(!events_.empty()&&supersedes_room_snapshot(event_view(value),event_view(events_.back().value))&&event_bytes_-events_.back().bytes+size<=maximum_*8){
        event_bytes_=event_bytes_-events_.back().bytes+size;events_.back()={std::move(value),size};++metrics_.coalesced_snapshots;
    }else if(events_.size()>=4096||event_bytes_+size>maximum_*8){
        events_.clear();events_.push_back({{{"type","error"},{"code","event_queue_full"},{"detail","application did not consume network events"}},128});event_bytes_=128;stopped=true;
    }else{events_.push_back({std::move(value),size});event_bytes_+=size;}
    metrics_.event_bytes_peak=std::max(metrics_.event_bytes_peak,event_bytes_);metrics_.event_items_peak=std::max(metrics_.event_items_peak,events_.size());
}
std::vector<WireObject> RoomTransportQueues::poll(size_t limit){if(!limit)throw std::invalid_argument("poll limit must be a positive integer");std::lock_guard lock(mutex_);std::vector<WireObject> result;for(size_t i=0;i<std::min(limit,size_t(4096))&&!events_.empty();++i){event_bytes_-=events_.front().bytes;result.push_back(std::move(events_.front().value));events_.pop_front();}return result;}
void RoomTransportQueues::close(){stopped=true;std::lock_guard lock(mutex_);ready_.clear();}
void RoomTransportQueues::received(size_t bytes,size_t retained){std::lock_guard lock(mutex_);metrics_.received_bytes+=bytes;metrics_.receive_block_peak=std::max(metrics_.receive_block_peak,bytes);metrics_.decoder_retained_peak=std::max(metrics_.decoder_retained_peak,retained);}
void RoomTransportQueues::sent(size_t bytes){std::lock_guard lock(mutex_);metrics_.sent_bytes+=bytes;}
void RoomTransportQueues::output(const std::string& peer,size_t bytes){std::lock_guard lock(mutex_);output_bytes_[peer]=bytes;metrics_.socket_output_peak=std::max(metrics_.socket_output_peak,bytes);}
void RoomTransportQueues::control_size(size_t size){std::lock_guard lock(mutex_);metrics_.control_items_peak=std::max(metrics_.control_items_peak,size);}
void RoomTransportQueues::control_overflow(){{std::lock_guard lock(mutex_);++metrics_.control_overflows;}emit({{"type","error"},{"code","control_queue_full"},{"detail","Connection control queue exceeded its bounded capacity"}});stopped=true;}
WireObject RoomTransportQueues::statistics()const{
    std::lock_guard lock(mutex_);const auto& m=metrics_;
    return {{"received_bytes",m.received_bytes},{"sent_bytes",m.sent_bytes},{"receive_block_peak",m.receive_block_peak},{"decoder_retained_peak",m.decoder_retained_peak},{"socket_output_peak",m.socket_output_peak},{"command_bytes_peak",m.command_bytes_peak},{"event_bytes_peak",m.event_bytes_peak},{"command_items_peak",m.command_items_peak},{"event_items_peak",m.event_items_peak},{"control_items_peak",m.control_items_peak},{"control_overflows",m.control_overflows},{"coalesced_snapshots",m.coalesced_snapshots},
        {"queued_command_bytes",command_bytes_},{"peer_command_bytes",peer_bytes_},{"command_items",commands_.size()},{"event_bytes",event_bytes_},{"event_items",events_.size()},
        {"available",true},{"scope","This process application transport; excludes public relay process RSS/buffers"},{"max_frame_bytes",maximum_},{"command_bytes_limit",maximum_*4},{"event_bytes_limit",maximum_*8},{"command_item_limit",256},{"event_item_limit",4096},{"socket_output_limit_per_connection",maximum_*4},{"control_item_limit_per_queue",256},{"receive_block_limit",65536}};
}
} // namespace pvz::typed72
