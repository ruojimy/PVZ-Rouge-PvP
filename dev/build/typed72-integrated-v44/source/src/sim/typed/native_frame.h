#pragma once
// Typed native draw recorder: the frames NativeBattle publishes as snapshot["native_frame"]
// (pvp/native_animation.py DrawRecorder, protocol "native-draw-v1"). Native drawing runs with
// camera and shake at zero (NamespaceGraphics.install), so commands carry canonical world pixels;
// each viewer culls with its own camera. Images are NativeArt recipes; their description matches
// NativeImage.describe(): {image: recipe, alpha, colorkey, size}.
#include "sim/typed/native_art.h"
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <vector>
namespace pvz::typed72 {
struct NativeFramePrimitive {
    std::string name;                // pygame.draw.<name>(screen, color, rect, width)
    Color color{};double x=0,y=0,w=0,h=0;int width=0;
    // When set, the recorded args verbatim (a JSON value owned by the canvas encoder).
    std::shared_ptr<const void> args;
};
struct NativeFrameCommand {
    FrozenArt image;                 // op "image" (null for op "primitive")
    std::optional<NativeFramePrimitive> primitive;
    Point position;
    std::optional<std::string> entity;
    std::string layer;               // replay layer tag ("below_ground", "vine_foreground"), empty = default
};
struct NativeFrame {
    int64_t tick=0;
    double tile=48.;
    std::vector<NativeFrameCommand> commands;
    // DrawRecorder.positions: insertion-ordered uid -> [x, y] of each attributed source.
    std::vector<std::pair<std::string,Point>> positions;
};
// DrawRecorder._append attribution: the entity override, else the active source; a source is
// attributed only when it has a native position (位置, or 玩家位置 for a hero).
struct NativeFrameSource {std::string id;Point position;};
using NativeFrameSources=std::function<std::optional<NativeFrameSource>()>;
class NativeFrameRecorder {
public:
    explicit NativeFrameRecorder(size_t max_commands=12000):max_commands_(max_commands){}
    NativeFrameSources sources;
    bool enabled=true;
    double tile=48.;
    std::optional<NativeFrameSource> entity_override;
    void begin_frame(int64_t tick);
    // screen.blit(image, pos): one "image" command.
    void blit(const NativeArt& image,Point position);
    // screen draw primitive: one "primitive" command.
    void primitive(NativeFramePrimitive);
    // Original helpers with camera = shake = 0 and 不显 always False.
    void camera_display(const NativeArt& image,Point position){blit(image,position);}
    // 旋转摄像显示: rotate by -degrees about the image's integer rect centre.
    void rotated_camera_display(const NativeArt& image,Point position,double degrees);
    NativeFrame snapshot()const;
    size_t size()const{return frame_.commands.size();}
    // Tags every command recorded since `start` (native_content draw_plant layer override).
    void tag_layer(size_t start,const std::string& layer){for(size_t i=start;i<frame_.commands.size();++i)frame_.commands[i].layer=layer;}
    const NativeFrame& frame()const{return frame_;}
private:
    size_t max_commands_;
    void append(NativeFrameCommand);
    NativeFrame frame_;
};
// 反: pygame.transform.flip(image, True, False).
NativeArt native_flip(const NativeArt&);
} // namespace pvz::typed72
