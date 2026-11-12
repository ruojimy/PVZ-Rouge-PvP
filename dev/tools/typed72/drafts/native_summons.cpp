#include "sim/typed/native_summons.h"
#include "core/pymath.h"

namespace pvz::typed72 {
std::shared_ptr<AttackSource> NativeSummons::metadata(const Source& source) {
    if(const auto* unit=std::get_if<ZombieRef>(&source))return source_ref(*unit);
    return std::get<ScriptedSpawnOrigin>(source).source;
}
ScriptedSpawnOrigin NativeSummons::snapshot(const Source& source) {
    if(const auto* unit=std::get_if<ZombieRef>(&source))return scripted_spawn_origin(*unit);
    return std::get<ScriptedSpawnOrigin>(source);
}
Motion NativeSummons::position(const Source& source) {
    if(const auto* unit=std::get_if<ZombieRef>(&source))return (*unit)->body.motion.get();
    return std::get<ScriptedSpawnOrigin>(source).position.get();
}
Motion NativeSummons::barrel_position(const Source& source) {
    if(const auto* unit=std::get_if<ZombieRef>(&source))return *(*unit)->barrel_position.get();
    return std::get<ScriptedSpawnOrigin>(source).barrel_position.get();
}
double NativeSummons::facing(const Source& source) {
    if(const auto* unit=std::get_if<ZombieRef>(&source))return (*unit)->body.facing;
    return std::get<ScriptedSpawnOrigin>(source).facing.get();
}
bool NativeSummons::summon(ZombieRef source,std::string name,bool thrown,double offset,bool defer) {
    return summon_source(Source(std::move(source)),name,thrown,offset,defer);
}
bool NativeSummons::summon_source(const Source& source,const std::string& name,bool thrown,double offset,bool defer) {
    const auto fields=metadata(source);
    const auto owner=world_.heroes.owner(fields).value();
    const auto start=position(source);
    if(!budget_.can_spawn(1,fields)) {
        if(defer) {
            const auto saved=snapshot(source);
            budget_.defer(fields,"content:"+name,offset,[this,saved,name,thrown,offset]() {
                return summon_source(Source(saved),name,thrown,offset,false);
            });
        }
        return false;
    }
    ZombieRef child;
    {
        HeroContext context(world_.heroes,{Seat::zombie,owner,CombatPhase::summon,fields,{}});
        struct Exemption {
            int& count;
            explicit Exemption(int& value):count(value){++count;}
            ~Exemption(){--count;}
        } exemption(world_.spawn_ban_exempt);
        const double direction=facing(source);const auto parent=snapshot(source);
        child=services_.spawn_content(name,{start.x,start.y-world_.runtime.tile},direction,parent);
    }
    if(!child)return false;
    if(owner==Seat::plant)child->source.charmed.set(200.);
    if(thrown) {
        child->native.entry.set(500.);child->native.rotation.set(0.);
        const double direction=facing(source);
        const double tile=world_.runtime.tile,plk=world_.runtime.plk;auto& point=child->body.motion.get();
        point.y=start.y-1.5*tile;point.x+=direction*offset*tile;
        point.vx=direction*plk*800.;point.vy=-plk*600.;
        const auto& content=fields->content;
        if(content.present() && !content.is_null() && content.get()=="滚桶僵尸") {
            const auto barrel=barrel_position(source);
            point={py::mod(barrel.x+direction*offset*tile,world_.world_width.get()),barrel.y-.75*tile,
                   direction*plk*(150.+offset*100.),-plk*180.};
        }
    }
    services_.content_summoned(fields->id,child->source.id.get(),"zombie:"+name,owner);
    return true;
}
} // namespace pvz::typed72
