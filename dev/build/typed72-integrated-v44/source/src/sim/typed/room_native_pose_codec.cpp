#include "sim/typed/room_native_pose_codec.h"
namespace pvz::typed72 {
WireObject encode_attack_identity(const AttackIdentity& token){
    using Kind=AttackIdentity::Kind;
    switch(token.kind()){
    case Kind::null:return nullptr;
    case Kind::string:return token.string_value();
    case Kind::integer:return token.integer_value();
    case Kind::boolean:return token.boolean_value();
    case Kind::tuple:case Kind::list:{auto out=WireObject::array();for(const auto& child:token.sequence_value())out.push_back(encode_attack_identity(child));return out;}
    }
    throw std::logic_error("invalid attack identity kind");
}
WireObject encode_native_pose(const RoomNativePose& pose){
    const auto& h=pose.value();const auto& frame=h.frame;auto out=WireObject::object();
    const auto add=[&]<class T>(const char* key,const Field<T>& field){if(field.present())out[key]=field.is_null()?WireObject(nullptr):WireObject(field.get());};
#define ADD(n,k) add(k,frame.n);
    PVZ72_HERO_NUMBERS(ADD) PVZ72_HERO_BOOLEANS(ADD) PVZ72_HERO_STRINGS(ADD)
#undef ADD
    if(frame.position.present()){
        if(frame.position.is_null()||!frame.position.get())out["玩家位置"]=nullptr;
        else{const auto& m=*frame.position.get();out["玩家位置"]=WireObject::array({m.x,m.y,m.vx,m.vy});}
    }
    if(frame.secrets.present())out["秘籍"]=frame.secrets.is_null()||!frame.secrets.get()?WireObject(nullptr):WireObject(*frame.secrets.get());
    add("_pvp_max_hp",h.max_hp);add("_pvp_ice",h.ice);add("_pvp_butter",h.butter);add("_pvp_stun",h.stun);
    add("_pvp_last_damage",h.last_damage);add("_pvp_regen_progress",h.regen_progress);add("_pvp_pea_angle",h.pea_angle);
    add("native_ticks",h.native_ticks);add("landing_result",h.landing_result);add("_pvp_balloon_hp",h.balloon_hp);
    add("_pvp_cold_until",h.cold_until);add("_pvp_previous_hp",h.previous_hp);add("_pvp_water_damage_clock",h.water_damage_clock);add("_pvp_masochist_ready",h.masochist_ready);
    add("_pvp_sturdy_down",h.sturdy_down);add("_pvp_floating_body",h.floating_body);add("_pvp_rally_before",h.rally_before);add("_pvp_rally_eligible",h.rally_eligible);add("_pvp_rally_checked",h.rally_checked);
    if(h.actual_seat)out["_pvp_seat"]=seat_name(*h.actual_seat);
    if(h.avatar_source){add("_pvp_owner",h.avatar_source->owner);add("_pvp_id",h.avatar_source->id);}
    if(h.launch_attack)out["_pvp_launch_attack"]=encode_attack_identity(*h.launch_attack);
    if(h.poison.present()){
        if(h.poison.is_null()||!h.poison.get())out["_pvp_poison"]=nullptr;
        else{
            const auto& poison=*h.poison.get();auto raw=WireObject::object();
            const auto entry=[&]<class T>(const char* key,const Field<T>& field){if(field.present())raw[key]=field.is_null()?WireObject(nullptr):WireObject(field.get());};
            entry("level",poison.level);entry("until",poison.until);entry("next",poison.next);
            if(poison.owner.present())raw["owner"]=poison.owner.is_null()?WireObject(nullptr):WireObject(seat_name(poison.owner.get()));
            if(poison.layers.present()){
                if(poison.layers.is_null()||!poison.layers.get())raw["layers"]=nullptr;
                else{auto layers=WireObject::object();for(const auto& [strength,layer]:*poison.layers.get())layers[std::to_string(strength)]=layer?WireObject{{"until",layer->until},{"next",layer->next},{"owner",seat_name(layer->owner)}}:WireObject(nullptr);raw["layers"]=std::move(layers);}
            }
            out["_pvp_poison"]=std::move(raw);
        }
    }
    return out;
}
}
