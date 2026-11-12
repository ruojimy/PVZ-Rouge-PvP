// A real bound callable: the stored receiver is prepended on every invocation.
#include "sim/pvp/pvprt.h"
namespace pvz::py {
V native_method_type();
namespace {
struct NativeMethod : PyObj {
    V function,receiver;
    const char* type_name() const override { return "method"; }
    bool isa(const char* name) const override { return std::string(name)=="method" || std::string(name)=="object"; }
    V property(Sym name,bool& found) override {
        found=true;
        if(name==Sym("__func__"))return function;
        if(name==Sym("__self__"))return receiver;
        if(name==Sym("__name__") || name==Sym("__qualname__") || name==Sym("__module__"))return pvz::getattr(function,name);
        found=false;return V();
    }
    bool set_property(Sym,const V&) override { throw PyError("AttributeError","method attributes are read-only"); }
    V call_self(const Args& input) override {
        Args bound=input;bound.pos.insert(bound.pos.begin(),receiver);return function.call(bound);
    }
    bool call_method(Sym name,const Args& args,V& result) override {
        if(name==Sym("__call__")){result=call_self(args);return true;}
        if(name==Sym("__eq__")){result=method(name).call(args);return true;}
        return false;
    }
    V method(Sym name) override {
        if(name==Sym("__native_type__")) {
            V metadata=V::func([](const Args&){return native_method_type();});
            metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true));return metadata;
        }
        auto self=std::static_pointer_cast<NativeMethod>(shared_from_this());
        if(name==Sym("__call__"))return V::func([self](const Args& a){return self->call_self(a);});
        if(name==Sym("__eq__"))return V::func([self](const Args& a){
            if(a.pos.size()!=1 || !a.kw.empty())throw PyError("TypeError","method equality requires one value");
            auto* other=as<NativeMethod>(a.pos[0]);return V(other && py_is(self->function,other->function) && py_is(self->receiver,other->receiver));
        });
        return V();
    }
};
}
V native_method_type() {
    static V type=[] {
        V result=class_value(V("method"),[](const Args& args) {
            if(args.pos.size()!=2 || !args.kw.empty())throw PyError("TypeError","method expected two positional arguments");
            const V& function=args.pos[0];
            bool callable=function.t==V::FUNC || (function.t==V::INST && std::string(function.box->inst->type_name())!="module" && function.box->inst->method(Sym("__call__")).has());
            if(!callable)throw PyError("TypeError","first argument must be callable");
            if(args.pos[1].is_none())throw PyError("TypeError","instance must not be None");
            auto method=std::make_shared<NativeMethod>();method->function=function;method->receiver=args.pos[1];return V::inst(method);
        });
        result.box->fattrs.emplace_back(Sym("__module__"),V("builtins"));return result;
    }();
    return type;
}
}
