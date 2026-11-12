// pvp/native_animation.py DrawRecorder and definitions.py 摄像显示 / 旋转摄像显示 / 反.
#include "sim/typed/native_frame.h"
#include <cmath>
#include <stdexcept>
namespace pvz::typed72 {
void NativeFrameRecorder::begin_frame(int64_t tick){
    // New containers every frame; the previous frame may still be shared.
    frame_=NativeFrame{};frame_.tick=tick;frame_.tile=tile;entity_override.reset();
}
void NativeFrameRecorder::append(NativeFrameCommand command){
    if(frame_.commands.size()>=max_commands_)throw std::runtime_error("Native draw command limit exceeded");
    const auto source=entity_override?entity_override:sources?sources():std::nullopt;
    if(source&&!source->id.empty()){
        command.entity=source->id;
        bool found=false;
        for(auto& [uid,point]:frame_.positions)if(uid==source->id){point=source->position;found=true;break;}
        if(!found)frame_.positions.emplace_back(source->id,source->position);
    }
    frame_.commands.push_back(std::move(command));
}
void NativeFrameRecorder::blit(const NativeArt& image,Point position){
    if(!image)throw std::invalid_argument("Original drawing returned None");
    if(!enabled)return;
    append(NativeFrameCommand{NativeArtStore::freeze(image),std::nullopt,position,std::nullopt,{}});
}
void NativeFrameRecorder::primitive(NativeFramePrimitive p){
    if(!enabled)return;
    append(NativeFrameCommand{{},std::move(p),{},std::nullopt,{}});
}
void NativeFrameRecorder::rotated_camera_display(const NativeArt& image,Point position,double degrees){
    // dushu = -dushu; center = image.get_rect().center; temp = rotate(image, dushu);
    // new = temp.get_rect(center=center); 摄像显示(temp, [x + new[0], y + new[1]]).
    const auto rotated=NativeArtStore::rotate(image,-degrees);
    const int cx=image->width/2,cy=image->height/2;
    const int left=cx-rotated->width/2,top=cy-rotated->height/2;
    camera_display(rotated,{position.x+double(left),position.y+double(top)});
}
NativeFrame NativeFrameRecorder::snapshot()const{return frame_;}
NativeArt native_flip(const NativeArt& image){return NativeArtStore::flip(image,true,false);}
} // namespace pvz::typed72
