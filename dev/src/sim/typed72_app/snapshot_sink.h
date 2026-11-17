#pragma once
#include <string>
#include <string_view>
#include <type_traits>
namespace pvz::typed72app {
// Synchronous value sink: Session knows neither V nor the receiver's storage.
// Names/text are borrowed for the call only. The sink must own emitted values.
struct SnapshotSink {
    virtual ~SnapshotSink()=default;
    virtual void object(std::string_view key)=0;
    virtual void array(std::string_view key)=0;
    virtual void end()=0;
    virtual void null(std::string_view key)=0;
    virtual void number(std::string_view key,double value)=0;
    virtual void boolean(std::string_view key,bool value)=0;
    virtual void text(std::string_view key,std::string_view value)=0;
    template<class T> void put(std::string_view k,const T& v){
        if constexpr(std::is_same_v<T,bool>)boolean(k,v);
        else if constexpr(std::is_arithmetic_v<T>)number(k,double(v));
        else text(k,v);
    }
    template<class Range> void strings(std::string_view k,const Range& values){
        array(k);for(const auto& v:values)put("",v);end();
    }
    template<class Field> void optional(std::string_view k,const Field& v){
        if(!v.present()||v.is_null())null(k);else put(k,v.get());
    }
    // Already-owned journal/pose/rare metadata values are traversed in place,
    // without an ordered_json -> json deep conversion at the Session boundary.
    template<class Json> void json(std::string_view k,const Json& v){
        if(v.is_null())null(k);
        else if(v.is_boolean())boolean(k,v.template get<bool>());
        else if(v.is_number())number(k,v.template get<double>());
        else if(v.is_string())text(k,v.template get_ref<const std::string&>());
        else if(v.is_array()){array(k);for(const auto& x:v)json("",x);end();}
        else {object(k);for(auto i=v.begin();i!=v.end();++i)json(i.key(),i.value());end();}
    }
};
}
