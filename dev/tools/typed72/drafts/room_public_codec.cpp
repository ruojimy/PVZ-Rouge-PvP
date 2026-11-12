#include "sim/typed/room_public_codec.h"
namespace pvz::typed72 {
WireObject encode_public_unit(const RoomPublishedUnit& u,const WireObject& complete_card){
    const auto current=seat_name(u.side),original=seat_name(u.original_owner);auto card=complete_card;if(u.orphan_barrel){card["name"]="滚桶";card["asset"]="滚桶";}
    WireObject out={{"id",u.id},{"card",std::move(card)},{"card_id",u.card->id},{"side",current},{"owner",current},{"original_owner",original},{"current_owner",current},{"source_entity",u.id},{"native_side",original},
        {"x",u.position.x},{"y",u.position.y},{"vx",u.velocity.x},{"vy",u.velocity.y},{"w",u.w},{"h",u.h},{"hp",u.hp},{"max_hp",u.max_hp},{"facing",u.facing},{"armor_hp",u.armor_hp},{"armor_max",u.armor_max},
        {"behavior",u.card->behavior},{"mobile",u.mobile},{"flying",u.card->flying},{"burrowed",u.burrowed},{"temporary",u.temporary},{"awake",u.awake},{"grounded",false},{"born",0},{"progress",0},{"native",true},{"floating",u.floating},
        {"frozen",u.frozen},{"slowed",u.slowed},{"buttered",u.buttered},{"stunned",u.stunned},{"production_rate",u.production_rate},{"mature",u.mature},{"torch_blue",u.torch_blue},{"drowsy",u.drowsy},{"drowsy_level",u.drowsy_level}};
    if(u.copy_card)out["copy_card_id"]=*u.copy_card;if(u.seat)out["seat"]=seat_name(*u.seat);if(u.first_soldier_ready)out["first_soldier_ready"]=*u.first_soldier_ready;
    if(!u.secret_speed.empty()){out["secret_speed_bonuses"]=WireObject::object();for(const auto& [key,value]:u.secret_speed)out["secret_speed_bonuses"][key]=value;}
    out["poison_level"]=u.poison_level;if(u.orphan_barrel)out["orphan_barrel"]=true;return out;
}
WireObject encode_public_terrain_cell(const RoomPublicCell& c){
    WireObject native=WireObject::object();const auto add=[&]<class T>(const char* key,const Field<T>& value){if(value.present())native[key]=value.is_null()?WireObject(nullptr):WireObject(value.get());};
    add("方块",c.native.block);add("里方块",c.native.inner_block);
#define ADD(n,k) add(k,c.native.n);
    PVZ72_TILE_NUMBERS(ADD)
    PVZ72_TILE_FLAGS(ADD)
#undef ADD
    return {{"kind",c.kind},{"solid",c.solid},{"water",c.water},{"ladder",c.ladder},{"background",c.background},{"native",std::move(native)}};
}
AiUnitView ai_public_unit(const RoomPublishedUnit& u){
    AiUnitView out;out.id=u.id;out.card=u.card->id;out.side=u.side;out.seat=u.seat;out.position=u.position;out.hp=u.hp;out.grave=u.card->behavior=="grave";out.max_hp=u.max_hp;out.velocity=u.velocity;out.mobile=u.mobile;out.awake=u.awake;out.behavior=u.card->behavior;
    out.card_info.name=u.orphan_barrel?"滚桶":u.card->name;out.card_info.behavior=u.card->behavior;out.card_info.cost=u.card->cost;out.card_info.range=u.card->range;out.card_info.damage=u.card->damage;out.card_info.producer=u.card->producer;out.card_info.mushroom=u.card->mushroom;return out;
}
} // namespace pvz::typed72
