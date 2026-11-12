#include "sim/typed/native_patch_draw.h"
#include "sim/typed/plant_zombie_target.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double pi=3.141592653589793;
double field(const Field<double>& f,double otherwise){return f.present()&&!f.is_null()?f.get():otherwise;}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::string text(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string{};}
constexpr double FIRE_ANIM_FRAMES=24.,UMBRELLA_FIRE_ANIM_FRAMES=50.;
}
void NativePatchDraw::draw_overlays(){
    zombie_peas();
    fume_bubbles();
    plant_zombie_heads();
}
NativeArt NativePatchDraw::bubble_surface(const std::string& name){
    // __pvz_sb_fumeshroom_bubble_surface: the atlas bubble when large enough, else a cached
    // scaled copy, else a drawn three-circle bubble (__pvz_sb_make_fumeshroom_bubble_surface).
    const double scale=std::max(1.,world_.runtime.tile),target=std::max(10.,scale*.58);
    const std::string key="__pvz_sb_visible_"+name;
    if(const auto cached=canvas_.atlas.find(key))if(cached->width>=target*.8&&cached->height>=target*.8)return cached;
    NativeArt surface=canvas_.atlas.find(name);if(!surface)surface=canvas_.atlas.find("大泡泡");if(!surface)surface=canvas_.atlas.find("泡泡");
    if(surface){
        if(surface->width>=target*.8&&surface->height>=target*.8)return surface;
        auto visible=NativeArtStore::scale(surface,int(target),int(target));canvas_.atlas.atlas[key]=visible;return visible;
    }
    using J=NativeCanvas::Json;
    const int size=std::max(4,int(target));
    auto made=NativeCanvas::surface(size,size);
    const bool blue=name=="蓝泡泡";
    const J fill=blue?J::array({88,170,255,190}):J::array({214,126,213,190});
    const J edge=blue?J::array({42,86,190,230}):J::array({94,44,126,230});
    const J shine=blue?J::array({190,230,255,210}):J::array({246,198,248,210});
    const int radius=std::max(2,size/2-2);
    canvas_.draw_on(made,"circle",J::array({edge,J::array({size/2,size/2}),radius}));
    canvas_.draw_on(made,"circle",J::array({fill,J::array({size/2,size/2}),std::max(1,radius-2)}));
    canvas_.draw_on(made,"circle",J::array({shine,J::array({std::max(1,size/3),std::max(1,size/3)}),std::max(1,size/8)}));
    canvas_.atlas.atlas[key]=made;return made;
}
void NativePatchDraw::fume_bubbles(){
    // __pvz_sb_draw_fumeshroom_bubbles: advances the bubbles to `now`, then draws each.
    if(world_.fume.bubbles.empty())return;
    if(update_bubbles)update_bubbles(now);
    if(world_.fume.bubbles.empty())return;
    canvas_.patch_plant_zombie_assets();
    for(const auto& b:world_.fume.bubbles){
        const auto surface=bubble_surface(b.name.empty()?std::string("大泡泡"):b.name);
        if(!surface)continue;
        canvas_.display(surface,{b.motion.x-double(surface->width)*.5,b.motion.y-double(surface->height)*.5});
    }
}
NativeArt NativePatchDraw::flip_cached(const NativeArt& source,const std::string& key){
    // __pvz_sb_flip_surface: the flipped art is cached in the atlas under `key`.
    if(const auto cached=canvas_.atlas.find(key))return cached;
    auto flipped=NativeCanvas::flip(source);canvas_.atlas.atlas[key]=flipped;return flipped;
}
NativeArt NativePatchDraw::smoothscaled(const NativeArt& surface,double factor){
    // __pvz_sb_scaled_surface through hand graphics transform.smoothscale.
    factor=std::max(.1,factor);
    if(std::fabs(factor-1.)<=.02)return surface;
    const int w=std::max(1,int(double(surface->width)*factor)),h=std::max(1,int(double(surface->height)*factor));
    auto out=NativeArtStore::scale(surface,w,h);
    auto r=std::make_shared<NativeArtRecipe>(*out->recipe);
    r->external=std::make_shared<const NativeCanvas::Json>(NativeCanvas::Json{{"op","smoothscale"},{"source",canvas_.describe(surface)},{"args",{{w,h}}}});
    out->recipe=r;return out;
}
void NativePatchDraw::zombie_peas(){
    // __pvz_sb_draw_zombie_peas: legacy shots first, then zombie-pea entities.
    std::vector<std::shared_ptr<Entity>> peas(world_.zombie_peas.legacy->begin(),world_.zombie_peas.legacy->end());
    for(const auto& e:*world_.runtime.entities.list())if(yes(e->pea.zombie_pea)||e->kind=="僵尸豌豆")peas.push_back(e);
    if(peas.empty())return;
    canvas_.patch_plant_zombie_assets();
    NativeArt pea=canvas_.atlas.find("僵尸豌豆");if(!pea)pea=canvas_.atlas.find("豌豆");if(!pea)return;
    for(const auto& e:peas){
        const auto& m=e->motion.get();
        NativeArt surface=pea;
        const auto fire=text(e->source.zombie_fire);
        if(!fire.empty())if(const auto alt=canvas_.atlas.find(fire=="blue"?"蓝火豆":"火豆"))surface=alt;
        canvas_.display(surface,{m.x-(double(surface->width)*.5),m.y-(double(surface->height)*.5)});
    }
}
void NativePatchDraw::plant_zombie_heads(){
    const double scale=world_.runtime.tile;
    std::vector<ZombieRef> drawable;
    for(const auto& t:*world_.targets){
        const auto& u=t.unit;
        if(!u||!yes(u->patch.plant_zombie))continue;
        if(u->body.hp<=0.)continue;
        if(!native_plant_zombie_config(text(u->patch.plant_name)))continue;
        drawable.push_back(u);
    }
    if(!drawable.empty())canvas_.patch_plant_zombie_assets();
    for(const auto& u:drawable){
        const auto name=text(u->patch.plant_name);
        const auto [direction,angle]=sync_native_head_angle(*u);
        const auto& cfg=*native_plant_zombie_config(name);
        // pm_native_patch status_head over __pvz_sb_plant_zombie_head_surface: a status variant
        // of the head art (受伤, 灰烬, 冰冻, 魅惑 in that priority) when the atlas has one. A
        // charmed 大喷菇僵尸 under the thunder secret uses the thunder head instead.
        const auto& b=u->body;
        const bool is_thunder=name=="大喷菇僵尸"&&thunder&&thunder(u);
        const std::string head_key=is_thunder?std::string("__pvz_sb_fumeshroom_zombie_thunder_head"):name+"-植头";
        const std::string suffix=b.hurt>0.?"-受伤":b.ash.present()?"-灰烬":(b.ice.present()&&!b.ice.is_null()&&b.ice.get()>0.)?"-冰冻":u->source.charmed.present()?"-魅惑":"";
        NativeArt head;
        if(!suffix.empty())if(const auto variant=canvas_.atlas.find(head_key+suffix))
            head=direction>0.?variant:flip_cached(variant,head_key+suffix+"-pvp-left");
        if(!head){
            head=canvas_.atlas.find(head_key);if(!head)continue;
            if(!(direction>0.))head=flip_cached(head,is_thunder?head_key+"-左":name+"-植头左");
        }
        // __pvz_sb_plant_zombie_head_center
        const auto& pos=u->body.motion.get();
        const bool duck=yes(u->patch.duck);
        const double y_factor=field(duck?cfg.duck_head_y:cfg.head_y,1.35),x_factor=field(duck?cfg.duck_head_x:cfg.head_x,.08);
        const double anim=field(u->patch.fire_animation,0.);
        const double frames=std::max(1.,field(cfg.fire_anim,FIRE_ANIM_FRAMES));
        const double elapsed=std::max(0.,frames-anim),window=std::max(1.,frames*.75);
        const double phase=anim>0.?std::sin((pi*std::min(window,elapsed))/window):0.;
        const double recoil=yes(cfg.fumeshroom)?0.:(std::max(0.,phase)*scale)*.05;
        Point center{(pos.x+((direction*scale)*x_factor))-(direction*recoil),pos.y-(scale*y_factor)};
        double angle_delta=0.;
        if(yes(cfg.fumeshroom)){
            // __pvz_sb_fumeshroom_zombie_animated_head: the mouth lunges along the shot.
            const double fire_frames=std::max(1.,double(int64_t(field(cfg.fire_anim,100.))));
            const double shot=double(int64_t(field(u->patch.shoot,0.))),shot_anim=field(u->patch.fire_animation,0.);
            const double tick=shot<=0.&&shot_anim<=0.?0.:std::max(1.,std::min(fire_frames,shot<=0.?1.:shot));
            if(tick>0.&&tick<fire_frames){
                double shoot=(tick*200.)/std::max(1.,fire_frames);
                if(shoot>=150.)shoot=200.-shoot;
                if(shoot>50.)shoot=50.;
                if(shoot>0.){
                    const double shoot_angle=(pi*shoot)/100.;
                    const double shoot_sin=(((-2./pi)*shoot_angle)+2.)*std::sin(shoot_angle);
                    const double facing=b.facing<0.?-1.:1.;
                    center={center.x+((shoot_sin*scale)*.15)*facing,center.y-(shoot_sin*scale)*.05};
                    angle_delta=(shoot_sin*20.)*facing;
                }
            }
        }
        const double head_w=double(head->width),head_h=double(head->height);
        const double base=direction>0.?0.:180.;
        const double local=((py::mod(((angle-base)+180.),360.)-180.)+0.)+angle_delta;
        canvas_.rotated(head,{center.x-(head_w*.5),center.y-(head_h*.5)},local);
        // __pvz_sb_draw_plant_zombie_head_armor
        const auto& armor=u->body.armor;
        if((armor=="路障"||armor=="铁桶")&&u->body.armor_hp>0.){
            if(NativeArt surface=canvas_.atlas.find(armor)){
                if(!(direction>0.))surface=flip_cached(surface,armor+"-植僵左");
                const double width=double(surface->width),height=double(surface->height);
                const double base_visible_x=width*(22.5/36.);
                const double visible_x=direction<0.?width-base_visible_x:base_visible_x,visible_y=height*(6./36.);
                const double px=scale/18.;
                const double tx=center.x+(direction*((scale*.02)+(field(cfg.armor_x,0.)*px)));
                const double ty=(center.y-(scale*.22))+(field(cfg.armor_y,0.)*px);
                canvas_.rotated(surface,{tx-visible_x,ty-visible_y},local);
            }
        }
        // __pvz_sb_draw_umbrella_zombie_leaf
        if(name=="萝卜伞僵尸"&&anim>0.){
            const auto* umbrella=native_plant_zombie_config("萝卜伞僵尸");
            const double leaf_frames=std::max(1.,umbrella?field(umbrella->fire_anim,UMBRELLA_FIRE_ANIM_FRAMES):UMBRELLA_FIRE_ANIM_FRAMES);
            if(const auto leaf=canvas_.atlas.find("叶子伞")){
                const double progress=std::max(0.,std::min(1.,(leaf_frames-anim)/leaf_frames));
                const double pulse=std::sin(pi*progress);
                const auto surface=smoothscaled(leaf,.85+(1.35*std::max(0.,pulse)));
                const double w=double(surface->width),h=double(surface->height);
                canvas_.display(surface,{center.x-(w*.5),(center.y-(h*.62))-(scale*.05)});
            }
        }
    }
}
} // namespace pvz::typed72
