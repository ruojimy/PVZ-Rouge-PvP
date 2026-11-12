#pragma once
#include "sim/typed/state.h"
#include <map>
#include <optional>

namespace pvz::typed72 {
struct NativeArtImage;
using NativeArt=std::shared_ptr<NativeArtImage>;
using FrozenArt=std::shared_ptr<const NativeArtImage>;
struct NativeArtRecipe {
    enum class Kind {asset,canvas,scale,flip,rotate,blit} kind=Kind::asset;
    std::string key;
    FrozenArt source,overlay;
    Point destination;
    double angle=0.;
    bool flip_x=false,flip_y=false;
    // Frame description owned by this recipe and opaque to the store: a cold recipe carried
    // verbatim, or a draw primitive (NativeCanvas). Lives exactly as long as the recipe.
    std::shared_ptr<const void> external;
    // scale(): the size the caller passed (变图 passes floats; pygame truncates them).
    std::optional<Point> requested;
    // canvas: pygame.Surface flags (SRCALPHA 65536 by default; 0 for an opaque surface).
    int flags=65536;
};
// Recipes are persistent values. Mutable atlas aliases share the image handle;
// transforms and recorded frames retain a snapshot of that handle's fields.
struct NativeArtImage {
    int width=0,height=0,alpha=-1;
    // hand graphics r.pixel_alpha: false only for Surface((w,h)) without SRCALPHA, whose
    // describe() reads alpha None until set_alpha. Transforms and copies keep it.
    bool pixel_alpha=true;
    std::shared_ptr<const NativeArtRecipe> recipe;
    mutable std::shared_ptr<const SpritePixels> pixels;
};
struct NativeArtBox {int left=0,top=0,right=0,bottom=0;};
class NativeArtStore {
public:
    std::map<std::string,NativeArt> atlas;
    std::map<std::string,double> factors,rider_lifts;
    NativeArt asset(std::string key,SpritePixels);
    NativeArt find(const std::string&)const;
    NativeArt register_asset(const std::string&,const NativeArt&);
    static FrozenArt freeze(const NativeArt&);
    static NativeArt copy(const NativeArt&);
    static NativeArt canvas(int width,int height,int flags=65536);
    // hand graphics rotated_size (the recorded size of transform.rotate / rotozoom).
    static std::pair<int,int> rotated_size(int width,int height,double degrees);
    static NativeArt scale(const NativeArt&,int width,int height);
    static NativeArt flip(const NativeArt&,bool horizontal,bool vertical);
    static NativeArt rotate(const NativeArt&,double degrees);
    static void blit(const NativeArt& destination,const NativeArt& overlay,Point);
    // The reference is owned by the frozen image, so a temporary is rejected.
    static const SpritePixels& pixels(const FrozenArt&);
    static const SpritePixels& pixels(FrozenArt&&)=delete;
    // Materializes and caches on the handle; blit() invalidates that cache.
    static std::shared_ptr<const SpritePixels> materialize(const NativeArt&);
    static std::optional<NativeArtBox> bounds(const NativeArt&,int threshold=8);
    static std::optional<int> painted_top(const NativeArt&,int threshold=40);
    static std::optional<std::string> art_key(const FrozenArt&);
    static std::string atlas_name(const std::string&);
    double factor(const std::string&)const;
    double rider_lift(const std::string&)const;
    NativeArt shrink(const NativeArt&,double scale)const;
    void install_scale(const std::map<std::string,double>& tiles,double tile);
private:
    static NativeArt transformed(const NativeArt&,NativeArtRecipe,int width,int height);
};
struct NativeArtDraw {FrozenArt image;Point position;};
}
