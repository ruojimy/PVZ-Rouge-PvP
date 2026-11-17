#pragma once
#include "sim/typed72_app/snapshot_sink.h"
#include "core/obj.h"
#include <stdexcept>
namespace pvz::typed72app {
// Only the UI-side consumer allocates V. No live Session/native references are
// retained; the result is a new object graph owned by this publication.
class ValueSnapshotSink final:public SnapshotSink {
    std::vector<V> stack_{V::dict()};
    void attach(std::string_view key,const V& v){
        if(stack_.back().is_list())stack_.back().append(v);
        else stack_.back().at(V(std::string(key)))=v;
    }
public:
    V result()const{if(stack_.size()!=1)throw std::logic_error("unbalanced snapshot sink");return stack_.front();}
    void object(std::string_view k)override{V v=V::dict();attach(k,v);stack_.push_back(v);}
    void array(std::string_view k)override{V v=V::list({});attach(k,v);stack_.push_back(v);}
    void end()override{if(stack_.size()<2)throw std::logic_error("snapshot sink underflow");stack_.pop_back();}
    void null(std::string_view k)override{attach(k,V::none());}
    void number(std::string_view k,double v)override{attach(k,V(v));}
    void boolean(std::string_view k,bool v)override{attach(k,V(v));}
    void text(std::string_view k,std::string_view v)override{attach(k,V(std::string(v)));}
};
}
