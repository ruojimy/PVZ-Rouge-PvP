#include "sim/typed/native_dave_draw.h"
#include "sim/typed/native_status_state.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double num(const Field<double>& own,const Field<double>& fallback,double otherwise=0.){
    if(own.present()&&!own.is_null())return own.get();
    if(fallback.present()&&!fallback.is_null())return fallback.get();
    return otherwise;
}
template<class T> bool truthy(const Field<T>& f){return f.present()&&!f.is_null()&&bool(f.get());}
}
void draw_dave(NativeCanvas& c,const DaveDraw& d,const std::function<void(const std::string&)>& unsupported){
    const auto& f=d.hero.frame;const auto& g=d.globals;const double tile=d.tile;
    const std::string skin=f.skin.get();
    const double facing=num(f.facing,g.facing,1.);
    const auto& position=*f.position.get();
    auto& atlas=c.atlas.atlas;
    const auto original_skin=c.atlas.find(skin);
    const auto restore=[&]{if(original_skin)atlas[skin]=original_skin;};
    try{
        if(d.materialize&&d.hero.ice.or_missing(0.)>0.&&c.has(skin+"-冰冻")){
            auto overlay=NativeArtStore::copy(c.image(skin+"-冰冻"));NativeCanvas::set_alpha(overlay,100.);
            auto iced=NativeArtStore::copy(original_skin);NativeArtStore::blit(iced,overlay,{0.,0.});
            atlas[skin]=iced;
        }
        if(d.materialize&&d.hero.poison.present()&&!d.hero.poison.is_null()&&d.hero.poison.get()){
            const auto& state=*d.hero.poison.get();
            if(state.level.present()&&!state.level.is_null())atlas[skin]=c.tint_poison(c.image(skin),state.level.get());
        }
        const double xx=num(f.xx,g.xx),yy=num(f.yy,g.yy),dushu=num(f.angle,g.angle);
        const Point at{(position.x-tile)+xx,(position.y-(tile*2.))+yy};
        const auto layer=[&](const std::string& key){
            if(facing==-1.)c.rotated(NativeCanvas::flip(c.image(key)),at,-dushu);
            else c.rotated(c.image(key),at,dushu);
        };
        if(d.materialize)layer(skin);
        if(d.hurt_alpha){
            NativeCanvas::set_alpha(c.image(skin+"-受伤"),double(*d.hurt_alpha));
            if(d.materialize)layer(skin+"-受伤");
        }
        if(d.materialize&&truthy(d.hero.secret.pea_head)&&f.hp.or_missing(0.)>0.){
            if(auto head=c.atlas.find("豌豆射手")){
                const int side=int(std::nearbyint(tile*.82));
                head=NativeArtStore::scale(head,side,side);
                if(facing<0.)head=NativeCanvas::flip(head);
                c.display(head,{position.x-tile*.41,position.y-tile*2.01});
            }
        }
        if(d.materialize&&d.hero.butter.or_missing(0.)>0.)c.display(c.image("黄油"),{position.x-tile*.5,position.y-tile*2.1});
        if(d.materialize&&d.hero.stun.or_missing(0.)>0.){
            const int side=std::max(1,int(tile*.2));
            const auto spark=NativeArtStore::scale(c.image("星星"),side,side);
            for(int n=0;n<3;++n){
                const double angle=double(d.native_tick)/50.+n*3.141592653589793*2/3;
                c.display(spark,{position.x+(std::cos(angle)*tile*.4-tile*.1),position.y+(-tile*2.25+std::sin(angle)*tile*.08)});
            }
        }
    }catch(...){restore();throw;}
    restore();
}
} // namespace pvz::typed72
