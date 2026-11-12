#include "sim/typed/command_codec.h"
#include <limits>
namespace pvz::typed72 {
namespace {
using J=nlohmann::json;
template<class T>InputField<T> field(const J& j,const char* name){
    InputField<T> result;auto it=j.find(name);if(it==j.end())return result;
    if(it->is_null()){result.state=InputFieldState::null;return result;}
    result.state=InputFieldState::invalid;
    if constexpr(std::is_same_v<T,bool>){if(!it->is_boolean())return result;}
    else if constexpr(std::is_same_v<T,std::string>){if(!it->is_string())return result;}
    else if constexpr(std::is_same_v<T,double>){if(!it->is_number())return result;}
    else {
        if(!it->is_number_integer())return result;
        if(it->is_number_unsigned()&&it->get<uint64_t>()>uint64_t(std::numeric_limits<int64_t>::max()))return result;
    }
    result.value=it->get<T>();result.state=InputFieldState::value;return result;
}
bool truth(const J& j,const char* name){
    const auto it=j.find(name);if(it==j.end()||it->is_null())return false;
    if(it->is_boolean())return it->get<bool>();
    if(it->is_number())return it->get<double>()!=0.;
    if(it->is_string())return !it->get_ref<const std::string&>().empty();
    return !it->empty();
}
template<class T>void write_field(J& out,const char* name,const InputField<T>& field){
    if(field.state==InputFieldState::missing)return;
    if(field.state==InputFieldState::null){out[name]=nullptr;return;}
    if(field.state==InputFieldState::invalid)throw std::invalid_argument("generated command contains an invalid literal; retain raw input at admission");
    out[name]=field.value;
}
}
nlohmann::json encode_generated_command(int64_t sequence,const CommandPayload& payload){J out={{"seq",sequence}};std::visit([&](const auto& c){using T=std::decay_t<decltype(c)>;
    if constexpr(std::is_same_v<T,MoveCommand>){out["type"]="move";write_field(out,"move",c.move);write_field(out,"jump",c.jump);out["edge"]=c.edge;}
    else if constexpr(std::is_same_v<T,RallyCommand>){out["type"]="rally";out["clear"]=c.clear;write_field(out,"x",c.x);write_field(out,"y",c.y);}
    else if constexpr(std::is_same_v<T,ToggleCommand>)out["type"]="command";
    else if constexpr(std::is_same_v<T,CollectCommand>){out["type"]="collect";write_field(out,"resource",c.resource);}
    else if constexpr(std::is_same_v<T,MarkCommand>)out["type"]="mark";
    else if constexpr(std::is_same_v<T,GiftCommand>){out["type"]="gift";write_field(out,"amount",c.amount);}
    else if constexpr(std::is_same_v<T,SurrenderCommand>){out["type"]=c.action==SurrenderAction::request?"surrender":c.action==SurrenderAction::accept?"surrender_accept":c.action==SurrenderAction::decline?"surrender_decline":"surrender_cancel";write_field(out,"request",c.request);}
    else if constexpr(std::is_same_v<T,NativeCommand>){static constexpr const char* names[]={"turn","detonate","select_grave","wake","teleport","deploy","cannon","cannon_cancel","shovel"};out["type"]=names[static_cast<size_t>(c.kind)];write_field(out,"card",c.card);write_field(out,"target",c.target);write_field(out,"grave",c.grave);write_field(out,"copy",c.copy);write_field(out,"x",c.x);write_field(out,"y",c.y);write_field(out,"facing",c.facing);write_field(out,"right",c.right);}
},payload);return out;}
CommandAttempt decode_command(const nlohmann::json& j){
    CommandAttempt a;a.dictionary=j.is_object();if(!a.dictionary)return a;
    a.sequence=field<int64_t>(j,"seq");const auto kind=field<std::string>(j,"type");if(!kind.valid())return a;
    const auto& name=kind.value;
    if(name=="move")a.payload=MoveCommand{field<int64_t>(j,"move"),field<bool>(j,"jump"),truth(j,"edge")};
    else if(name=="rally")a.payload=RallyCommand{field<bool>(j,"clear").valid()&&field<bool>(j,"clear").value,field<double>(j,"x"),field<double>(j,"y")};
    else if(name=="command")a.payload=ToggleCommand{};
    else if(name=="collect")a.payload=CollectCommand{field<std::string>(j,"resource")};
    else if(name=="mark")a.payload=MarkCommand{};
    else if(name=="gift")a.payload=GiftCommand{field<int64_t>(j,"amount")};
    else if(name=="surrender"||name=="surrender_accept"||name=="surrender_decline"||name=="surrender_cancel"){
        auto request=field<double>(j,"request");const auto boolean=field<bool>(j,"request");
        if(boolean.valid())request={InputFieldState::value,boolean.value?1.:0.};
        a.payload=SurrenderCommand{name=="surrender"?SurrenderAction::request:name=="surrender_accept"?SurrenderAction::accept:name=="surrender_decline"?SurrenderAction::decline:SurrenderAction::cancel,request};
    }else{
        std::optional<NativeCommandKind> k;
        if(name=="turn")k=NativeCommandKind::turn;else if(name=="detonate")k=NativeCommandKind::detonate;
        else if(name=="select_grave")k=NativeCommandKind::select_grave;else if(name=="wake")k=NativeCommandKind::wake;
        else if(name=="teleport")k=NativeCommandKind::teleport;else if(name=="deploy")k=NativeCommandKind::deploy;
        else if(name=="cannon")k=NativeCommandKind::cannon;else if(name=="cannon_cancel")k=NativeCommandKind::cannon_cancel;
        else if(name=="shovel")k=NativeCommandKind::shovel;
        if(k)a.payload=NativeCommand{*k,field<std::string>(j,"card"),field<std::string>(j,"target"),field<std::string>(j,"grave"),field<std::string>(j,"copy"),field<double>(j,"x"),field<double>(j,"y"),field<int64_t>(j,"facing"),field<bool>(j,"right")};
    }
    return a;
}
} // namespace pvz::typed72
