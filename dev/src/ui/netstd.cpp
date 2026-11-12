// threading / queue / socket / select for the translated network code (network.py, relay.py).
//
// Transports run on real background threads, as in python, serialized by the GIL (core/gil.h): every
// blocking primitive here releases it. Threads that would only burn CPU without ever blocking (the AI
// draft "think" thread) keep running synchronously on start(), since there is no preemptive switch.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/pyops.h"
#include "sim/pvp/pvprt.h"
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
static inline int sock_nonblock(SOCKET s, bool nb) { u_long v = nb ? 1 : 0; return ioctlsocket(s, FIONBIO, &v); }
static inline int select_nfds(int) { return 0; }
#else   // POSIX (Android / Linux): winsock names over BSD sockets
#include <arpa/inet.h>
#include <cerrno>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define closesocket ::close
#define WSAGetLastError() errno
#define WSAEWOULDBLOCK EWOULDBLOCK
#define WSAEINPROGRESS EINPROGRESS
#define WSAEALREADY EALREADY
#define WSAECONNRESET ECONNRESET
#define WSAECONNREFUSED ECONNREFUSED
#define WSAECONNABORTED ECONNABORTED
#define WSAETIMEDOUT ETIMEDOUT
#define WSAESHUTDOWN EPIPE
#define WSAEADDRINUSE EADDRINUSE
#define WSAEACCES EACCES
#define WSAENOTCONN ENOTCONN
#define WSAEHOSTUNREACH EHOSTUNREACH
#define WSAENETUNREACH ENETUNREACH
#define SD_RECEIVE SHUT_RD
#define SD_SEND SHUT_WR
#define SD_BOTH SHUT_RDWR
static inline int sock_nonblock(SOCKET s, bool nb) { int f = fcntl(s, F_GETFL, 0); return fcntl(s, F_SETFL, nb ? (f | O_NONBLOCK) : (f & ~O_NONBLOCK)); }
static inline int select_nfds(int maxfd) { return maxfd + 1; }
#endif
#include <atomic>
#include <chrono>
#include <cstdio>
#include <deque>
#include <mutex>
#include <thread>

namespace pvz::pg {
namespace {

using clk = std::chrono::steady_clock;
V mod(const char* name) { return new_module(name); }
Module* M(const V& m) { return module_of(m); }
double num_or(const Args& a, size_t i, const char* kw, double dflt) {
    if (a.pos.size() > i && !a.pos[i].is_none()) return a.pos[i].num();
    for (auto& [k, v] : a.kw) if (k.str() == kw) return v.is_none() ? dflt : v.num();
    return dflt;
}
bool bool_or(const Args& a, size_t i, const char* kw, bool dflt) {
    if (a.pos.size() > i) return a.pos[i].truthy();
    for (auto& [k, v] : a.kw) if (k.str() == kw) return v.truthy();
    return dflt;
}
const V* kwarg(const Args& a, const char* kw) {
    for (auto& [k, v] : a.kw) if (k.str() == kw) return &v;
    return nullptr;
}
template <class T>
V bound(const std::shared_ptr<T>& sp, Sym name) {
    return V::func([sp, name](const Args& a) {
        V out;
        if (!sp->call_method(name, a, out)) throw PyError("AttributeError", std::string(sp->type_name()) + "." + name.str());
        return out;
    });
}
void sleep_released(double seconds) {
    gil::Release r;
    std::this_thread::sleep_for(std::chrono::duration<double>(std::max(0.0, seconds)));
}

// ------------------------------------------------------------------ threading
thread_local std::string t_thread_name = "MainThread";
struct LockObj : PyObj {
    std::timed_mutex m;
    bool reentrant = false;
    std::thread::id owner;
    int count = 0;
    std::atomic<bool> held{false};
    const char* type_name() const override { return reentrant ? "RLock" : "lock"; }
    bool acquire(bool blocking, double timeout) {
        auto me = std::this_thread::get_id();
        if (reentrant && held && owner == me) { ++count; return true; }
        bool ok = m.try_lock();
        if (!ok && blocking) {
            gil::Release r;
            if (timeout < 0) {
                if (getenv("PVZ_NETDBG") && !m.try_lock_for(std::chrono::seconds(1))) { fprintf(stderr, "NETDBG %s waits >1s for a lock\n", t_thread_name.c_str()); m.lock(); }
                else if (!getenv("PVZ_NETDBG")) m.lock();
                ok = true;
            }
            else ok = m.try_lock_for(std::chrono::duration<double>(timeout));
        }
        if (ok) { owner = me; count = 1; held = true; }
        return ok;
    }
    void release() {
        if (!held) throw PyError("RuntimeError", "release unlocked lock");
        if (reentrant && --count > 0) return;
        held = false; owner = std::thread::id(); count = 0;
        m.unlock();
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "acquire" || n == "__enter__") {
            out = V(acquire(n == "__enter__" ? true : bool_or(a, 0, "blocking", true), n == "__enter__" ? -1 : num_or(a, 1, "timeout", -1)));
            return true;
        }
        if (n == "release") { release(); out = V::none(); return true; }
        if (n == "__exit__") { release(); out = V(false); return true; }
        if (n == "locked") { out = V(held.load()); return true; }
        return false;
    }
    V method(Sym name) override { return bound(std::static_pointer_cast<LockObj>(shared_from_this()), name); }
};
V make_lock(bool reentrant) { auto l = std::make_shared<LockObj>(); l->reentrant = reentrant; return V::inst(l); }

struct EventObj : PyObj {
    std::atomic<bool> flag{false};
    const char* type_name() const override { return "Event"; }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "set") { flag = true; out = V::none(); return true; }
        if (n == "clear") { flag = false; out = V::none(); return true; }
        if (n == "is_set" || n == "isSet") { out = V(flag.load()); return true; }
        if (n == "wait") {
            double timeout = num_or(a, 0, "timeout", -1);
            if (!flag) {
                gil::Release r;
                auto end = clk::now() + std::chrono::duration_cast<clk::duration>(std::chrono::duration<double>(timeout < 0 ? 1e9 : timeout));
                while (!flag && clk::now() < end) std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            out = V(flag.load());
            return true;
        }
        return false;
    }
    V method(Sym name) override { return bound(std::static_pointer_cast<EventObj>(shared_from_this()), name); }
};


struct ThreadObj : PyObj {
    V target, args, kwargs;
    std::string name = "Thread";
    bool daemon = false, started = false;
    std::atomic<bool> alive{false};
    const char* type_name() const override { return "Thread"; }
    bool real() const {
        // PVZ_REAL_THREADS=1 (set by the old-suite runner): every thread is a real OS thread, as in CPython -
        // test code starts its own consumer / event-loop threads that must not run inline in start()
        static const bool all_real = [] { const char* e = getenv("PVZ_REAL_THREADS"); return e && *e == '1'; }();
        if (all_real && name != "PvP-room-draft") return true;
        if (name.rfind("pvp-pack-worker-", 0) == 0) return true;
        return name.rfind("PvP-", 0) == 0 && !(name == "PvP-room-draft" && getenv("PVZ_SYNC_DRAFT"));   // incl. AI think: the GIL switch interval keeps the UI live
    }
    void run_target() {
        Args b;
        if (args.has() && !args.is_none()) for (auto& x : py::iter_list(args).items()) b.pos.push_back(x);
        if (kwargs.has() && kwargs.is_dict()) for (auto& kv : kwargs.kv()) b.kw.emplace_back(Sym(kv.first.str()), kv.second);
        target.call(b);
    }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& s = n.str();
        if (s == "name") return V(name);
        if (s == "daemon") return V(daemon);
        if (s == "ident") return started ? V(double(reinterpret_cast<uintptr_t>(this) & 0xffffffff)) : V::none();
        found = false;
        return V();
    }
    bool set_property(Sym n, const V& v) override {
        if (n.str() == "daemon") { daemon = v.truthy(); return true; }
        if (n.str() == "name") { name = py_str(v); return true; }
        return false;
    }
    bool call_method(Sym nm, const Args& a, V& out) override {
        const std::string& n = nm.str();
        if (n == "start") {
            if (started) throw PyError("RuntimeError", "threads can only be started once");
            started = true;
            out = V::none();
            if (!target.has() || target.is_none()) return true;
            if (!real() || !gil::active()) {   // synchronous (see header)
                alive = true;
                try { run_target(); } catch (...) { alive = false; throw; }
                alive = false;
                return true;
            }
            alive = true;
            auto sp = std::static_pointer_cast<ThreadObj>(shared_from_this());
            auto* holder = new std::shared_ptr<ThreadObj>(sp);   // dropped under the GIL at thread end
            std::thread([holder] {
                gil::acquire();
                {
                    std::shared_ptr<ThreadObj> self = *holder;
                    delete holder;
                    t_thread_name = self->name;
                    try { self->run_target(); }
                    catch (PyError& e) { fprintf(stderr, "Exception in thread %s: %s\n", self->name.c_str(), e.what()); }
                    catch (std::exception& e) { fprintf(stderr, "Exception in thread %s: %s\n", self->name.c_str(), e.what()); }
                    self->alive = false;
                }
                gil::release();
            }).detach();
            return true;
        }
        if (n == "is_alive" || n == "isAlive") { out = V(alive.load()); return true; }
        if (n == "join") {
            double timeout = num_or(a, 0, "timeout", -1);
            if (alive) {
                gil::Release r;
                auto end = clk::now() + std::chrono::duration_cast<clk::duration>(std::chrono::duration<double>(timeout < 0 ? 1e9 : timeout));
                while (alive && clk::now() < end) std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            out = V::none();
            return true;
        }
        if (n == "getName") { out = V(name); return true; }
        if (n == "setDaemon") { daemon = a.pos.at(0).truthy(); out = V::none(); return true; }
        return false;
    }
    V method(Sym name) override { return bound(std::static_pointer_cast<ThreadObj>(shared_from_this()), name); }
};

V threading_module() {
    V m = mod("threading");
    M(m)->fn("Lock", [](const Args&) { return make_lock(false); });
    M(m)->fn("RLock", [](const Args&) { return make_lock(true); });
    M(m)->fn("Event", [](const Args&) { return V::inst(std::make_shared<EventObj>()); });
    M(m)->fn("Thread", [](const Args& a) {
        auto t = std::make_shared<ThreadObj>();
        if (const V* v = kwarg(a, "target")) t->target = *v; else if (a.pos.size() > 1) t->target = a.pos[1];
        if (const V* v = kwarg(a, "name")) { if (!v->is_none()) t->name = py_str(*v); }
        if (const V* v = kwarg(a, "args")) t->args = *v;
        if (const V* v = kwarg(a, "kwargs")) t->kwargs = *v;
        if (const V* v = kwarg(a, "daemon")) t->daemon = v->truthy();
        return V::inst(t);
    });
    M(m)->fn("current_thread", [](const Args&) {
        V t = mod("Thread");
        M(t)->add("name", V(t_thread_name));
        M(t)->add("daemon", V(t_thread_name != "MainThread"));
        return t;
    });
    M(m)->fn("main_thread", [](const Args&) { V t = mod("Thread"); M(t)->add("name", V("MainThread")); return t; });
    M(m)->fn("get_ident", [](const Args&) { return V(double(std::hash<std::thread::id>()(std::this_thread::get_id()) & 0xffffffffffull)); });
    M(m)->fn("active_count", [](const Args&) { return V(1.0); });
    return m;
}

// ------------------------------------------------------------------ queue
struct QueueObj : PyObj {
    V items = V::list();
    V mutex = make_lock(false);
    int maxsize = 0;
    int unfinished = 0;
    const char* type_name() const override { return "Queue"; }
    V property(Sym n, bool& found) override {
        found = true;
        if (n.str() == "queue") return items;
        if (n.str() == "mutex") return mutex;
        if (n.str() == "maxsize") return V(double(maxsize));
        found = false;
        return V();
    }
    bool full() const { return maxsize > 0 && int(items.len()) >= maxsize; }
    template <class Ready>
    bool wait_for(bool block, double timeout, Ready ready) {
        if (ready()) return true;
        if (!block) return false;
        auto end = clk::now() + std::chrono::duration_cast<clk::duration>(std::chrono::duration<double>(timeout < 0 ? 1e9 : timeout));
        while (clk::now() < end) {
            sleep_released(0.001);
            if (ready()) return true;
        }
        return false;
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "put" || n == "put_nowait") {
            bool block = n == "put" && bool_or(a, 1, "block", true);
            if (!wait_for(block, num_or(a, 2, "timeout", -1), [&] { return !full(); })) throw PyError("Full", "queue full", {"Exception"});
            items.append(a.pos.at(0));
            ++unfinished;
            out = V::none();
            return true;
        }
        if (n == "get" || n == "get_nowait") {
            bool block = n == "get" && bool_or(a, 0, "block", true);
            if (!wait_for(block, num_or(a, 1, "timeout", -1), [&] { return items.len() > 0; })) throw PyError("Empty", "queue empty", {"Exception"});
            auto& it = items.items();
            V v = it.front();
            it.erase(it.begin());
            out = v;
            return true;
        }
        if (n == "qsize") { out = V(double(items.len())); return true; }
        if (n == "empty") { out = V(items.len() == 0); return true; }
        if (n == "full") { out = V(full()); return true; }
        if (n == "task_done") { if (unfinished > 0) --unfinished; out = V::none(); return true; }
        if (n == "join") { wait_for(true, -1, [&] { return unfinished == 0; }); out = V::none(); return true; }
        return false;
    }
    V method(Sym name) override { return bound(std::static_pointer_cast<QueueObj>(shared_from_this()), name); }
};

V queue_module() {
    V m = mod("queue");
    M(m)->fn("Queue", [](const Args& a) {
        auto q = std::make_shared<QueueObj>();
        q->maxsize = int(num_or(a, 0, "maxsize", 0));
        return V::inst(q);
    });
    M(m)->add("Empty", py::exc_type(V("Empty")));
    M(m)->add("Full", py::exc_type(V("Full")));
    return m;
}

// ------------------------------------------------------------------ socket
void wsa_init() {
#ifdef _WIN32
    static bool done = [] { WSADATA d; WSAStartup(MAKEWORD(2, 2), &d); return true; }();
#else
    static bool done = true;
#endif
    (void)done;
}
[[noreturn]] void raise_wsa(int code, const char* what) {
    const char* text = "socket error";
    switch (code) {
        case WSAEWOULDBLOCK: text = "A non-blocking socket operation could not be completed immediately"; break;
        case WSAECONNRESET: text = "An existing connection was forcibly closed by the remote host"; break;
        case WSAECONNREFUSED: text = "No connection could be made because the target machine actively refused it"; break;
        case WSAECONNABORTED: text = "An established connection was aborted by the software in your host machine"; break;
        case WSAETIMEDOUT: text = "A connection attempt failed because the connected party did not properly respond"; break;
        case WSAEADDRINUSE: text = "Only one usage of each socket address is normally permitted"; break;
        case WSAEACCES: text = "An attempt was made to access a socket in a way forbidden by its access permissions"; break;
        case WSAENOTCONN: text = "A request to send or receive data was disallowed because the socket is not connected"; break;
        case WSAEHOSTUNREACH: case WSAENETUNREACH: text = "A socket operation was attempted to an unreachable host"; break;
        default: break;
    }
    std::string msg = "[WinError " + std::to_string(code) + "] " + text;
    (void)what;
    const char* kind = "OSError";
    switch (code) {
        case WSAEWOULDBLOCK: case WSAEINPROGRESS: case WSAEALREADY: kind = "BlockingIOError"; break;
        case WSAECONNRESET: kind = "ConnectionResetError"; break;
        case WSAECONNREFUSED: kind = "ConnectionRefusedError"; break;
        case WSAECONNABORTED: kind = "ConnectionAbortedError"; break;
        case WSAETIMEDOUT: kind = "TimeoutError"; break;
        case WSAESHUTDOWN: kind = "BrokenPipeError"; break;
        default: break;
    }
    throw PyError(kind, msg);
}

V sockaddr_v(const sockaddr* sa) {
    char host[INET6_ADDRSTRLEN] = {0};
    if (sa->sa_family == AF_INET6) {
        auto* s6 = reinterpret_cast<const sockaddr_in6*>(sa);
        inet_ntop(AF_INET6, &s6->sin6_addr, host, sizeof host);
        return V::tuple({V(std::string(host)), V(double(ntohs(s6->sin6_port))), V(double(ntohl(s6->sin6_flowinfo))), V(double(s6->sin6_scope_id))});
    }
    auto* s4 = reinterpret_cast<const sockaddr_in*>(sa);
    inet_ntop(AF_INET, &s4->sin_addr, host, sizeof host);
    return V::tuple({V(std::string(host)), V(double(ntohs(s4->sin_port)))});
}
// (host, port[, flow, scope]) -> sockaddr for the socket's family
int sockaddr_of(const V& addr, int family, sockaddr_storage& out) {
    memset(&out, 0, sizeof out);
    std::string host = addr.idx(0).is_none() ? std::string() : py_str(addr.idx(0));
    int port = int(addr.idx(1).num());
    if (host == "<broadcast>") host = "255.255.255.255";
    if (family == AF_INET6) {
        auto* s6 = reinterpret_cast<sockaddr_in6*>(&out);
        s6->sin6_family = AF_INET6;
        s6->sin6_port = htons(uint16_t(port));
        if (host.empty()) s6->sin6_addr = in6addr_any;
        else if (inet_pton(AF_INET6, host.c_str(), &s6->sin6_addr) != 1) {
            addrinfo hints{}, *res = nullptr; hints.ai_family = AF_INET6;
            if (getaddrinfo(host.c_str(), nullptr, &hints, &res) != 0 || !res) throw PyError("gaierror", "address " + host);
            s6->sin6_addr = reinterpret_cast<sockaddr_in6*>(res->ai_addr)->sin6_addr;
            freeaddrinfo(res);
        }
        if (addr.len() > 3) s6->sin6_scope_id = uint32_t(addr.idx(3).num());
        return int(sizeof(sockaddr_in6));
    }
    auto* s4 = reinterpret_cast<sockaddr_in*>(&out);
    s4->sin_family = AF_INET;
    s4->sin_port = htons(uint16_t(port));
    if (host.empty()) s4->sin_addr.s_addr = INADDR_ANY;
    else if (inet_pton(AF_INET, host.c_str(), &s4->sin_addr) != 1) {
        addrinfo hints{}, *res = nullptr; hints.ai_family = AF_INET;
        if (getaddrinfo(host.c_str(), nullptr, &hints, &res) != 0 || !res) throw PyError("gaierror", "address " + host);
        s4->sin_addr = reinterpret_cast<sockaddr_in*>(res->ai_addr)->sin_addr;
        freeaddrinfo(res);
    }
    return int(sizeof(sockaddr_in));
}

struct SockObj : PyObj {
    SOCKET s = INVALID_SOCKET;
    int family = AF_INET, type = SOCK_STREAM, proto = 0;
    double timeout = -1;   // <0 blocking, 0 non-blocking, >0 timeout mode
    const char* type_name() const override { return "socket"; }
    ~SockObj() override { if (s != INVALID_SOCKET) closesocket(s); }
    void set_os_blocking(bool blocking) { sock_nonblock(s, !blocking); }
    void apply_timeout(double t) { timeout = t; set_os_blocking(t < 0); }
    void check() const { if (s == INVALID_SOCKET) throw PyError("OSError", "[WinError 10038] bad file descriptor"); }
    // timeout mode: wait for readiness (GIL released) or raise socket.timeout
    void wait_ready(bool write) {
        if (timeout <= 0) return;
        fd_set fs; FD_ZERO(&fs); FD_SET(s, &fs);
        timeval tv{long(timeout), long((timeout - long(timeout)) * 1e6)};
        int r;
        { gil::Release g; r = ::select(select_nfds(int(s)), write ? nullptr : &fs, write ? &fs : nullptr, nullptr, &tv); }
        if (r == 0) throw PyError("timeout", "timed out");
        if (r < 0) raise_wsa(WSAGetLastError(), "select");
    }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& k = n.str();
        if (k == "family") return V(double(family));
        if (k == "type") return V(double(type));
        if (k == "proto") return V(double(proto));
        found = false;
        return V();
    }
    bool call_method(Sym name, const Args& a, V& out) override;
    V method(Sym name) override { return bound(std::static_pointer_cast<SockObj>(shared_from_this()), name); }
};

V new_socket(int family, int type, int proto) {
    wsa_init();
    auto o = std::make_shared<SockObj>();
    o->family = family; o->type = type; o->proto = proto;
    o->s = ::socket(family, type, proto);
    if (o->s == INVALID_SOCKET) raise_wsa(WSAGetLastError(), "socket");
    return V::inst(o);
}
SockObj* sock_of(const V& v) { return as<SockObj>(v); }

bool SockObj::call_method(Sym name, const Args& a, V& out) {
    const std::string& n = name.str();
    if (n == "close") { if (s != INVALID_SOCKET) { closesocket(s); s = INVALID_SOCKET; } out = V::none(); return true; }
    if (n == "fileno") { out = V(s == INVALID_SOCKET ? -1.0 : double(s)); return true; }
    if (n == "__enter__") { out = self(); return true; }
    if (n == "__exit__") { if (s != INVALID_SOCKET) { closesocket(s); s = INVALID_SOCKET; } out = V(false); return true; }
    check();
    if (n == "setblocking") { apply_timeout(a.pos.at(0).truthy() ? -1 : 0); out = V::none(); return true; }
    if (n == "settimeout") { apply_timeout(a.pos.at(0).is_none() ? -1 : a.pos[0].num()); out = V::none(); return true; }
    if (n == "gettimeout") { out = timeout < 0 ? V::none() : V(timeout); return true; }
    if (n == "getblocking") { out = V(timeout != 0); return true; }
    if (n == "setsockopt") {
        int level = int(a.pos.at(0).num()), opt = int(a.pos.at(1).num());
        int v = a.pos.at(2).t == V::BOOL ? int(a.pos[2].b) : int(a.pos[2].num());
        if (setsockopt(s, level, opt, reinterpret_cast<const char*>(&v), sizeof v) != 0) raise_wsa(WSAGetLastError(), "setsockopt");
        out = V::none(); return true;
    }
    if (n == "getsockopt") {
        int v = 0; socklen_t len = sizeof v;
        if (getsockopt(s, int(a.pos.at(0).num()), int(a.pos.at(1).num()), reinterpret_cast<char*>(&v), &len) != 0) raise_wsa(WSAGetLastError(), "getsockopt");
        out = V(double(v)); return true;
    }
    if (n == "bind") {
        sockaddr_storage ss; int len = sockaddr_of(a.pos.at(0), family, ss);
        if (::bind(s, reinterpret_cast<sockaddr*>(&ss), len) != 0) raise_wsa(WSAGetLastError(), "bind");
        out = V::none(); return true;
    }
    if (n == "listen") { if (::listen(s, a.pos.empty() ? SOMAXCONN : int(a.pos[0].num())) != 0) raise_wsa(WSAGetLastError(), "listen"); out = V::none(); return true; }
    if (n == "getsockname" || n == "getpeername") {
        sockaddr_storage ss; socklen_t len = sizeof ss;
        int r = n == "getsockname" ? getsockname(s, reinterpret_cast<sockaddr*>(&ss), &len) : getpeername(s, reinterpret_cast<sockaddr*>(&ss), &len);
        if (r != 0) raise_wsa(WSAGetLastError(), n.c_str());
        out = sockaddr_v(reinterpret_cast<sockaddr*>(&ss)); return true;
    }
    if (n == "accept") {
        wait_ready(false);
        sockaddr_storage ss; socklen_t len = sizeof ss;
        SOCKET c;
        if (timeout < 0) { gil::Release g; c = ::accept(s, reinterpret_cast<sockaddr*>(&ss), &len); }
        else c = ::accept(s, reinterpret_cast<sockaddr*>(&ss), &len);
        if (c == INVALID_SOCKET) raise_wsa(WSAGetLastError(), "accept");
        auto o = std::make_shared<SockObj>();
        o->s = c; o->family = family; o->type = type; o->proto = proto;
        o->apply_timeout(-1);   // python: accepted sockets follow the default timeout (blocking)
        out = V::tuple({V::inst(o), sockaddr_v(reinterpret_cast<sockaddr*>(&ss))});
        return true;
    }
    if (n == "connect" || n == "connect_ex") {
        sockaddr_storage ss; int len = sockaddr_of(a.pos.at(0), family, ss);
        int r;
        if (timeout < 0) { gil::Release g; r = ::connect(s, reinterpret_cast<sockaddr*>(&ss), len); }
        else r = ::connect(s, reinterpret_cast<sockaddr*>(&ss), len);
        int err = r == 0 ? 0 : WSAGetLastError();
        if ((err == WSAEWOULDBLOCK || err == WSAEINPROGRESS) && timeout > 0) {   // timeout mode: wait for the connect to finish
            fd_set w, x; FD_ZERO(&w); FD_ZERO(&x); FD_SET(s, &w); FD_SET(s, &x);
            timeval tv{long(timeout), long((timeout - long(timeout)) * 1e6)};
            int k;
            { gil::Release g; k = ::select(select_nfds(int(s)), nullptr, &w, &x, &tv); }
            if (k == 0) { if (n == "connect") throw PyError("timeout", "timed out"); out = V(double(WSAETIMEDOUT)); return true; }
            int e = 0; socklen_t el = sizeof e;
            getsockopt(s, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&e), &el);
            err = e;
        }
        if (n == "connect_ex") { out = V(double(err)); return true; }
        if (err) raise_wsa(err, "connect");
        out = V::none(); return true;
    }
    if (n == "recv") {
        int k = int(a.pos.at(0).num());
        std::string buf(size_t(std::max(1, k)), '\0');
        wait_ready(false);
        int r;
        if (timeout < 0) { gil::Release g; r = ::recv(s, &buf[0], k, 0); }
        else r = ::recv(s, &buf[0], k, 0);
        if (r < 0) raise_wsa(WSAGetLastError(), "recv");
        buf.resize(size_t(r));
        if (getenv("PVZ_NETDBG") && s != INVALID_SOCKET && r > 1) fprintf(stderr, "NETIO %s %lld recv %d\n", t_thread_name.c_str(), (long long)std::chrono::duration_cast<std::chrono::milliseconds>(clk::now().time_since_epoch()).count() % 1000000, r);
        out = V::bytes(buf); return true;
    }
    if (n == "send" || n == "sendall") {
        std::string data = py::bytes_data(a.pos.at(0));
        size_t sent = 0;
        do {
            wait_ready(true);
            int r;
            if (timeout < 0) { gil::Release g; r = ::send(s, data.data() + sent, int(data.size() - sent), 0); }
            else r = ::send(s, data.data() + sent, int(data.size() - sent), 0);
            if (r < 0) {
                int e = WSAGetLastError();
                if (n == "sendall" && e == WSAEWOULDBLOCK && timeout == 0) { sleep_released(0.001); continue; }
                raise_wsa(e, "send");
            }
            sent += size_t(r);
            if (getenv("PVZ_NETDBG") && r > 1) fprintf(stderr, "NETIO %s %lld send %d\n", t_thread_name.c_str(), (long long)std::chrono::duration_cast<std::chrono::milliseconds>(clk::now().time_since_epoch()).count() % 1000000, r);
        } while (n == "sendall" && sent < data.size());
        out = n == "sendall" ? V::none() : V(double(sent)); return true;
    }
    if (n == "shutdown") { ::shutdown(s, int(a.pos.at(0).num())); out = V::none(); return true; }
    return false;
}

V getaddrinfo_v(const Args& a) {
    wsa_init();
    V hostv = a.pos.at(0), portv = a.pos.size() > 1 ? a.pos[1] : V::none();
    addrinfo hints{};
    hints.ai_family = int(num_or(a, 2, "family", AF_UNSPEC));
    hints.ai_socktype = int(num_or(a, 3, "type", 0));
    hints.ai_protocol = int(num_or(a, 4, "proto", 0));
    hints.ai_flags = int(num_or(a, 5, "flags", 0));
    std::string host = hostv.is_none() ? std::string() : py_str(hostv);
    std::string port = portv.is_none() ? std::string() : (portv.t == V::STR ? portv.str() : std::to_string(int64_t(portv.num())));
    addrinfo* res = nullptr;
    int r;
    { gil::Release g; r = ::getaddrinfo(host.empty() ? nullptr : host.c_str(), port.empty() ? nullptr : port.c_str(), &hints, &res); }
    if (r != 0) throw PyError("gaierror", "[Errno " + std::to_string(r) + "] getaddrinfo failed");
    std::vector<V> out;
    for (addrinfo* p = res; p; p = p->ai_next)
        out.push_back(V::tuple({V(double(p->ai_family)), V(double(p->ai_socktype)), V(double(p->ai_protocol)),
                                V(std::string(p->ai_canonname ? p->ai_canonname : "")), sockaddr_v(p->ai_addr)}));
    freeaddrinfo(res);
    return V::list(out);
}

V create_connection_v(const Args& a) {
    V addr = a.pos.at(0);
    double timeout = num_or(a, 1, "timeout", -1);
    V infos = getaddrinfo_v(Args{addr.idx(0), addr.idx(1), V(double(AF_UNSPEC)), V(double(SOCK_STREAM))});
    std::string last = "getaddrinfo returns an empty list";
    for (auto& info : infos.items()) {
        V sv = new_socket(int(info.idx(0).num()), int(info.idx(1).num()), int(info.idx(2).num()));
        SockObj* so = sock_of(sv);
        try {
            so->apply_timeout(timeout);
            V r; so->call_method(Sym("connect"), Args{info.idx(4)}, r);
            return sv;
        } catch (PyError& e) {
            last = e.what();
            V ignored; so->call_method(Sym("close"), Args{}, ignored);
        }
    }
    throw PyError("OSError", last);
}

V socketpair_v() {
    V lst = new_socket(AF_INET, SOCK_STREAM, 0);
    SockObj* l = sock_of(lst);
    V r;
    l->call_method(Sym("bind"), Args{V::tuple({V("127.0.0.1"), V(0.0)})}, r);
    l->call_method(Sym("listen"), Args{V(1.0)}, r);
    V name; l->call_method(Sym("getsockname"), Args{}, name);
    V a = new_socket(AF_INET, SOCK_STREAM, 0);
    sock_of(a)->call_method(Sym("connect"), Args{name}, r);
    V acc; l->call_method(Sym("accept"), Args{}, acc);
    l->call_method(Sym("close"), Args{}, r);
    return V::tuple({acc.idx(0), a});
}

V socket_module() {
    wsa_init();
    V m = mod("socket");
    Module* d = M(m);
    SOCKET ipv6=::socket(AF_INET6,SOCK_STREAM,IPPROTO_TCP);
    const bool has_ipv6=ipv6!=INVALID_SOCKET;
    if(has_ipv6)closesocket(ipv6);
    d->add("has_ipv6",V(has_ipv6));
    d->fn("socket", [](const Args& a) {
        return new_socket(int(num_or(a, 0, "family", AF_INET)), int(num_or(a, 1, "type", SOCK_STREAM)), int(num_or(a, 2, "proto", 0)));
    });
    d->fn("socketpair", [](const Args&) { return socketpair_v(); });
    d->fn("getaddrinfo", getaddrinfo_v);
    d->fn("create_connection", create_connection_v);
    d->fn("gethostname", [](const Args&) { wsa_init(); char b[256] = {0}; gethostname(b, sizeof b); return V(std::string(b)); });
    d->fn("inet_pton", [](const Args& a) {
        wsa_init();
        int fam = int(a.pos.at(0).num());
        unsigned char buf[16];
        if (inet_pton(fam, py_str(a.pos.at(1)).c_str(), buf) != 1) throw PyError("OSError", "illegal IP address string passed to inet_pton");
        return V(std::string(reinterpret_cast<char*>(buf), fam == AF_INET6 ? 16 : 4));
    });
    d->fn("inet_ntop", [](const Args& a) {
        int fam = int(a.pos.at(0).num());
        std::string raw = a.pos.at(1).str();
        char host[INET6_ADDRSTRLEN] = {0};
        inet_ntop(fam, raw.data(), host, sizeof host);
        return V(std::string(host));
    });
    d->fn("getdefaulttimeout", [](const Args&) { return V::none(); });
    d->fn("setdefaulttimeout", [](const Args&) { return V::none(); });
    auto k = [&](const char* name, double v) { d->add(name, V(v)); };
    k("AF_INET", AF_INET); k("AF_INET6", AF_INET6); k("AF_UNSPEC", AF_UNSPEC);
    k("SOCK_STREAM", SOCK_STREAM); k("SOCK_DGRAM", SOCK_DGRAM);
    k("AI_PASSIVE", AI_PASSIVE); k("AI_NUMERICHOST", AI_NUMERICHOST);
    k("SOL_SOCKET", SOL_SOCKET); k("SO_REUSEADDR", SO_REUSEADDR);
#ifdef _WIN32
    k("SO_EXCLUSIVEADDRUSE", double(SO_EXCLUSIVEADDRUSE));
#endif
    k("SO_ERROR", SO_ERROR); k("SO_KEEPALIVE", SO_KEEPALIVE); k("SO_BROADCAST", SO_BROADCAST);
    k("SO_RCVBUF", SO_RCVBUF); k("SO_SNDBUF", SO_SNDBUF);
    k("IPPROTO_TCP", IPPROTO_TCP); k("IPPROTO_UDP", IPPROTO_UDP); k("TCP_NODELAY", TCP_NODELAY);
    k("IPPROTO_IPV6", IPPROTO_IPV6); k("IPV6_V6ONLY", IPV6_V6ONLY);
    k("SHUT_RD", SD_RECEIVE); k("SHUT_WR", SD_SEND); k("SHUT_RDWR", SD_BOTH);
    d->add("error", py::exc_type(V("OSError")));
    d->add("gaierror", py::exc_type(V("gaierror")));
    d->add("herror", py::exc_type(V("herror")));
    d->add("timeout", py::exc_type(V("timeout")));
    return m;
}

V select_module() {
    V m = mod("select");
    M(m)->fn("select", [](const Args& a) {
        V lists[3] = {a.pos.at(0), a.pos.at(1), a.pos.at(2)};
        double timeout = a.pos.size() > 3 && !a.pos[3].is_none() ? a.pos[3].num() : -1;
        fd_set sets[3];
        bool any = false;
        int maxfd = 0;
        size_t counts[3] = {0, 0, 0};
        std::vector<V> items[3];
        for (int i = 0; i < 3; ++i) {
            FD_ZERO(&sets[i]);
            for (auto& v : py::iter_list(lists[i]).items()) {
                SockObj* so = sock_of(v);
                if (!so || so->s == INVALID_SOCKET) continue;
                items[i].push_back(v);
                if (counts[i] < FD_SETSIZE) { FD_SET(so->s, &sets[i]); ++counts[i]; any = true; maxfd = std::max(maxfd, int(so->s)); }
            }
        }
        if (!any) {   // windows select rejects three empty sets
            if (timeout > 0) sleep_released(timeout);
            return V::tuple({V::list(), V::list(), V::list()});
        }
        timeval tv{long(std::max(0.0, timeout)), long((std::max(0.0, timeout) - long(std::max(0.0, timeout))) * 1e6)};
        int r;
        { gil::Release g; r = ::select(select_nfds(maxfd), &sets[0], &sets[1], &sets[2], timeout < 0 ? nullptr : &tv); }
        if (getenv("PVZ_NETDBG")) {
            static thread_local int calls = 0; static thread_local clk::time_point last = clk::now();
            ++calls;
            if (clk::now() - last > std::chrono::seconds(2)) { fprintf(stderr, "NETDBG %s selects=%d r=%d n=%d/%d/%d\n", t_thread_name.c_str(), calls, r, int(items[0].size()), int(items[1].size()), int(items[2].size())); calls = 0; last = clk::now(); }
        }
        if (r < 0) raise_wsa(WSAGetLastError(), "select");
        std::vector<V> out[3];
        for (int i = 0; i < 3; ++i)
            for (auto& v : items[i]) if (FD_ISSET(sock_of(v)->s, &sets[i])) out[i].push_back(v);
        return V::tuple({V::list(out[0]), V::list(out[1]), V::list(out[2])});
    });
    M(m)->add("error", py::exc_type(V("OSError")));
    return m;
}

// ------------------------------------------------------------------ ipaddress (classification only)
V ipaddress_module() {
    V m = mod("ipaddress");
    M(m)->fn("ip_address", [](const Args& a) {
        wsa_init();
        std::string s = py_str(a.pos.at(0));
        unsigned char b[16] = {0};
        V o = mod("IPAddress");
        Module* d = M(o);
        if (inet_pton(AF_INET, s.c_str(), b) == 1) {
            bool loop = b[0] == 127, unspec = !b[0] && !b[1] && !b[2] && !b[3];
            bool link = b[0] == 169 && b[1] == 254;
            bool priv = b[0] == 10 || (b[0] == 172 && (b[1] & 0xF0) == 16) || (b[0] == 192 && b[1] == 168) || loop || link || unspec;
            d->add("version", V(4.0)); d->add("is_loopback", V(loop)); d->add("is_unspecified", V(unspec));
            d->add("is_link_local", V(link)); d->add("is_private", V(priv)); d->add("is_global", V(!priv));
            d->add("is_multicast", V(b[0] >= 224 && b[0] <= 239));
        } else if (inet_pton(AF_INET6, s.c_str(), b) == 1) {
            bool zero = true; for (int i = 0; i < 16; ++i) zero = zero && !b[i];
            bool loop = true; for (int i = 0; i < 15; ++i) loop = loop && !b[i]; loop = loop && b[15] == 1;
            bool link = b[0] == 0xfe && (b[1] & 0xC0) == 0x80;
            bool ula = (b[0] & 0xFE) == 0xfc;
            d->add("version", V(6.0)); d->add("is_loopback", V(loop)); d->add("is_unspecified", V(zero));
            d->add("is_link_local", V(link)); d->add("is_private", V(ula || loop || link || zero)); d->add("is_global", V(!(ula || loop || link || zero)));
            d->add("is_multicast", V(b[0] == 0xff));
        } else {
            throw PyError("ValueError", "'" + s + "' does not appear to be an IPv4 or IPv6 address");
        }
        d->add("compressed", V(s));
        d->fn("__str__", [s](const Args&) { return V(s); });
        return o;
    });
    return m;
}

}  // namespace

void install_netstd() {
    py::register_module("ipaddress", ipaddress_module());
    py::register_module("threading", threading_module());
    py::register_module("queue", queue_module());
    py::register_module("socket", socket_module());
    py::register_module("select", select_module());
}

}  // namespace pvz::pg
