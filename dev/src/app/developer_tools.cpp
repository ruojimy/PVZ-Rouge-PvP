// Developer API v1: call the actual compiled modules, never import legacy Python.
#include "app/developer_tools.h"
#include "core/fsutil.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_custom_maps.h"
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "ui/gen/pm_room.h"
#include "ui/gen/pm_replay.h"
#include "ui/gen/pm_relay.h"
#include "ui/gen/pm_smoke.h"
#include "pg/pg.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <cmath>
#include <fstream>
#include <set>
#include <map>
#include <algorithm>
#include <stdexcept>

namespace pvz {
namespace {
using json=nlohmann::json;
namespace fs=std::filesystem;
struct ApiError : std::runtime_error {
    std::string code;
    ApiError(std::string c,std::string message):std::runtime_error(message),code(std::move(c)){}
};
void require(bool valid,const std::string& message) {if(!valid)throw ApiError("INVALID_REQUEST",message);}
json read_json(const fs::path& p,uintmax_t limit=16*1024*1024) {
    require(fs::is_regular_file(p),"Input file missing");
    require(fs::file_size(p)<=limit,"Input file exceeds byte limit");
    std::ifstream f(p,std::ios::binary);return json::parse(f);
}
V jv(const json& j) {
    if(j.is_null())return V::none();if(j.is_boolean())return V(j.get<bool>());
    if(j.is_number_integer())return V(j.get<int64_t>());
    if(j.is_number())return V(j.get<double>());if(j.is_string())return V(j.get<std::string>());
    if(j.is_array()){V out=V::list();for(const auto& x:j)out.append(jv(x));return out;}
    V out=V::dict();for(const auto& x:j.items())out.at(V(x.key()))=jv(x.value());return out;
}
json j(const V& v) {
    // The debug dumper is not a JSON string encoder (descriptions contain LF).
    if(v.is_none())return nullptr;
    if(v.t==V::BOOL)return v.truthy();
    if(v.is_str())return v.str();
    if(v.is_num()) {
        double n=v.num();require(std::isfinite(n),"Non-finite exported value");
        if(std::floor(n)==n && n>=-9007199254740991. && n<=9007199254740991.)return static_cast<int64_t>(n);
        return n;
    }
    if(v.is_list()){json out=json::array();V sequence=py::iter_list(v);for(const auto& x:sequence.items())out.push_back(j(x));return out;}
    if(v.is_dict()){json out=json::object();for(const auto& x:py::items_vec(v))out[x.first.str()]=j(x.second);return out;}
    throw ApiError("INVALID_REQUEST","Unsupported exported native value type");
}
void keys(const json& value,std::initializer_list<const char*> allowed) {
    require(value.is_object(),"Expected an object");
    std::set<std::string> names;for(auto n:allowed)names.insert(n);
    for(const auto& item:value.items())require(names.count(item.key())!=0,"Unknown field: "+item.key());
}
int integer(const json& a,const char* name,int fallback,int low,int high) {
    if(!a.contains(name))return fallback;
    require(a[name].is_number_integer() && a[name]>=low && a[name]<=high,std::string("Invalid integer bounds: ")+name);
    return a[name].get<int>();
}
json identity() {
    return {{"build",data::get("__init__","BUILD")},{"catalog_hash",pm_catalog::f_catalog_hash(Args{}).str()},
            {"rules_hash",pm_catalog::f_rules_hash(Args{}).str()},{"developer_api",1},
            {"adapter","native-devtools.1"},{"game_network_protocol",data::get("__init__","PROTOCOL")}};
}
void unused_close(const V& object){if(object.has() && !object.is_none())try{callm(object,SY("close"),Args{});}catch(...) {}}
struct Close {V object;~Close(){unused_close(object);}};

json verify_replay(const fs::path& file) {
    // Preserve the runtime reader's own schema, version and operation checks.
    auto header=read_json(file,64*1024*1024);
    require(header.contains("ticks") && header["ticks"].is_number_integer(),"Replay ticks must be an integer");
    // Offline tool budget only. Does not alter normal in-game replay limits.
    require(header["ticks"]>=0 && header["ticks"]<=120000,"Offline verification limit is 120000 room ticks");
    V data=pm_replay::f_read_recording(Args{V(p8(file))});
    V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
    V playback=pm_replay::new_Playback(Args{data,bridge,py::stdlib_module(SV("pygame"))});Close close{playback};
    auto* pb=as<pm_replay::C_Playback>(playback);
    pb->m_seek(Args{rd(data,SV("ticks"))});
    auto until=std::chrono::steady_clock::now()+std::chrono::minutes(3);
    while(!pb->a_verified.truthy() && !pb->a_error.truthy()) {
        if(std::chrono::steady_clock::now()>until)throw ApiError("TIMEOUT","Replay verification exceeded 180 seconds");
        pb->m_update(Args({V(0.)},{{SY("max_steps"),V(2000)},{SY("budget"),V(.1)}}));
    }
    if(!pb->a_verified.truthy())throw ApiError("NATIVE_REJECTED",pb->a_error.str());
    return {{"verified",true},{"ticks",j(rd(data,SV("ticks")))},{"operations",rd(data,SV("operations")).len()},
            {"final_hash",pm_replay::f_state_hash(Args{pb->a_battle}).str()}};
}

json relay_probe(const json& a) {
    keys(a,{"port"});require(a.contains("port") && a["port"].is_number_integer(),"port is required");
    int port=integer(a,"port",0,1,65535);
    // This acceptance operation is deliberately loopback-only. Service deployment is separate.
    V endpoint("127.0.0.1:"+std::to_string(port));
    V server=pm_relay::new_RelayHostTransport(Args{endpoint});Close cs{server};
    V client;Close cc{client};
    bool host_got=false,guest_got=false;
    const V payload=py_dict({{SV("developer_probe"),SV("native-roundtrip")},{SV("value"),V(72)}});
    auto pump=[&](const V& transport,bool host){
        V events=callm(transport,SY("poll"),Args{});
        for(const auto& event:events.items()) {
            auto type=py::m_get(event,SV("type"),SV("")).str();
            if(type=="connected")callm(transport,SY("send"),Args{host?py::m_get(event,SV("peer_id")):SV("server"),payload});
            if(type=="message" && py::m_get(event,SV("payload"))==payload)(host?host_got:guest_got)=true;
        }
    };
    auto until=std::chrono::steady_clock::now()+std::chrono::seconds(15);
    while(std::chrono::steady_clock::now()<until && !(host_got && guest_got)) {
        pump(server,true);
        V code=pvz::getattr(server,SY("code"));
        if(code.truthy() && !client.has()) {
            client=pm_relay::new_RelayClientTransport(Args({endpoint},{{SY("room_code"),code}}));cc.object=client;
        }
        if(client.has())pump(client,false);
        {gil::Release release;SDL_Delay(10);}
    }
    if(!(host_got && guest_got))throw ApiError("NATIVE_REJECTED","Native relay roundtrip did not complete");
    return {{"host_received",host_got},{"guest_received",guest_got},{"loopback",true},{"relay_protocol",1}};
}

json room_script(const json& a) {
    keys(a,{"steps","seed","map_id"});
    require(a.contains("steps") && a["steps"].is_array() && !a["steps"].empty() && a["steps"].size()<=128,"steps requires1..128items");
    int seed=integer(a,"seed",301,0,2147483647),total_ticks=0;std::map<std::string,int> sequences;
    require(!a.contains("map_id") || (a["map_id"].is_string() && a["map_id"].get<std::string>().size()<=128),"Invalid map_id");
    V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{}),room=pm_room::new_Room(Args{bridge});Close close{room};
    auto until=std::chrono::steady_clock::now()+std::chrono::seconds(20);
    auto budget=[&](){if(std::chrono::steady_clock::now()>until)throw ApiError("TIMEOUT","Room script exceeded20seconds");};
    auto snapshot=[&](){return callm(room,SY("snapshot"),Args({},{{SY("include_map"),V(false)}}));};
    auto stamp=[&](){V snap=snapshot(),battle=pvz::getattr(room,SY("battle"));
        json out={{"phase",j(rd(snap,SV("phase")))},{"revision",j(rd(snap,SV("revision")))},{"paused",j(rd(snap,SV("paused")))}};
        if(battle.truthy()){out["battle_tick"]=j(pvz::getattr(battle,SY("tick")));out["native_tick"]=j(pvz::getattr(pvz::getattr(battle,SY("engine")),SY("native_tick")));}
        return out;};
    json trace=json::array(),checks=json::array();int current_step=-1;
    auto send=[&](const std::string& peer,json payload){budget();json before=stamp();
        if(!payload.contains("revision"))payload["revision"]=before["revision"];
        V error=callm(room,SY("command"),Args{V(peer),jv(payload)});
        trace.push_back({{"step",current_step},{"peer",peer},{"command",payload},{"before",before},{"after",stamp()},{"error",j(error)}});return error;};
    V connected=callm(room,SY("connect"),Args{SV("guest")});
    require(!connected.truthy(),"Local guest connection failed");
    V map_error=send("host",{{"type","map"},{"map_id",a.value("map_id",std::string("家院"))},{"seed",seed}});
    if(map_error.truthy())throw ApiError("NATIVE_REJECTED",map_error.str());
    pm_smoke::init();V reserved=pm_smoke::PLANT_DECK+pm_smoke::ZOMBIE_DECK;
    for(const auto& step:a["steps"]) {
        ++current_step;budget();keys(step,{"action","peer","payload","input","card","ticks","expect_error","expect_phase"});
        require(step.contains("action") && step["action"].is_string(),"Step action is required");
        require(!step.contains("peer") || (step["peer"].is_string() && step["peer"].get<std::string>().size()<=64),"Invalid peer");
        require(!step.contains("expect_error") || step["expect_error"].is_boolean(),"expect_error must be boolean");
        require(!step.contains("expect_phase") || step["expect_phase"].is_string(),"expect_phase must be a string");
        std::string action=step["action"],peer=step.value("peer",std::string("host"));V error=SV("");json before=stamp();
        if(action=="command") {
            require(step.contains("payload") && step["payload"].is_object(),"command requires payload");error=send(peer,step["payload"]);
        } else if(action=="input" || action=="deploy") {
            json input=step.value("input",json::object());require(input.is_object(),"input must be an object");
            if(action=="deploy") {
                require(step.contains("card") && step["card"].is_string(),"deploy requires card");
                V battle=pvz::getattr(room,SY("battle")),seat=callm(room,SY("side_for"),Args{V(peer)});
                if(!battle.truthy() || !seat.truthy())error=SV("No active battle or local seat");
                else {
                    V terrain=pvz::getattr(battle,SY("map")),key=jv(step["card"]);double tile=pvz::getattr(battle,SY("tile")).num();
                    int cols=int(rd(terrain,SV("width")).num()/tile),rows=int(rd(terrain,SV("height")).num()/tile);bool found=false;
                    require(cols>0 && rows>0 && cols*rows<=8192,"Map exceeds offline placement-search budget");
                    for(int row=0;row<rows && !found;++row)for(int col=0;col<cols && !found;++col){budget();double x=(col+.5)*tile,y=row*tile-2;
                        V plan=callm(battle,SY("placement"),Args{seat,key,V(x),V(y),V::none()});
                        if(!plan.idx(0).truthy()){input={{"type","deploy"},{"card",step["card"]},{"x",x},{"y",y}};found=true;}}
                    if(!found)error=SV("No legal deployment found by authoritative placement rules");
                }
            }
            if(!error.truthy()) {
                if(!input.contains("seq"))input["seq"]=++sequences[peer];
                else if(input["seq"].is_number_integer() && input["seq"]>=0 && input["seq"]<=1000000)sequences[peer]=std::max(sequences[peer],input["seq"].get<int>());
                error=send(peer,{{"type","input"},{"input",input}});
            }
        } else if(action=="advance") {
            int ticks=integer(step,"ticks",1,0,1000);total_ticks+=ticks;require(total_ticks<=3000,"Advance budget is3000ticks per script");
            double hz=rd(pvz::getattr(room,SY("rules")),SV("tick_rate")).num();require(hz>0 && hz<=1000,"Invalid tick rate");
            for(int tick=0;tick<ticks;++tick){budget();callm(room,SY("update"),Args{V(1./hz)});}
        } else if(action=="ready" || action=="load") {
            for(const auto& member:py::items_vec(pvz::getattr(room,SY("members")))) {
                json payload={{"type",action=="ready"?"ready":"loaded"}};
                if(action=="ready")payload["ready"]=true;
                else{payload["loading_id"]=j(pvz::getattr(room,SY("loading_id")));payload["terrain_hash"]=j(pvz::getattr(pvz::getattr(room,SY("map")),SY("terrain_hash")));}
                V result=send(member.first.str(),payload);if(result.truthy())error=result;
            }
        } else if(action=="autodraft") {
            for(int n=0;n<64;++n) {
                V snap=snapshot(),phase=rd(snap,SV("phase"));if(rd(snap,SV("draft_stage"))==SV("complete"))break;
                if(phase!=SV("banning") && phase!=SV("picking")){error=SV("Autodraft requires banning or picking phase");break;}
                V actor=py::m_get(snap,SV("current_seat"),rd(snap,SV("current_side"))),chosen=V::none();std::string owner;
                for(const auto& member:py::items_vec(pvz::getattr(room,SY("members"))))if(member.second==actor)owner=member.first.str();
                require(!owner.empty(),"Draft actor has no local peer");
                if(phase==SV("banning")) {
                    if(callm(room,SY("_ban_error"),Args{actor,V::none()}).truthy()) {
                        V candidates=py::sorted_it(pm_catalog::CARDS,py::Key(),false);
                        for(const auto& key:candidates.items()) {
                            if(py::in(key,reserved) || callm(room,SY("_ban_error"),Args{actor,key}).truthy())continue;
                            bool allowed=true;V bans=pvz::getattr(room,SY("bans"))+V::list({key});
                            for(const auto& wanted:reserved.items())if(!pm_catalog::f_allowed(Args{wanted,bans}).truthy())allowed=false;
                            if(allowed){chosen=key;break;}
                        }
                        if(chosen.is_none()){error=SV("No legal draft ban found");break;}
                    }
                } else {
                    V preferred=actor==SV("plant")?pm_smoke::PLANT_DECK:pm_smoke::ZOMBIE_DECK;
                    for(const auto& key:preferred.items())if(!callm(room,SY("_pick_error"),Args{actor,key}).truthy()){chosen=key;break;}
                    if(chosen.is_none())chosen=callm(room,SY("_timeout_pick"),Args{actor});
                    if(chosen.is_none()){error=SV("No legal draft pick found");break;}
                }
                error=send(owner,{{"type",phase==SV("banning")?"ban":"pick"},{"card",j(chosen)}});if(error.truthy())break;
            }
            if(!error.truthy() && pvz::getattr(room,SY("draft_stage"))!=SV("complete"))error=SV("Autodraft exceeded64commands");
        } else require(action=="snapshot","Unknown room-script action: "+action);
        bool expected_rejection=step.value("expect_error",false),passed=error.truthy()==expected_rejection;
        json after=stamp();if(step.contains("expect_phase"))passed=passed && after["phase"]==step["expect_phase"];
        checks.push_back({{"step",current_step},{"action",action},{"before",before},{"after",after},{"error",j(error)},{"expectations_met",passed}});
    }
    bool passed=true;for(const auto& check:checks)if(!check["expectations_met"].get<bool>())passed=false;
    return {{"completed",true},{"all_expectations_met",passed},{"steps",checks},{"commands",trace},{"advance_ticks",total_ticks},
        {"game_log",j(py::list_it(pvz::getattr(room,SY("log"))))},{"final_snapshot",j(callm(room,SY("snapshot"),Args{}))},{"network","in-process local peers only"}};
}

json execute(const std::string& op,const json& a) {
    if(op=="capabilities") {
        keys(a,{});
        return {{"operations",{"capabilities","export","map-new","map-check","map-import","replay-demo","replay-check","relay-probe","room-script"}},
                {"room_script_limits",{{"steps",128},{"advance_ticks_per_step",1000},{"advance_ticks_total",3000},{"wall_seconds",20},{"mode","local duel"}}},
                {"map_schema",j(pm_custom_maps::SCHEMA)},{"map_palette",j(pm_custom_maps::PALETTE)},
                {"maps",j(pm_maps::f_map_registry(Args{pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{})}))},{"replay_format",j(pm_replay::FORMAT)},
                {"content_plugins",false},{"ai_plugins",false}};
    }
    if(op=="room-script")return room_script(a);
    if(op=="export") {
        keys(a,{"night","secrets"});
        require(!a.contains("night") || a["night"].is_boolean(),"night must be boolean");
        auto secret_json=a.value("secrets",json::array());require(secret_json.is_array(),"secrets must be an array");
        require(secret_json.size()<=100,"Too many secrets");
        for(const auto& secret:secret_json) {
            require(secret.is_string(),"Secret id must be a string");V key(secret.get<std::string>());
            require(py::in(key,pm_catalog::CARDS) && rd(rd(pm_catalog::CARDS,key),SV("category"))==SV("secret"),"Unknown secret id");
        }
        V secrets=jv(secret_json),night(a.value("night",false));
        json descriptions=json::object(),cards=json::object();
        for(const auto& item:py::items_vec(pm_catalog::CARDS)) {
            cards[item.first.str()]=j(pm_catalog::f_actual_card(Args{item.first,secrets,night}));
            descriptions[item.first.str()]=j(pm_catalog::f_describe(Args{item.first,secrets,night}));
        }
        return {{"rules",j(pm_catalog::RULES)},{"cards",cards},{"raw_templates",j(pm_catalog::CARDS)},{"descriptions",descriptions},
                {"context",{{"night",a.value("night",false)},{"secrets",secret_json},{"resolved_by","catalog.actual_card"},
                            {"scope","Resolved catalog values; battle-time cooldown/resource rules still apply; not a legality check"}}},
                {"excluded",j(pm_catalog::EXCLUDED)},{"boss_names",j(pm_catalog::BOSS_NAMES)}};
    }
    if(op=="map-new") {
        keys(a,{"base_map","seed","name","blank"});
        int seed=integer(a,"seed",1,0,2147483647);
        V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        V doc=pm_custom_maps::f_new_document(Args{bridge,V(a.value("base_map",std::string("家院"))),V(seed),V(a.value("blank",false))});
        if(a.contains("name"))setitem(doc,SV("name"),jv(a["name"]));
        doc=pm_custom_maps::f_validate_document(Args{doc});
        return {{"document",j(doc)}};
    }
    if(op=="map-check" || op=="map-import") {
        if(op=="map-import")keys(a,{"file","store"});else keys(a,{"file"});
        require(a.contains("file") && a["file"].is_string(),"file is required");
        V doc=pm_custom_maps::f_validate_document(Args{jv(read_json(u8p(a["file"].get<std::string>()))) });
        V snapshot=pm_custom_maps::f_snapshot_from_document(Args{doc});
        V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        V room=pm_room::new_Room(Args{bridge});Close cr{room};
        V proposal=callm(room,SY("_map_proposal"),Args{py_dict({{SV("map_id"),SV("custom:")+rd(doc,SV("id"))},
            {SV("seed"),rd(doc,SV("seed"))},{SV("custom_map"),doc}})});
        if(proposal.idx(0).truthy())throw ApiError("NATIVE_REJECTED",proposal.idx(0).str());
        V terrain=callm(proposal.idx(1),SY("to_dict"),Args{});
        V decks=py_dict({{SV("plant"),V::list({SV("plant:豌豆射手"),SV("plant:向日葵")})},
                         {SV("zombie"),V::list({SV("zombie:脑光墓碑"),SV("zombie:普通僵尸")})}});
        V battle=pm_native_battle::new_NativeBattle(Args({terrain,decks},{{SY("bridge"),bridge},{SY("pygame"),py::stdlib_module(SV("pygame"))},{SY("seed"),rd(doc,SV("seed"))}}));Close cb{battle};
        callm(battle,SY("step"),Args{V(2)});
        json result={{"valid",true},{"document",j(doc)},{"room_accepted",true},{"battle_tick",j(pvz::getattr(battle,SY("tick")))},
                     {"terrain_hash",j(pvz::getattr(snapshot,SY("terrain_hash")))},{"room_terrain_hash",j(pvz::getattr(proposal.idx(1),SY("terrain_hash")))}};
        if(op=="map-import") {
            require(a.contains("store") && a["store"].is_string(),"Explicit store directory is required");
            fs::path store=fs::absolute(u8p(a["store"].get<std::string>()));
            fs::path dest=store/u8p(rd(doc,SV("id")).str()+".json");
            require(!fs::exists(dest),"Map already exists; use a new document id");
            V object=pm_custom_maps::new_MapStore(Args{V(p8(store))});
            callm(object,SY("save"),Args{doc});
            V loaded=callm(object,SY("load"),Args{rd(doc,SV("id"))});
            require(loaded==doc,"MapStore roundtrip mismatch");
            result["saved_file"]=p8(dest);result["store_roundtrip"]=true;
        }
        return result;
    }
    if(op=="replay-demo") {
        keys(a,{"file","ticks"});require(a.contains("file") && a["file"].is_string(),"file is required");
        fs::path file=fs::absolute(u8p(a["file"].get<std::string>()));require(!fs::exists(file),"Replay already exists");
        int ticks=integer(a,"ticks",30,2,600);
        auto h=battle_from_scenario({{"seed",701}});Close cb{h.battle};
        V decks=py_dict({{SV("plant"),V::list({SV("plant:豌豆射手"),SV("plant:向日葵"),SV("plant:火炬树桩"),SV("secret:猫尾"),SV("secret:蓝火")})},
                         {SV("zombie"),V::list({SV("zombie:普通僵尸"),SV("zombie:脑光墓碑")})}});
        // Save pristine terrain before initialization decorations, as the application does.
        V pristine=callm(pm_maps::f_build_snapshot(Args{h.bridge,SV("家院"),V(701)}),SY("to_dict"),Args{});
        V rec=pm_replay::new_Recording(Args{h.battle,V(701),decks,V::list(),pristine});
        V movement=py_dict({{SV("type"),SV("move")},{SV("seq"),V(1)},{SV("move"),V(1)},{SV("jump"),V(true)},{SV("edge"),V(true)}});
        V error=callm(h.battle,SY("command_input"),Args{SV("plant"),movement});
        if(error.truthy())throw ApiError("NATIVE_REJECTED",error.str());
        callm(h.battle,SY("step"),Args{V(ticks)});
        callm(rec,SY("export"),Args{V(p8(file))});
        return {{"recorded",true},{"ticks",ticks},{"file",p8(file)},{"input_accepted",true}};
    }
    if(op=="replay-check") {keys(a,{"file"});require(a.contains("file") && a["file"].is_string(),"file is required");return verify_replay(u8p(a["file"].get<std::string>()));}
    if(op=="relay-probe")return relay_probe(a);
    throw ApiError("UNKNOWN_OPERATION","Unsupported operation: "+op);
}
}

int run_developer_tools(const std::string& request_path,const std::string& response_path) {
    json response={{"protocol",1},{"ok",false}};int status=2;
    fs::path output=u8p(response_path);
    // Never overwrite an existing request, report or player file.
    if(fs::exists(output))return 6;
    try {
        auto request=read_json(u8p(request_path));keys(request,{"protocol","operation","expected","arguments"});
        if(!request.contains("protocol") || !request["protocol"].is_number_integer() || request["protocol"]!=1)
            throw ApiError("PROTOCOL_MISMATCH","Developer protocol 1 is required");
        require(request.contains("operation") && request["operation"].is_string(),"operation is required");
        auto op=request["operation"].get<std::string>();response["operation"]=op;
        auto actual=identity();response["identity"]=actual;
        if(op!="capabilities") {
            require(request.contains("expected"),"expected identity is required; call capabilities first");
            keys(request["expected"],{"build","rules_hash","catalog_hash","developer_api","adapter","game_network_protocol"});
            if(request["expected"]!=actual)throw ApiError("VERSION_MISMATCH","Target build/rules/catalog/API identity differs");
        }
        response["result"]=execute(op,request.value("arguments",json::object()));response["ok"]=true;status=0;
    } catch(const ApiError& e) {response["error"]={{"code",e.code},{"message",e.what()}};
    } catch(const PyError& e) {response["error"]={{"code","NATIVE_REJECTED"},{"message",e.what()}};status=3;
    } catch(const std::exception& e) {response["error"]={{"code","INVALID_REQUEST"},{"message",e.what()}};}
    try {
        if(!output.parent_path().empty())fs::create_directories(output.parent_path());
        fs::path pending=output;pending+=".pending";
        if(fs::exists(pending))return 6;
        {std::ofstream f(pending,std::ios::binary);f<<response.dump(2)<<"\n";f.close();if(f.fail())return 6;}
        fs::rename(pending,output);
    }catch(...){return 6;}
    return status;
}
}
