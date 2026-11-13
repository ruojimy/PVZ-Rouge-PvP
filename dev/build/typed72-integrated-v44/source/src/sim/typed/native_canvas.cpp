#include "sim/typed/native_canvas.h"
#include <algorithm>
#include <stdexcept>
namespace pvz::typed72 {
void NativeCanvas::install(const Json& draw_atlas,const std::unordered_map<std::string,SpritePixels>& pixels,
                           const Json& scale_factor,const Json& rider_lift){
    std::unordered_map<std::string,NativeArt> objects;
    const auto load=[&](const Json& entries,std::map<std::string,NativeArt>& into){
        for(const auto& [name,item]:entries.items()){
            auto& image=objects[item.at("id").dump()];
            if(!image){
                const auto& d=item.at("describe");image=std::make_shared<NativeArtImage>();
                image->width=d.at("size").at(0);image->height=d.at("size").at(1);
                if(d.at("alpha").is_number()&&d.at("alpha").get<int>()!=255)image->alpha=d.at("alpha");
                auto r=std::make_shared<NativeArtRecipe>();const auto& source=d.at("image");
                if(source.at("op")=="asset")r->key=source.at("key");else r->external=std::make_shared<const Json>(source);
                image->recipe=r;
            }
            into.emplace(name,image);
        }
    };
    load(draw_atlas.at("world"),atlas.atlas);
    load(draw_atlas.at("ui"),ui);
    if(draw_atlas.contains("world_before")){
        // Keep the patched art aside and install the pre-patch art (null: key added by the patch).
        std::map<std::string,NativeArt> before;
        for(const auto& [name,item]:draw_atlas.at("world_before").items())if(!item.is_null()){
            // Ids are only unique among live objects; a freed pre-patch image may share one
            // with a post-patch image, so pre-patch identities live in their own namespace.
            Json copy=item;copy["id"]="before:"+item.at("id").dump();Json one=Json::object();one[name]=copy;load(one,before);
        }
        for(const auto& [name,item]:draw_atlas.at("world_before").items()){
            patched_art_[name]=atlas.atlas.at(name);
            if(item.is_null())atlas.atlas.erase(name);else atlas.atlas[name]=before.at(name);
        }
        patched_=patched_art_.empty();
    }
    // Pixels for art measurements (headgear seats, rider lift). The patched plant-zombie
    // display head is a transparent fill; other non-asset recipes are never measured.
    for(auto& [id,image]:objects){
        if(image->recipe->external){
            const auto& r=*std::static_pointer_cast<const Json>(image->recipe->external);
            if(r.at("op")=="fill"&&r.at("color")==Json::array({0,0,0,0})&&r.at("rect").is_null()){
                auto p=std::make_shared<SpritePixels>();p->width=image->width;p->height=image->height;
                p->pixels.resize(size_t(p->width)*p->height);image->pixels=p;
            }
            continue;
        }
        const auto found=pixels.find(NativeArtStore::atlas_name(image->recipe->key));
        if(found!=pixels.end())image->pixels=std::make_shared<const SpritePixels>(found->second);
    }
    for(const auto& [unit,value]:scale_factor.items())atlas.factors[unit]=value;
    for(const auto& [unit,value]:rider_lift.items())atlas.rider_lifts[unit]=value;
}
void NativeCanvas::patch_plant_zombie_assets(){
    if(patched_)return;
    for(const auto& [name,image]:patched_art_)atlas.atlas[name]=image;
    patched_=true;
}
NativeArt NativeCanvas::image(const std::string& name)const{
    const auto found=atlas.find(name);
    if(!found)throw std::out_of_range("native atlas has no image "+name);
    return found;
}
NativeArt NativeCanvas::ui_image(const std::string& name)const{
    const auto found=ui.find(name);
    if(found==ui.end())throw std::out_of_range("native ui atlas has no image "+name);
    return found->second;
}
NativeArt NativeCanvas::resize(const NativeArt& image,double width,double height){
    // hand graphics transform.scale: int() of each size; the recipe records those ints.
    auto out=NativeArtStore::scale(image,int(width),int(height));
    // pg transform and convert_alpha both keep the source's surface alpha.
    return out;
}
void NativeCanvas::display(const NativeArt& image,Point position){
    if(!frames.enabled)return;
    for(const auto& layer:expansion.seated(image,position))
        frames.blit(std::const_pointer_cast<NativeArtImage>(layer.image),layer.position);
}
void NativeCanvas::rotated(const NativeArt& image,Point position,double degrees){
    if(rotation_filter)degrees=rotation_filter(image,degrees);
    if(!frames.enabled)return;  // 补帧 != 0: the original skips the transform as well
    const auto turned=NativeArtStore::rotate(image,-degrees);
    display(turned,{position.x+double(image->width/2-turned->width/2),position.y+double(image->height/2-turned->height/2)});
}
void NativeCanvas::draw_on(const NativeArt& target,const std::string& primitive,Json args,Json kwargs){
    Json recipe={{"op","draw"},{"source",describe(target)},{"primitive",primitive},{"args",std::move(args)},{"kwargs",std::move(kwargs)}};
    auto r=std::make_shared<NativeArtRecipe>();r->kind=NativeArtRecipe::Kind::canvas;
    r->external=std::make_shared<const Json>(std::move(recipe));
    target->recipe=r;target->pixels.reset();
}
void NativeCanvas::draw_batch(const NativeArt& target,Json strokes){
    Json recipe={{"op","draw_batch"},{"source",describe(target)},{"strokes",std::move(strokes)}};
    auto r=std::make_shared<NativeArtRecipe>();r->kind=NativeArtRecipe::Kind::canvas;
    r->external=std::make_shared<const Json>(std::move(recipe));target->recipe=r;target->pixels.reset();
}
NativeArt NativeCanvas::crop(const NativeArt& image,double x,double y,double width,double height)const{
    // hand graphics subsurface: copy_image (alpha, pixel alpha kept), op crop, int size.
    auto out=NativeArtStore::copy(image);out->width=int(width);out->height=int(height);
    auto r=std::make_shared<NativeArtRecipe>();r->kind=NativeArtRecipe::Kind::canvas;
    r->external=std::make_shared<const Json>(Json{{"op","crop"},{"source",describe(image)},{"rect",{x,y,width,height}}});
    out->recipe=r;out->pixels.reset();return out;
}
NativeArt NativeCanvas::rotozoom(const NativeArt& image,double degrees,double scale)const{
    const auto [w,h]=NativeArtStore::rotated_size(int(image->width*scale+.5),int(image->height*scale+.5),degrees);
    auto out=NativeArtStore::copy(image);out->width=w;out->height=h;
    auto r=std::make_shared<NativeArtRecipe>();r->kind=NativeArtRecipe::Kind::canvas;
    r->external=std::make_shared<const Json>(Json{{"op","rotozoom"},{"source",describe(image)},{"args",{degrees,scale}}});
    out->recipe=r;out->pixels.reset();return out;
}
void NativeCanvas::fill(const NativeArt& target,Json color,Json rect,int flags){
    Json recipe={{"op","fill"},{"source",describe(target)},{"color",std::move(color)},{"rect",std::move(rect)},{"flags",flags}};
    auto r=std::make_shared<NativeArtRecipe>();r->kind=NativeArtRecipe::Kind::canvas;
    r->external=std::make_shared<const Json>(std::move(recipe));
    target->recipe=r;target->pixels.reset();
}
NativeArt NativeCanvas::tint_poison(const NativeArt& image,int level){
    static const std::map<int,Json> colors{{1,Json::array({255,115,190})},{2,Json::array({170,70,230})}};
    auto mask=NativeArtStore::copy(image);
    fill(mask,Json::array({255,255,255}),nullptr,5);   // BLEND_RGB_MAX
    fill(mask,colors.at(level),nullptr,3);             // BLEND_RGB_MULT
    set_alpha(mask,110.);
    auto result=NativeArtStore::copy(image);NativeArtStore::blit(result,mask,{0.,0.});
    return result;
}
void NativeCanvas::tint_roots(const std::vector<std::string>& roots,int level){
    std::vector<std::string> keys;
    for(const auto& [key,image]:atlas.atlas)for(const auto& r:roots)if(key==r||key.starts_with(r+"-")){keys.push_back(key);break;}
    for(const auto& key:keys){
        const auto original=atlas.atlas.at(key);const auto token=std::pair{original.get(),level};
        auto found=tints_.find(token);
        if(found==tints_.end()){if(tints_.size()>256)tints_.clear();found=tints_.emplace(token,std::pair{original,tint_poison(original,level)}).first;}
        saved_.emplace(key,original);
        atlas.atlas[key]=found->second.second;
    }
}
bool NativeCanvas::recipe_mentions(const NativeArt& image,const std::string& text)const{
    return recipe(image).dump(-1,' ',false,Json::error_handler_t::replace).find(text)!=std::string::npos;
}
void NativeCanvas::set_alpha(const NativeArt& image,double value){image->alpha=std::clamp(int(value),0,255);}
void NativeCanvas::set_alpha(const std::string& name,double value){set_alpha(image(name),value);}
void NativeCanvas::alias_one(const std::string& old,const std::string& next){
    const auto a=atlas.find(old),b=atlas.find(next);if(!a||!b)return;
    saved_[old]=a;atlas.atlas[old]=b;
}
void NativeCanvas::alias(const std::string& old,const std::string& next){
    for(const auto suffix:{"","-受伤","-冰冻","-灰烬","-魅惑"})
        if(has(old+suffix)&&has(next+suffix))alias_one(old+suffix,next+suffix);
}
void NativeCanvas::restore(){
    for(auto& [key,image]:saved_)atlas.atlas[key]=image;
    saved_.clear();
}
NativeCanvas::Json NativeCanvas::recipe(const FrozenArt& image)const{
    const auto& r=*image->recipe;using K=NativeArtRecipe::Kind;
    if(r.external)return *std::static_pointer_cast<const Json>(r.external);
    switch(r.kind){
    case K::asset:return {{"op","asset"},{"key",r.key},{"size",{image->width,image->height}}};
    case K::canvas:return {{"op","canvas"},{"size",{image->width,image->height}},{"flags",r.flags},{"depth",32}};
    case K::scale:{
        Json args=Json::array({image->width,image->height});
        if(r.requested)args=Json::array({r.requested->x,r.requested->y});
        return {{"op","scale"},{"source",describe(r.source)},{"args",Json::array({args})}};
    }
    case K::flip:return {{"op","flip"},{"source",describe(r.source)},{"args",{r.flip_x,r.flip_y}}};
    case K::rotate:return {{"op","rotate"},{"source",describe(r.source)},{"args",{r.angle}}};
    case K::blit:return {{"op","blit"},{"source",describe(r.source)},{"overlay",describe(r.overlay)},
                         {"dest",{r.destination.x,r.destination.y}},{"area",nullptr},{"flags",0}};
    }
    throw std::logic_error("native frame recipe");
}
// NativeImage.describe(): {image, alpha, colorkey, size}; the default alpha reads 255 (SRCALPHA).
NativeCanvas::Json NativeCanvas::describe(const FrozenArt& image)const{
    const Json alpha=image->alpha<0&&!image->pixel_alpha?Json(nullptr):Json(image->alpha<0?255:image->alpha);
    return {{"image",recipe(image)},{"alpha",alpha},{"colorkey",nullptr},{"size",{image->width,image->height}}};
}
NativeCanvas::Json NativeCanvas::frame_json(const NativeFrame& f)const{
    Json commands=Json::array();
    for(const auto& c:f.commands){
        if(c.primitive){
            const auto& p=*c.primitive;
            Json row={{"op","primitive"},{"primitive",p.name},{"args",p.args?*std::static_pointer_cast<const Json>(p.args):Json{{p.color[0],p.color[1],p.color[2],p.color[3]},{p.x,p.y,p.w,p.h},p.width}},{"kwargs",Json::object()}};
            if(c.entity)row["entity"]=*c.entity;
            commands.push_back(std::move(row));continue;
        }
        Json row={{"op","image"},{"surface",describe(c.image)},{"pos",{c.position.x,c.position.y}},{"area",nullptr},{"flags",0}};
        if(c.entity)row["entity"]=*c.entity;
        if(!c.layer.empty())row["layer"]=c.layer;
        commands.push_back(std::move(row));
    }
    Json positions=Json::object();for(const auto& [uid,p]:f.positions)positions[uid]={p.x,p.y};
    return {{"protocol","native-draw-v1"},{"tick",f.tick},{"tile",f.tile},{"commands",commands},{"positions",positions}};
}
} // namespace pvz::typed72
