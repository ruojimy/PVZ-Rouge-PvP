#pragma once
#include "sim/typed/room_public.h"
#include "core/obj.h"
namespace pvz::typed72app {
// UI boundary for the already published unit. Mirrors room_public_codec.cpp;
// no resampling, combat calculations or native body pointers. Differential
// tests check every field against the unchanged wire codec, including absence.
inline V project_public_unit(const typed72::RoomPublishedUnit& u,const V& card){
    V out=V::dict();
    const auto put=[&](const char* k,const auto& value){out.at(V(k))=V(value);};
    const auto current=std::string(typed72::seat_name(u.side));
    const auto original=std::string(typed72::seat_name(u.original_owner));
    put("id",u.id);out.at(V("card"))=card;put("card_id",u.card->id);
    for(const char* k:{"side","owner","current_owner"})put(k,current);
    put("original_owner",original);put("native_side",original);put("source_entity",u.id);
    put("x",u.position.x);put("y",u.position.y);put("vx",u.velocity.x);put("vy",u.velocity.y);
#define NUM(n) put(#n,double(u.n));
    NUM(w) NUM(h) NUM(hp) NUM(max_hp) NUM(facing) NUM(armor_hp) NUM(armor_max)
    NUM(production_rate) NUM(drowsy_level) NUM(poison_level)
#undef NUM
#define FLAG(n) put(#n,u.n);
    FLAG(mobile) FLAG(burrowed) FLAG(temporary) FLAG(awake) FLAG(floating)
    FLAG(frozen) FLAG(slowed) FLAG(buttered) FLAG(stunned) FLAG(mature) FLAG(torch_blue) FLAG(drowsy)
#undef FLAG
    put("behavior",u.card->behavior);put("flying",u.card->flying);
    put("grounded",false);put("born",0.);put("progress",0.);put("native",true);
    if(u.defense)put("defense",*u.defense);
    if(u.copy_card)put("copy_card_id",*u.copy_card);
    if(u.seat)put("seat",std::string(typed72::seat_name(*u.seat)));
    if(u.first_soldier_ready)put("first_soldier_ready",*u.first_soldier_ready);
    if(!u.secret_speed.empty()){
        V speed=V::dict();for(const auto& [k,v]:u.secret_speed)speed.at(V(k))=V(v);
        out.at(V("secret_speed_bonuses"))=speed;
    }
    if(u.orphan_barrel)put("orphan_barrel",true);
    return out;
}
struct LocalHudCounts {
    int graves=0,damaged_graves=0,scarecrows=0;
    void add(const typed72::RoomPublishedUnit& u){
        if(u.side!=typed72::Seat::zombie||!(u.hp>0.))return;
        if(u.card->id=="zombie:稻草人")++scarecrows;
        if(u.card->behavior=="grave"){++graves;if(u.hp<u.max_hp)++damaged_graves;}
    }
    V value()const{
        V out=V::dict();out.at(V("graves"))=V(double(graves));
        out.at(V("damaged_graves"))=V(double(damaged_graves));
        out.at(V("scarecrows"))=V(double(scarecrows));return out;
    }
};
}
