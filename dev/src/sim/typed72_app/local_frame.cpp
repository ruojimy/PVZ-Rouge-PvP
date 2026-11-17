#include "sim/typed72_app/local_frame.h"
#include "sim/typed72_app/frame_projection.h"
#include "sim/pvp/pvprt.h"
#include "core/function_profile.h"
namespace pvz::typed72app {
namespace {
struct LocalFrame final:PyObj {
    typed72::NativeFrame frame;
    FrameProjection projection;
    std::vector<V> rows;
    V shell;
    std::shared_ptr<LocalFrameStats> stats;
    const char* type_name()const override{return "LocalTypedFrame";}
    explicit LocalFrame(const typed72::NativeFrame& f,std::shared_ptr<LocalFrameStats> s):frame(f),rows(f.commands.size()),stats(std::move(s)){
        if(f.commands.size()>12000)throw PyError("NativeGraphicsError","Native draw command limit exceeded");
        ++stats->frames;shell=V::dict();
        shell.at(V("protocol"))=V("native-draw-v1");shell.at(V("tick"))=V(double(f.tick));shell.at(V("tile"))=V(f.tile);
        shell.at(V("command_count"))=V(double(f.commands.size()));shell.at(V("commands"))=V::list();
        V positions=V::dict();for(const auto& [id,p]:f.positions)positions.at(V(id))=V::list({V(p.x),V(p.y)});
        shell.at(V("positions"))=positions;
    }
    V row(size_t index){
        if(!rows[index].has()){PVP_PROFILE_SCOPE("LocalFrame::project_command");rows[index]=projection.command(frame.commands[index]);++stats->projected;}
        return rows[index];
    }
    bool call_method(Sym name,const Args&,V& out)override{
        if(name.str()!="project")return false;
        ++stats->full_fallbacks;V commands=V::list();for(size_t i=0;i<rows.size();++i)commands.append(row(i));
        out=py::dict_of(shell);out.at(V("commands"))=commands;return true;
    }
};
}
V make_local_frame(const typed72::NativeFrame& frame,const std::shared_ptr<LocalFrameStats>& stats){
    PVP_PROFILE_SCOPE("LocalFrame::copy");
    auto p=std::make_shared<LocalFrame>(frame,stats);V out=py::dict_of(p->shell);out.at(V("_typed_local_frame"))=V::inst(p);return out;
}
V select_local_frame(const V& value,const std::function<bool(const LocalCommandBounds&)>& visible){
    if(!value.is_dict())return value;
    const auto* handle=value.find(V("_typed_local_frame"));if(!handle)return value;
    auto* local=as<LocalFrame>(*handle);if(!local)throw PyError("NativeGraphicsError","Invalid local frame owner");
    PVP_PROFILE_SCOPE("LocalFrame::select");
    const V hidden=value.get(V("_hidden_entity"),V::none());
    V commands=V::list();
    for(size_t i=0;i<local->frame.commands.size();++i){
        const auto& c=local->frame.commands[i];++local->stats->considered;
        if(!hidden.is_none()&&c.entity&&*c.entity==py_str(hidden)){++local->stats->culled;continue;}
        LocalCommandBounds bounds{bool(c.image),c.position.x,c.position.y,c.image?c.image->width:0,c.image?c.image->height:0,c.entity.value_or(""),c.image&&!c.layer.empty()?c.layer:"foreground"};
        if(!visible(bounds)){++local->stats->culled;continue;}
        commands.append(local->row(i));
    }
    local->shell.at(V("commands"))=commands;return local->shell;
}
}
