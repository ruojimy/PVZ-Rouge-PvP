// Line-for-line port of the original 显示植物 (src/sim/gen/original_funcs.cpp:2304-2789).
// Every expression keeps the original operand order so recorded positions/angles are exact.
#include "sim/typed/native_plant_draw.h"
#include "core/pymath.h"
#include <algorithm>
#include <array>
#include <cmath>
namespace pvz::typed72 {
namespace {
constexpr double pi=3.141592653589793;
bool has(const std::vector<std::string>& values,const std::string& name){return std::find(values.begin(),values.end(),name)!=values.end();}
double num(const Field<double>& f){return f.present()&&!f.is_null()?f.get():0.;}
bool truthy(const Field<double>& f){return num(f)!=0.;}
std::string int_text(double v){return std::to_string(int64_t(v));}
}
void NativePlantDraw::draw_all(){
    // native_runtime.draw_plants: lilies first, then every plant except pots/lilies with
    // pumpkin shells deferred, then the shells.
    const auto& plants=*world_.plant_roster;
    for(size_t i=0;i<plants.size();++i)if(plants[i]->kind=="睡莲"){
        if(!(hooks&&hooks->draw_lily(i)))show(i);
    }
    std::vector<size_t> shells;
    for(size_t i=0;i<plants.size();++i){
        const auto& p=*plants[i];
        if(p.kind=="花盆"||p.kind=="睡莲")continue;
        if(hooks&&hooks->is_shell(p))shells.push_back(i);else show(i);
    }
    for(const auto i:shells)show(i);
}
void NativePlantDraw::show(size_t index){
    if(hooks&&hooks->draw_plant(index))return;
    // native_content draw_plant: a content plant keeps the original roots, sway, attack arm,
    // squash, flower-pot lift and water bob; only its sprite layers are swapped (copies).
    const auto& p=*world_.plant_roster->at(index);
    const std::string content=p.source.content.present()&&!p.source.content.is_null()?p.source.content.get():std::string{};
    if(content.empty()||!has(rules_.content_plants,content)){
        const auto start=canvas_.frames.size();
        expansion_layer(index);
        // 埋在土里的土豆地雷同胆小菇：贴图必须落在地形前景（方块/花盆）之下。
        if(p.kind=="胆小菇"||(p.kind=="土豆地雷"&&num(p.buried)>0.))canvas_.frames.tag_layer(start,"below_ground");
        return;
    }
    auto& atlas=canvas_.atlas.atlas;std::vector<std::pair<std::string,NativeArt>> saved;
    const std::vector<std::string> parts=content=="甜椒投手"?std::vector<std::string>{"","-投","-投空"}:std::vector<std::string>{""};
    for(const auto& part:parts)for(const auto suffix:{"","-黑白","-受伤","-冰冻","-灰烬","-魅惑"}){
        const auto old=p.kind+part+suffix,next=content+part+suffix;
        if(atlas.contains(old)&&atlas.contains(next)){saved.emplace_back(old,atlas.at(old));atlas[old]=NativeArtStore::copy(atlas.at(next));}
    }
    try{expansion_layer(index);}catch(...){for(auto& [k,v]:saved)atlas[k]=v;throw;}
    for(auto& [k,v]:saved)atlas[k]=v;
}
void NativePlantDraw::lily(size_t index){
    auto& c=canvas_;const auto& p=*world_.plant_roster->at(index);const double tile=world_.runtime.tile;
    const std::string bw=p.monochrome.present()&&c.has("睡莲块-黑白")?"-黑白":"";
    auto image=c.atlas.find("睡莲块"+bw);if(!image)return;
    const bool flip=p.facing==-1.;
    const double x=double(p.cell.x)*tile,y=((double(p.cell.y)*tile)+water_offset_)-(tile*.15);
    if(p.dead.present()||num(p.hp)<=0.){image=NativeArtStore::copy(image);NativeCanvas::set_alpha(image,150.);}
    c.display(flip?NativeCanvas::flip(image):image,{x,y});
    const double hurt=num(p.hurt);
    if(hurt>0.&&c.has("睡莲块-受伤")){
        auto white=NativeArtStore::copy(c.image("睡莲块-受伤"));
        NativeCanvas::set_alpha(white,double(int64_t(std::sin((pi*hurt)/50.)*150.)));
        c.display(flip?NativeCanvas::flip(white):white,{x,y});
    }
}
void NativePlantDraw::expansion_layer(size_t index){
    // native_expansion show: while this plant draws, a head whose recipe names the plant
    // turns by its seeded pea angle.
    const auto& p=*world_.plant_roster->at(index);
    if(!p.pea_angle.present()||p.pea_angle.is_null()){patch_layer(index);return;}
    const auto previous=canvas_.rotation_filter;
    canvas_.rotation_filter=[&,previous](const NativeArt& image,double angle){
        if(canvas_.recipe_mentions(image,p.kind)){
            const double base=p.facing>0.?0.:180.;
            angle-=py::mod((p.pea_angle.get()-base+180.),360.)-180.;
        }
        return previous?previous(image,angle):angle;
    };
    try{patch_layer(index);}catch(...){canvas_.rotation_filter=previous;throw;}
    canvas_.rotation_filter=previous;
}
void NativePlantDraw::patch_layer(size_t index){
    // patch1501 __pvz_sb_show_plant_wrapper.
    const auto& p=*world_.plant_roster->at(index);
    if((p.bonus.stone_placeholder.present()&&!p.bonus.stone_placeholder.is_null()&&p.bonus.stone_placeholder.get())||p.kind=="石块")return;
    auto& atlas=canvas_.atlas.atlas;
    if(p.kind=="三向射手"){
        const std::string key=p.monochrome.present()?"三向射手-黑白":"三向射手";
        const auto full=canvas_.atlas.find(key),body=canvas_.atlas.find(p.monochrome.present()&&canvas_.has("三向射手根-黑白")?"三向射手根-黑白":"三向射手根");
        if(body){
            atlas[key]=body;
            try{original(index);}catch(...){if(full)atlas[key]=full;throw;}
            if(full)atlas[key]=full;
            tripea_heads(p);
            return;
        }
    }
    original(index);
}
void NativePlantDraw::tripea_heads(const CombatPlant& p){
    // patch1501 __pvz_sb_draw_tripea_plant_heads with its head/vine helpers.
    auto& c=canvas_;const double direction=p.facing<0.?-1.:1.;
    const std::string grey=p.monochrome.present()&&c.has("三向射手头-黑白")?"-黑白":"";
    NativeArt head=c.atlas.find("三向射手头"+grey);if(!head)return;
    if(direction<=0.){
        if(const auto left=c.atlas.find("三向射手头左"+grey))head=left;
        else{head=NativeCanvas::flip(head);c.atlas.atlas["三向射手头左"+grey]=head;}
    }
    const double head_w=double(head->width),head_h=double(head->height),scale=world_.runtime.tile;
    const double root=num(p.root_animation),sway=(std::sin(root/28.)*scale)*.018;
    const double x0=double(p.cell.x)*scale,y0=double(p.cell.y)*scale;
    std::array<Point,3> centers;
    if(direction<0.)centers={Point{(x0+(scale*.64))-sway,y0+(scale*.16)},Point{(x0+(scale*.45))+sway,y0+(scale*.38)},Point{(x0+(scale*.27))-sway,y0+(scale*.6)}};
    else centers={Point{(x0+(scale*.36))+sway,y0+(scale*.16)},Point{(x0+(scale*.55))-sway,y0+(scale*.38)},Point{(x0+(scale*.73))+sway,y0+(scale*.6)}};
    std::array<double,3> angles=direction>0.?std::array<double,3>{-15.,0.,15.}:std::array<double,3>{195.,180.,165.};
    if(p.bonus.tripea_angles.present()&&!p.bonus.tripea_angles.is_null()&&p.bonus.tripea_angles.get().size()==3)
        for(size_t i=0;i<3;++i)angles[i]=p.bonus.tripea_angles.get()[i].get();
    const std::array<double,3> fans{-.02,0.,.02};
    bool anchored=true;
    for(size_t i=0;i<3;++i){
        if(anchored){
            const Point anchor{x0+(scale*(.52+(direction*fans[i]))),y0+(scale*(.55+(.03*double(i))))};
            const double ax=anchor.x,ay=anchor.y,hx=centers[i].x,hy=centers[i].y,dx=hx-ax,dy=hy-ay;
            if(!(((dx*dx)+(dy*dy))<1.)){
                const double back1=scale*(std::fabs(dy)>=(scale*.04)?.1:.08),back2=scale*.06;
                const double c1x=ax-(direction*back1),c1y=ay+((hy-ay)*.3),c2x=hx-(direction*back2),c2y=hy-((hy-ay)*.3);
                const int64_t pad=int64_t(scale*.12)+6;
                const int64_t min_x=int64_t(std::min({ax,hx,c1x,c2x}))-pad,min_y=int64_t(std::min({ay,hy,c1y,c2y}))-pad;
                const int64_t width=(int64_t(std::max({ax,hx,c1x,c2x}))+pad)-min_x,height=(int64_t(std::max({ay,hy,c1y,c2y}))+pad)-min_y;
                if(!(width<2||height<2||width>4096||height>4096)){
                    auto vine=NativeCanvas::surface(int(width),int(height));
                    NativeCanvas::Json points=NativeCanvas::Json::array(),lifted=NativeCanvas::Json::array();
                    for(int step=0;step<17;++step){
                        const double t=double(step)/16.,mt=1.-t;
                        const double px=(((((mt*mt)*mt)*ax)+((((3.*mt)*mt)*t)*c1x)+((((3.*mt)*t)*t)*c2x)+(((t*t)*t)*hx))-double(min_x));
                        const double py_=(((((mt*mt)*mt)*ay)+((((3.*mt)*mt)*t)*c1y)+((((3.*mt)*t)*t)*c2y)+(((t*t)*t)*hy))-double(min_y));
                        points.push_back({px,py_});lifted.push_back({px,py_-1.});
                    }
                    const int64_t outline=std::max<int64_t>(3,int64_t(std::nearbyint(scale*.04))),inner=std::max<int64_t>(1,int64_t(std::nearbyint(scale*.02)));
                    c.draw_on(vine,"lines",{{8,65,19},false,points,outline});
                    c.draw_on(vine,"lines",{{54,168,42},false,points,inner});
                    c.draw_on(vine,"lines",{{119,224,73},false,lifted,1});
                    c.rotated(vine,{double(min_x),double(min_y)},0.);
                }
            }
        }
        const double base=direction>0.?0.:180.;
        const double local=py::mod(((angles[i]-base)+180.),360.)-180.;
        c.rotated(head,{centers[i].x-(head_w*.5),centers[i].y-(head_h*.5)},local);
    }
}
void NativePlantDraw::original(size_t l){
    auto& c=canvas_;const auto& p=*world_.plant_roster->at(l);const double B=world_.runtime.tile;
    const auto& terrain=world_.terrain;
    const std::string hb=p.monochrome.present()?"-黑白":"";
    const int64_t y=p.cell.y,x=p.cell.x;
    const double yy=double(y)*B,xx=double(x)*B;
    double citoux=0.,citouy=0.;
    double sinzhi=std::sin(pi*2.*(num(p.root_animation)/250.))*10.;
    std::string name=p.kind,zi;
    const double facing=p.facing;
    if(name=="模仿者"&&num(p.imitator_cd)>0.)sinzhi=sinzhi*5.;
    if(has(rules_.root_plants,name)){
        zi="根茎叶";
        if(name=="三叶草")zi="三叶草-根";
        if(name=="双子向日葵"){zi="双子根";citouy-=B*.3;citoux-=B*.25;}
        if(name=="大嘴花"||name=="龙蒺藜"){
            sinzhi=sinzhi/2.;zi="大嘴根";
            if(name=="龙蒺藜")zi="龙蒺藜根";
            citouy-=B*.6;citoux-=B*.25;
        }
    }else if(has(rules_.lobbers,name)){
        zi=num(p.shooting)>100.&&num(p.shooting)<200.?name+"-投空":name+"-投";
    }else if(name=="香蒲"){
        zi="香蒲尾";
    }else{
        if(name=="火炬树桩")name="火炬树桩-秃";
        if(name=="磁力菇"||name=="吸金磁"){
            if(p.sleep.present()&&name=="磁力菇")name="磁力菇-睡觉";
            if(num(p.magnet)>0.)name+="-吸";
        }
        if(name=="玉米加农炮"){citouy-=B*.6;citoux-=B*.5;}
        if(has(rules_.big_heads,name)){citouy-=B*.5;citoux-=B*.25;}
        if(name=="高坚果"){
            if(num(p.hp)<=96.)name="高坚果-小残";
            if(num(p.hp)<=48.)name="高坚果-大残";
        }
        if(name=="南瓜头"){
            sinzhi=sinzhi/2.;
            if(num(p.hp)<=48.)name="南瓜头-小残";
            if(num(p.hp)<=24.)name="南瓜头-大残";
        }
        if(name=="坚果"){
            if(num(p.hp)<=48.)name="坚果-小残";
            if(num(p.hp)<=24.)name="坚果-大残";
        }
        if(name=="大蒜"){
            if(num(p.hp)<=12.)name="大蒜-小残";
            if(num(p.hp)<=6.)name="大蒜-大残";
        }
        zi=name;
    }
    if(name=="海蘑菇"&&!has(*secrets_,"水兵"))citouy-=B*.6;
    if(name=="缠绕海草")citouy+=(-B)*.8;
    if(name=="香蒲")citouy+=(-B)*.9;
    auto gen=c.image(zi+hb);
    auto tou=c.image(name+hb);
    double daxiao=0.;
    if(name=="阳光菇"&&num(p.grown)<200.){
        daxiao=(((200.-num(p.grown))/200.)*B)/2.;
        tou=c.resize(tou,B-daxiao,B-daxiao);
    }
    if(name=="小喷菇"&&p.small_puff.present()){
        daxiao=((-B)/2.)*std::pow(num(p.small_puff)/15.,.5);
        tou=c.resize(tou,B-daxiao,B-daxiao);
    }
    if(name=="忧郁蘑菇"&&num(p.shooting)>0.&&num(p.shooting)<50.){
        const double dx=(std::sin(pi*(num(p.shooting)/50.))*B)*.15;
        tou=c.resize(tou,B+dx,B+dx);
        citoux-=dx/2.;citouy-=dx;
    }
    double toudushu=0.;
    if(name=="墓碑吞噬者"){
        citouy+=(((-B)*2.)/3.)+((std::pow(num(p.grave_eating)/1000.,2.)*B)/2.);
        const auto cell=terrain.grid.at(size_t(y)).at(size_t(x));
        if(py::mod(num(p.grave_eating),100.)==0.&&cell->grave_art.present()&&!p.sleep.present())
            world_.runtime.emit_particles(cell->block.get()+int_text(cell->grave_art.get()),{double(x)*B+B*.5,double(y)*B+B*.5},4);
    }
    if(name=="三叶草"){toudushu=(num(p.expires)*6.)*facing;sinzhi=15.;}
    if(facing==-1.){gen=NativeCanvas::flip(gen);tou=NativeCanvas::flip(tou);sinzhi=-sinzhi;}
    if(name=="樱桃炸弹"||name=="毁灭菇"||name=="火爆辣椒"){
        const double daxiaox=std::pow(num(p.expires)/200.,2.)*B;
        tou=c.resize(tou,B+daxiaox,B+daxiaox);
        citouy=(-daxiaox)+(B*.1);citoux=(-daxiaox)/2.;
    }
    const auto recoil=[&](double shot,double side){
        const double shedu=pi*(shot/100.);
        const double shesin=(((-2./pi)*shedu)+2.)*std::sin(shedu);
        citoux+=(((-shesin)*B)*.15)*side;
        citouy+=(shesin*B)*.05;
        toudushu=((-shesin)*40.)*side;
    };
    if(name=="裂荚射手"){
        if(num(p.shooting)>0.&&num(p.shooting)<100.)recoil(num(p.shooting),facing);
        if(num(p.secondary_shot)>0.&&num(p.secondary_shot)<100.)recoil(num(p.secondary_shot),-facing);
    }
    if((name=="豌豆射手"||name=="海蘑菇"||name=="机枪射手"||name=="寒冰射手"||name=="双发射手"||name=="小喷菇"||
        name=="胆小菇"||name=="仙人掌"||name=="杨桃")&&num(p.shooting)>0.&&num(p.shooting)<100.)recoil(num(p.shooting),facing);
    if((name=="地刺"||name=="地刺王")&&num(p.shooting)>0.&&num(p.shooting)<100.){
        const double shedu=(pi*2.)*(num(p.shooting)/100.);
        citouy=(std::sin(shedu)*B)*.1;
    }
    if((name=="大喷菇"||name=="雷蘑菇")&&num(p.shooting)>0.&&num(p.shooting)<200.){
        double she=num(p.shooting);
        if(she>=150.)she=200.-she;
        if(she>50.)she=50.;
        const double shedu=pi*(she/100.);
        const double shesin=(((-2./pi)*shedu)+2.)*std::sin(shedu);
        citoux=((shesin*B)*.15)*facing;
        citouy=((-shesin)*B)*.05;
        toudushu=(shesin*20.)*facing;
    }
    if(name=="胆小菇"&&num(p.scared)>0.)citouy+=((num(p.scared)/100.)*B)/2.;
    double genx=xx,geny=yy+(B*.3);
    if(name=="大嘴花"||name=="龙蒺藜"){genx-=B*.25;geny-=B*.75;}
    double toux=(xx+citoux)+(daxiao/2.);
    double touy=((yy-(B*.05))+citouy)+daxiao;
    if(const auto lift=rules_.pot_tops.find(std::to_string(y+1)+"-"+std::to_string(x));lift!=rules_.pot_tops.end()){
        touy-=lift->second;geny-=lift->second;
    }
    const auto block=[&](int64_t row,int64_t col)->const std::string&{return terrain.grid.at(size_t(row)).at(size_t(col))->block.get();};
    if(block(y+1,x)=="水"||block(y,x)=="水"){touy+=water_offset_;geny+=water_offset_;}
    if(p.burst.present()&&num(p.burst)>0.)touy-=(std::sin(pi*(num(p.burst)/250.))*B)*.1;
    bool dazui=false;
    NativeArt sbtou,xbtou;
    if(name=="土豆地雷"){
        touy+=(B*.5)-(((num(p.emerged)/200.)*B)*.2);
        if(truthy(p.emerged)&&py::mod(py::floordiv(num(p.flash),150.),2.)==0.){
            tou=facing==-1.?NativeCanvas::flip(c.image("土豆地雷-亮"+hb)):c.image("土豆地雷-亮"+hb);
        }
    }else if(has(rules_.root_plants,name)){
        if((name=="大嘴花"||name=="龙蒺藜")&&(num(p.shooting)>0.||num(p.eating)>0.)){
            dazui=true;
            sbtou=c.image(name+"-上半"+hb);xbtou=c.image(name+"-下半"+hb);
            if(facing==-1.){sbtou=NativeCanvas::flip(sbtou);xbtou=NativeCanvas::flip(xbtou);}
            const double shot=num(p.shooting);
            if(shot>0.&&shot<150.){
                toux+=(std::sin(pi*(shot/150.))*B)*facing;
                touy-=(std::sin(pi*(shot/150.))*B)*.3;
                if(shot>60.){
                    if(shot>60.&&shot<90.)toudushu=-25.*facing;
                    else{
                        const double lzx=shot-30.;
                        toudushu=(std::sin((pi*2.)*(lzx/120.))*30.)*facing;
                        if(num(p.eating)>0.){
                            if(facing==1.&&toudushu>15.)toudushu=15.;
                            if(facing==-1.&&toudushu<-15.)toudushu=-15.;
                        }
                    }
                }else toudushu=(std::sin((pi*2.)*(shot/120.))*70.)*facing;
                sinzhi=(std::sin(pi*(shot/150.))*60.)*facing;
                genx+=(std::sin(pi*(shot/150.))*B)*facing;
            }
        }
        toux+=(sinzhi*B)*.005;
        touy+=(std::fabs(sinzhi)*B)*.01;
        c.rotated(gen,{genx,geny+((std::fabs(sinzhi)*B)*.005)},sinzhi);
    }else{
        toux+=((sinzhi/4.)*B)*.005;
        touy+=(((std::fabs(sinzhi)/4.)*B)*.01)+(B*.15);
        toudushu+=sinzhi/4.;
        if(has(rules_.lobbers,name)){
            double tousin=0.;
            if(num(p.shooting)>0.&&num(p.shooting)<200.){
                const double shedu=(pi*2.)*(num(p.shooting)/200.);
                const double shesin=std::sin(shedu);
                citoux=(((-shesin)*B)*.15)*facing;
                citouy=(shesin*B)*.05;
                toudushu=((-shesin)*40.)*facing;
                const double toudu=(pi*2.)*(num(p.shooting)/200.);
                tousin=((-std::sin(toudu))*120.)*facing;
            }
            c.rotated(gen,{((genx-(B*.5))-((facing*B)*.2))+(citoux*2.),((geny+citouy)-(B*.9))},tousin+sinzhi);
        }
        if(name=="香蒲"){
            double tousin=0.;
            if(num(p.shooting)>0.&&num(p.shooting)<100.){
                const double shedu=(pi*2.)*(num(p.shooting)/100.);
                const double shesin=std::sin(shedu);
                citoux=(((-shesin)*B)*.15)*facing;
                toudushu=((-shesin)*20.)*facing;
                const double toudu=(pi*2.)*(num(p.shooting)/100.);
                tousin=((-std::sin(toudu))*60.)*facing;
            }
            c.rotated(gen,{(genx-((facing*B)*.15))+(citoux*2.),((geny+citouy)-(B*.25))},tousin+sinzhi);
        }
    }
    if(name=="火炬树桩-秃"&&block(y,x)!="水"){
        const std::string blue=has(*secrets_,"蓝火")?"蓝":"";
        const double shu=py::mod(py::floordiv(num(p.root_animation),25.),3.)+1.;
        const auto torch=c.image(blue+"火炬"+int_text(shu));
        c.rotated(facing==-1.?NativeCanvas::flip(torch):torch,{toux,touy},toudushu);
    }
    if(name=="玉米加农炮")toudushu-=(std::sin(pi*(num(p.cannon_animation)/500.))*90.)*facing;
    if(name=="玉米加农炮"&&((num(p.cannon_animation)>0.&&num(p.cannon_animation)<250.)||num(p.cannon_cd)<=100.)){
        auto tu=c.image("玉米炮");
        if(facing==-1.)tu=NativeCanvas::flip(tu);
        double xxxx,yyyy;
        if(num(p.cannon_animation)>0.){
            xxxx=((-std::sin(pi*(num(p.cannon_animation)/500.)))*B)*.4;
            yyyy=((-std::sin(pi*(num(p.cannon_animation)/500.)))*B)*.5;
        }else{
            xxxx=((-(num(p.cannon_cd)/100.))*B)*.3;
            yyyy=0.;
        }
        const Point at{(toux+((facing*B)*.3))+(xxxx*facing),(touy-(B*.1))+yyyy};
        c.rotated(tu,at,toudushu);
        if(num(p.cannon_flash)<50.){
            c.set_alpha("玉米炮-受伤",std::sin(pi*(num(p.cannon_flash)/50.))*255.);
            auto sc=c.image("玉米炮-受伤");
            if(facing==-1.)sc=NativeCanvas::flip(sc);
            c.rotated(sc,at,toudushu);
        }
    }
    if(dazui){
        double xxxx=0.,yyyy=0.;
        if(num(p.eating)>0.){
            toudushu=-15.*facing;
            if(num(p.eating)<200.)toudushu+=(std::sin(pi*((200.-num(p.eating))/400.))*15.)*facing;
            else{
                xxxx=(std::cos((pi*2.)*(num(p.eating)/200.))*B)*.08;
                yyyy=((std::sin((pi*2.)*(num(p.eating)/200.))*B)*.08)-(B*.15);
            }
        }
        c.rotated(xbtou,{toux+xxxx,touy+yyyy},toudushu);
        c.rotated(sbtou,{toux+(xxxx/4.),touy+(yyyy/4.)},-toudushu);
        if(num(p.hurt)>0.){
            auto lower=c.image(name+"-下半-受伤");
            if(facing==-1.)lower=NativeCanvas::flip(lower);
            c.set_alpha(name+"-下半-受伤",std::sin(pi*(num(p.hurt)/50.))*150.);
            c.rotated(lower,{toux+xxxx,touy+yyyy},toudushu);
            auto upper=c.image(name+"-上半-受伤");
            if(facing==-1.)upper=NativeCanvas::flip(upper);
            c.set_alpha(name+"-上半-受伤",std::sin(pi*(num(p.hurt)/50.))*150.);
            c.rotated(upper,{toux+(xxxx/4.),touy+(yyyy/4.)},-toudushu);
        }
        toux+=xxxx;touy+=yyyy;
    }else c.rotated(tou,{toux,touy},toudushu);
    if(name=="玉米加农炮"){
        auto tu=c.image("玉米加农炮-车"+hb);
        if(facing==-1.)tu=NativeCanvas::flip(tu);
        c.display(tu,{toux,touy});
    }
    if(name=="石果子"&&num(p.expires)>4000.){
        auto dark=c.image(name+"-黑");
        if(facing==-1.)dark=NativeCanvas::flip(dark);
        c.set_alpha(name+"-黑",std::pow((num(p.expires)-4000.)/1000.,5.)*255.);
        if(toudushu==0.)c.display(dark,{toux,touy});else c.rotated(dark,{toux,touy},toudushu);
    }
    if(!(num(p.hurt)<=0.||dazui)){
        auto hurt=c.image(name+"-受伤");
        if(facing==-1.)hurt=NativeCanvas::flip(hurt);
        if(daxiao!=0.)hurt=c.resize(hurt,B-daxiao,B-daxiao);
        c.set_alpha(name+"-受伤",std::sin(pi*(num(p.hurt)/50.))*150.);
        if(toudushu==0.)c.display(hurt,{toux,touy});else c.rotated(hurt,{toux,touy},toudushu);
    }
    if(name=="萝卜伞"&&num(p.shooting)>0.&&num(p.shooting)<100.){
        const double dx=(std::sin(pi*(num(p.shooting)/100.))*B)*3.;
        auto sc=c.image("叶子伞"+hb);
        if(facing==-1.)sc=NativeCanvas::flip(sc);
        sc=c.resize(sc,dx+(B*1.5),dx+(B*1.5));
        c.display(sc,{toux-(dx/2.),touy-((dx*2.)/3.)});
    }
    const auto glow=[&](const std::string& key){
        c.set_alpha(key,std::sin(pi*(num(p.burst)/250.))*255.);
        auto sc=c.image(key);
        if(facing==-1.)sc=NativeCanvas::flip(sc);
        c.display(sc,{toux,touy});
    };
    if(name=="向日葵"&&num(p.burst)>0.)glow("向日葵-生产");
    if(name=="路灯花"&&num(p.burst)>0.){
        glow("路灯花-光疗");
        const auto light=c.ui_image("发光1");
        NativeCanvas::set_alpha(light,std::sin(pi*(num(p.burst)/250.))*255.);
        c.display(light,{toux-(B*2.),touy-(B*2.)});
    }
    if(name=="双子向日葵"&&num(p.burst)>0.)glow("双子向日葵-生产");
    if(name=="阳光菇"&&num(p.burst)>0.){
        c.set_alpha("阳光菇-生产",std::sin(pi*(num(p.burst)/250.))*255.);
        auto sc=c.image("阳光菇-生产");
        if(num(p.grown)<200.)sc=c.resize(sc,B-daxiao,B-daxiao);
        if(facing==-1.)sc=NativeCanvas::flip(sc);
        c.rotated(sc,{toux,touy},toudushu);
    }
    if(name=="金盏花"&&num(p.burst)>0.)glow("金盏花-受伤");
    if(int64_t(l)==target_plant_()&&rules_.mode=="我是僵尸")c.display(c.image("小脑子"),{toux+(B*.25),touy});
}
} // namespace pvz::typed72
