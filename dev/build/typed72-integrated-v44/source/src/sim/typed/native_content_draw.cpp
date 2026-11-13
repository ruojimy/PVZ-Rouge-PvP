#include "sim/typed/native_content_draw.h"
#include "core/pymath.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double num(const Field<double>& f){return f.present()&&!f.is_null()?f.get():0.;}
std::string text(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string{};}
}
void NativeContentDraw::draw_center(const NativeArt& image,double x,double y,double angle){
    const auto turned=NativeArtStore::rotate(image,angle);
    canvas_.display(turned,{x-double(turned->width)/2.,y-double(turned->height)/2.});
}
namespace {
constexpr double kpi=3.141592653589793;
std::string itext(double v){return std::to_string(int64_t(v));}
// CartDrawing over the native canvas: handles index the images of one cart draw.
class CanvasCartDrawing final:public CartDrawing {
public:
    explicit CanvasCartDrawing(NativeCanvas& canvas):canvas_(canvas){}
    CartImage art(std::string_view name)override{return add(canvas_.image(std::string(name)));}
    CartImage saved_art(std::string_view name,CartImage)override{return add(canvas_.unaliased(std::string(name)));}
    CartImage copy(CartImage i)override{return add(NativeArtStore::copy(at(i)));}
    Point dimensions(CartImage i)override{return {double(at(i)->width),double(at(i)->height)};}
    void fill(CartImage i,int r,int g,int b,CartBlend blend)override{canvas_.fill(at(i),NativeCanvas::Json::array({r,g,b}),nullptr,blend==CartBlend::rgb_max?5:3);}
    void alpha(CartImage i,int value)override{NativeCanvas::set_alpha(at(i),double(value));}
    void blit(CartImage d,CartImage s,Point p)override{NativeArtStore::blit(at(d),at(s),p);}
    CartImage rotate(CartImage i,double degrees)override{return add(NativeArtStore::rotate(at(i),degrees));}
    CartImage scale(CartImage i,Point size)override{return add(canvas_.resize(at(i),size.x,size.y));}
    CartImage mirror(CartImage i)override{return add(NativeCanvas::flip(at(i)));}
    CartImage tint_poison(CartImage i,int level)override{return add(canvas_.tint_poison(at(i),level));}
    void display(CartImage i,Point p)override{canvas_.display(at(i),p);}
private:
    NativeCanvas& canvas_;
    std::vector<NativeArt> images_;
    CartImage add(NativeArt image){images_.push_back(std::move(image));return images_.size()-1;}
    const NativeArt& at(CartImage i)const{return images_.at(size_t(i));}
};
}
void NativeContentDraw::draw_custom_plant(const CombatPlant& p,std::string key,double x,double y,bool bottom,double angle){
    if(!canvas_.drawing())return;
    const double tile=world_.runtime.tile,now=double(native_tick);
    const auto base_key=key;
    if(p.monochrome.present()&&canvas_.has(key+"-黑白"))key+="-黑白";
    auto image=NativeArtStore::copy(canvas_.image(key));
    const bool sleeping=p.sleep.present();const double hurt=num(p.hurt);
    if(hurt>0.&&canvas_.has(base_key+"-受伤")){
        auto overlay=NativeArtStore::copy(canvas_.image(base_key+"-受伤"));
        NativeCanvas::set_alpha(overlay,std::nearbyint(std::fabs(std::sin(hurt/50.*kpi))*200.));
        NativeArtStore::blit(image,overlay,{0.,0.});
    }
    if(p.facing<0.)image=NativeCanvas::flip(image);
    const bool dead=p.dead.present()||(p.hp.present()&&!p.hp.is_null()&&p.hp.get()<=0.);
    if(dead){
        image=NativeArtStore::scale(image,int(std::nearbyint(tile*1.2)),std::max(1,int(std::nearbyint(tile*.3))));
        x=(double(p.cell.x)+.5)*tile;y=(double(p.cell.y)+1.)*tile;bottom=true;
        NativeCanvas::set_alpha(image,185.);
    }else{
        if(sleeping){
            canvas_.fill(image,NativeCanvas::Json::array({180,190,210}),nullptr,3);
            angle=p.facing*(8.+std::sin(now/85.)*2.);
        }else if(hurt>0.)angle+=p.facing*std::sin(hurt/5.)*3.;
        if(angle!=0.)image=NativeArtStore::rotate(image,angle);
    }
    const double w=double(image->width),h=double(image->height);
    canvas_.display(image,{x-w/2.,bottom?y-h:y-h/2.});
    if(sleeping&&!dead){
        const int side=int(std::nearbyint(tile*.4));
        const auto mark=NativeArtStore::scale(canvas_.image("睡觉"),side,side);
        const double lift=py::mod(now,200.)/200.*tile*.3;
        canvas_.display(mark,{x+tile*.22,y-(bottom?h:h/2.)-tile*.2-lift});
    }
}
bool NativeContentDraw::draw_plant(const CombatPlant& p){
    const auto name=text(p.source.content);if(name.empty())return false;
    const double tile=world_.runtime.tile,now=double(native_tick);
    const double row=double(p.cell.y),col=double(p.cell.x);
    const double fired=p.last_fired.present()&&!p.last_fired.is_null()?p.last_fired.get():-std::pow(10.,6.);
    if(name=="甜薯"||name=="豌豆迫击炮"||name=="弹簧草"){
        if(!canvas_.drawing())return true;
        const auto sink=pvp64_sinks.find(name);
        const double x=(col+.5)*tile,y=((row+1.)*tile)+(sink!=pvp64_sinks.end()?sink->second:0.);
        std::string key;
        if(name=="甜薯")key=p.sleep.present()?name+"-睡眠0":name+"-帧"+itext(py::mod(py::floordiv(now,60.),4.));
        else{
            const double elapsed=now-fired;
            if(p.sleep.present())key=name+"-睡眠0";
            else if(elapsed<80.)key=name+"-攻击"+itext(std::min(3.,py::floordiv(std::max(0.,elapsed),20.)));
            else key=name+"-帧"+itext(py::mod(py::floordiv(now,45.),4.));
        }
        draw_custom_plant(p,key,x,y,true);return true;
    }
    if(name=="闪电芦苇"||name=="超载芦苇"){
        if(!canvas_.drawing())return true;
        const double elapsed=now-fired;
        const std::string state=p.sleep.present()?"睡眠":elapsed<80.?"攻击":"帧";
        const double frame=state=="攻击"?std::min(3.,py::floordiv(std::max(0.,elapsed),20.)):py::mod(py::floordiv(now,45.),4.);
        draw_custom_plant(p,name+"-"+state+itext(frame),(col+.5)*tile,(row+1.)*tile,true);return true;
    }
    if(name=="幽灵辣椒"||name=="黄金蓓蕾"){
        if(!canvas_.drawing())return true;
        const double age=num(p.content_age);
        double frame=py::mod(py::floordiv(age,35.),2.);
        if(name=="幽灵辣椒"&&p.ghost_started.present())frame=2.+py::mod(py::floordiv(age,35.),2.);
        else if(name=="黄金蓓蕾"&&age>75.)frame=2.;
        if(p.sleep.present())frame=0.;
        const double x=(col+.5)*tile;double y=(row+.45)*tile;
        if(name=="幽灵辣椒"){
            // september draw_ghost_range: the armed pepper's white fog over cells -5..+5,
            // as two strips so each origin stays near its visible cells on wrap maps.
            const bool effect_done=p.effect_done.present()&&!p.effect_done.is_null()&&p.effect_done.get();
            const bool live=p.hp.present()&&!p.hp.is_null()&&p.hp.get()>0.;
            if(p.ghost_started.present()&&!p.ghost_started.is_null()&&!effect_done&&!p.dead.present()&&live&&now-p.ghost_started.get()<2500.){
                const double started=p.ghost_started.get();
                const auto fog=canvas_.image("幽灵白雾-帧"+itext(py::mod(py::floordiv(now-started,25.),8.)));
                const double split=tile*6.;
                for(const auto [offset,width]:{std::pair{0.,split},std::pair{split,tile*5.}}){
                    const auto piece=canvas_.crop(fog,offset,0.,width,double(fog->height));
                    canvas_.display(piece,{x-tile*5.5+offset,y-double(fog->height)/2.});
                }
            }
            y+=(std::sin(age/40.)*tile)*.04;
        }
        draw_custom_plant(p,name+"-帧"+itext(frame),x,y);return true;
    }
    if(name=="阳光藤蔓"||name=="忧郁藤蔓"){
        if(!canvas_.drawing())return true;
        const auto start=canvas_.frames.size();
        double y=(row+1.)*tile;std::string key=name;
        if(name=="忧郁藤蔓")y+=tile*.1;
        if(!p.sleep.present())key+="-帧"+itext(py::mod(py::floordiv(now,60.),4.));
        draw_custom_plant(p,key,(col+.5)*tile,y,true);
        canvas_.frames.tag_layer(start,"vine_foreground");return true;
    }
    if(name=="抓人草"||name=="冰冻生菜"){
        // pvp70_content.draw_plant: x from native_content.point (row+.45 is unused here).
        const double x=(col+.5)*tile,ground=(row+1.)*tile;
        draw_custom_plant(p,name+"-帧"+itext(py::mod(py::floordiv(now,60.),4.)),x,ground,true);
        if(name=="冰冻生菜"&&p.hp.present()&&!p.hp.is_null()&&p.hp.get()>0.&&!p.dead.present()&&!(p.effect_done.present()&&!p.effect_done.is_null()&&p.effect_done.get()))
            frost(x,ground-tile*.55,11,tile*.7,col,std::nullopt,ground);
        return true;
    }
    if(name=="水盆"){
        // pvp70_content.draw_plant BASIN: scaled water with an open-topped two-tone rim.
        const bool grey=p.monochrome.present();
        const auto image=NativeArtStore::copy(canvas_.resize(canvas_.image(grey&&canvas_.has("水-黑白")?"水-黑白":"水"),tile,tile));
        using J=NativeCanvas::Json;
        const auto rim=[&](J color,double inset,int width){
            const double a=inset,b=tile-2.-inset;
            canvas_.draw_on(image,"lines",J::array({std::move(color),false,J::array({J::array({a,0}),J::array({a,b}),J::array({b,b}),J::array({b,0})}),width}));
        };
        rim(grey?J::array({58,58,58}):J::array({91,48,24}),0.,std::max(2,int(std::nearbyint(tile*.09))));
        // Second rim: (2,0),(2,tile-4),(tile-4,tile-4),(tile-4,0).
        canvas_.draw_on(image,"lines",J::array({grey?J::array({112,112,112}):J::array({162,99,48}),false,J::array({J::array({2,0}),J::array({2,tile-4.}),J::array({tile-4.,tile-4.}),J::array({tile-4.,0})}),std::max(1,int(std::nearbyint(tile*.035)))}));
        if(num(p.hurt)>0.)rim(J::array({220,171,99}),0.,2);
        canvas_.display(image,{col*tile,row*tile});
        return true;
    }
    if(name=="抓人草触手"){draw_head(p);return true;}
    if(name=="旋转芜菁"||name=="芦笋战机"){
        // pvp56 FlyingPlants.draw_plant.
        if(!canvas_.drawing())return true;
        const double age=num(p.content_age);const bool sleeping=p.sleep.present();
        const double frame=sleeping?0.:py::mod(py::floordiv(age,18.),4.);
        const double last=p.last_fired.present()&&!p.last_fired.is_null()?p.last_fired.get():-1000.;
        const std::string pose=sleeping?"睡眠":(now-last<50.?"攻击":"帧");
        const auto mode=text(p.flying.mode);
        const double angle=name=="芦笋战机"&&(mode=="sweep"||mode=="rest")?-num(p.flying.sweep_angle):0.;
        const double x=(col+.5)*tile,y=(row+.45)*tile+std::sin(age/40.)*tile*.035;
        draw_custom_plant(p,name+"-"+pose+itext(frame),x,y,false,angle);
        return true;
    }
    if(name=="原始土豆地雷"){
        // pvp64 draw_primal: rises out of the ground; below the terrain foreground until out.
        if(!canvas_.drawing())return true;
        const double out=std::max(0.,std::min(200.,num(p.emerged)));
        const bool buried=num(p.buried)>0.||out<200.;
        const double sink=tile*(.76-out/200.*.46);
        const bool lit=out>0.&&py::mod(py::floordiv(num(p.flash),150.),2.)==0.;
        const auto start=canvas_.frames.size();
        draw_custom_plant(p,name+(lit?"-亮":""),(col+.5)*tile,(row+1.)*tile+sink,true);
        if(buried)canvas_.frames.tag_layer(start,"below_ground");
        return true;
    }
    return false;
}
// pvp70_content.frost: cold-air motes, a pure function of the native tick.
void NativeContentDraw::frost(double x,double y,int count,double radius,double seed,std::optional<double> age,std::optional<double> ground){
    const double tile=world_.runtime.tile,now=double(native_tick);
    for(int i=0;i<count;++i){
        const double k=i*2.399+seed;double p,px,py_;
        if(!age){
            p=py::mod(now+i*53.+seed*17.,150.)/150.;
            px=x+std::cos(k)*radius*(.25+.75*p);
            py_=y+std::sin(k)*tile*.12+p*tile*.4;
            if(ground)py_=std::min(py_,*ground-tile*.08);
        }else{
            p=std::min(1.,*age/100.);
            const double r=radius*(.2+.8*p)*(.6+.1*double(i*7%5));
            px=x+std::cos(k)*r;py_=y+std::sin(k)*r*.6+p*tile*.2;
        }
        const int alpha=int(210.*(1.-p*p));
        if(alpha<=0)continue;
        const int size=std::max(2,int(std::nearbyint(tile*(.07+.09*p))));
        const auto mote=NativeCanvas::surface(size,size,0);
        canvas_.fill(mote,NativeCanvas::Json::array({205,240,255}));
        if(i%4==0&&p<.5)canvas_.fill(mote,NativeCanvas::Json::array({255,255,255}),NativeCanvas::Json::array({0,size/3,size,std::max(1,size/3)}));
        NativeCanvas::set_alpha(mote,double(alpha));
        canvas_.display(mote,{px-size/2.,py_-size/2.});
    }
}
// pvp70_content.draw_head: a tentacle head (a plant record), its thorned vine to the root and
// the mouth; a dead head is flattened (crushed) or wilts and fades.
void NativeContentDraw::draw_head(const CombatPlant& z){
    if(!canvas_.drawing())return;
    using J=NativeCanvas::Json;
    const double tile=world_.runtime.tile,now=double(native_tick);
    const auto& s=z.content70;const int color=s.head_color.present()&&!s.head_color.is_null()?s.head_color.get():0;
    const std::string head="抓人草触手-色"+std::to_string(((color%3)+3)%3);
    const auto alive=[](const CombatPlant& p){return p.hp.present()&&!p.hp.is_null()&&p.hp.get()>0.&&!p.dead.present();};
    const Point at=z.head_point.present()&&!z.head_point.is_null()?z.head_point.get():Point{};
    const double x=at.x,y=at.y;
    if(!alive(z)){
        auto image=canvas_.image(head+"-帧0");
        const bool crushed=s.head_crushed.present()&&!s.head_crushed.is_null();
        double since;
        if(crushed)since=s.head_crushed.get();
        else{const auto key=text(z.source.id);auto found=head_died_.find(key);if(found==head_died_.end())found=head_died_.emplace(key,now).first;since=found->second;}
        const double age=std::max(0.,now-since);
        if(crushed){
            const double f=std::min(1.,age/30.);
            const int w=int(std::nearbyint(image->width*(1.+.25*f))),h=std::max(1,int(std::nearbyint(image->height*(1.-.7*f))));
            image=canvas_.resize(image,w,h);
        }else{
            const double k=std::max(.2,1.-age/250.);image=canvas_.rotozoom(image,z.facing*-age*.3,k);
        }
        image=NativeArtStore::copy(image);NativeCanvas::set_alpha(image,double(std::max(0,255-int(std::max(0.,age-150.)*255./250.))));
        const double w=image->width,h=image->height;
        canvas_.display(image,crushed?Point{x-w/2.,y+tile*.45-h}:Point{x-w/2.,y-h/2.});
        return;
    }
    const CombatPlant* parent=nullptr;
    if(s.parent.present()&&!s.parent.is_null())
        for(const auto& plant:*world_.plant_roster)if(text(plant->source.id)==s.parent.get()){parent=plant.get();break;}
    if(!parent||!alive(*parent))return;
    const double bx=(double(parent->cell.x)+.5)*tile,by=(double(parent->cell.y)+41./48.)*tile;
    // head_pose: drawn mouth direction and the neck the vine joins.
    double ux=parent->facing,uy=0.;
    if(s.head_aim.present()&&!s.head_aim.is_null()){ux=s.head_aim.get().x;uy=s.head_aim.get().y;}
    const bool sleeping=z.sleep.present();
    if(sleeping){
        const double droop=-z.facing*(20.+std::sin(now/85.)*3.);
        const double turn=std::atan2(uy,ux)-droop*(kpi/180.);ux=std::cos(turn);uy=std::sin(turn);
    }
    const double neck_x=x-ux*tile*.44,neck_y=y-uy*tile*.44;
    const double dx=wrap_delta(bx,neck_x,world_.world_width.get());
    const int width=std::max(1,int(std::nearbyint(std::fabs(dx)+tile))),height=std::max(1,int(std::nearbyint(std::fabs(neck_y-by)+tile)));
    if(width>32.*tile||height>24.*tile)return;
    const auto canvas=NativeCanvas::surface(width,height);
    const bool grey=parent->monochrome.present();
    const auto tone=[&](std::array<int,3> c){
        if(grey){const int g=int(std::nearbyint(.299*c[0]+.587*c[1]+.114*c[2]));c={g,g,g};}
        return J::array({c[0],c[1],c[2]});
    };
    const double ox=std::min(bx,bx+dx)-tile/2.,oy=std::min(by,neck_y)-tile/2.;
    J points=J::array(),lifted=J::array();
    for(int i=0;i<33;++i){
        const double f=i/32.;const double a=bx+dx*f-ox,b=by+(neck_y-by)*f+std::sin(f*kpi)*tile*.2-oy;
        points.push_back(J::array({a,b}));lifted.push_back(J::array({a,b-tile*.025}));
    }
    const auto w=[&](double v,int lo){return std::max(lo,int(std::nearbyint(v)));};
    J strokes=J::array();
    const auto stroke=[&](const std::string& primitive,J args){strokes.push_back({{"primitive",primitive},{"args",std::move(args)}});};
    stroke("lines",J::array({tone({48,24,30}),false,points,w(tile*.15,3)}));
    static constexpr std::array<std::array<int,3>,3> mids{{{155,64,61},{165,72,82},{130,77,60}}},lights{{{216,115,94},{222,119,129},{186,130,93}}};
    const int ci=((color%3)+3)%3;
    const auto mid=tone(mids[ci]),light=tone(lights[ci]);
    stroke("lines",J::array({mid,false,points,w(tile*.10,2)}));
    stroke("lines",J::array({light,false,lifted,w(tile*.025,1)}));
    const double length=std::hypot(dx,neck_y-by);
    const int joints=std::max(2,std::min(48,int(length/(tile*.55))));
    for(int i=1;i<joints;++i){
        const double f=i/double(joints);
        const double a=bx+dx*f-ox,b=by+(neck_y-by)*f+std::sin(f*kpi)*tile*.2-oy;
        double tx=dx,ty=neck_y-by+std::cos(f*kpi)*kpi*tile*.2;
        double norm=std::hypot(tx,ty);if(norm==0.)norm=1.;tx/=norm;ty/=norm;
        const double nx=-ty,ny=tx;
        stroke("line",J::array({tone({85,39,41}),J::array({a-nx*tile*.05,b-ny*tile*.05}),J::array({a+nx*tile*.05,b+ny*tile*.05}),w(tile*.035,1)}));
        const double side=i%2?1.:-1.;
        const double tipx=a+nx*tile*.14*side-tx*tile*.025,tipy=b+ny*tile*.14*side-ty*tile*.025;
        stroke("polygon",J::array({tone({67,33,33}),J::array({J::array({a-tx*tile*.055,b-ty*tile*.055}),J::array({tipx,tipy}),J::array({a+tx*tile*.065,b+ty*tile*.065})})}));
        stroke("line",J::array({light,J::array({a,b}),J::array({a+(tipx-a)*.62,b+(tipy-b)*.62}),w(tile*.02,1)}));
    }
    canvas_.draw_batch(canvas,std::move(strokes));
    canvas_.display(canvas,{ox,oy});
    const double frame=sleeping?0.:py::mod(py::floordiv(now,45.),4.);
    const std::string key=head+"-帧"+itext(frame);
    const std::string suffix=num(z.hurt)>0.?"-受伤":grey?"-黑白":"";
    auto image=canvas_.image(key+suffix);
    const double angle=-(std::atan2(uy,ux)*(180./kpi));
    if(sleeping){image=NativeArtStore::copy(image);canvas_.fill(image,J::array({180,190,210}),nullptr,3);}
    if(angle!=0.)image=NativeArtStore::rotate(image,angle);
    const double h=image->height;
    canvas_.display(image,{x-image->width/2.,y-h/2.});
    if(sleeping){
        const int side=int(std::nearbyint(tile*.4));
        const auto mark=NativeArtStore::scale(canvas_.image("睡觉"),side,side);
        const double lift=py::mod(now,200.)/200.*tile*.3;
        canvas_.display(mark,{x+tile*.22,y-h/2.-tile*.2-lift});
    }
}
namespace {
struct ZombieFrameArt {bool overlay_if_present=false;bool key_fallback=false;};
}
static NativeArt status_frame(NativeCanvas& c,const ZombieRef& u,const std::string& key,bool fallback,bool checked){
    const auto& b=u->body;
    const std::string suffix=b.ash.present()?"-灰烬":b.hurt>0.?"-受伤":"";
    auto image=NativeArtStore::copy(fallback&&!c.has(key+suffix)?c.image(key):c.image(key+suffix));
    if(!b.ash.present()){
        const bool iced=b.ice.present()&&!b.ice.is_null()&&b.ice.get()>0.,charmed=u->source.charmed.present();
        for(const auto& [enabled,state]:{std::pair{iced,"-冰冻"},std::pair{charmed,"-魅惑"}})if(enabled&&(!checked||c.has(key+state))){
            auto overlay=NativeArtStore::copy(c.image(key+state));NativeCanvas::set_alpha(overlay,100.);
            NativeArtStore::blit(image,overlay,{0.,0.});
        }
    }
    if(u->poison.poison.present()&&!u->poison.poison.is_null()&&u->poison.poison.get()){
        const auto& level=u->poison.poison.get()->level;
        if(level.present()&&!level.is_null())image=c.tint_poison(image,level.get());
    }
    if(b.facing<0.)image=NativeCanvas::flip(image);
    return image;
}
static void place_frame(NativeCanvas& c,const ZombieRef& u,const NativeArt& image){
    const auto& b=u->body;const auto& m=b.motion.get();
    const double w=double(image->width),h=double(image->height);
    c.display(image,{m.x-w/2.,m.y-h});
    if(b.butter.present()&&!b.butter.is_null()&&b.butter.get()>0.&&b.hp>0.){
        const auto butter=c.unaliased("黄油砸");
        c.display(butter,{m.x-double(butter->width)/2.,(m.y-h)-double(butter->height)/2.});
    }
}
void NativeContentDraw::draw_zombie64(const ZombieRef& u){
    const auto name=text(u->source.content);
    const bool slime=name=="史莱姆僵尸"||name=="中型史莱姆"||name=="小型史莱姆";
    if((!slime&&name!="掷弹兵僵尸")||!canvas_.drawing())return;
    const auto& b=u->body;const auto& m=b.motion.get();const double now=double(native_tick);
    std::string key;
    if(b.hp<=0.)key=name+"-帧3";
    else if(name=="掷弹兵僵尸"&&u->grenadier.phase.present()&&!u->grenadier.phase.is_null()&&u->grenadier.phase.get()==GrenadierPhase::wind)
        key=name+"-投"+itext(std::min(3.,double(int64_t(py::floordiv(num(u->grenadier.clock)*4.,1.*250.)))));
    else if(slime)key=name+"-帧"+itext(py::mod(py::floordiv(now,40.),3.));
    else{
        const bool moving=std::fabs(m.vx)>.01||num(u->native.biting)!=0.;
        key=name+"-帧"+itext(moving?py::mod(py::floordiv(now,35.),3.):0.);
    }
    auto image=status_frame(canvas_,u,key,true,true);
    if(b.hp<=0.){
        const double age=std::max(0.,-b.hp);
        NativeCanvas::set_alpha(image,std::max(0.,255.-double(int64_t((std::max(0.,age-120.)*255.)/200.))));
    }
    place_frame(canvas_,u,image);
}
void NativeContentDraw::draw_zombie61(const ZombieRef& u){
    const auto name=text(u->source.content);
    if((name!="稻草人"&&name!="乌鸦")||!canvas_.drawing())return;
    const auto& b=u->body;const auto& m=b.motion.get();const double now=double(native_tick);
    const bool falling=name=="稻草人"&&(-90.<b.hp&&b.hp<=0.);
    double frame;
    if(b.hp<=0.)frame=falling?0.:3.;
    else if(name=="乌鸦")frame=py::mod(py::floordiv(now,18.),3.);
    else frame=std::fabs(m.vy)>.01?1.+py::mod(py::floordiv(now,40.),2.):0.;
    const bool attacking=name=="乌鸦"&&b.hp>0.&&num(u->native.biting)>0.;
    if(attacking)frame=py::mod(py::floordiv(now,12.),4.);
    const auto key=name+(attacking?"-攻击":"-帧")+itext(frame);
    auto image=status_frame(canvas_,u,key,false,false);
    if(name=="乌鸦"&&b.hp<=0.){
        const double age=std::max(0.,-b.hp);
        image=NativeArtStore::rotate(image,(-b.facing)*std::min(80.,age*.35));
        NativeCanvas::set_alpha(image,std::max(0.,255.-double(int64_t((std::max(0.,age-150.)*255.)/200.))));
    }else if(falling)image=NativeArtStore::rotate(image,-std::max(0.,-b.hp));
    place_frame(canvas_,u,image);
}
void NativeContentDraw::draw_barrel(Point feet,double angle){
    if(!canvas_.drawing())return;
    const auto image=canvas_.unaliased("滚桶");
    draw_center(image,feet.x,feet.y-double(image->height)/2.,angle);
}
void NativeContentDraw::draw_zombie(const ZombieRef& u){
    const auto name=text(u->source.content);
    if(name=="稻草人"||name=="乌鸦"){draw_zombie61(u);return;}
    if(std::find(content_zombies.begin(),content_zombies.end(),name)==content_zombies.end()||name=="海盗船长"||!canvas_.drawing())return;
    if(name=="小鬼炮"){
        // native_content.draw_zombie -> self.carts.draw(z) (CartLifecycle::draw).
        if(!draw_cart){missing("content_zombie:小鬼炮");return;}
        CanvasCartDrawing drawing(canvas_);draw_cart(u,drawing);return;
    }
    const auto& b=u->body;const auto& m=b.motion.get();
    int frame=(num(u->native.biting)!=0.||std::fabs(m.vx)>.01||name=="海盗鹦鹉")?int(1+py::mod(py::floordiv(double(native_tick),35.),2.)):0;
    if(b.hp<=0.)frame=3;
    const auto key=name+"-帧"+std::to_string(frame);
    const std::string suffix=b.ash.present()?"-灰烬":b.hurt>0.?"-受伤":"";
    auto image=NativeArtStore::copy(canvas_.image(key+suffix));
    if(!b.ash.present()){
        const bool iced=b.ice.present()&&!b.ice.is_null()&&b.ice.get()>0.,charmed=u->source.charmed.present();
        for(const auto& [enabled,state]:{std::pair{iced,"-冰冻"},std::pair{charmed,"-魅惑"}})if(enabled){
            auto overlay=NativeArtStore::copy(canvas_.image(key+state));NativeCanvas::set_alpha(overlay,100.);
            NativeArtStore::blit(image,overlay,{0.,0.});
        }
    }
    if(u->poison.poison.present()&&!u->poison.poison.is_null()&&u->poison.poison.get()){
        const auto& level=u->poison.poison.get()->level;
        if(level.present()&&!level.is_null())image=canvas_.tint_poison(image,level.get());
    }
    if(b.facing<0.)image=NativeCanvas::flip(image);
    if(name=="海盗鹦鹉"&&b.hp<=0.){
        const double age=std::max(0.,-b.hp);
        image=NativeArtStore::rotate(image,-b.facing*std::min(80.,age*.35));
        NativeCanvas::set_alpha(image,double(std::max(0,255-int(std::max(0.,age-150.)*255./200.))));
    }
    const double w=double(image->width),h=double(image->height);
    canvas_.display(image,{m.x-w/2.,m.y-h});
    if(b.butter.present()&&!b.butter.is_null()&&b.butter.get()>0.&&b.hp>0.){
        const auto butter=canvas_.unaliased("黄油砸");
        canvas_.display(butter,{m.x-double(butter->width)/2.,m.y-h-double(butter->height)/2.});
    }
    if(name=="滚桶僵尸"&&b.hand_hp>0.&&carried_barrel)carried_barrel(u);
}
namespace {
using CJ=NativeCanvas::Json;
int iround(double v){return int(std::nearbyint(v));}  // Python round() to an int
CJ xy(double x,double y){return CJ::array({x,y});}
}
void NativeContentDraw::ghost_effect(const GhostBlast& e){
    // september draw_effects: an expanding, fading ring where a ghost pepper exploded.
    if(!canvas_.drawing())return;
    const double tile=world_.runtime.tile,age=double(native_tick-e.tick);
    const int size=std::max(1,iround(tile*2.5));
    const auto s=NativeCanvas::surface(size,size);
    const int radius=std::max(1,iround(size*.5*std::min(1.,(age+8.)/60.)));
    canvas_.draw_on(s,"circle",CJ::array({CJ::array({185,248,230,std::max(0,160-int(age*1.6))}),CJ::array({size/2,size/2}),radius,std::max(1,iround(tile*.06))}));
    canvas_.display(s,{e.point.x-size/2.,e.point.y-size/2.});
}
void NativeContentDraw::reed_effect(const ReedBolt& bolt){
    // pvp61 draw_effects: a jagged two-tone bolt through the chain, a spark at its end.
    if(!canvas_.drawing()||bolt.points.empty())return;
    const double tile=world_.runtime.tile,born=double(bolt.tick),age=double(native_tick-bolt.tick);
    const int alpha=std::max(0,255-int((age*255.)/70.));
    const bool overload=bolt.content=="超载芦苇";
    const std::array<int,3> outer=overload?std::array<int,3>{255,110,200}:std::array<int,3>{150,205,255};
    const std::array<int,3> inner=overload?std::array<int,3>{255,236,250}:std::array<int,3>{255,255,255};
    std::vector<Point> path{bolt.points.front()};
    for(size_t n=0;n+1<bolt.points.size();++n){
        const Point a=bolt.points[n],b=bolt.points[n+1];
        const double length=std::hypot(b.x-a.x,b.y-a.y);
        const int64_t steps=std::max<int64_t>(2,int64_t(length/(tile*.45)));
        const double nx=length!=0.?(-(b.y-a.y))/length:0.,ny=length!=0.?(b.x-a.x)/length:0.;
        for(int64_t k=1;k<steps;++k){
            const double t=double(k)/double(steps);
            const double wobble=((((py::mod(((born*7.+double(n)*31.)+double(k)*17.)+py::floordiv(age,6.)*13.,9.))-4.)/4.)*tile)*.16;
            path.push_back({(a.x+(b.x-a.x)*t)+nx*wobble,(a.y+(b.y-a.y)*t)+ny*wobble});
        }
        path.push_back(b);
    }
    double left=path[0].x,top=path[0].y,right=path[0].x,bottom=path[0].y;
    for(const auto& p:path){left=std::min(left,p.x);top=std::min(top,p.y);right=std::max(right,p.x);bottom=std::max(bottom,p.y);}
    left-=6.;top-=6.;
    const int w=int(right-left)+12,h=int(bottom-top)+12;
    const auto surface=NativeCanvas::surface(std::max(1,w),std::max(1,h));
    CJ local=CJ::array();for(const auto& p:path)local.push_back(xy(p.x-left,p.y-top));
    const auto rgba=[&](const std::array<int,3>& c){return CJ::array({c[0],c[1],c[2],alpha});};
    canvas_.draw_on(surface,"lines",CJ::array({rgba(outer),false,local,std::max(2,iround(tile*.12))}));
    canvas_.draw_on(surface,"lines",CJ::array({rgba(inner),false,local,std::max(1,iround(tile*.04))}));
    const auto& last=path.back();
    canvas_.draw_on(surface,"circle",CJ::array({rgba(inner),CJ::array({iround(last.x-left),iround(last.y-top)}),std::max(2,iround(tile*.12))}));
    canvas_.display(surface,{left,top});
}
void NativeContentDraw::spring_effect(const SpringSwipe& e){
    // pvp64 draw_effects: the spring's fading fan swipe.
    if(!canvas_.drawing())return;
    const double tile=world_.runtime.tile,age=double(native_tick-e.tick);
    const int alpha=std::max(0,230-int((age*230.)/60.));
    const double reach=(2.4*tile)*(.55+.45*std::min(1.,age/18.));
    const int size=int(reach*2.+8.);
    const auto surface=NativeCanvas::surface(size,size);
    const int c=size/2;
    const double half=30.*(kpi/180.);
    CJ points=CJ::array({CJ::array({c,c})}),arc=CJ::array();
    for(int k=0;k<9;++k){
        const double a=(e.angle-half)+(double(k)*half)/4.;
        const auto p=xy(c+std::cos(a)*reach,c+std::sin(a)*reach);points.push_back(p);arc.push_back(p);
    }
    canvas_.draw_on(surface,"polygon",CJ::array({CJ::array({150,230,110,alpha/3}),points}));
    canvas_.draw_on(surface,"lines",CJ::array({CJ::array({220,255,190,alpha}),false,arc,std::max(2,int(py::floordiv(tile,14.)))}));
    canvas_.display(surface,{e.point.x-c,e.point.y-c});
}
void NativeContentDraw::grenade_effect(const GrenadeBlast& e){
    // pvp64 draw_effects: a grenade's expanding blast disc (larger when instant).
    if(!canvas_.drawing())return;
    const double tile=world_.runtime.tile,age=double(native_tick-e.tick);
    const int radius=int(tile*(e.instant?(.8+(.7*age)/45.):(.3+(.45*age)/45.)));
    const int alpha=std::max(0,240-int((age*240.)/45.));
    const auto surface=NativeCanvas::surface(radius*2+4,radius*2+4);
    canvas_.draw_on(surface,"circle",CJ::array({CJ::array({255,170,60,alpha}),CJ::array({radius+2,radius+2}),radius}));
    canvas_.draw_on(surface,"circle",CJ::array({CJ::array({255,240,170,alpha}),CJ::array({radius+2,radius+2}),std::max(1,radius/2)}));
    canvas_.display(surface,{(e.point.x-radius)-2.,(e.point.y-radius)-2.});
}
void NativeContentDraw::grenade_projectile(const GrenadeRef& shot,double angle,double alpha){
    // pvp64 draw_effects: the spinning grenade, faded once defused.
    if(!canvas_.drawing())return;
    auto rotated=NativeArtStore::rotate(canvas_.image("手榴弹"),angle);
    if(alpha<255.){rotated=NativeArtStore::copy(rotated);NativeCanvas::set_alpha(rotated,alpha);}
    canvas_.display(rotated,{shot->motion.x-double(rotated->width)/2.,shot->motion.y-double(rotated->height)/2.});
}
void NativeContentDraw::hook_rope(Point p){
    // pvp70 draw_effects: one grey 3x3 dot of a flying hook's rope.
    if(!canvas_.drawing())return;
    const auto image=NativeCanvas::surface(3,3);
    canvas_.fill(image,CJ::array({151,153,150}));
    canvas_.display(image,p);
}
void NativeContentDraw::zombie_projectile(const ContentProjectileRef& shot,std::string_view sprite,double angle,double alpha){
    // pvp70 draw_effects: reaper bone / hook head, faded once defused.
    if(!canvas_.drawing())return;
    auto image=canvas_.image(std::string(sprite));
    if(shot->defused.present()&&!shot->defused.is_null()&&shot->defused.get()){image=NativeArtStore::copy(image);NativeCanvas::set_alpha(image,alpha);}
    draw_center(image,shot->motion.x,shot->motion.y,angle);
}
void NativeContentDraw::lettuce_flash(const LettuceFlash& flash){
    // pvp70 draw_effects: frozen water cells flash, with a burst of cold air at the lettuce.
    if(!canvas_.drawing())return;
    const double tile=world_.runtime.tile,age=double(native_tick-flash.tick);
    const auto image=NativeCanvas::surface(int(tile),int(tile));
    canvas_.fill(image,CJ::array({120,220,255,std::max(0,120-int(age*1.2))}));
    for(const auto& [row,col]:flash.water)canvas_.display(image,{double(col)*tile,double(row)*tile});
    frost(flash.point.x,flash.point.y,16,tile*1.6,double(flash.tick%7),age,std::nullopt);
}
} // namespace pvz::typed72
