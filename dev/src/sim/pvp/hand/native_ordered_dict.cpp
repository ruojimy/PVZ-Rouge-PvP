// Native ordered mapping retains the real insertion-order storage and type
// marker across clear/copy/deepcopy; it is distinct from an ordinary dict.
#include "sim/pvp/pvprt.h"
namespace pvz::py {
V native_ordered_dict_type() {
    static V type=[] {
        V result=class_value(V("OrderedDict"),[](const Args& args){
            if(args.pos.size()>1)throw PyError("TypeError","OrderedDict expects at most one positional argument");
            V value=args.pos.empty()?V::dict():dict_of(args.pos[0]);
            for(const auto& kw:args.kw)value.at(V(kw.first))=kw.second;
            value.box->fattrs.emplace_back(Sym("__native_ordered_dict__"),V(true));
            return value;
        });
        result.box->fattrs.emplace_back(Sym("__module__"),V("collections"));return result;
    }();return type;
}
}
