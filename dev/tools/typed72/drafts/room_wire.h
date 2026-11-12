#pragma once
#include <nlohmann/json.hpp>
#include <cstdint>
#include <deque>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace pvz::typed72 {
using WireObject=nlohmann::ordered_json;
class RoomFrameDecoder {
public:
    explicit RoomFrameDecoder(size_t max_frame_bytes=1024*1024):maximum_(max_frame_bytes){}
    std::vector<WireObject> feed(std::span<const uint8_t>);
    size_t retained_bytes()const{return buffer_.size();}
private:
    size_t maximum_;std::vector<uint8_t> buffer_;
};
std::vector<uint8_t> encode_room_frame(const WireObject&,size_t max_frame_bytes=1024*1024);
struct RoomWireEvent {
    std::string type,peer;
    WireObject payload;
};
bool supersedes_room_snapshot(const RoomWireEvent& newer,const RoomWireEvent& older);
bool valid_latency_payload(const WireObject&);
struct RoomLatencyBucket {
    std::optional<double> sampled;
    double tokens=4.;
    bool allow(const WireObject&,double now);
};
} // namespace pvz::typed72
