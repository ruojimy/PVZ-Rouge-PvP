#pragma once
// Display boundary only: preserve the native-draw-v1 schema without a JSON round trip.
#include "core/pyobj.h"
#include "sim/typed/native_frame.h"
#include <nlohmann/json.hpp>
#include <map>
#include <tuple>
namespace pvz::typed72app {
class FrameProjection {
    using J=nlohmann::json;
    using Key=std::tuple<uintptr_t,int,int,int,bool>;
    struct Entry {std::shared_ptr<const typed72::NativeArtRecipe> owner;V value;};
    std::map<Key,Entry> previous_,current_;
    static V json_value(const J& j){
        if(j.is_null())return V::none();if(j.is_boolean())return V(j.get<bool>());
        if(j.is_number())return V(j.get<double>());if(j.is_string())return V(j.get<std::string>());
        if(j.is_array()){std::vector<V> a;a.reserve(j.size());for(const auto& x:j)a.push_back(json_value(x));return V::list(a);}
        V d=V::dict();for(auto i=j.begin();i!=j.end();++i)d.at(V(i.key()))=json_value(i.value());return d;
    }
    static V point(double x,double y){return V::list({V(x),V(y)});}
    V describe(const typed72::FrozenArt& image){
        const Key key{uintptr_t(image->recipe.get()),image->width,image->height,image->alpha,image->pixel_alpha};
        if(const auto i=current_.find(key);i!=current_.end()){++hits;return i->second.value;}
        V d;
        if(const auto i=previous_.find(key);i!=previous_.end()){++hits;d=i->second.value;}
        else{
            ++descriptions;const auto& r=*image->recipe;using K=typed72::NativeArtRecipe::Kind;V recipe=V::dict();
            if(r.external)recipe=json_value(*std::static_pointer_cast<const J>(r.external));
            else switch(r.kind){
            case K::asset:recipe.at(V("op"))=V("asset");recipe.at(V("key"))=V(r.key);recipe.at(V("size"))=point(image->width,image->height);break;
            case K::canvas:recipe.at(V("op"))=V("canvas");recipe.at(V("size"))=point(image->width,image->height);recipe.at(V("flags"))=V(double(r.flags));recipe.at(V("depth"))=V(32.);break;
            case K::scale:
                recipe.at(V("op"))=V("scale");recipe.at(V("source"))=describe(r.source);
                recipe.at(V("args"))=V::list({r.requested?point(r.requested->x,r.requested->y):point(image->width,image->height)});break;
            case K::flip:recipe.at(V("op"))=V("flip");recipe.at(V("source"))=describe(r.source);recipe.at(V("args"))=V::list({V(r.flip_x),V(r.flip_y)});break;
            case K::rotate:recipe.at(V("op"))=V("rotate");recipe.at(V("source"))=describe(r.source);recipe.at(V("args"))=V::list({V(r.angle)});break;
            case K::blit:
                recipe.at(V("op"))=V("blit");recipe.at(V("source"))=describe(r.source);recipe.at(V("overlay"))=describe(r.overlay);
                recipe.at(V("dest"))=point(r.destination.x,r.destination.y);recipe.at(V("area"))=V::none();recipe.at(V("flags"))=V(0.);break;
            }
            d=V::dict();d.at(V("image"))=recipe;
            d.at(V("alpha"))=image->alpha<0&&!image->pixel_alpha?V::none():V(double(image->alpha<0?255:image->alpha));
            d.at(V("colorkey"))=V::none();d.at(V("size"))=point(image->width,image->height);
        }
        if(current_.size()<8192)current_.emplace(key,Entry{image->recipe,d});
        return d;
    }
public:
    uint64_t descriptions=0,hits=0,frames=0;
    V project(const typed72::NativeFrame& frame){
        ++frames;current_.clear();V commands=V::list();
        for(const auto& c:frame.commands){
            V row=V::dict();
            if(c.primitive){
                const auto& p=*c.primitive;row.at(V("op"))=V("primitive");row.at(V("primitive"))=V(p.name);
                row.at(V("args"))=p.args?json_value(*std::static_pointer_cast<const J>(p.args)):
                    V::list({V::list({V(double(p.color[0])),V(double(p.color[1])),V(double(p.color[2])),V(double(p.color[3]))}),V::list({V(p.x),V(p.y),V(p.w),V(p.h)}),V(double(p.width))});
                row.at(V("kwargs"))=V::dict();
            }else{
                row.at(V("op"))=V("image");row.at(V("surface"))=describe(c.image);row.at(V("pos"))=point(c.position.x,c.position.y);
                row.at(V("area"))=V::none();row.at(V("flags"))=V(0.);
                if(!c.layer.empty())row.at(V("layer"))=V(c.layer);
            }
            if(c.entity)row.at(V("entity"))=V(*c.entity);commands.append(row);
        }
        V positions=V::dict();for(const auto& [id,p]:frame.positions)positions.at(V(id))=point(p.x,p.y);
        V out=V::dict();out.at(V("protocol"))=V("native-draw-v1");out.at(V("tick"))=V(double(frame.tick));out.at(V("tile"))=V(frame.tile);
        out.at(V("commands"))=commands;out.at(V("positions"))=positions;
        previous_=std::move(current_);current_.clear();return out;
    }
};
}
