#include "ui/hand/texture74_internal.h"
#include "core/fsutil.h"
#include <algorithm>
namespace pvz::texture74 {
namespace {
void exchange(Connection& c){auto& s=state();
 std::swap(s.transport_id,c.transport_id);std::swap(s.mode,c.mode);std::swap(s.retry,c.retry);
 s.offered.swap(c.offered);s.acked.swap(c.acked);s.sending.swap(c.sending);std::swap(s.receiving,c.receiving);
 std::swap(s.local_before_remote,c.local_before_remote);std::swap(s.rejected,c.rejected);std::swap(s.received_packs,c.received_packs);std::swap(s.sent_chunks,c.sent_chunks);std::swap(s.guest_ready,c.guest_ready);std::swap(s.remote,c.remote);
}
}
void select_connection(const V& app){auto& s=state();const auto key=py_str(py::id(app));if(s.selected_connection==key)return;
 if(!s.selected_connection.empty())exchange(s.connections[s.selected_connection]);
 exchange(s.connections[key]);s.selected_connection=key;
}
void close_connection(const V& app){auto& s=state();select_connection(app);if(s.remote)activate_local();Connection discarded;exchange(discarded);s.connections.erase(s.selected_connection);s.selected_connection.clear();}
namespace {
constexpr int CHUNK=16384;
V value(const J& j){return py::json_loads(V(j.dump()));}
bool send(const V& app,const V& peer,const J& payload){V transport=getattr(app,Sym("transport"),V::none());if(transport.is_none())return false;
 if(getattr(app,Sym("mode"),V::none())==V("host"))return callm(transport,Sym("send"),Args{peer,value(payload)}).truthy();return callm(transport,Sym("send"),Args{value(payload)}).truthy();}
bool authorized(const V& app,const V& peer){V room=getattr(app,Sym("room"),V::none());return !room.is_none()&&(py::in(peer,getattr(room,Sym("members")))||py::in(peer,getattr(room,Sym("spectators"),V::dict())));}
void accepted(const V& app,const V& peer,const J& doc,const std::string& hash){auto& s=state();if(!s.remote)s.local_before_remote=s.document;activate(doc,true);s.guest_ready=true;s.receiving={};++s.received_packs;
 save_file(s.root/"received"/u8p(hash+".pvptex"),doc);send(app,peer,{{"type","texture74_ack"},{"hash",hash}});wr(getattr(app,Sym("state")),V("texture_pack_status"))=V("房主材质 · "+doc.at("name").get<std::string>());}
}
void update(const V& app,double dt){auto& s=state();if(!s.initialized)return;select_connection(app);auto picked=poll_file();if(!picked.empty()){if(picked[0]=='!')set_notice("文件操作失败："+picked.substr(1));else choose_import(u8p(picked));}
 V transport=getattr(app,Sym("transport"),V::none()),mode=getattr(app,Sym("mode"),V::none());const std::string id=transport.is_none()?"":py_str(py::id(transport));
 if(id!=s.transport_id||py_str(mode)!=s.mode){if(s.remote){activate_local();s.local_before_remote=J();}s.offered.clear();s.acked.clear();s.sending.clear();s.receiving={};s.guest_ready=false;s.transport_id=id;s.mode=py_str(mode);s.retry=0;}
 if(transport.is_none())return;
 if(mode==V("guest")){if(!s.guest_ready){s.retry+=std::max(0.,dt);if(s.retry>=3.){send(app,V::none(),{{"type","texture74_hello"}});s.retry=0;}}if(s.receiving.chunks){s.receiving.elapsed+=std::max(0.,dt);if(s.receiving.elapsed>15.){send(app,V::none(),{{"type","texture74_request"},{"hash",s.receiving.hash}});s.receiving.elapsed=0;}}return;}
 if(mode!=V("host"))return;V room=getattr(app,Sym("room"),V::none());if(room.is_none())return;
 std::vector<V> peers;for(const char* key:{"members","spectators"}){V list=py::iter_list(getattr(room,Sym(key),V::dict()));for(const auto& peer:list.items())if(peer!=V("host")&&!py::in(peer,getattr(room,Sym("ai_peers"),V::tuple({})))&&(py::m_get(getattr(room,Sym("connected")),peer).truthy()||py::in(peer,getattr(room,Sym("spectators"),V::dict()))))peers.push_back(peer);}
 s.retry+=std::max(0.,dt);const bool retry=s.retry>2.;if(retry)s.retry=0;
 for(const auto& peer:peers){const std::string p=py_str(peer);if(s.acked[p]!=s.wire_hash&&(s.offered[p]!=s.wire_hash||retry)){
   send(app,peer,{{"type","texture74_offer"},{"hash",s.wire_hash},{"bytes",s.wire.size()},{"chunks",(s.wire.size()+CHUNK-1)/CHUNK},{"name",s.active_name}});s.offered[p]=s.wire_hash;}
  auto it=s.sending.find(p);if(it==s.sending.end())continue;auto& t=it->second;if(t.hash!=s.wire_hash){s.sending.erase(it);continue;}
  V pending=getattr(transport,Sym("pending_bytes"),V::none());if(!pending.is_none()&&pending.call(Args{peer}).num()>64*1024)continue;
  const auto part=t.bytes.substr(t.offset,CHUNK);if(send(app,peer,{{"type","texture74_chunk"},{"hash",t.hash},{"index",t.offset/CHUNK},{"data",b64(part)}})){t.offset+=part.size();++s.sent_chunks;if(t.offset>=t.bytes.size())s.sending.erase(it);}
 }
}
bool receive(const V& app,const V& peer,const V& payload){if(!payload.is_dict())return false;const auto type=py_str(py::m_get(payload,V("type"),V("")));if(type.rfind("texture74_",0)!=0)return false;
 select_connection(app);auto& s=state();try{J p=J::parse(dump(payload));V mode=getattr(app,Sym("mode"));
 if(mode==V("host")){if(!authorized(app,peer))throw std::runtime_error("未知材质请求来源");const std::string id=py_str(peer);
  if(type=="texture74_hello"){s.offered.erase(id);s.acked.erase(id);return true;}
  if(type=="texture74_ack"){if(p.value("hash",std::string{})==s.wire_hash){s.acked[id]=s.wire_hash;s.sending.erase(id);}return true;}
  if(type=="texture74_request"){if(p.value("hash",std::string{})!=s.wire_hash)return true;Transfer t;t.hash=s.wire_hash;t.bytes=s.wire;s.sending[id]=std::move(t);return true;}
  throw std::runtime_error("房主不接受客机提供的材质");
 }
 if(mode!=V("guest"))return true;
 if(type=="texture74_offer"){const auto hash=p.at("hash").get<std::string>();const int64_t bytes=p.at("bytes").get<int64_t>(),chunks=p.at("chunks").get<int64_t>();
  if(hash.size()!=64||hash.find_first_not_of("0123456789abcdef")!=std::string::npos||bytes<1||bytes>int64_t(MAX_PACK)||chunks!=(bytes+CHUNK-1)/CHUNK)throw std::runtime_error("材质包传输清单无效");
  if(s.guest_ready&&s.remote&&s.wire_hash==hash){send(app,peer,{{"type","texture74_ack"},{"hash",hash}});return true;}
  const auto cache=s.root/"received"/u8p(hash+".pvptex");if(std::filesystem::exists(cache)){try{J doc=validate_pack(load_file(cache));if(pack_digest(doc)==hash){accepted(app,peer,doc,hash);return true;}}catch(const std::exception&){} }
  if(s.receiving.hash!=hash){s.receiving={};s.receiving.hash=hash;s.receiving.offset=size_t(bytes);s.receiving.chunks=int(chunks);s.receiving.name=p.value("name",std::string("房主材质"));s.guest_ready=false;wr(getattr(app,Sym("state")),V("texture_pack_status"))=V("正在接收房主材质包");send(app,peer,{{"type","texture74_request"},{"hash",hash}});}return true;
 }
 if(type=="texture74_chunk"){auto& t=s.receiving;if(!t.chunks||p.value("hash",std::string{})!=t.hash)return true;const int64_t i=p.at("index").get<int64_t>();if(i<0||i>=t.chunks||!p["data"].is_string()||p["data"].get_ref<const std::string&>().size()>((CHUNK+2)/3)*4)throw std::runtime_error("材质分片越界");const auto bytes=unb64(p["data"]);const size_t expected=i==t.chunks-1?t.offset-size_t(i)*CHUNK:CHUNK;if(bytes.size()!=expected)throw std::runtime_error("材质分片长度错误");auto it=t.parts.find(int(i));if(it!=t.parts.end()&&it->second!=bytes)throw std::runtime_error("重复材质分片冲突");t.parts[int(i)]=bytes;t.elapsed=0;
  wr(getattr(app,Sym("state")),V("texture_pack_status"))=V("房主材质 "+std::to_string(100*t.parts.size()/t.chunks)+"%");
  if(t.parts.size()==size_t(t.chunks)){std::string all;all.reserve(t.offset);for(int n=0;n<t.chunks;++n)all+=t.parts.at(n);const auto hash=t.hash;if(all.size()!=t.offset||digest(all)!=hash)throw std::runtime_error("材质包摘要不匹配");J doc=validate_pack(J::parse(all));if(pack_digest(doc)!=hash)throw std::runtime_error("材质包格式未规范化");accepted(app,peer,doc,hash);}return true;
 }
 throw std::runtime_error("未知材质传输消息");
 }catch(const std::exception& e){++s.rejected;s.receiving={};s.guest_ready=false;set_notice(std::string("材质同步失败：")+e.what());wr(getattr(app,Sym("state")),V("texture_pack_status"))=V("材质校验失败，将重试");}
 return true;
}
}
