#include "ui/hand/texture74_internal.h"
#include "core/fsutil.h"
#include "core/resource_paths.h"
#include "data/datastore.h"
#include "sim/pvp/hand/original_namespace.h"
#include <SDL_image.h>
#include <fstream>
#include <algorithm>
#include <cmath>
#include <set>
namespace pvz {V fn_换黑白(Match&,const Args&);V fn_纯换色(Match&,const Args&);V fn_不纯换色(Match&,const Args&);}
namespace pvz::texture74 {
namespace {thread_local bool display_images=false;}
DisplayScope::DisplayScope():previous(display_images){display_images=true;}DisplayScope::~DisplayScope(){display_images=previous;}
OriginalScope::OriginalScope():previous(display_images){display_images=false;}OriginalScope::~OriginalScope(){display_images=previous;}
State& state(){static State s;return s;}
std::string digest(const std::string& bytes){return py_str(callm(py::stdlib_call(V("hashlib.sha256"),Args{V::bytes(bytes)}),Sym("hexdigest"),Args{}));}
std::string b64(const std::string& bytes){return py::stdlib_call(V("base64.b64encode"),Args{V::bytes(bytes)}).str();}
std::string unb64(const std::string& text){
    if(text.size()>MAX_PACK)throw std::runtime_error("图片数据过大");
    return py::stdlib_call(V("base64.b64decode"),Args({V(text)},{{Sym("validate"),V(true)}})).str();
}
J inventory(){return data::module("texture_resources74");}
void load_inventory(){auto& s=state();if(!s.resources.empty())return;const auto j=inventory();s.cards=j.at("cards");s.heroes=j.value("heroes",J::array());for(const auto& key:j.value("excluded_resources",J::array()))s.excluded_keys.insert(key.get<std::string>());
 for(const auto& e:j.at("entries")){Resource r;r.key=e.at("key");r.name=e.at("name");r.file=e.at("file");r.scope=e.at("scope");r.category=e.at("category");r.w=e.at("width");r.h=e.at("height");r.projectile=e.at("projectile");r.cards=e.at("cards").get<std::vector<std::string>>();r.heroes=e.value("heroes",std::vector<std::string>{});s.by_key.emplace(r.key,s.resources.size());s.resources.push_back(std::move(r));}}
const Resource* resource(const std::string& key){load_inventory();auto& s=state();const auto it=s.by_key.find(key);return it==s.by_key.end()?nullptr:&s.resources.at(it->second);}
V original(const Resource& r){
 OriginalScope original_pixels;
 std::filesystem::path path=u8p(r.file);if(r.file.rfind("图片/",0)==0)path=native_image_directory()/u8p(r.file.substr(7));
 else {auto base=u8p(data::data_dir()).parent_path().parent_path();path=base/path;}
 V image=callm(pg::image_module(),Sym("load"),Args{V(p8(path))});
 if(pg::surf(image)->w()!=r.w||pg::surf(image)->h()!=r.h)image=callm(pg::transform_module(),Sym("scale"),Args{image,V::tuple({V(r.w),V(r.h)})});
 return image;
}
std::vector<uint32_t> pixels(const V& image){const auto* im=pg::surf(image);std::vector<uint32_t> out(size_t(im->w())*im->h());
 for(int y=0;y<im->h();++y)for(int x=0;x<im->w();++x){uint8_t r,g,b,a;uint32_t p;std::memcpy(&p,(uint8_t*)im->s->pixels+y*im->s->pitch+x*4,4);SDL_GetRGBA(p,im->s->format,&r,&g,&b,&a);out[size_t(y)*im->w()+x]=(uint32_t(r)<<24)|(uint32_t(g)<<16)|(uint32_t(b)<<8)|a;}return out;}
V surface(int w,int h,const std::vector<uint32_t>& data){V v=pg::new_surface(w,h,true);auto* im=pg::surf(v);for(int y=0;y<h;++y)for(int x=0;x<w;++x){const auto p=data.at(size_t(y)*w+x);const uint32_t q=SDL_MapRGBA(im->s->format,p>>24,(p>>16)&255,(p>>8)&255,p&255);std::memcpy((uint8_t*)im->s->pixels+y*im->s->pitch+x*4,&q,4);}return v;}
std::string png_encode(const V& image){
 struct Writer {std::string bytes;};Writer data;SDL_RWops* rw=SDL_AllocRW();if(!rw)throw std::runtime_error("无法创建图片缓存");
 rw->hidden.unknown.data1=&data;rw->size=[](SDL_RWops* r)->Sint64{return ((Writer*)r->hidden.unknown.data1)->bytes.size();};rw->seek=[](SDL_RWops*,Sint64,int)->Sint64{return -1;};rw->read=[](SDL_RWops*,void*,size_t,size_t)->size_t{return 0;};
 rw->write=[](SDL_RWops* r,const void* p,size_t sz,size_t n)->size_t{auto& b=((Writer*)r->hidden.unknown.data1)->bytes;if(sz&&n>(MAX_PACK-b.size())/sz)return 0;b.append((const char*)p,sz*n);return n;};rw->close=[](SDL_RWops* r)->int{SDL_FreeRW(r);return 0;};
 if(IMG_SavePNG_RW(pg::surf(image)->s,rw,1)!=0)throw std::runtime_error("PNG 编码失败");return data.bytes;
}
V png_decode(const std::string& bytes,int w,int h){
 if(bytes.size()<24||bytes.size()>MAX_PACK||bytes.compare(0,8,"\x89PNG\r\n\x1a\n",8)!=0)throw std::runtime_error("材质只接受 PNG 数据");
 const auto be=[&](int at){uint32_t v=0;for(int n=0;n<4;++n)v=(v<<8)|(uint8_t)bytes[at+n];return v;};
 if(be(16)!=uint32_t(w)||be(20)!=uint32_t(h))throw std::runtime_error("材质画布尺寸与原资源不一致");
 auto* raw=IMG_Load_RW(SDL_RWFromConstMem(bytes.data(),int(bytes.size())),1);if(!raw)throw std::runtime_error("PNG 无法解码");auto* out=SDL_ConvertSurfaceFormat(raw,SDL_PIXELFORMAT_ARGB8888,0);SDL_FreeSurface(raw);if(!out)throw std::runtime_error("PNG 像素格式不支持");return pg::wrap_surface(out,true);
}
J load_file(const std::filesystem::path& p){std::ifstream in(p,std::ios::binary|std::ios::ate);if(!in||in.tellg()>std::streamoff(MAX_PACK))throw std::runtime_error("材质包不存在或超过 32 MB");in.seekg(0);return J::parse(in);}
void save_file(const std::filesystem::path& p,const J& j){const auto bytes=j.dump();if(bytes.size()>MAX_PACK)throw std::runtime_error("材质包超过 32 MB");std::filesystem::create_directories(p.parent_path());auto tmp=p;tmp+=".tmp";{std::ofstream out(tmp,std::ios::binary);out.write(bytes.data(),bytes.size());if(!out)throw std::runtime_error("材质包写入失败");}std::error_code ec;std::filesystem::rename(tmp,p,ec);if(ec){std::filesystem::remove(p,ec);std::filesystem::rename(tmp,p);}}
J validate_pack(const J& doc){load_inventory();
 if(!doc.is_object()||doc.value("format",std::string{})!="pvz-texture-pack-v1"||!doc.contains("entries")||!doc["entries"].is_object()||!doc.contains("name")||!doc["name"].is_string())throw std::runtime_error("不是有效的 PvP 材质包");
 const auto name=doc["name"].get<std::string>();if(name.empty()||name.size()>160||doc["entries"].size()>state().resources.size()+state().excluded_keys.size())throw std::runtime_error("材质包信息无效");
 J clean={{"format","pvz-texture-pack-v1"},{"name",name},{"entries",J::object()}};size_t total=0,decoded=0;
 for(auto& [key,e]:doc["entries"].items()){if(state().excluded_keys.count(key))continue;const auto* r=resource(key);if(!r)throw std::runtime_error("材质包包含未知资源："+key);
  if(!e.is_object()||!e.contains("png")||!e["png"].is_string()||e.value("width",0)!=r->w||e.value("height",0)!=r->h||r->w<1||r->h<1||r->w>8192||r->h>8192)throw std::runtime_error("材质画布尺寸错误："+key);
  total+=size_t(r->w)*r->h;if(total>MAX_PIXELS)throw std::runtime_error("材质包像素总量超过限制");
  const auto bytes=unb64(e["png"]);decoded+=bytes.size();if(decoded>MAX_PACK)throw std::runtime_error("材质包解码后过大");(void)png_decode(bytes,r->w,r->h);clean["entries"][key]={{"width",r->w},{"height",r->h},{"png",e["png"]}};
  if(e.contains("layers")){if(!e["layers"].is_array()||e["layers"].size()>8||e["layers"].empty())throw std::runtime_error("图层数量无效");J layers=J::array();for(const auto& l:e["layers"]){
    const auto b=unb64(l.at("png"));decoded+=b.size();total+=size_t(r->w)*r->h;if(decoded>MAX_PACK||total>MAX_PIXELS)throw std::runtime_error("图层数据超过限制");(void)png_decode(b,r->w,r->h);
    const auto ln=l.value("name",std::string("图层"));if(ln.size()>100)throw std::runtime_error("图层名称过长");int op=l.value("opacity",255);if(op<0||op>255)throw std::runtime_error("图层透明度无效");layers.push_back({{"name",ln},{"visible",l.value("visible",true)},{"opacity",op},{"png",l["png"]}});}clean["entries"][key]["layers"]=layers;}
 }
 if(clean.dump().size()>MAX_PACK)throw std::runtime_error("材质包超过 32 MB");return clean;
}
std::string pack_digest(const J& doc){return digest(doc.dump());}
void activate(const J& doc,bool remote){auto& s=state();J clean=validate_pack(doc);std::map<std::string,V> images;for(auto& [key,e]:clean["entries"].items()){const auto* r=resource(key);images[key]=png_decode(unb64(e["png"]),r->w,r->h);}s.overrides=std::move(images);s.derived.clear();s.remote=remote;s.active_name=clean["name"].get<std::string>();++s.generation;
 J wire=clean;for(auto& [k,e]:wire["entries"].items())e.erase("layers");s.wire=wire.dump();s.wire_hash=digest(s.wire);s.offered.clear();s.acked.clear();s.sending.clear();}
bool active(){return !state().overrides.empty();}uint64_t revision(){return state().generation;}
bool icon(const V& screen,const std::string& name,const V& box,bool flip){auto it=state().overrides.find("icon:"+name);if(it==state().overrides.end())return false;V image=it->second;if(flip)image=callm(pg::transform_module(),Sym("flip"),Args{image,V(true),V(false)});auto r=pg::rect_of(box);auto* src=pg::surf(image);const double scale=std::min(double(r.w)/src->w(),double(r.h)/src->h());SDL_Rect dest{r.x+int((r.w-src->w()*scale)/2),r.y+int((r.h-src->h()*scale)/2),std::max(1,int(src->w()*scale)),std::max(1,int(src->h()*scale))};SDL_BlitScaled(src->s,nullptr,pg::surf(screen)->s,&dest);return true;}
void set_notice(const std::string& text){state().notice=text;}
void persist_editor(const V& app){auto& s=state();if(!s.initialized)return;V st=getattr(app,Sym("state"),V::none());if(!st.is_dict())return;const auto screen=py_str(py::m_get(st,V("screen"),V("")));if(screen!="texture_library"&&screen!="texture_editor")return;try{s.dragging=s.panning=false;s.preview.clear();s.active_slider=-1;save_current(s.local_enabled);}catch(const std::exception& e){set_notice(std::string("自动保存失败：")+e.what());}}
void activate_local(){auto& s=state();if(s.local_enabled)activate(s.document);else activate({{"format","pvz-texture-pack-v1"},{"name","原版材质"},{"entries",J::object()}});}
void save_current(bool enable){auto& s=state();commit_canvas();save_file(s.root/"packs"/u8p(s.local_id+".pvptex"),s.document);s.local_enabled=enable;save_file(s.root/"selection.json",{{"active",s.local_id},{"enabled",enable}});activate_local();s.dirty=false;set_notice(enable?"已保存并启用 · 联机时由房主自动共享":"已保存 · 当前仍使用原版材质");}
void import_pack(const std::filesystem::path& file){auto& s=state();J doc=validate_pack(load_file(file));if(s.initialized)save_current(s.local_enabled);s.local_id="pack-"+digest(doc.dump()).substr(0,16);s.document=std::move(doc);s.selected_key.clear();s.canvas={};save_current();set_notice("材质包导入完成");}
void export_pack(const std::filesystem::path& file){save_current();save_file(file,state().document);}
void initialize(const V& app){auto& s=state();load_inventory();auto parent=u8p(py_str(getattr(getattr(app,Sym("settings_path")),Sym("parent"))));auto root=parent/"texture-packs";if(s.initialized&&s.root==root)return;
 s.root=root;s.initialized=true;std::filesystem::create_directories(root/"packs");std::filesystem::create_directories(root/"exports");std::filesystem::create_directories(root/"received");
 try{if(std::filesystem::exists(root/"selection.json"))s.local_id=load_file(root/"selection.json").value("active",std::string("default"));if(s.local_id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")!=std::string::npos)s.local_id="default";
 s.document={{"format","pvz-texture-pack-v1"},{"name","我的材质包"},{"entries",J::object()}};if(std::filesystem::exists(root/"packs"/u8p(s.local_id+".pvptex")))s.document=validate_pack(load_file(root/"packs"/u8p(s.local_id+".pvptex")));s.local_enabled=!std::filesystem::exists(root/"selection.json")||load_file(root/"selection.json").value("enabled",true);activate_local();}catch(const std::exception& e){set_notice(std::string("材质包加载失败：")+e.what());s.document={{"format","pvz-texture-pack-v1"},{"name","我的材质包"},{"entries",J::object()}};activate(s.document);}
 register_hooks();
}
void new_pack(){auto& s=state();if(s.initialized)save_current(s.local_enabled);commit_canvas();s.local_id="pack-"+digest(std::to_string(SDL_GetPerformanceCounter())).substr(0,16);s.document={{"format","pvz-texture-pack-v1"},{"name","新材质包"},{"entries",J::object()}};s.selected_key.clear();s.canvas={};save_current();}
void commit_canvas(){auto& s=state();if(s.selected_key.empty()||!s.canvas.w||!s.dirty)return;auto& c=s.canvas;J e={{"width",c.w},{"height",c.h},{"png",b64(png_encode(surface(c.w,c.h,c.flatten())))},{"layers",J::array()}};for(const auto& l:c.layers)e["layers"].push_back({{"name",l.name},{"visible",l.visible},{"opacity",l.opacity},{"png",b64(png_encode(surface(c.w,c.h,l.pixels)))}});s.document["entries"][s.selected_key]=e;s.dirty=false;}
namespace {void swap_canvas(Canvas& a,Canvas& b)noexcept{
 std::swap(a.w,b.w);std::swap(a.h,b.h);std::swap(a.selected,b.selected);std::swap(a.history_bytes,b.history_bytes);
 a.layers.swap(b.layers);a.undo.swap(b.undo);a.redo.swap(b.redo);
}}
void open_resource(const std::string& key){auto& s=state();
 // key may alias selected_key. Decode everything before saving or changing the
 // current editor identity: a missing original must not relabel the old canvas.
 std::string next_key(key);const auto* r=resource(next_key);if(!r)throw std::runtime_error("资源不存在");Canvas c;c.w=r->w;c.h=r->h;
 if(next_key==s.selected_key&&s.dirty&&s.canvas.w==r->w&&s.canvas.h==r->h&&!s.canvas.layers.empty())c.layers=s.canvas.layers;
 else if(s.document["entries"].contains(next_key)){const auto& e=s.document["entries"][next_key];if(e.contains("layers"))for(const auto& l:e["layers"])c.layers.push_back({l["name"],l["visible"],l["opacity"],pixels(png_decode(unb64(l["png"]),r->w,r->h))});else c.layers.push_back({"导入材质",true,255,pixels(png_decode(unb64(e["png"]),r->w,r->h))});}
 else c.layers.push_back({"原始图层",true,255,pixels(original(*r))});
 const bool previous_dirty=s.dirty;if(!s.selected_key.empty())try{save_current(s.local_enabled);}catch(...){s.dirty=previous_dirty;throw;}
 // Member swaps allocate nothing, so no exception can separate the key from its
 // completed canvas (Canvas's deque move construction may allocate).
 s.selected_key.swap(next_key);swap_canvas(s.canvas,c);s.dirty=false;s.dragging=false;s.selection={};s.fit_pending=true;fit_canvas();}
namespace {uint32_t blend(uint32_t dst,uint32_t src,int opacity=255){const int sa=(src&255)*opacity/255,da=dst&255;const int a=sa+da*(255-sa)/255;if(!a)return 0;uint32_t out=a;for(int shift:{8,16,24}){int c=(((src>>shift)&255)*sa+((dst>>shift)&255)*da*(255-sa)/255)/a;out|=uint32_t(c)<<shift;}return out;}}
void Canvas::checkpoint(){if(layers.empty())return;redo.clear();size_t n=size_t(w)*h*4*layers.size();if(n>64*1024*1024)return;undo.push_back({layers,selected});history_bytes+=n;while(undo.size()>40||history_bytes>64*1024*1024){history_bytes-=size_t(w)*h*4*undo.front().layers.size();undo.pop_front();}}
bool Canvas::undo_step(bool forward){auto& from=forward?redo:undo;auto& to=forward?undo:redo;if(from.empty())return false;to.push_back({layers,selected});auto prev=std::move(from.back());from.pop_back();layers=std::move(prev.layers);selected=prev.selected;history_bytes=0;for(auto& x:undo)history_bytes+=size_t(w)*h*4*x.layers.size();return true;}
std::vector<uint32_t> Canvas::flatten()const{std::vector<uint32_t> out(size_t(w)*h);for(const auto& l:layers)if(l.visible)for(size_t i=0;i<out.size();++i)out[i]=blend(out[i],l.pixels[i],l.opacity);return out;}
void Canvas::dot(int x,int y,int size,uint32_t color,bool erase){auto& p=layers.at(selected).pixels;const int lo=-(size/2),hi=lo+size;for(int dy=lo;dy<hi;++dy)for(int dx=lo;dx<hi;++dx){if(size>2&&dx*dx+dy*dy>size*size/4)continue;const int px=x+dx,py=y+dy;if(px<0||py<0||px>=w||py>=h)continue;auto& v=p[size_t(py)*w+px];if(erase){const int a=(v&255)*(255-int(color&255))/255;v=a?((v&0xffffff00)|a):0;}else v=blend(v,color);}}
void Canvas::line(int x,int y,int x2,int y2,int size,uint32_t color,bool erase){int dx=std::abs(x2-x),dy=-std::abs(y2-y),sx=x<x2?1:-1,sy=y<y2?1:-1,err=dx+dy;for(;;){dot(x,y,size,color,erase);if(x==x2&&y==y2)break;int e2=err*2;if(e2>=dy){err+=dy;x+=sx;}if(e2<=dx){err+=dx;y+=sy;}}}
void Canvas::fill(int x,int y,uint32_t color){if(x<0||y<0||x>=w||y>=h)return;auto& p=layers.at(selected).pixels;const auto old=p[size_t(y)*w+x];const auto replacement=blend(old,color);if(old==replacement)return;std::vector<size_t> q{size_t(y)*w+x};p[q[0]]=replacement;for(size_t n=0;n<q.size();++n){const auto k=q[n];const int px=k%w,py=k/w;for(auto pos:{std::pair{px-1,py},std::pair{px+1,py},std::pair{px,py-1},std::pair{px,py+1}}){if(pos.first<0||pos.second<0||pos.first>=w||pos.second>=h)continue;size_t at=size_t(pos.second)*w+pos.first;if(p[at]==old){p[at]=replacement;q.push_back(at);}}}}
void Canvas::shape(int x,int y,int x2,int y2,int size,uint32_t color,bool ellipse,bool solid){int x0=std::min(x,x2),x1=std::max(x,x2),y0=std::min(y,y2),y1=std::max(y,y2);if(!ellipse){if(solid)for(int yy=y0;yy<=y1;++yy)line(x0,yy,x1,yy,1,color);else{line(x0,y0,x1,y0,size,color);line(x1,y0,x1,y1,size,color);line(x1,y1,x0,y1,size,color);line(x0,y1,x0,y0,size,color);}return;}double rx=std::max(.5,(x1-x0)/2.),ry=std::max(.5,(y1-y0)/2.),cx=(x0+x1)/2.,cy=(y0+y1)/2.;for(int yy=y0;yy<=y1;++yy)for(int xx=x0;xx<=x1;++xx){double d=std::pow((xx-cx)/rx,2)+std::pow((yy-cy)/ry,2);double inner=std::max(0.,1.-double(size)/std::min(rx,ry));if(d<=1.&&(solid||d>=inner*inner))dot(xx,yy,1,color);}}
void fit_canvas(){auto& s=state();if(!s.canvas.w)return;s.zoom=std::clamp(std::min(double(std::max(100,s.viewport.w-32))/s.canvas.w,double(std::max(100,s.viewport.h-32))/s.canvas.h),.05,32.);s.panx=s.pany=0;}
void import_image(const std::filesystem::path& path){auto& s=state();if(!s.canvas.w)throw std::runtime_error("请先选择要绘制的资源");if(std::filesystem::file_size(path)>MAX_PACK)throw std::runtime_error("图片文件超过 32 MB");
 V in=callm(pg::image_module(),Sym("load"),Args{V(p8(path))});auto* image=pg::surf(in);if(image->w()>8192||image->h()>8192||size_t(image->w())*image->h()>MAX_PIXELS)throw std::runtime_error("图片尺寸过大");
 V out=pg::new_surface(s.canvas.w,s.canvas.h,true);SDL_Rect dest{0,0,image->w(),image->h()};if(s.import_mode==1){dest.w=s.canvas.w;dest.h=s.canvas.h;}else if(s.import_mode==0){const double ratio=std::min(double(s.canvas.w)/dest.w,double(s.canvas.h)/dest.h);dest.w=std::max(1,int(dest.w*ratio));dest.h=std::max(1,int(dest.h*ratio));}dest.x=(s.canvas.w-dest.w)/2;dest.y=(s.canvas.h-dest.h)/2;SDL_BlitScaled(image->s,nullptr,pg::surf(out)->s,&dest);s.canvas.checkpoint();s.canvas.layers.at(s.canvas.selected).pixels=pixels(out);s.dirty=true;set_notice("图片已导入当前图层，可撤销");}
void choose_import(const std::filesystem::path& path){if(path.empty())return;try{auto ext=p8(path.extension());for(char& c:ext)if(c>='A'&&c<='Z')c=char(c-'A'+'a');if(ext==".pvptex"||ext==".json")import_pack(path);else import_image(path);}catch(const std::exception& e){set_notice(std::string("导入失败：")+e.what());}}
V artwork(const std::string& name){
 auto& s=state();if(!active())return V::none();
 if(auto it=s.overrides.find(name);it!=s.overrides.end())return it->second;
 if(auto it=s.derived.find(name);it!=s.derived.end())return it->second;
 std::string plain=name;
 for(const char* prefix:{"world:","ui:","bg:","near:","global:"})if(plain.rfind(prefix,0)==0){plain=plain.substr(std::strlen(prefix));break;}
 for(const auto& key:{"world:"+plain,"ui:"+plain,"bg:"+plain,"near:"+plain,"global:"+plain,"raw:图片/"+plain+".png","raw:extract/data/pvp/assets/content/"+plain+".png"})
  if(auto it=s.overrides.find(key);it!=s.overrides.end())return it->second;
 for(const auto& [key,image]:s.overrides)if(key.rfind("raw:",0)==0){const auto* r=resource(key);if(r&&r->name==plain){s.derived[name]=image;return image;}}
 // Derived status sprites keep the new silhouette. Explicit painted variants win.
 for(const std::string suffix:{"-黑白","-受伤","-冰冻","-灰烬","-魅惑"}){
  if(name.size()<=suffix.size()||name.compare(name.size()-suffix.size(),suffix.size(),suffix)!=0)continue;
  V base=artwork(name.substr(0,name.size()-suffix.size()));if(base.is_none())break;
  auto world=std::make_unique<Match>();world->pygame=pg::pygame_module();V image;
  if(suffix=="-黑白")image=fn_换黑白(*world,Args{base});
  else {const V color=suffix=="-受伤"?V::tuple({V(255),V(255),V(255)}):suffix=="-灰烬"?V::tuple({V(0),V(0),V(0)}):suffix=="-冰冻"?V::tuple({V(0),V(0),V(255)}):V::tuple({V(128),V(0),V(128)});
   image=(suffix=="-受伤"||suffix=="-灰烬")?fn_纯换色(*world,Args{base,color}):fn_不纯换色(*world,Args{base,color});}
  s.derived[name]=image;return image;
 }
 return V::none();
}
void sync_art(const V& art){auto& s=state();V stamp=getattr(art,Sym("_texture74_revision"),V::none());if(stamp.is_none()){setattr(art,Sym("_texture74_revision"),V(double(s.generation)));return;}if(stamp.num()==double(s.generation))return;for(const char* name:{"images","scaled"}){V c=getattr(art,Sym(name),V::none());if(!c.is_none())callm(c,Sym("clear"),Args{});}setattr(art,Sym("_texture74_revision"),V(double(s.generation)));}
void sync_renderer(const V& renderer){auto& s=state();V stamp=getattr(renderer,Sym("_texture74_revision"),V::none());if(stamp.is_none()){setattr(renderer,Sym("_texture74_revision"),V(double(s.generation)));return;}if(stamp.num()==double(s.generation))return;callm(renderer,Sym("clear_transient_caches"),Args{});for(const char* name:{"images","_grave_icons"}){V c=getattr(renderer,Sym(name),V::none());if(!c.is_none())callm(c,Sym("clear"),Args{});}setattr(renderer,Sym("_texture74_revision"),V(double(s.generation)));}
void register_hooks(){static bool once=false;if(once)return;once=true;
 py::register_native_hook("texture74.image_path",[](const Args& a){if(!display_images||!active())return V::none();std::string path=py_str(a.pos.at(0));std::replace(path.begin(),path.end(),'\\','/');
  for(const auto& [key,image]:state().overrides)if(key.rfind("raw:",0)==0){const std::string file=key.substr(4);if(path==file||(path.size()>file.size()&&path.compare(path.size()-file.size(),file.size(),file)==0&&path[path.size()-file.size()-1]=='/'))return callm(image,Sym("copy"),Args{});}return V::none();});
 py::register_native_hook("texture74.surface",[](const Args& a){const auto resolver=a.pos.at(2);if(!getattr(resolver,Sym("__texture74_display_resolver__"),V(false)).truthy())return V::none();const auto key=py_str(a.pos.at(0));V image=artwork(key);if(image.is_none()&&key.rfind("world:@load/",0)==0){auto name=key.substr(12);name=name.substr(0,name.rfind('/'));image=artwork("raw:"+name);}if(image.is_none())return image;auto size=a.pos.at(1);if(callm(image,Sym("get_width"),Args{})!=size.idx(0)||callm(image,Sym("get_height"),Args{})!=size.idx(1))image=callm(pg::transform_module(),Sym("scale"),Args{image,size});return image;});
 py::register_native_hook("texture74.render_begin",[](const Args& a){const V replay=a.pos.at(0);auto rev=getattr(replay,Sym("_texture74_revision"),V::none());if(rev.is_none()){setattr(replay,Sym("_texture74_revision"),V(double(revision())));return V(active());}if(rev.num()!=double(revision())){for(const char* name:{"cache","_frame_keys","_local_scaled"})callm(getattr(replay,Sym(name)),Sym("clear"),Args{});for(const char* name:{"cache_bytes","_frame_key_bytes","local_bytes"})setattr(replay,Sym(name),V(0));setattr(replay,Sym("_texture74_revision"),V(double(revision())));}return V(active());});
}
J diagnostics(){auto& s=state();return {{"resources",s.resources.size()},{"entries",s.overrides.size()},{"revision",s.generation},{"remote",s.remote},{"active_name",s.active_name},{"local_enabled",s.local_enabled},{"acked_peers",std::count_if(s.acked.begin(),s.acked.end(),[&](const auto& row){return row.second==s.wire_hash;})},{"wire_hash",s.wire_hash},{"received_packs",s.received_packs},{"rejected",s.rejected},{"sent_chunks",s.sent_chunks},{"ready",s.guest_ready}};}
}
