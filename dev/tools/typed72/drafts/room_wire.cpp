#include "sim/typed/room_wire.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace pvz::typed72 {
namespace {
void finite_json(const WireObject& value){
    if(value.is_number_float()&&!std::isfinite(value.get<double>()))throw std::invalid_argument("non-finite JSON number");
    if(value.is_structured())for(const auto& child:value)finite_json(child);
}
}
std::vector<uint8_t> encode_room_frame(const WireObject& value,size_t maximum){
    if(!value.is_object())throw std::invalid_argument("message must be a JSON object");
    finite_json(value);const auto raw=value.dump(-1,' ',false,WireObject::error_handler_t::strict);
    if(raw.empty()||raw.size()>maximum||raw.size()>std::numeric_limits<uint32_t>::max())throw std::length_error("message exceeds frame limit");
    const auto size=uint32_t(raw.size());std::vector<uint8_t> result;result.reserve(raw.size()+4);
    for(int shift:{24,16,8,0})result.push_back(uint8_t(size>>shift));result.insert(result.end(),raw.begin(),raw.end());return result;
}
std::vector<WireObject> RoomFrameDecoder::feed(std::span<const uint8_t> data){
    if(data.size()>maximum_&&data.size()-maximum_>65540)throw std::length_error("input chunk exceeds limit");
    buffer_.insert(buffer_.end(),data.begin(),data.end());std::vector<WireObject> result;size_t offset=0;
    while(buffer_.size()-offset>=4){
        const auto size=(uint32_t(buffer_[offset])<<24)|(uint32_t(buffer_[offset+1])<<16)|(uint32_t(buffer_[offset+2])<<8)|uint32_t(buffer_[offset+3]);
        if(size==0||size>maximum_)throw std::length_error("invalid frame length");
        if(buffer_.size()-offset-4<size)break;
        auto value=WireObject::parse(buffer_.begin()+offset+4,buffer_.begin()+offset+4+size);
        if(!value.is_object())throw std::invalid_argument("frame must contain a JSON object");
        finite_json(value);result.push_back(std::move(value));offset+=4+size;
    }
    if(offset)buffer_.erase(buffer_.begin(),buffer_.begin()+offset);
    if(buffer_.size()>maximum_&&buffer_.size()-maximum_>4)throw std::length_error("receive buffer exceeds limit");
    return result;
}
bool supersedes_room_snapshot(const RoomWireEvent& newer,const RoomWireEvent& older){
    if(newer.type!="message"||older.type!="message"||newer.peer!=older.peer||!newer.payload.is_object()||!older.payload.is_object())return false;
    const auto& a=newer.payload;const auto& b=older.payload;
    if(a.value("type",WireObject{})!="room_snapshot"||b.value("type",WireObject{})!="room_snapshot")return false;
    const auto map=b.find("map_included"),stream=a.find("snapshot_stream"),previous=b.find("snapshot_stream");
    return map!=b.end()&&map->is_boolean()&&!map->get<bool>()&&stream!=a.end()&&!stream->is_null()&&previous!=b.end()&&*stream==*previous;
}
bool valid_latency_payload(const WireObject& value){
    if(!value.is_object()||value.size()!=2||!value.contains("type")||!value.contains("nonce"))return false;
    if(value["type"]!="latency_probe"&&value["type"]!="latency_echo")return false;
    if(!value["nonce"].is_string())return false;const auto& nonce=value["nonce"].get_ref<const std::string&>();
    return nonce.size()==16&&std::all_of(nonce.begin(),nonce.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
bool RoomLatencyBucket::allow(const WireObject& payload,double now){
    if(!valid_latency_payload(payload))return false;
    const auto previous=sampled.value_or(now);tokens=std::min(4.,tokens+std::max(0.,now-previous)*2.);sampled=now;
    if(tokens<1.)return false;tokens-=1.;return true;
}
} // namespace pvz::typed72
