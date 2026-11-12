#include "sim/pvp/pvprt.h"
#include <exception>
namespace pvz::py {
namespace {
struct ExitStack final : PyObj {
    std::vector<V> exits;
    const char* type_name() const override { return "ExitStack"; }
    V unwind(const Args& a) {
        Args details=a;
        if(details.pos.size()!=3)throw PyError("TypeError","ExitStack exit requires exception details");
        const bool received=!details.pos[0].is_none();bool suppressed=false;
        std::exception_ptr pending;
        while(!exits.empty()) {
            V exit=exits.back();exits.pop_back();
            try {
                if(exit.call(details).truthy()) {
                    suppressed=true;pending=nullptr;
                    details=Args{V::none(),V::none(),V::none()};
                }
            } catch(const PyError& error) {
                pending=std::current_exception();
                details=Args{py::exc_type(V(error.kind)),py::exc_value(error),V::none()};
            } catch(const std::exception& error) {
                pending=std::current_exception();
                details=Args{py::exc_type(V("RuntimeError")),py::make_exc(V("RuntimeError"),Args{V(error.what())},""),V::none()};
            }
        }
        if(pending)std::rethrow_exception(pending);
        return V(received && suppressed);
    }
    V method(Sym name) override {
        auto owner=std::static_pointer_cast<ExitStack>(shared_from_this());
        if(name==Sym("__enter__"))return V::func([owner](const Args&){return V::inst(owner);});
        if(name==Sym("__exit__"))return V::func([owner](const Args& a){return owner->unwind(a);});
        if(name==Sym("close"))return V::func([owner](const Args&){owner->unwind(Args{V::none(),V::none(),V::none()});return V::none();});
        if(name==Sym("enter_context"))return V::func([owner](const Args& a){
            V manager=a.pos.at(0),exit=pvz::getattr(manager,Sym("__exit__"));
            V result=callm(manager,Sym("__enter__"),Args{});owner->exits.push_back(exit);return result;
        });
        if(name==Sym("push"))return V::func([owner](const Args& a){
            V value=a.pos.at(0);owner->exits.push_back(pvz::hasattr(value,Sym("__exit__"))?pvz::getattr(value,Sym("__exit__")):value);return value;
        });
        if(name==Sym("callback"))return V::func([owner](const Args& a){
            V fn=a.pos.at(0);Args bound;for(size_t i=1;i<a.pos.size();++i)bound.pos.push_back(a.pos[i]);bound.kw=a.kw;
            owner->exits.push_back(V::func([fn,bound](const Args&){fn.call(bound);return V(false);}));return fn;
        });
        if(name==Sym("pop_all"))return V::func([owner](const Args&){auto next=std::make_shared<ExitStack>();next->exits.swap(owner->exits);return V::inst(next);});
        return V();
    }
};
}
V native_exit_stack(const Args& a) {
    if(!a.pos.empty() || !a.kw.empty())throw PyError("TypeError","ExitStack takes no arguments");
    return V::inst(std::make_shared<ExitStack>());
}
}
