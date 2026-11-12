#include "sim/typed/ai_field.h"
#include "sim/typed/ai_plan_codec.h"
#include "sim/typed/room_wire.h"
#include "sim/typed/replay_codec.h"
#include "sim/typed/replay_digest.h"
#include <fstream>
#include <iostream>
#include <sstream>

using namespace pvz::typed72;
namespace {
using J=nlohmann::ordered_json;
J spots(const std::vector<AiFieldSpot>& values){J out=J::array();for(const auto& v:values)out.push_back({v.point.x,v.point.y,v.water});return out;}
std::string hex(std::span<const uint8_t> bytes){static const char* digits="0123456789abcdef";std::string out;for(const auto b:bytes){out+=digits[b>>4];out+=digits[b&15];}return out;}
std::vector<uint8_t> unhex(std::string_view value){std::vector<uint8_t> out;for(size_t i=0;i<value.size();i+=2)out.push_back(uint8_t(std::stoul(std::string(value.substr(i,2)),nullptr,16)));return out;}
J run(const J& c){
    const auto kind=c.at("kind").get<std::string>();J out=J::array();
    if(kind=="field"){
        TargetSight terrain;for(const auto& row:c.at("tiles")){std::vector<uint8_t> solid,water;for(const auto& cell:row){solid.push_back(cell.value("solid",false));water.push_back(cell.value("water",false));}terrain.solid.push_back(solid);terrain.water.push_back(water);}
        AiField field(terrain,c.at("width"),c.at("height"),c.value("tile",48.));
        for(const auto& q:c.at("queries")){
            if(q.value("zones",false))out.push_back(field.zones_in_view(q.at("x")));
            else out.push_back(spots(field.candidates(q.at("zone"),q.at("x"),q.contains("y")?std::optional<double>(q.at("y").get<double>()):std::nullopt,q.value("limit",int64_t(8)))));
        }
    }else if(kind=="wire"){
        RoomFrameDecoder decoder(c.value("maximum",size_t(1024*1024)));
        for(const auto& step:c.at("steps")){
            if(step.contains("encode")){try{out.push_back({{"encoded",hex(encode_room_frame(step.at("encode"),c.value("maximum",size_t(1024*1024))))}});}catch(const std::exception&){out.push_back({{"error",true}});}}
            if(step.contains("feed")){try{out.push_back({{"decoded",decoder.feed(unhex(step.at("feed").get<std::string>()))},{"retained",decoder.retained_bytes()}});}catch(const std::exception&){out.push_back({{"error",true},{"retained",decoder.retained_bytes()}});}}
        }
    }else if(kind=="latency"){
        RoomLatencyBucket bucket;for(const auto& step:c.at("steps")){const auto allowed=bucket.allow(step.at("payload"),step.at("time"));out.push_back({allowed,bucket.tokens,bucket.sampled?J(*bucket.sampled):J(nullptr)});}
    }else if(kind=="supersedes"){
        const auto event=[](const J& v){return RoomWireEvent{v.value("type",std::string{}),v.value("peer_id",std::string{}),v.value("payload",J::object())};};
        for(const auto& pair:c.at("pairs"))out.push_back(supersedes_room_snapshot(event(pair[0]),event(pair[1])));
    }else if(kind=="plan"){
        const auto deck=c.at("deck").get<std::vector<std::string>>();
        for(const auto& raw:c.at("plans")){
            try{const auto p=decode_ai_plan(raw,deck);J quotas=J::object();for(const auto& [k,v]:p.quotas)quotas[k]=v;
                out.push_back({{"priority",p.priority},{"quotas",quotas},{"stance",int(p.stance)},{"target_x",p.target_x?J(*p.target_x):J(nullptr)},
                    {"reserve",p.reserve},{"distance",p.distance},{"ahead",p.deploy_ahead},{"economy",p.economy_offset},{"jump",p.jump_every},{"teleport",p.teleport_hp},
                    {"save",p.save_for?J(*p.save_for):J(nullptr)},{"flags",{p.evade,p.jump_on_block,p.dodge_jump,p.mark}},{"command",p.command?J(*p.command==PathMode::follow_hero?"follow":"attack"):J(nullptr)}});
            }catch(const std::exception& e){out.push_back({{"error",e.what()}});}
        }
    }else if(kind=="digest"){
        for(const auto& input:c.at("payloads"))out.push_back({{"canonical",native_replay_canonical(input)},{"sha256",native_replay_digest(input)}});
    }else if(kind=="replay_fields"){
        for(const auto& input:c.at("payloads"))out.push_back(legacy_replay_input(input));
    }else if(kind=="rope"){
        for(const auto& step:c.at("steps")){auto snapshot=step.at("snapshot");const bool changed=normalize_r8_rope_width(snapshot,step.at("format").get<std::string>(),step.at("build").get<std::string>());out.push_back({{"changed",changed},{"snapshot",snapshot}});}
    }else throw std::invalid_argument("unknown boundary case");
    return out;
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: room_boundary72_probe input output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';return input.bad()||!output?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
