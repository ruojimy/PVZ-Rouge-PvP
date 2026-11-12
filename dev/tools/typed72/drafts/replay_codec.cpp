#include "sim/typed/replay_codec.h"
#include "sim/typed/command_codec.h"
#include <array>
#include <cmath>
#include <stdexcept>

namespace pvz::typed72 {
namespace {
constexpr size_t maximum_bytes=64*1024*1024;
constexpr std::array<std::string_view,16> fields{"type","seq","move","jump","edge","card","x","y","facing","grave","copy","resource","right","target","clear","request"};
bool allowed(std::string_view key,bool version2=false){return (version2&&key=="amount")||std::find(fields.begin(),fields.end(),key)!=fields.end();}
bool integer(const WireObject& value){return value.is_number_integer()&&!value.is_boolean();}
bool same_python_type(const WireObject& a,const WireObject& b){
    if(integer(a)&&integer(b))return true;
    return a.type()==b.type();
}
std::string text_or_none(const WireObject& value){if(value.is_string())return value.get<std::string>();if(value.is_null())return "None";return value.dump();}
void finite(const WireObject& value){
    if(value.is_number_float()&&!std::isfinite(value.get<double>()))throw std::invalid_argument("非有限数值");
    if(value.is_structured())for(const auto& child:value)finite(child);
}
bool truth(const WireObject& value){
    if(value.is_null())return false;if(value.is_boolean())return value.get<bool>();
    if(value.is_number())return value.get<double>()!=0.;
    if(value.is_string())return !value.get_ref<const std::string&>().empty();
    return !value.empty();
}
int64_t bounded_integer(const WireObject& value,int64_t low,int64_t high,const char* error){
    if(!integer(value))throw std::invalid_argument(error);
    if(value.is_number_unsigned()&&value.get<uint64_t>()>uint64_t(high))throw std::invalid_argument(error);
    const auto v=value.get<int64_t>();if(v<low||v>high)throw std::invalid_argument(error);return v;
}
}
WireObject legacy_replay_input(const WireObject& input){
    if(!input.is_object())return input;
    WireObject clean=WireObject::object();for(const auto& [key,value]:input.items())if(allowed(key))clean[key]=value;
    // PvP72 replay-1 omitted gift.amount. Preserve that recorded format here;
    // a corrected recorder must have an explicitly new format/build identity.
    return clean;
}
WireObject recorded_replay_input(const WireObject& input,std::string_view format){
    if(format=="pvz-pvp-replay-1")return legacy_replay_input(input);
    if(format!="pvz-pvp-replay-2")throw std::invalid_argument("unsupported recording format");
    if(!input.is_object())return input;
    WireObject clean=WireObject::object();for(const auto& [key,value]:input.items())if(allowed(key,true))clean[key]=value;return clean;
}
ReplayDocument decode_replay(std::string_view bytes,const ReplayIdentity& identity,const WireObject& schema,ReplayAdmission& admission){
    if(bytes.size()>maximum_bytes)throw std::length_error("回放超过 64 MB，无法加载");
    auto data=WireObject::parse(bytes.begin(),bytes.end());finite(data);
    if(!data.is_object()||(data.value("format",WireObject{})!="pvz-pvp-replay-1"&&data.value("format",WireObject{})!="pvz-pvp-replay-2"))throw std::invalid_argument("这是旧审计日志或不支持的格式；缺少完整输入，不能可靠回放");
    const auto format=data.at("format").get<std::string>();const bool version2=format=="pvz-pvp-replay-2";
    if(data.value("build",WireObject{})!=identity.build||data.value("catalog_hash",WireObject{})!=identity.catalog_hash||data.value("rules_hash",WireObject{})!=identity.rules_hash)
        throw std::invalid_argument("回放与当前游戏版本/规则不同，请使用记录时的版本："+text_or_none(data.value("build",WireObject{})));
    const auto initial=data.value("initial",WireObject::object());const auto rules=initial.value("rules",WireObject::object());
    if(!rules.is_object()||rules.size()!=schema.size())throw std::invalid_argument("回放规则无效");
    for(const auto& [key,value]:rules.items())if(!schema.contains(key)||!same_python_type(value,schema.at(key)))throw std::invalid_argument("回放规则无效");
    const auto rate=rules.at("tick_rate").get<int>();if(rate!=30&&rate!=60)throw std::invalid_argument("回放时间刻频率无效");
    const auto ticks=bounded_integer(data.value("ticks",WireObject{}),0,6*3600*int64_t(rate),"回放时长无效");
    admission.validate_map(initial.at("map"));bounded_integer(initial.value("seed",WireObject{}),0,(int64_t(1)<<31)-1,"回放随机种子无效");
    const auto mode=initial.value("mode",WireObject("duel"));if(mode!="duel"&&mode!="duo")throw std::invalid_argument("回放模式无效");
    const auto seats=seats_for(mode=="duel"?MatchMode::duel:MatchMode::duo);
    const auto operations=data.value("operations",WireObject{});
    if(!operations.is_array()||operations.size()>1000000)throw std::length_error("回放输入数量无效");
    ReplayDocument document;document.initial=initial;document.metadata=data;document.metadata.erase("operations");
    auto& replay=document.playback;replay.tick_rate=rate;replay.ticks=ticks;replay.format=format;replay.build=identity.build;
    replay.final_hash=data.at("final_hash").get<std::string>();replay.operations.reserve(operations.size());int64_t previous=0;
    for(const auto& op:operations){
        if(!op.is_object())throw std::invalid_argument("回放输入时间顺序无效");
        const auto tick=bounded_integer(op.value("tick",WireObject{}),previous,ticks,"回放输入时间顺序无效");previous=tick;
        const auto kind=op.value("kind",WireObject{});if(kind!="input"&&kind!="clear"&&kind!="check")throw std::invalid_argument("未知回放操作");
        std::optional<Seat> seat;
        if(kind=="input"||kind=="clear"){
            const auto value=op.value("side",WireObject{});if(value.is_string())seat=known_seat(value.get<std::string>());
            if(!seat||std::find(seats.begin(),seats.end(),*seat)==seats.end())throw std::invalid_argument("回放阵营无效");
        }
        if(kind=="input"){
            const auto payload=op.value("payload",WireObject{});if(!payload.is_object())throw std::invalid_argument("回放输入字段无效");
            for(const auto& [key,value]:payload.items())if(!allowed(key,version2))throw std::invalid_argument("回放输入字段无效");
            replay.operations.push_back({tick,ReplayInput{*seat,decode_command(nlohmann::json(payload)),op.at("error").get<std::string>()}});
        }else if(kind=="clear")replay.operations.push_back({tick,ReplayClear{*seat}});
        else replay.operations.push_back({tick,ReplayCheck{op.at("sha256").get<std::string>()}});
    }
    return document;
}
bool normalize_r8_rope_width(WireObject& snapshot,std::string_view format,std::string_view build){
    if(format!="pvz-pvp-replay-1"||build!="1.6.0.72-native.20261104")return false;
    auto frame=snapshot.find("native_frame");if(frame==snapshot.end()||!frame->is_object())return false;
    const int width=int(frame->value("tile",48.)/17.);auto commands=frame->find("commands");if(commands==frame->end()||!commands->is_array())return false;
    bool changed=false;
    for(auto& command:*commands){
        if(!command.is_object()||command.value("op",WireObject{})!="primitive"||command.value("primitive",WireObject{})!="line")continue;
        auto args=command.find("args");if(args==command.end()||!args->is_array()||args->size()!=4||(*args)[0]!=WireObject::array({50,50,50})||(*args)[3]!=width)continue;
        const auto entity=command.find("entity");if(entity==command.end()||!truth(*entity))continue;
        const auto kwargs=command.find("kwargs");if(kwargs!=command.end()&&truth(*kwargs))continue;
        (*args)[3]=nullptr;changed=true;
    }
    return changed;
}
} // namespace pvz::typed72
