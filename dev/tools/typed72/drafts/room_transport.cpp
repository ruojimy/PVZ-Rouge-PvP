#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#endif
#include "sim/typed/room_transport.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <condition_variable>
#include <future>
#include <random>
#include <thread>

namespace pvz::typed72 {
namespace {
using J=WireObject;
#ifdef _WIN32
using Socket=SOCKET;using SockLen=int;constexpr Socket invalid_socket=INVALID_SOCKET;
int socket_error(){return WSAGetLastError();}
void close_socket(Socket s){if(s!=invalid_socket)closesocket(s);}
bool pending_error(int e){return e==0||e==WSAEWOULDBLOCK||e==WSAEINPROGRESS||e==WSAEALREADY;}
bool would_block(int e){return e==WSAEWOULDBLOCK;}
void nonblocking(Socket s){u_long mode=1;if(ioctlsocket(s,FIONBIO,&mode))throw std::runtime_error("cannot set nonblocking socket");}
void initialize_sockets(){static std::once_flag flag;std::call_once(flag,[]{WSADATA data;if(WSAStartup(MAKEWORD(2,2),&data))throw std::runtime_error("Winsock initialization failed");});}
int select_count(Socket){return 0;}
#else
using Socket=int;using SockLen=socklen_t;constexpr Socket invalid_socket=-1;
int socket_error(){return errno;}
void close_socket(Socket s){if(s!=invalid_socket)::close(s);}
bool pending_error(int e){return e==0||e==EWOULDBLOCK||e==EINPROGRESS||e==EALREADY;}
bool would_block(int e){return e==EWOULDBLOCK||e==EAGAIN;}
void nonblocking(Socket s){const auto flags=fcntl(s,F_GETFL,0);if(flags<0||fcntl(s,F_SETFL,flags|O_NONBLOCK)<0)throw std::runtime_error("cannot set nonblocking socket");}
void initialize_sockets(){}
int select_count(Socket s){return s+1;}
#endif
struct ProtocolError:std::runtime_error{using std::runtime_error::runtime_error;};
struct TimeoutError:std::runtime_error{using std::runtime_error::runtime_error;};
struct ResolveError:std::runtime_error{using std::runtime_error::runtime_error;};
struct WouldBlock{};
double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
void fail_socket(const char* operation){throw std::runtime_error(std::string(operation)+": "+std::to_string(socket_error()));}
void no_delay(Socket s){int one=1;if(setsockopt(s,IPPROTO_TCP,TCP_NODELAY,reinterpret_cast<const char*>(&one),sizeof(one)))fail_socket("TCP_NODELAY");}
int send_bytes(Socket s,const void* bytes,size_t size){
#ifdef MSG_NOSIGNAL
    constexpr int flags=MSG_NOSIGNAL;
#else
    constexpr int flags=0;
#endif
    return int(::send(s,static_cast<const char*>(bytes),int(size),flags));
}
bool truth(const J& v){if(v.is_null())return false;if(v.is_boolean())return v.get<bool>();if(v.is_number())return v.get<double>()!=0.;if(v.is_string())return !v.get_ref<const std::string&>().empty();return !v.empty();}
bool equivalent(const J& a,const J& b){
    if((a.is_number()||a.is_boolean())&&(b.is_number()||b.is_boolean()))return (a.is_boolean()?double(a.get<bool>()):a.get<double>())==(b.is_boolean()?double(b.get<bool>()):b.get<double>());
    if(a.is_object()&&b.is_object()){if(a.size()!=b.size())return false;for(const auto& [key,v]:a.items())if(!b.contains(key)||!equivalent(v,b[key]))return false;return true;}
    if(a.is_array()&&b.is_array()){if(a.size()!=b.size())return false;for(size_t i=0;i<a.size();++i)if(!equivalent(a[i],b[i]))return false;return true;}return a==b;
}
bool same_secret(std::string_view a,std::string_view b){size_t diff=a.size()^b.size();for(size_t i=0;i<std::max(a.size(),b.size());++i)diff|=static_cast<unsigned char>(i<a.size()?a[i]:0)^static_cast<unsigned char>(i<b.size()?b[i]:0);return diff==0;}
size_t text_length(std::string_view s){return std::count_if(s.begin(),s.end(),[](unsigned char c){return (c&0xc0)!=0x80;});}
std::string text_prefix(std::string_view s,size_t count){size_t i=0,n=0;for(;i<s.size();++i)if((static_cast<unsigned char>(s[i])&0xc0)!=0x80&&n++==count)break;return std::string(s.substr(0,i));}
std::string text(const J& v){if(v.is_string())return v.get<std::string>();if(v.is_null())return "None";if(v.is_boolean())return v.get<bool>()?"True":"False";return v.dump();}
std::string token(size_t bytes,bool hex=false){
    std::random_device random;std::vector<uint8_t> raw(bytes);for(auto& b:raw)b=uint8_t(random());
    static constexpr char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",digits[]="0123456789abcdef";
    std::string out;if(hex){for(auto b:raw){out+=digits[b>>4];out+=digits[b&15];}return out;}
    uint32_t buffer=0;int bits=0;for(auto b:raw){buffer=(buffer<<8)|b;bits+=8;while(bits>=6){bits-=6;out+=alphabet[(buffer>>bits)&63];}}if(bits)out+=alphabet[(buffer<<(6-bits))&63];return out;
}
uint64_t sequence(const J& v,bool zero){if(!v.is_number_integer()||v.is_boolean()||(v.is_number_integer()&&!v.is_number_unsigned()&&v.get<int64_t>()<0))throw ProtocolError("invalid sequence");const auto n=v.get<uint64_t>();if(n>=(uint64_t(1)<<53)||(!zero&&n==0))throw ProtocolError("invalid sequence");return n;}
struct SocketOwner{Socket value=invalid_socket;~SocketOwner(){close_socket(value);}Socket release(){auto v=value;value=invalid_socket;return v;}};
struct Addresses{addrinfo* values=nullptr;~Addresses(){if(values)freeaddrinfo(values);}Addresses(const std::string& host,uint16_t port,bool passive){addrinfo hints{};hints.ai_family=AF_UNSPEC;hints.ai_socktype=SOCK_STREAM;hints.ai_flags=passive?AI_PASSIVE:0;const auto code=getaddrinfo(host.c_str(),std::to_string(port).c_str(),&hints,&values);if(code)throw ResolveError("address resolution failed: "+std::to_string(code));}};
void validate(const RoomTransportOptions& o){
    if(!o.identity.is_object()||!equivalent(o.identity.value("protocol",J{}),J(1)))throw std::invalid_argument("unsupported local protocol");
    for(const auto& [key,v]:o.identity.items())if(!(v.is_string()||v.is_number_integer())||v.is_boolean())throw std::invalid_argument("identity values must be strings or integers");
    if(o.identity.dump(-1,' ',true).size()>8192)throw std::invalid_argument("identity too large");
    if(o.room_code.size()>256)throw std::invalid_argument("room code must be text of at most 256 UTF-8 bytes");
    if(o.max_frame_bytes<1024||o.max_frame_bytes>16*1024*1024)throw std::invalid_argument("frame limit must be between 1 KiB and 16 MiB");
    for(const auto d:{o.heartbeat_interval,o.idle_timeout,o.handshake_timeout,o.reconnect_timeout,o.connect_timeout,o.reconnect_delay})if(!std::isfinite(d)||d<=0.)throw std::invalid_argument("timeouts must be positive finite numbers");
    if(o.idle_timeout<=o.heartbeat_interval)throw std::invalid_argument("idle timeout must exceed heartbeat interval");
    if(o.max_peers<1||o.max_peers>8||o.max_spectators<1||o.max_spectators>4)throw std::invalid_argument("invalid spectator or player policy");
    if(bool(o.session_id&&!o.session_id->empty())!=bool(o.token&&!o.token->empty()))throw std::invalid_argument("session ID and token must both be supplied as text");
}
}
RoomEndpoint parse_room_endpoint(std::string_view input,uint16_t port){
    std::string v(input);const auto space=[](unsigned char c){return std::isspace(c)!=0;};while(!v.empty()&&space(v.front()))v.erase(v.begin());while(!v.empty()&&space(v.back()))v.pop_back();
    if(v.empty()||std::any_of(v.begin(),v.end(),space)||v.find_first_of("/\\")!=std::string::npos)throw std::invalid_argument("invalid address; use hostname:port or [IPv6]:port");
    std::string host;bool ipv6=false;
    const auto parse_port=[&](std::string_view s){if(s.empty()||!std::all_of(s.begin(),s.end(),[](char c){return c>='0'&&c<='9';}))throw std::invalid_argument("port must be a number");uint64_t n=0;for(char c:s){n=n*10+(c-'0');if(n>65535)throw std::invalid_argument("port must be between 1 and 65535");}if(!n)throw std::invalid_argument("port must be between 1 and 65535");port=uint16_t(n);};
    if(v.front()=='['){auto end=v.find(']');if(end==std::string::npos)throw std::invalid_argument("IPv6 address is missing ]");host=v.substr(1,end-1);if(end+1<v.size()){if(v[end+1]!=':')throw std::invalid_argument("invalid port after IPv6 address");parse_port(std::string_view(v).substr(end+2));}ipv6=true;}
    else if(std::count(v.begin(),v.end(),':')==1){auto colon=v.find(':');host=v.substr(0,colon);parse_port(std::string_view(v).substr(colon+1));}else{host=v;ipv6=host.find(':')!=std::string::npos;}
    if(host.empty()||host.find_first_of("[]")!=std::string::npos)throw std::invalid_argument("invalid host");
    if(ipv6){const auto address=host.substr(0,host.find('%'));in6_addr binary{};if(inet_pton(AF_INET6,address.c_str(),&binary)!=1)throw std::invalid_argument("invalid IPv6 address");}
    if(!port)throw std::invalid_argument("port must be between 1 and 65535");return {host,port};
}

struct RoomTransport::Impl:std::enable_shared_from_this<RoomTransport::Impl>{
    struct Session;
    struct Connection {
        Socket socket;RoomFrameDecoder decoder;std::vector<uint8_t> output;double created,last_received,last_ping,rate_start,last_snapshot_request=0.;size_t rate_count=0;
        bool ready=false;std::string peer,close_reason;std::shared_ptr<Session> session;RoomLatencyBucket latency;
        Connection(Socket s,size_t maximum):socket(s),decoder(maximum),created(now()),last_received(created),last_ping(created),rate_start(created){}
        ~Connection(){close_socket(socket);}
    };
    struct Session {std::string peer,id,token;uint64_t in=0,out=0;std::weak_ptr<Connection> connection;std::optional<double> expires;bool spectator=false,initial_spectator=false,role_changed=false,relay_spectator=false;};
    enum class ControlKind{release,role,reject};
    struct Control{ControlKind kind;std::string peer,message;bool spectator=false;std::shared_ptr<std::promise<std::string>> completion;};
    RoomTransportOptions options;RoomEndpoint endpoint;bool server;RoomTransportQueues queues;
    std::atomic<size_t> max_peers;std::atomic<bool> allow_spectators,policy_changed=false;
    std::mutex wake_mutex,control_mutex,done_mutex;std::condition_variable done_cv;bool done=false,wake_pending=false;
    Socket wake_reader=invalid_socket,wake_writer=invalid_socket,listener=invalid_socket;
    std::deque<Control> releases,roles,rejections;
    std::map<Socket,std::shared_ptr<Connection>> connections;std::vector<std::shared_ptr<Session>> sessions;
    std::shared_ptr<Connection> client_connection;bool ever_connected=false,terminal_rejection=false;uint64_t client_in=0,client_out=0;
    explicit Impl(RoomEndpoint e,bool host,RoomTransportOptions o):options(std::move(o)),endpoint(std::move(e)),server(host),queues(options.max_frame_bytes),max_peers(options.max_peers),allow_spectators(options.allow_spectators){validate(options);}
    void start(){auto self=shared_from_this();std::thread([self]{self->run();}).detach();}
    void notify(){std::lock_guard lock(wake_mutex);if(wake_writer==invalid_socket||wake_pending)return;char byte=0;if(send_bytes(wake_writer,&byte,1)==1)wake_pending=true;}
    void open_wakeup(){
        SocketOwner acceptor{::socket(AF_INET,SOCK_STREAM,IPPROTO_TCP)};if(acceptor.value==invalid_socket)fail_socket("wakeup socket");sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);address.sin_port=0;
        if(bind(acceptor.value,reinterpret_cast<sockaddr*>(&address),sizeof(address))||listen(acceptor.value,1))fail_socket("wakeup bind");SockLen length=sizeof(address);if(getsockname(acceptor.value,reinterpret_cast<sockaddr*>(&address),&length))fail_socket("wakeup address");
        SocketOwner writer{::socket(AF_INET,SOCK_STREAM,IPPROTO_TCP)};if(writer.value==invalid_socket||connect(writer.value,reinterpret_cast<sockaddr*>(&address),sizeof(address)))fail_socket("wakeup connect");SocketOwner reader{accept(acceptor.value,nullptr,nullptr)};if(reader.value==invalid_socket)fail_socket("wakeup accept");nonblocking(reader.value);nonblocking(writer.value);
        std::lock_guard lock(wake_mutex);wake_reader=reader.release();wake_writer=writer.release();
    }
    void drain_wakeup(fd_set& readers){if(wake_reader==invalid_socket||!FD_ISSET(wake_reader,&readers))return;FD_CLR(wake_reader,&readers);std::lock_guard lock(wake_mutex);std::array<char,1024> buffer;while(recv(wake_reader,buffer.data(),int(buffer.size()),0)>0){}wake_pending=false;}
    void close_wakeup(){std::lock_guard lock(wake_mutex);close_socket(wake_reader);close_socket(wake_writer);wake_reader=wake_writer=invalid_socket;wake_pending=false;}
    void emit(J event){queues.emit(std::move(event));}
    void queue(Connection& c,const J& value){auto frame=encode_room_frame(value,options.max_frame_bytes);if(c.output.size()+frame.size()>options.max_frame_bytes*4)throw ProtocolError("send buffer full");c.output.insert(c.output.end(),frame.begin(),frame.end());queues.output(c.peer,c.output.size());}
    void write(Connection& c){if(c.output.empty())return;const auto sent=send_bytes(c.socket,c.output.data(),c.output.size());if(sent<0){if(would_block(socket_error()))throw WouldBlock{};fail_socket("send");}if(sent==0)throw std::runtime_error("socket write returned zero");c.output.erase(c.output.begin(),c.output.begin()+sent);queues.sent(size_t(sent));queues.output(c.peer,c.output.size());}
    void read(const std::shared_ptr<Connection>& c){std::array<char,65536> bytes;const auto received=recv(c->socket,bytes.data(),int(bytes.size()),0);if(received<0){if(would_block(socket_error()))throw WouldBlock{};fail_socket("recv");}if(!received)throw std::runtime_error("peer closed connection");
        std::vector<J> messages;try{messages=c->decoder.feed({reinterpret_cast<const uint8_t*>(bytes.data()),size_t(received)});}catch(const std::exception& e){throw ProtocolError(e.what());}
        queues.received(size_t(received),c->decoder.retained_bytes());
        for(const auto& message:messages){if(!c->close_reason.empty())break;const double t=now();if(t-c->rate_start>=1.){c->rate_start=t;c->rate_count=0;}if(++c->rate_count>1200)throw ProtocolError("message rate limit exceeded");c->last_received=t;if(server)server_frame(c,message);else client_frame(c,message);}
    }
    void heartbeat(Connection& c,double time){if(time-c.last_received>(c.ready?options.idle_timeout:options.handshake_timeout))throw TimeoutError(c.ready?"idle_timeout":"handshake_timeout");if(c.ready&&time-c.last_ping>=options.heartbeat_interval){queue(c,{{"type","ping"}});c.last_ping=time;}}
    bool control(Connection& c,const J& message){const auto type=message.value("type",J{});if(type=="ping"){queue(c,{{"type","pong"}});return true;}return type=="pong";}
    uint64_t data(Connection& c,const J& m,const std::string& peer,uint64_t previous,bool publish=true){
        if(m.value("type",J{})!="data"||!m.contains("payload")||!m["payload"].is_object())throw ProtocolError("expected data frame");const auto seq=sequence(m.value("seq",J{}),false);if(seq<=previous)return previous;if(seq!=previous+1)throw ProtocolError("sequence gap; authoritative resync required");
        const auto& payload=m["payload"];const auto type=payload.value("type",J{});if(type=="latency_probe"||type=="latency_echo")publish=publish&&c.latency.allow(payload,now());if(publish)emit({{"peer_id",peer},{"payload",payload},{"sequence",seq},{"type","message"}});return seq;
    }
    void reject(Connection& c,std::string code,std::string detail){queue(c,{{"type","reject"},{"code",code},{"detail",detail}});c.close_reason=std::move(code);}
    size_t role_count(bool spectator,const std::string& exclude={})const{size_t total=0;for(const auto& s:sessions)if(s->spectator==spectator&&s->peer!=exclude)++total;return total;}
    std::shared_ptr<Session> by_peer(const std::string& peer)const{for(const auto& s:sessions)if(s->peer==peer)return s;return {};}
    void server_frame(const std::shared_ptr<Connection>& c,const J& m){
        if(!c->ready){
            if(m.value("type",J{})!="hello")throw ProtocolError("first frame must be hello");
            if(!equivalent(m.value("protocol",J{}),J(1)))return reject(*c,"protocol_mismatch","transport protocol differs");
            const auto identity=m.value("identity",J{});
            if(!equivalent(identity,options.identity)){
                std::set<std::string> keys;for(const auto& [key,v]:options.identity.items())keys.insert(key);if(identity.is_object())for(const auto& [key,v]:identity.items())keys.insert(key);
                std::string detail="incompatible fields: ";bool first=true;for(const auto& key:keys)if(!identity.is_object()||!equivalent(identity.value(key,J{}),options.identity.value(key,J{}))){if(!first)detail+=", ";first=false;detail+=key;}return reject(*c,"identity_mismatch",detail);
            }
            const auto code=m.value("room_code",J(""));if(!code.is_string()||!same_secret(code.get_ref<const std::string&>(),options.room_code))return reject(*c,"room_code_invalid","room code differs");
            const auto sid=m.value("session_id",J{}),secret=m.value("token",J{}),role=m.value("spectator",J(false)),request=m.value("request_player",J(false));
            if(!role.is_boolean())return reject(*c,"invalid_role","invalid spectator role");if(!request.is_boolean())return reject(*c,"invalid_role","invalid seat request");bool spectator=role.get<bool>();const bool resumed=truth(sid),request_player=request.get<bool>();
            if(spectator&&!allow_spectators&&!resumed&&!request_player)return reject(*c,"spectators_disabled","host disabled spectators");
            std::shared_ptr<Session> session;
            if(resumed){
                if(sid.is_string())for(const auto& s:sessions)if(s->id==sid.get_ref<const std::string&>()){session=s;break;}
                if(!session||!secret.is_string()||!same_secret(secret.get_ref<const std::string&>(),session->token)||(session->expires&&now()>*session->expires))return reject(*c,"session_invalid","session expired or token differs");
                if(!session->connection.expired())return reject(*c,"session_in_use","session is already connected");
                if(session->spectator!=spectator&&!(session->role_changed&&session->initial_spectator==spectator))return reject(*c,"session_invalid","session role differs");
                spectator=session->spectator;if(spectator&&!allow_spectators)return reject(*c,"spectators_disabled","host disabled spectators");
            }else{
                if(request_player&&role_count(false)>=max_peers)return reject(*c,"room_full","player seats are full or reserved for reconnect");
                if(role_count(spectator)>=(spectator?options.max_spectators:max_peers.load()))return reject(*c,"room_full","room is full or reserved for reconnect");
                session=std::make_shared<Session>();session->id=token(18);session->token=token(32);session->peer=(spectator?"spectator-":"peer-")+token(6,true);session->spectator=session->initial_spectator=spectator;session->relay_spectator=m.value("relay_spectator",J{})==J(true);sessions.push_back(session);
            }
            c->session=session;c->peer=session->peer;c->ready=true;queues.role(c->peer,spectator);session->connection=c;session->expires.reset();
            queue(*c,{{"type","welcome"},{"protocol",1},{"identity",options.identity},{"peer_id",c->peer},{"session_id",session->id},{"token",session->token},{"receive_sequence",session->in},{"server_sequence",session->out},{"resumed",resumed},{"spectator",spectator}});queues.ready(c->peer,true);
            emit({{"peer_id",c->peer},{"session_id",session->id},{"resumed",resumed},{"require_full_snapshot",true},{"spectator",spectator},{"request_player",request_player},{"type",resumed?"reconnected":"connected"}});return;
        }
        if(control(*c,m))return;const auto payload=m.value("payload",J{});const bool spectator=c->session->spectator;bool allowed=!spectator;
        if(spectator&&payload.is_object()&&c->rate_count<=8){const auto kind=payload.value("type",J{});allowed=kind=="request_full_snapshot"||kind=="leave"||kind=="result_received"||kind=="role_change"||kind=="latency_probe"||kind=="latency_echo";if(allowed&&kind=="request_full_snapshot"){const double t=now();allowed=t-c->last_snapshot_request>=1.;if(allowed)c->last_snapshot_request=t;}}
        c->session->in=data(*c,m,c->peer,c->session->in,allowed);
    }
    void client_frame(const std::shared_ptr<Connection>& c,const J& m){
        if(!c->ready){
            if(m.value("type",J{})=="reject"){
                terminal_rejection=true;const auto code=m.value("code",J{});static const std::array allowed{"protocol_mismatch","identity_mismatch","room_code_invalid","session_invalid","session_in_use","room_full","spectators_disabled","invalid_role"};
                const auto safe=code.is_string()&&std::find(allowed.begin(),allowed.end(),code.get<std::string>())!=allowed.end()?code.get<std::string>():"handshake_rejected";
                emit({{"code",safe},{"detail",text_prefix(text(m.value("detail",J(""))),512)},{"type","error"}});throw ProtocolError("handshake_rejected");
            }
            if(m.value("type",J{})!="welcome"||!equivalent(m.value("protocol",J{}),J(1))||!equivalent(m.value("identity",J{}),options.identity))throw ProtocolError("invalid welcome or incompatible identity");
            for(const auto* key:{"peer_id","session_id","token"}){const auto value=m.value(key,J{});if(!value.is_string()||text_length(value.get_ref<const std::string&>())<1||text_length(value.get_ref<const std::string&>())>256)throw ProtocolError("invalid welcome credentials");}
            uint64_t out,in;try{out=sequence(m.value("receive_sequence",J{}),true);in=sequence(m.value("server_sequence",J{}),true);}catch(const ProtocolError&){throw ProtocolError("invalid welcome sequence");}
            const auto resumed=m.value("resumed",J{});if(!resumed.is_boolean())throw ProtocolError("invalid reconnect state");const auto spectator=m.value("spectator",J(false));if(!equivalent(spectator,J(options.spectator))&&!resumed.get<bool>())throw ProtocolError("server assigned an unexpected role");
            options.spectator=truth(spectator);options.session_id=m["session_id"].get<std::string>();options.token=m["token"].get<std::string>();client_out=out;client_in=in;c->ready=true;ever_connected=true;queues.ready("server",true);
            emit({{"peer_id","server"},{"assigned_peer_id",m["peer_id"]},{"session_id",m["session_id"]},{"token",m["token"]},{"resumed",resumed},{"require_full_snapshot",true},{"spectator",spectator},{"type",resumed.get<bool>()?"reconnected":"connected"}});return;
        }
        if(m.value("type",J{})=="role_changed"){const auto role=m.value("spectator",J{});if(!role.is_boolean())throw ProtocolError("invalid role change");options.spectator=role.get<bool>();emit({{"peer_id","server"},{"spectator",role},{"type","role_changed"}});return;}
        if(!control(*c,m))client_in=data(*c,m,"server",client_in);
    }
    void disconnect(const std::shared_ptr<Connection>& c,std::string reason,std::string detail={}){
        if(!connections.erase(c->socket))return;close_socket(c->socket);c->socket=invalid_socket;queues.output(c->peer,0);
        if(c->ready){queues.ready(c->peer,false);c->session->connection.reset();c->session->expires=now()+options.reconnect_timeout;emit({{"peer_id",c->peer},{"reason",reason},{"detail",detail},{"reconnect_seconds",options.reconnect_timeout},{"clear_continuous_input",!c->session->spectator},{"spectator",c->session->spectator},{"type","disconnected"}});}
    }
    bool enqueue_control(Control c){std::lock_guard lock(control_mutex);auto& q=c.kind==ControlKind::release?releases:c.kind==ControlKind::role?roles:rejections;if(q.size()>=256){queues.control_overflow();notify();return false;}q.push_back(std::move(c));queues.control_size(q.size());notify();return true;}
    std::deque<Control> take_control(ControlKind k){std::lock_guard lock(control_mutex);auto& q=k==ControlKind::release?releases:k==ControlKind::role?roles:rejections;std::deque<Control> out;out.swap(q);return out;}
    void controls(){
        for(auto& c:take_control(ControlKind::reject)){auto s=by_peer(c.peer);if(!s)continue;std::erase(sessions,s);queues.erase_peer(c.peer);if(auto conn=s->connection.lock()){queue(*conn,{{"type","data"},{"seq",++s->out},{"payload",{{"type","error"},{"message",c.message},{"terminal",true}}}});conn->close_reason="peer_left";}}
        for(auto& c:take_control(ControlKind::role)){auto s=by_peer(c.peer);std::string error;auto conn=s?s->connection.lock():nullptr;
            if(!conn)error="not_connected";else if(c.spectator&&!allow_spectators)error="spectators_disabled";else if(role_count(c.spectator,c.peer)>=(c.spectator?options.max_spectators:max_peers.load()))error="room_full";
            else{s->spectator=c.spectator;s->role_changed=true;queues.role(c.peer,c.spectator);queue(*conn,{{"type","role_changed"},{"spectator",c.spectator}});}if(c.completion)c.completion->set_value(error);
        }
        if(policy_changed.exchange(false)&&!allow_spectators){auto old=sessions;for(const auto& s:old)if(s->spectator){std::erase(sessions,s);queues.erase_peer(s->peer);if(auto conn=s->connection.lock())disconnect(conn,"spectators_disabled");}}
        for(auto& c:take_control(ControlKind::release)){auto s=by_peer(c.peer);if(s){std::erase(sessions,s);queues.erase_peer(s->peer);if(auto conn=s->connection.lock())disconnect(conn,"peer_left");}if(c.completion)c.completion->set_value(s?"true":"false");}
    }
    int select_ready(fd_set& readers,fd_set& writers,fd_set& errors,Socket largest){timeval interval{};interval.tv_usec=20000;const auto count=select(select_count(largest),&readers,&writers,&errors,&interval);if(count<0)fail_socket("select");drain_wakeup(readers);return count;}
    void listen_server(){
        Addresses candidates(endpoint.host,endpoint.port,true);std::string error="no listen address";
        for(auto* a=candidates.values;a;a=a->ai_next){SocketOwner sock{::socket(a->ai_family,a->ai_socktype,a->ai_protocol)};if(sock.value==invalid_socket)continue;try{int one=1;
#ifdef _WIN32
            if(setsockopt(sock.value,SOL_SOCKET,SO_EXCLUSIVEADDRUSE,reinterpret_cast<const char*>(&one),sizeof(one)))fail_socket("exclusive bind");
#else
            if(setsockopt(sock.value,SOL_SOCKET,SO_REUSEADDR,reinterpret_cast<const char*>(&one),sizeof(one)))fail_socket("reuse bind");
#endif
            if(a->ai_family==AF_INET6){int zero=0;setsockopt(sock.value,IPPROTO_IPV6,IPV6_V6ONLY,reinterpret_cast<const char*>(&zero),sizeof(zero));}
            if(bind(sock.value,a->ai_addr,SockLen(a->ai_addrlen))||listen(sock.value,8))fail_socket("listen");nonblocking(sock.value);listener=sock.release();break;
        }catch(const std::exception& e){error=e.what();}}
        if(listener==invalid_socket)throw std::runtime_error(error);
        sockaddr_storage address{};SockLen size=sizeof(address);if(getsockname(listener,reinterpret_cast<sockaddr*>(&address),&size))fail_socket("listen address");char host[NI_MAXHOST],service[NI_MAXSERV];if(getnameinfo(reinterpret_cast<sockaddr*>(&address),size,host,sizeof(host),service,sizeof(service),NI_NUMERICHOST|NI_NUMERICSERV))throw std::runtime_error("cannot format listen address");endpoint.port=uint16_t(std::stoul(service));
        J tuple=J::array({std::string(host),endpoint.port});if(address.ss_family==AF_INET6){const auto& v=*reinterpret_cast<const sockaddr_in6*>(&address);tuple.push_back(v.sin6_flowinfo);tuple.push_back(v.sin6_scope_id);}
        emit({{"address",tuple},{"port",endpoint.port},{"wildcard",std::string_view(host)=="::"||std::string_view(host)=="0.0.0.0"},{"type","listening"}});
        while(!queues.stopped){
            controls();const double t=now();auto prior=sessions;for(const auto& s:prior)if(s->expires&&t>*s->expires){std::erase(sessions,s);queues.erase_peer(s->peer);emit({{"peer_id",s->peer},{"type","session_expired"}});}
            for(auto& command:queues.take_commands()){
                auto s=by_peer(command.peer);auto c=s?s->connection.lock():nullptr;if(!c){emit({{"peer_id",command.peer},{"reason","disconnected"},{"type","send_dropped"}});continue;}
                try{queue(*c,{{"type","data"},{"seq",s->out+1},{"payload",std::move(command.payload)}});++s->out;}catch(const std::exception& e){disconnect(c,"backpressure",e.what());}
            }
            fd_set r,w,e;FD_ZERO(&r);FD_ZERO(&w);FD_ZERO(&e);FD_SET(listener,&r);FD_SET(wake_reader,&r);Socket largest=std::max(listener,wake_reader);
            for(const auto& [socket,c]:connections){FD_SET(socket,&r);FD_SET(socket,&e);if(!c->output.empty())FD_SET(socket,&w);largest=std::max(largest,socket);}select_ready(r,w,e,largest);
            if(FD_ISSET(listener,&r)){SocketOwner sock{accept(listener,nullptr,nullptr)};if(sock.value!=invalid_socket){nonblocking(sock.value);no_delay(sock.value);if(connections.size()<max_peers+options.max_spectators+4){auto value=sock.release();connections.emplace(value,std::make_shared<Connection>(value,options.max_frame_bytes));}}}
            auto current=connections;for(const auto& [socket,c]:current)if(connections.contains(socket)){
                try{if(FD_ISSET(socket,&e))throw std::runtime_error("socket exception");if(FD_ISSET(socket,&r))read(c);if(FD_ISSET(socket,&w))write(*c);if(!c->close_reason.empty()&&c->output.empty())disconnect(c,c->close_reason);}
                catch(const WouldBlock&){}catch(const ProtocolError& ex){disconnect(c,"protocol_error",ex.what());}catch(const std::exception& ex){disconnect(c,"connection_lost",ex.what());}
            }
            current=connections;for(const auto& [socket,c]:current)try{heartbeat(*c,now());}catch(const std::exception& ex){disconnect(c,ex.what());}
        }
    }
    std::shared_ptr<Connection> connect_client(std::optional<double> remaining){
        emit({{"type",ever_connected?"reconnecting":"connecting"}});const double deadline=now()+std::min(options.connect_timeout,remaining.value_or(options.connect_timeout));Addresses addresses(endpoint.host,endpoint.port,false);std::string error="no connection address";
        for(auto* a=addresses.values;a;a=a->ai_next){SocketOwner sock{::socket(a->ai_family,a->ai_socktype,a->ai_protocol)};if(sock.value==invalid_socket)continue;
            try{nonblocking(sock.value);const auto result=connect(sock.value,a->ai_addr,SockLen(a->ai_addrlen));if(result&& !pending_error(socket_error()))fail_socket("connect");
                while(!queues.stopped&&now()<deadline){fd_set r,w,e;FD_ZERO(&r);FD_ZERO(&w);FD_ZERO(&e);FD_SET(wake_reader,&r);FD_SET(sock.value,&w);FD_SET(sock.value,&e);select_ready(r,w,e,std::max(wake_reader,sock.value));
                    if(FD_ISSET(sock.value,&w)||FD_ISSET(sock.value,&e)){int code=0;SockLen n=sizeof(code);if(getsockopt(sock.value,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&code),&n)||code)throw std::runtime_error("connection refused or address unreachable: "+std::to_string(code));no_delay(sock.value);auto c=std::make_shared<Connection>(sock.release(),options.max_frame_bytes);c->peer="server";return c;}}
                throw TimeoutError("connect_timeout");
            }catch(const TimeoutError&){throw;}catch(const std::exception& ex){error=ex.what();if(queues.stopped||now()>=deadline)break;}
        }throw std::runtime_error(error);
    }
    void run_connection(const std::shared_ptr<Connection>& c){
        emit({{"type","handshaking"}});queue(*c,{{"type","hello"},{"protocol",1},{"identity",options.identity},{"room_code",options.room_code},{"session_id",options.session_id?J(*options.session_id):J(nullptr)},{"token",options.token?J(*options.token):J(nullptr)},{"spectator",options.relay_spectator||options.spectator},{"relay_spectator",options.relay_spectator},{"request_player",options.request_player}});
        while(!queues.stopped){
            for(auto& command:queues.take_commands()){if(!c->ready){emit({{"peer_id","server"},{"reason","resync_required"},{"type","send_dropped"}});continue;}queue(*c,{{"type","data"},{"seq",client_out+1},{"payload",std::move(command.payload)}});++client_out;}
            fd_set r,w,e;FD_ZERO(&r);FD_ZERO(&w);FD_ZERO(&e);FD_SET(c->socket,&r);FD_SET(wake_reader,&r);FD_SET(c->socket,&e);if(!c->output.empty())FD_SET(c->socket,&w);select_ready(r,w,e,std::max(c->socket,wake_reader));
            try{if(FD_ISSET(c->socket,&e))throw std::runtime_error("socket exception");if(FD_ISSET(c->socket,&r))read(c);if(FD_ISSET(c->socket,&w))write(*c);}catch(const WouldBlock&){}heartbeat(*c,now());
        }
    }
    void client_loop(){
        std::optional<double> reconnect_deadline;
        while(!queues.stopped){bool was_connected=false;
            try{const auto remaining=reconnect_deadline?std::optional<double>(*reconnect_deadline-now()):std::nullopt;if(remaining&&*remaining<=0.)break;client_connection=connect_client(remaining);run_connection(client_connection);}
            catch(const std::exception& ex){was_connected=client_connection&&client_connection->ready;if(!queues.stopped&&!terminal_rejection){
                if(was_connected)emit({{"peer_id","server"},{"reason",dynamic_cast<const ProtocolError*>(&ex)?"protocol_error":dynamic_cast<const TimeoutError*>(&ex)?"idle_timeout":"connection_lost"},{"detail",ex.what()},{"clear_continuous_input",true},{"reconnect_seconds",options.reconnect_timeout},{"type","disconnected"}});
                else if(!ever_connected)emit({{"code",dynamic_cast<const ResolveError*>(&ex)?"address_resolution_failed":dynamic_cast<const TimeoutError*>(&ex)?"connect_timeout":dynamic_cast<const ProtocolError*>(&ex)?"protocol_error":"connection_failed"},{"detail",ex.what()},{"type","error"}});
            }}
            queues.ready("server",false);client_connection.reset();queues.output("server",0);queues.discard_commands();
            if(queues.stopped||terminal_rejection||!ever_connected)break;if(was_connected||!reconnect_deadline)reconnect_deadline=now()+options.reconnect_timeout;if(now()>=*reconnect_deadline)break;
            const double until=now()+std::min(options.reconnect_delay,std::max(0.,*reconnect_deadline-now()));while(!queues.stopped&&now()<until){fd_set r,w,e;FD_ZERO(&r);FD_ZERO(&w);FD_ZERO(&e);FD_SET(wake_reader,&r);select_ready(r,w,e,wake_reader);}
        }
        if(reconnect_deadline&&!queues.stopped&&!terminal_rejection)emit({{"code","reconnect_expired"},{"detail","reconnect window elapsed"},{"type","error"}});
    }
    void run(){
        try{initialize_sockets();open_wakeup();if(server)listen_server();else client_loop();}
        catch(const std::exception& ex){emit({{"type","error"},{"code",server&&listener==invalid_socket?"listen_failed":"transport_error"},{"detail",ex.what()}});}
        if(server){auto prior=connections;for(const auto& [socket,c]:prior)disconnect(c,"local_close");close_socket(listener);listener=invalid_socket;}else{queues.ready("server",false);client_connection.reset();}
        queues.stopped=true;close_wakeup();emit({{"reason",server?"local_close":terminal_rejection?"rejected":"cancelled"},{"type","closed"}});
        {std::lock_guard lock(done_mutex);done=true;}done_cv.notify_all();
    }
    void close(){queues.close();notify();std::unique_lock lock(done_mutex);done_cv.wait_for(lock,std::chrono::milliseconds(200),[&]{return done;});}
};
RoomTransport RoomTransport::server(std::string host,uint16_t port,RoomTransportOptions options){if(host.empty())throw std::invalid_argument("listen host must be text");auto impl=std::make_shared<Impl>(RoomEndpoint{std::move(host),port},true,std::move(options));impl->start();return RoomTransport(impl);}
RoomTransport RoomTransport::client(RoomEndpoint endpoint,RoomTransportOptions options){if(endpoint.host.empty()||!endpoint.port)throw std::invalid_argument("invalid connection endpoint");auto impl=std::make_shared<Impl>(std::move(endpoint),false,std::move(options));impl->start();return RoomTransport(impl);}
RoomTransport& RoomTransport::operator=(RoomTransport&& other)noexcept{if(this!=&other){close();impl_=std::move(other.impl_);}return *this;}
RoomTransport::~RoomTransport(){close();}
bool RoomTransport::send(const std::string& peer,const WireObject& value,std::optional<uint64_t> generation){const bool ok=impl_->queues.send(peer,value,generation);if(ok)impl_->notify();return ok;}
bool RoomTransport::send_spectator(const std::string& peer,const WireObject& value,bool full){const bool ok=impl_->queues.spectator(peer,value,full);if(ok)impl_->notify();return ok;}
std::vector<WireObject> RoomTransport::poll(size_t limit){return impl_->queues.poll(limit);}
uint64_t RoomTransport::generation(const std::string& peer)const{return impl_->queues.generation(peer);}
size_t RoomTransport::pending_bytes(const std::string& peer)const{return impl_->queues.pending(peer);}
WireObject RoomTransport::statistics()const{return impl_->queues.statistics();}
void RoomTransport::set_max_peers(size_t count){if(count<1||count>8)throw std::invalid_argument("max_peers must be between 1 and 8");impl_->max_peers=count;}
void RoomTransport::set_allow_spectators(bool value){impl_->allow_spectators=value;impl_->policy_changed=true;impl_->notify();}
std::string RoomTransport::set_peer_role(const std::string& peer,bool spectator){auto done=std::make_shared<std::promise<std::string>>();auto result=done->get_future();if(!impl_->enqueue_control({Impl::ControlKind::role,peer,{},spectator,done}))return "control_queue_full";return result.wait_for(std::chrono::seconds(1))==std::future_status::ready?result.get():"not_connected";}
bool RoomTransport::release_peer(const std::string& peer){const bool spectator=impl_->queues.is_spectator(peer);auto done=std::make_shared<std::promise<std::string>>();auto result=done->get_future();if(!impl_->enqueue_control({Impl::ControlKind::release,peer,{},false,done}))return false;if(spectator)return true;return result.wait_for(std::chrono::seconds(1))==std::future_status::ready&&result.get()=="true";}
bool RoomTransport::reject_peer(const std::string& peer,std::string message){return impl_->enqueue_control({Impl::ControlKind::reject,peer,text_prefix(message,512),false,{}});}
void RoomTransport::close(){if(impl_)impl_->close();}
} // namespace pvz::typed72
