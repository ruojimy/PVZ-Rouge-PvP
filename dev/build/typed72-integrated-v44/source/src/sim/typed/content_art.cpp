#include "sim/typed/content_art.h"
#include "sim/typed/content_raster.h"
#include "core/pymath.h"
#include <cmath>
namespace pvz::typed72 {
namespace {
using content_raster::Canvas;
constexpr double pi=3.141592653589793;
Color rgba(int r,int g,int b,int a=255){return {uint8_t(r),uint8_t(g),uint8_t(b),uint8_t(std::clamp(a,0,255))};}
int rounded(double value){return int(py::round0(value));}
}
NativeArt ContentArt::required(const std::string& name)const {
    auto image=store_.find(name);if(!image)throw std::out_of_range("missing content art: "+name);return image;
}
void ContentArt::emit(const NativeArt& image,Point point){frame_.push_back({NativeArtStore::freeze(image),point});}
void ContentArt::center(const NativeArt& image,Point point,double angle) {
    const auto rotated=NativeArtStore::rotate(image,angle);
    emit(rotated,{point.x-rotated->width/2.,point.y-rotated->height/2.});
}
void ContentArt::draw_dart(const EntityRef& entity,Point point,double angle) {
    auto image=store_.find(entity->art_name.get());if(!image)image=required("豌豆");center(image,point,angle);
}
void ContentArt::draw_mortar_projectile(const EntityRef& entity,double angle,const std::optional<Point>& trail,std::string_view tail) {
    if(trail)center(required(std::string(tail)),*trail,angle);
    auto image=store_.find(entity->kind);if(!image)image=required("豌豆");
    const auto& p=entity->motion.get();center(image,{p.x,p.y},angle);
}
void ContentArt::draw_ghost_effect(const GhostBlast& effect) {
    const double age=double(world_.heroes.tick-effect.tick),tile=world_.runtime.tile;
    const int size=std::max(1,rounded(tile*2.5)),radius=std::max(1,rounded(size*.5*std::min(1.,(age+8.)/60.)));
    Canvas surface(size,size);surface.color=rgba(185,248,230,std::max(0,160-int(age*1.6)));
    content_raster::draw_circle(surface,size/2,size/2,radius,std::max(1,rounded(tile*.06)));
    emit(surface.image,{effect.point.x-size/2.,effect.point.y-size/2.});
}
void ContentArt::draw_reed_effect(const ReedBolt& effect) {
    const double age=double(world_.heroes.tick-effect.tick),tile=world_.runtime.tile;
    const int alpha=std::max(0,255-int(age*255./70.));
    Color outer,inner;
    if(effect.content=="闪电芦苇"){outer=rgba(150,205,255,alpha);inner=rgba(255,255,255,alpha);}
    else if(effect.content=="超载芦苇"){outer=rgba(255,110,200,alpha);inner=rgba(255,236,250,alpha);}
    else throw std::out_of_range("unknown reed bolt color");
    if(effect.points.empty())throw std::out_of_range("empty reed path");
    std::vector<Point> path{effect.points.front()};
    for(size_t n=0;n+1<effect.points.size();++n) {
        const auto a=effect.points[n],b=effect.points[n+1];const double dx=b.x-a.x,dy=b.y-a.y,length=std::hypot(dx,dy);
        const auto steps=std::max(2,int(length/(tile*.45)));const double nx=length?-dy/length:0.,ny=length?dx/length:0.;
        for(int k=1;k<steps;++k) {
            const double t=double(k)/steps;
            const double wobble=(py::mod(double(effect.tick)*7.+double(n)*31.+k*17.+std::floor(age/6.)*13.,9.)-4.)/4.*tile*.16;
            path.push_back({a.x+dx*t+nx*wobble,a.y+dy*t+ny*wobble});
        }
        path.push_back(b);
    }
    double left=path.front().x,top=path.front().y,right=left,bottom=top;
    for(const auto& p:path){left=std::min(left,p.x);top=std::min(top,p.y);right=std::max(right,p.x);bottom=std::max(bottom,p.y);}
    left-=6.;top-=6.;Canvas surface(std::max(1,int(right-left)+12),std::max(1,int(bottom-top)+12));
    for(auto& p:path){p.x-=left;p.y-=top;}
    surface.color=outer;content_raster::lines(surface,path,std::max(2,rounded(tile*.12)));
    surface.color=inner;content_raster::lines(surface,path,std::max(1,rounded(tile*.04)));
    content_raster::draw_circle(surface,rounded(path.back().x),rounded(path.back().y),std::max(2,rounded(tile*.12)),0);
    emit(surface.image,{left,top});
}
void ContentArt::draw_spring_effect(const SpringSwipe& effect) {
    const double age=double(world_.heroes.tick-effect.tick),tile=world_.runtime.tile;
    const int alpha=std::max(0,230-int(age*230./60.));const double reach=2.4*tile*(.55+.45*std::min(1.,age/18.));
    const int size=int(reach*2.+8.),center=size/2;const double half=30.*(pi/180.);  // math.radians(SPRING_HALF_ANGLE)
    Canvas surface(size,size);std::vector<Point> points{{double(center),double(center)}};
    for(int k=0;k<9;++k){const double angle=effect.angle-half+k*half/4.;points.push_back({center+std::cos(angle)*reach,center+std::sin(angle)*reach});}
    surface.color=rgba(150,230,110,alpha/3);content_raster::polygon(surface,points);
    surface.color=rgba(220,255,190,alpha);points.erase(points.begin());content_raster::lines(surface,points,std::max(2,int(std::floor(tile/14.))));
    emit(surface.image,{effect.point.x-center,effect.point.y-center});
}
void ContentArt::draw_grenade_effect(const GrenadeBlast& effect) {
    const double age=double(world_.heroes.tick-effect.tick),tile=world_.runtime.tile;
    const int radius=int(tile*(effect.instant?(.8+.7*age/45.):(.3+.45*age/45.))),alpha=std::max(0,240-int(age*240./45.));
    Canvas surface(radius*2+4,radius*2+4);surface.color=rgba(255,170,60,alpha);
    content_raster::draw_circle(surface,radius+2,radius+2,radius,0);surface.color=rgba(255,240,170,alpha);
    content_raster::draw_circle(surface,radius+2,radius+2,std::max(1,radius/2),0);
    emit(surface.image,{effect.point.x-radius-2.,effect.point.y-radius-2.});
}
void ContentArt::draw_grenade_projectile(const GrenadeRef& shot,double angle,double alpha) {
    auto image=NativeArtStore::rotate(required("手榴弹"),angle);if(alpha<255.){image=NativeArtStore::copy(image);image->alpha=int(alpha);}
    emit(image,{shot->motion.x-image->width/2.,shot->motion.y-image->height/2.});
}
void ContentArt::draw_hook_rope(Point point) {Canvas surface(3,3);surface.fill(rgba(151,153,150));emit(surface.image,point);}
void ContentArt::draw_zombie_projectile(const ContentProjectileRef& shot,std::string_view sprite,double angle,double alpha) {
    auto image=required(std::string(sprite));
    if(shot->defused.present()&&!shot->defused.is_null()&&shot->defused.get()){image=NativeArtStore::copy(image);image->alpha=int(alpha);}
    center(image,{shot->motion.x,shot->motion.y},angle);
}
void ContentArt::frost(Point point,int count,double radius,int seed,double age) {
    const double tile=world_.runtime.tile;
    for(int i=0;i<count;++i) {
        const double k=i*2.399+seed,p=std::min(1.,age/100.),r=radius*(.2+.8*p)*(.6+.1*(i*7%5));
        const double x=point.x+std::cos(k)*r,y=point.y+std::sin(k)*r*.6+p*tile*.2;
        const int alpha=int(210.*(1.-p*p));if(alpha<=0)continue;
        const int size=std::max(2,rounded(tile*(.07+.09*p)));Canvas mote(size,size);mote.fill(rgba(205,240,255));
        if(i%4==0&&p<.5){mote.color=rgba(255,255,255);for(int row=size/3;row<size/3+std::max(1,size/3);++row)mote.hline(0,size-1,row);}
        mote.image->alpha=alpha;emit(mote.image,{x-size/2.,y-size/2.});
    }
}
void ContentArt::draw_lettuce_flash(const LettuceFlash& effect) {
    const double tile=world_.runtime.tile,age=double(world_.heroes.tick-effect.tick);
    Canvas surface{int(tile),int(tile)};surface.fill(rgba(120,220,255,std::max(0,120-int(age*1.2))));
    for(const auto& [row,col]:effect.water)emit(surface.image,{col*tile,row*tile});
    frost(effect.point,16,tile*1.6,int(py::mod(double(effect.tick),7.)),age);
}
} // namespace pvz::typed72
