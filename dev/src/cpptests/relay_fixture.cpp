#include "cpptests/gen/pm_baseline61_art_fixture.h"
// Test-only: the REAL Python relay server, out of process, for native client tests (decision 2026-11-02:
// the relay server stays a Python product; its implementation tests stay in the Python suite).
//
//   importlib.util.module_from_spec(<.../server/relay_server.py>) -> a module whose RelayServer(port=0, **opts)
//   starts tools/relay_fixture_server.py (unmodified relay_server.py on its own asyncio loop) and talks to it
//   over a JSON-lines pipe. Every client under test (RelayHostTransport, RelayClientTransport, LobbyQuery,
//   the App) is the translated native C++ code connecting over real TCP.
//
// Exposed: port, config[...] (get/set), rooms (code -> host/guest/allow_spectators/spectator_lanes, host lane
// abort, clear), snapshot(), connections' write-buffer limits. NOT exposed (explicit NotImplementedError,
// counted as not covered here): arbitrary server method replacements and mocking server modules
// (server_module.secrets) - those are server-implementation tests.
//
// asyncio here is only the thin loop LocalRelay drives (new_event_loop / run_forever / stop / close /
// call_soon_threadsafe / run_coroutine_threadsafe). It runs no coroutines of the product.
#include "cpptests/registry.h"
#include "pg/pg.h"
#include "core/gil.h"
#include <condition_variable>
#include <cstdlib>
#include <cstdio>
#include <mutex>
#include <string>
#ifdef _WIN32
#include <windows.h>
#endif

namespace pvz::cpptests {
namespace {

V not_here(const std::string& what) {
    throw PyError("NotImplementedError", "relay server internals stay in the Python server suite: " + what);
}

std::wstring widen(const std::string& s) {
#ifdef _WIN32
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0);
    std::wstring w(size_t(n), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), w.data(), n);
    return w;
#else
    return std::wstring(s.begin(), s.end());
#endif
}

V json_dumps(const V& v) { return py::stdlib_call(V("json.dumps"), Args{v}); }
V json_loads(const std::string& s) { return py::stdlib_call(V("json.loads"), Args{V(s)}); }

struct RelayProcess {
#ifdef _WIN32
    HANDLE proc = nullptr, to_child = nullptr, from_child = nullptr;
#endif
    std::string pending;
    std::mutex io;
    bool closed = false;

    void spawn(const V& options) {
#ifdef _WIN32
        const char* py = std::getenv("PVZ_TEST_PYTHON");
        const char* script = std::getenv("PVZ_RELAY_FIXTURE");
        const char* root = std::getenv("PVZ_TEST_ROOT");
        if (!py || !script || !root) throw PyError("RuntimeError", "relay fixture needs PVZ_TEST_PYTHON, PVZ_RELAY_FIXTURE and PVZ_TEST_ROOT (set by tools/run_cpp_suite.py)");
        std::string server = std::string(root) + "/server/relay_server.py";
        std::string opts = json_dumps(options).str();
        std::string q;   // options JSON as one quoted argument
        for (char c : opts) { if (c == '"') q += "\\\""; else q += c; }
        std::string cmd = "\"" + std::string(py) + "\" -I \"" + script + "\" \"" + server + "\" \"" + q + "\"";
        SECURITY_ATTRIBUTES sa{sizeof(sa), nullptr, TRUE};
        HANDLE in_r, in_w, out_r, out_w;
        if (!CreatePipe(&in_r, &in_w, &sa, 0) || !CreatePipe(&out_r, &out_w, &sa, 0)) throw PyError("OSError", "relay fixture pipe");
        SetHandleInformation(in_w, HANDLE_FLAG_INHERIT, 0);
        SetHandleInformation(out_r, HANDLE_FLAG_INHERIT, 0);
        STARTUPINFOW si{}; si.cb = sizeof(si); si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdInput = in_r; si.hStdOutput = out_w; si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
        PROCESS_INFORMATION pi{};
        std::wstring wcmd = widen(cmd);
        BOOL ok = CreateProcessW(nullptr, wcmd.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi);
        CloseHandle(in_r); CloseHandle(out_w);
        if (!ok) { CloseHandle(in_w); CloseHandle(out_r); throw PyError("OSError", "cannot start relay fixture: " + cmd); }
        CloseHandle(pi.hThread);
        proc = pi.hProcess; to_child = in_w; from_child = out_r;
#else
        (void)options;
        throw PyError("NotImplementedError", "relay fixture process is only wired on Windows");
#endif
    }
    std::string read_line() {
#ifdef _WIN32
        for (;;) {
            size_t nl = pending.find('\n');
            if (nl != std::string::npos) { std::string line = pending.substr(0, nl); pending.erase(0, nl + 1); return line; }
            char buf[4096]; DWORD got = 0;
            BOOL ok;
            { gil::Release unlocked; ok = ReadFile(from_child, buf, sizeof buf, &got, nullptr); }
            if (!ok || got == 0) throw PyError("RuntimeError", "relay fixture process exited");
            pending.append(buf, got);
        }
#else
        return {};
#endif
    }
    V request(const V& cmd);
    V send(const V& cmd) {
        std::lock_guard<std::mutex> lock(io);
        if (closed) throw PyError("RuntimeError", "relay fixture already closed");
#ifdef _WIN32
        std::string line = json_dumps(cmd).str() + "\n";
        DWORD put = 0;
        if (!WriteFile(to_child, line.data(), DWORD(line.size()), &put, nullptr)) throw PyError("RuntimeError", "relay fixture pipe closed");
#endif
        V r = json_loads(read_line());
        if (!r.get(V("ok"), V(false)).truthy()) throw PyError("RuntimeError", "relay fixture: " + py_str(r.get(V("error"), V("?"))));
        return r.get(V("value"), V::none());
    }
    double wait_ready() {
        std::lock_guard<std::mutex> lock(io);
        V r = json_loads(read_line());
        if (!r.get(V("ready"), V(false)).truthy()) throw PyError("RuntimeError", "relay fixture did not start");
        return r.get(V("port"), V(0.0)).num();
    }
    void shutdown() {
        if (closed) return;
        try { request(py_dict({{V("op"), V("close")}})); } catch (const PyError&) {}
        closed = true;
#ifdef _WIN32
        if (to_child) { CloseHandle(to_child); to_child = nullptr; }
        if (proc) { { gil::Release unlocked; if (WaitForSingleObject(proc, 5000) != WAIT_OBJECT_0) TerminateProcess(proc, 1); } CloseHandle(proc); proc = nullptr; }
        if (from_child) { CloseHandle(from_child); from_child = nullptr; }
#endif
    }
    ~RelayProcess() { try { shutdown(); } catch (...) {} }
};
using Proc = std::shared_ptr<RelayProcess>;

// writes made inside one loop.call_soon_threadsafe callback reach the server as ONE batch, applied in one
// server loop callback - the original test callbacks (abort the host lanes, then clear the registry) are atomic
struct Batch { std::vector<std::pair<RelayProcess*, V>> ops; };
thread_local Batch* t_batch = nullptr;
V RelayProcess::request(const V& cmd) {
    std::string o = cmd.get(V("op"), V("")).str();
    if (t_batch && (o == "abort_host" || o == "clear_rooms" || o == "config_set")) { t_batch->ops.emplace_back(this, cmd); return V::none(); }
    return send(cmd);
}
void flush(Batch& b) {
    for (size_t i = 0; i < b.ops.size();) {
        RelayProcess* p = b.ops[i].first;
        V ops = V::list();
        for (; i < b.ops.size() && b.ops[i].first == p; ++i) ops.append(b.ops[i].second);
        p->send(py_dict({{V("op"), V("batch")}, {V("ops"), ops}}));
    }
}

V op(const char* name, std::initializer_list<std::pair<const char*, V>> extra = {}) {
    V d = py_dict({{V("op"), V(name)}});
    for (auto& p : extra) d.at(V(p.first)) = p.second;
    return d;
}

// a finished awaitable: run_coroutine_threadsafe executes it on the calling thread
struct Coro : PyObj {
    std::function<V()> body;
    const char* type_name() const override { return "coroutine"; }
};
V coro(std::function<V()> f) { auto c = std::make_shared<Coro>(); c->body = std::move(f); return V::inst(c); }

struct TransportProxy : PyObj {
    Proc p; std::string code;
    const char* type_name() const override { return "Transport"; }
    V method(Sym n) override {
        if (n == Sym("abort")) { Proc pp = p; std::string c = code; return V::func([pp, c](const Args&) { pp->request(op("abort_host", {{"code", V(c)}})); return V::none(); }); }
        return V();
    }
};
struct WriterProxy : PyObj {
    Proc p; std::string code;
    const char* type_name() const override { return "StreamWriter"; }
    V property(Sym n, bool& found) override {
        found = n == Sym("transport");
        if (!found) return V();
        auto t = std::make_shared<TransportProxy>(); t->p = p; t->code = code; return V::inst(t);
    }
};
struct RoomProxy : PyObj {
    Proc p; std::string code;
    const char* type_name() const override { return "Room"; }
    V view() {
        V rooms = p->request(op("rooms"));
        const V* r = rooms.find(V(code));
        if (!r) throw PyError("KeyError", code);
        return *r;
    }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& s = n.str();
        if (s == "code") return V(code);
        if (s == "host" || s == "guest") {
            if (!view().get(V(s), V(false)).truthy()) return V::none();
            if (s == "guest") return not_here("guest lane objects");
            auto w = std::make_shared<WriterProxy>(); w->p = p; w->code = code;
            return V::tuple({V::none(), V::inst(w)});
        }
        if (s == "allow_spectators" || s == "public" || s == "active") return view().get(V(s), V::none());
        if (s == "spectator_lanes") {
            V out = V::dict();
            for (auto& kv : view().get(V("spectator_lanes"), V::dict()).kv()) {
                V lane = py::new_object();
                pvz::setattr(lane, Sym("guest"), kv.second.get(V("guest"), V(false)).truthy() ? V(true) : V::none());
                out.at(py::int_(V(std::stod(kv.first.str())))) = lane;
            }
            return out;
        }
        found = false;
        return not_here("room." + s);
    }
};
struct RoomsProxy : PyObj {
    Proc p;
    const char* type_name() const override { return "dict"; }
    V room(const std::string& c) { auto r = std::make_shared<RoomProxy>(); r->p = p; r->code = c; return V::inst(r); }
    V getitem(const V& key) override {
        V rooms = p->request(op("rooms"));
        if (!rooms.find(key)) throw PyError("KeyError", py_str(key));
        return room(key.str());
    }
    bool contains(const V& key) override { return p->request(op("rooms")).find(key) != nullptr; }
    size_t length() override { return p->request(op("rooms")).kv().size(); }
    V iterate() override { V out = V::list(); for (auto& kv : p->request(op("rooms")).kv()) out.append(kv.first); return out; }
    V method(Sym n) override {
        auto self = std::static_pointer_cast<RoomsProxy>(shared_from_this());
        if (n == Sym("values")) return V::func([self](const Args&) { V r = self->p->request(op("rooms")); V out = V::list(); for (auto& kv : r.kv()) out.append(self->room(kv.first.str())); return out; });
        if (n == Sym("keys")) return V::func([self](const Args&) { return self->iterate(); });
        if (n == Sym("clear")) return V::func([self](const Args&) { self->p->request(op("clear_rooms")); return V::none(); });
        return V();
    }
};
struct ConfigProxy : PyObj {
    Proc p;
    const char* type_name() const override { return "dict"; }
    V getitem(const V& key) override { return p->request(op("config_get", {{"key", key}})); }
    void setitem(const V& key, const V& value) override { p->request(op("config_set", {{"key", key}, {"value", value}})); }
};

struct OriginalAsyncFixture : PyObj {
    Proc process;V descriptor;
    const char* type_name()const override{return "OriginalRelayAsyncFixture";}
    V call_self(const Args& args)override {
        if(!args.pos.empty() || !args.kw.empty())return not_here("calling server.send in the native process");
        Proc held=process;V request=py::copy(descriptor);request.at(V("op"))=V("fixture_call");
        return coro([held,request]{return held->request(request);});
    }
};
struct ServerProxy : PyObj {
    Proc p = std::make_shared<RelayProcess>();
    V options; double port = 0;
    const char* type_name() const override { return "RelayServer"; }
    V property(Sym n, bool& found) override {
        found = true;
        const std::string& s = n.str();
        if (s == "port") return V(port);
        if (s == "config") { auto c = std::make_shared<ConfigProxy>(); c->p = p; return V::inst(c); }
        if (s == "rooms") { auto r = std::make_shared<RoomsProxy>(); r->p = p; return V::inst(r); }
        if (s == "connections") {
            V out = V::list();
            for (auto& row : py::iter_list(p->request(op("connections"))).items()) {
                V transport = py::new_object();
                V limits = V::tuple(py::iter_list(row.get(V("limits"), V::list())).items());
                pvz::setattr(transport, Sym("get_write_buffer_limits"), V::func([limits](const Args&) { return limits; }));
                V ms = row.get(V("max_size"), V::none());
                if (!ms.is_none()) pvz::setattr(transport, Sym("max_size"), ms);
                V writer = py::new_object();
                pvz::setattr(writer, Sym("transport"), transport);
                out.append(writer);
            }
            return out;
        }
        found = false;
        if (s == "start" || s == "close" || s == "snapshot" || s == "send") return V();   // methods below
        return not_here("server." + s);
    }
    bool set_property(Sym name,const V& value)override {
        if(name==Sym("send"))if(auto* fixture=as<OriginalAsyncFixture>(value)) {
            if(fixture->process!=p || fixture->descriptor.get(V("fixture")).str().find(":legacy_send")==std::string::npos)throw PyError("ValueError","server fixture owner mismatch");
            V request=py::copy(fixture->descriptor);request.at(V("op"))=V("fixture_install");p->request(request);return true;
        }
        not_here("replacing server."+name.str());return false;
    }
    V method(Sym n) override {
        auto self = std::static_pointer_cast<ServerProxy>(shared_from_this());
        if (n == Sym("start")) return V::func([self](const Args&) {
            return coro([self] { self->p->spawn(self->options); self->port = self->p->wait_ready(); return V::inst(self); });
        });
        if (n == Sym("close")) return V::func([self](const Args&) { return coro([self] { self->p->shutdown(); return V::none(); }); });
        if (n == Sym("snapshot")) return V::func([self](const Args&) { return self->p->request(op("snapshot")); });
        if(n==Sym("send")){V function=V::func([](const Args&)->V{return not_here("server.send");});function.box->fattrs.emplace_back(Sym("__relay_server_owner__"),V::inst(self));return function;}
        return V();
    }
};

struct LoopObj : PyObj {
    std::mutex m; std::condition_variable cv; bool stopped = false;
    const char* type_name() const override { return "EventLoop"; }
    V method(Sym n) override {
        auto self = std::static_pointer_cast<LoopObj>(shared_from_this());
        if (n == Sym("run_forever")) return V::func([self](const Args&) {
            gil::Release unlocked;
            std::unique_lock<std::mutex> lk(self->m);
            self->cv.wait(lk, [&] { return self->stopped; });
            return V::none();
        });
        if (n == Sym("stop")) return V::func([self](const Args&) { { std::lock_guard<std::mutex> lk(self->m); self->stopped = true; } self->cv.notify_all(); return V::none(); });
        if (n == Sym("close")) return V::func([](const Args&) { return V::none(); });
        if (n == Sym("is_running")) return V::func([self](const Args&) { std::lock_guard<std::mutex> lk(self->m); return V(!self->stopped); });
        // the callback runs on the calling thread under the GIL; the fixture server serialises its own work
        if (n == Sym("call_soon_threadsafe")) return V::func([](const Args& a) {
            Args rest; for (size_t i = 1; i < a.pos.size(); ++i) rest.pos.push_back(a.pos[i]);
            Batch b; Batch* outer = t_batch; t_batch = &b;
            try { a.pos.at(0).call(rest); } catch (...) { t_batch = outer; throw; }
            t_batch = outer;
            flush(b);
            return V::none();
        });
        return V();
    }
};

V run_coroutine_threadsafe(const Args& a) {
    V c = a.pos.at(0);
    V value = c;   // a translated `async def` already returned its value when called
    if (c.is_inst()) if (auto* co = dynamic_cast<Coro*>(c.box->inst.get())) value = co->body();
    V fut = py::new_object();
    pvz::setattr(fut, Sym("result"), V::func([value](const Args&) { return value; }));
    pvz::setattr(fut, Sym("done"), V::func([](const Args&) { return V(true); }));
    return fut;
}

}  // namespace

void install_relay_fixture() {
    py::register_native_hook("test.relay_async_fixture",[](const Args& args){
        if(args.pos.size()!=4)throw PyError("TypeError","original relay fixture needs identity, AST/source fingerprints and server owner");
        V capture=args.pos[3],owner=pvz::getattr(capture,Sym("__relay_server_owner__"),V());
        if(!owner.has())owner=pvz::getattr(capture,Sym("server"));
        auto* server=as<ServerProxy>(owner);if(!server)throw PyError("TypeError","original relay fixture must bind a real relay process");
        auto fixture=std::make_shared<OriginalAsyncFixture>();fixture->process=server->p;
        fixture->descriptor=py_dict({{V("fixture"),args.pos[0]},{V("ast_sha256"),args.pos[1]},{V("source_sha256"),args.pos[2]}});return V::inst(fixture);
    });

    V asyncio = pg::new_module("asyncio");
    pg::module_of(asyncio)->fn("new_event_loop", [](const Args&) { return V::inst(std::make_shared<LoopObj>()); });
    pg::module_of(asyncio)->fn("run_coroutine_threadsafe", run_coroutine_threadsafe);
    py::register_module("asyncio", asyncio);
    py::register_native_hook("importlib.file_module", [](const Args& a) -> V {
        std::string origin = a.pos.at(0).str();
        for (auto& c : origin) if (c == '\\') c = '/';
        static const std::string old_art="/pvp61-art/baseline-assets.py";
        if(origin.size()>=old_art.size() && origin.compare(origin.size()-old_art.size(),old_art.size(),old_art)==0) {
            V path=py::stdlib_call(V("pathlib.Path"),Args{V(origin)}),bytes=callm(path,Sym("read_bytes"),Args{});
            V sha=callm(py::stdlib_call(V("hashlib.sha256"),Args{bytes}),Sym("hexdigest"),Args{});
            if(sha!=V("02915675c68a934c18b8471f0cd64379f8f58ba6b52473ec21018b856eadacdf"))throw PyError("RuntimeError","Original historical art fixture fingerprint mismatch");
            return pm_baseline61_art_fixture::module_ns();
        }
        static const std::string want = "/server/relay_server.py";
        if (origin.size() < want.size() || origin.compare(origin.size() - want.size(), want.size(), want) != 0) return V::none();
        V m = pg::new_module("relay_server");
        pg::module_of(m)->fn("RelayServer", [](const Args& a) {
            auto s = std::make_shared<ServerProxy>();
            V opts = V::dict();
            for (auto& kw : a.kw) if (kw.first != Sym("port")) opts.at(V(kw.first)) = kw.second;
            s->options = opts;
            return V::inst(s);
        });
        pg::module_of(m)->add("secrets", pg::new_module("relay_server.secrets (server internals: Python suite)"));
        return m;
    });
}
}  // namespace pvz::cpptests
