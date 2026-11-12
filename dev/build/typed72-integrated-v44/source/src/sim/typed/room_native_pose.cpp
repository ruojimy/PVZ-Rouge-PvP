#include "sim/typed/room_native_pose.h"
namespace pvz::typed72 {
namespace {
template<class T>void detach(Field<std::shared_ptr<T>>& value){
    if(value.present()&&!value.is_null()&&value.get())value.set(std::make_shared<T>(*value.get()));
}
}
void RoomNativePose::capture(const HeroState& source){
    HeroState next=source;
    detach(next.frame.position);detach(next.frame.secrets);detach(next.poison);
    if(next.poison.present()&&!next.poison.is_null()&&next.poison.get()){
        auto& layers=next.poison.get()->layers;detach(layers);
        if(layers.present()&&!layers.is_null()&&layers.get())for(auto& [strength,layer]:*layers.get())if(layer)layer=std::make_shared<PoisonLayer>(*layer);
    }
    if(next.avatar_source)next.avatar_source=std::make_shared<AttackSource>(*next.avatar_source);
    state_=std::move(next);
}
}
