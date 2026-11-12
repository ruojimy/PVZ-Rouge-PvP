#pragma once
// The native drawing surface of one battle: the draw atlas (图集 as NativeArt images), the
// original camera helpers with camera = shake = 0 (摄像显示, 旋转摄像显示, 反, 变图,
// set_alpha), pvp native_expansion's art aliases and seated-headgear 摄像显示 wrapper,
// and the native-draw-v1 encoding NativeBattle publishes as snapshot["native_frame"].
// Sources: pvp/native_animation.py (NamespaceGraphics, DrawRecorder, NativeImage.describe),
// original definitions 摄像显示/旋转摄像显示/反/变图, pvp/native_expansion.py.
#include "sim/typed/native_frame.h"
#include "sim/typed/expansion_art.h"
#include <nlohmann/json.hpp>
#include <functional>
#include <unordered_map>
namespace pvz::typed72 {
class NativeCanvas {
public:
    using Json=nlohmann::json;
    NativeCanvas():expansion(atlas){}
    NativeCanvas(const NativeCanvas&)=delete;
    NativeCanvas& operator=(const NativeCanvas&)=delete;
    NativeArtStore atlas;
    NativeFrameRecorder frames;
    ExpansionArt expansion;
    // Cold boundary: draw atlas {name: {id, describe}} (one image per V object), the
    // simulation atlas pixels for art measurements, and native_scale FACTOR/LIFT.
    void install(const Json& draw_atlas,const std::unordered_map<std::string,SpritePixels>& pixels,
                 const Json& scale_factor,const Json& rider_lift);
    bool drawing()const{return frames.enabled;}
    // patch1501 __pvz_sb_patch_plant_zombie_assets runs lazily (first zombie-pea / plant-zombie
    // head draw): until then the installed pre-patch art is current.
    void patch_plant_zombie_assets();
    bool plant_zombie_assets_patched()const{return patched_;}
    bool has(const std::string& name)const{return atlas.atlas.contains(name);}
    NativeArt image(const std::string& name)const;
    std::map<std::string,NativeArt> ui;  // ui图集
    NativeArt ui_image(const std::string& name)const;
    // 反 = transform.flip(image, True, False)
    static NativeArt flip(const NativeArt& image){return NativeArtStore::flip(image,true,false);}
    // 变图 = transform.scale(image, (int(w), int(h))).convert_alpha().
    NativeArt resize(const NativeArt& image,double width,double height);
    // 摄像显示 through native_expansion.seated_headgear.
    void display(const NativeArt& image,Point position);
    // 旋转摄像显示: rotate by -degrees, re-centred on the source's integer rect centre.
    void rotated(const NativeArt& image,Point position,double degrees);
    // pygame.Surface((w, h), SRCALPHA): a transparent canvas; flags 0 is an opaque surface.
    static NativeArt surface(int width,int height,int flags=65536){return NativeArtStore::canvas(width,height,flags);}
    // Surface.subsurface(rect): recipe op "crop" over the source description.
    NativeArt crop(const NativeArt& image,double x,double y,double width,double height)const;
    // transform.rotozoom(image, angle, scale): recipe op "rotozoom" with the recorded size.
    NativeArt rotozoom(const NativeArt& image,double degrees,double scale)const;
    // pygame.draw.<primitive>(target, *args) on an image: the recipe becomes op "draw".
    // Pixels are not rasterised (frames only describe); a drawn image is never measured.
    void draw_on(const NativeArt& target,const std::string& primitive,Json args,Json kwargs=Json::object());
    // Image.fill(color, rect, special_flags) on an image: the recipe becomes op "fill".
    void fill(const NativeArt& target,Json color,Json rect=nullptr,int flags=0);
    // native_status.tint_poison: an alpha-masked colour wash over a copy (level 1 or 2).
    NativeArt tint_poison(const NativeArt& image,int level);
    // native_status.tint_zombie: replace every art of the unit's roots by its cached tint,
    // keeping the first original in the expansion save so restore_art puts it back.
    void tint_roots(const std::vector<std::string>& roots,int level);
    // The installed 旋转摄像显示 wrapper (native_expansion pea angle), when one is active.
    std::function<double(const NativeArt&,double)> rotation_filter;
    // str(image.recipe) contains `text`.
    bool recipe_mentions(const NativeArt& image,const std::string& text)const;
    // 画线(color, start, end): pygame.draw.line(screen, color, start, end, xianbi).
    void line(Json color,Point start,Point end){
        if(!frames.enabled)return;
        NativeFramePrimitive p;p.name="line";p.args=std::make_shared<const Json>(Json{std::move(color),{start.x,start.y},{end.x,end.y},line_width});
        frames.primitive(std::move(p));
    }
    double line_width=1.;  // xianbi
    // Surface.set_alpha on the atlas image: clamp(int(value), 0, 255).
    void set_alpha(const std::string& name,double value);
    static void set_alpha(const NativeArt& image,double value);
    // native_expansion.alias_art / restore_art (aliases share the image object).
    void alias_one(const std::string& old,const std::string& next);
    void alias(const std::string& old,const std::string& next);
    void restore();
    // expansion.saved_atlas.get(name, 图集[name]): the art under any active alias.
    NativeArt unaliased(const std::string& name)const{const auto i=saved_.find(name);return i!=saved_.end()?i->second:image(name);}
    Json describe(const FrozenArt&)const;
    Json frame_json(const NativeFrame&)const;
private:
    std::map<std::string,NativeArt> saved_;
    std::map<std::string,NativeArt> patched_art_;bool patched_=true;
    std::map<std::pair<const NativeArtImage*,int>,std::pair<NativeArt,NativeArt>> tints_;
    Json recipe(const FrozenArt&)const;
};
} // namespace pvz::typed72
