// Standard-library/native module adapters shared by the UI and software oracle runner.
#include "pg/pg.h"
#include "core/fsutil.h"
#include "core/png.h"
#include "core/pyops.h"
#include "core/gil.h"
#include "core/snapshot_compression.h"
#include "core/native_file.h"
#include "ui/pyregex.h"
#include "sim/pvp/pvprt.h"
#include <nlohmann/json.hpp>
#include <cerrno>
#include <climits>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cwchar>
#include <ctime>
#include <deque>
#include <filesystem>
#include <fstream>
#include <random>
#include <sstream>
#include <thread>
#include <regex>
#ifdef _WIN32
#include <windows.h>
#include <process.h>
#include <shellapi.h>
#include <psapi.h>
#else
#include <sys/resource.h>
extern char** environ;
#endif

namespace pvz::pg {
namespace fs = std::filesystem;
namespace {

V mod(const char* name) { return new_module(name); }
Module* M(const V& m) { return module_of(m); }
std::string path_str(const V& v) { return v.t == V::STR ? v.str() : py_str(v); }
static const V none_v = V::none();

// ------------------------------------------------------------------ os / os.path
std::string norm_sep(std::string s) { for (auto& c : s) if (c == '/') c = '\\'; return s; }

V os_path_module() {
    V m = mod("os.path");
    Module* d = M(m);
    d->fn("join", [](const Args& a) {
        fs::path p;
        for (auto& x : a.pos) { std::string s = path_str(x); if (s.empty()) continue; p /= u8p(s); }
        return V(p8(p));
    });
    d->fn("dirname", [](const Args& a) { return V(p8(u8p(path_str(a.pos.at(0))).parent_path())); });
    d->fn("basename", [](const Args& a) { return V(p8(u8p(path_str(a.pos.at(0))).filename())); });
    d->fn("normcase", [](const Args& a) {   // ntpath: ASCII lowercase + backslashes; posixpath: unchanged
        std::string s = path_str(a.pos.at(0));
#ifdef _WIN32
        for (auto& c : s) { if (c == '/') c = '\\'; else if (c >= 'A' && c <= 'Z') c = char(c - 'A' + 'a'); }
#endif
        return V(s);
    });
    d->fn("abspath", [](const Args& a) { return V(p8(fs::absolute(u8p(path_str(a.pos.at(0)))).lexically_normal())); });
    d->fn("realpath", [](const Args& a) { std::error_code ec; auto p = fs::weakly_canonical(u8p(path_str(a.pos.at(0))), ec); return V(p8(p)); });
    d->fn("normpath", [](const Args& a) { return V(p8(u8p(path_str(a.pos.at(0))).lexically_normal())); });
    d->fn("exists", [](const Args& a) { std::error_code ec; return V(fs::exists(u8p(path_str(a.pos.at(0))), ec)); });
    d->fn("isfile", [](const Args& a) { std::error_code ec; return V(fs::is_regular_file(u8p(path_str(a.pos.at(0))), ec)); });
    d->fn("isdir", [](const Args& a) { std::error_code ec; return V(fs::is_directory(u8p(path_str(a.pos.at(0))), ec)); });
    d->fn("isabs", [](const Args& a) { return V(u8p(path_str(a.pos.at(0))).is_absolute()); });
    d->fn("getsize", [](const Args& a) {
        std::error_code ec; auto n = fs::file_size(u8p(path_str(a.pos.at(0))), ec);
        if (ec) throw PyError("FileNotFoundError", path_str(a.pos.at(0)));
        return V(double(n));
    });
    d->fn("getmtime", [](const Args& a) {
        std::error_code ec; auto t = fs::last_write_time(u8p(path_str(a.pos.at(0))), ec);
        if (ec) throw PyError("FileNotFoundError", path_str(a.pos.at(0)));
        return V(double(std::chrono::duration_cast<std::chrono::seconds>(t.time_since_epoch()).count()) - 11644473600.0);
    });
    d->fn("splitext", [](const Args& a) {
        std::string s = path_str(a.pos.at(0));
        size_t slash = s.find_last_of("/\\"), dot = s.rfind('.');
        if (dot == std::string::npos || (slash != std::string::npos && dot < slash) || dot == (slash == std::string::npos ? 0 : slash + 1))
            return V::tuple({V(s), V("")});
        return V::tuple({V(s.substr(0, dot)), V(s.substr(dot))});
    });
    d->fn("split", [](const Args& a) {
        std::string s = path_str(a.pos.at(0));
        size_t slash = s.find_last_of("/\\");
        if (slash == std::string::npos) return V::tuple({V(""), V(s)});
        return V::tuple({V(s.substr(0, slash)), V(s.substr(slash + 1))});
    });
    d->fn("expanduser", [](const Args& a) {
        std::string s = path_str(a.pos.at(0));
        if (!s.empty() && s[0] == '~') { std::string h; if (env_u8("USERPROFILE", h)) s = h + s.substr(1); }
        return V(s);
    });
    d->add("sep", V("\\"));
    return m;
}

// os.environ: live view of the process environment
struct Environ : PyObj {
    const char* type_name() const override { return "_Environ"; }
    bool isa(const char* c) const override { return std::string(c) == "dict" || std::string(c) == "object"; }
    static bool get_env(const std::string& k, std::string& out) {
#ifdef _WIN32
        std::wstring wk = u8p(k).wstring();
        SetLastError(ERROR_SUCCESS);
        DWORD n = GetEnvironmentVariableW(wk.c_str(), nullptr, 0);
        if (!n) {
            if(GetLastError()==ERROR_ENVVAR_NOT_FOUND)return false;
            if(GetLastError()!=ERROR_SUCCESS)throw PyError("OSError","GetEnvironmentVariableW failed");
            out.clear();return true;
        }
        std::wstring buf(n, L'\0');
        GetEnvironmentVariableW(wk.c_str(), buf.data(), n);
        buf.resize(n - 1);
        out = p8(fs::path(buf));
        return true;
#else
        const char* v = std::getenv(k.c_str()); if (!v) return false; out = v; return true;
#endif
    }
    static void set_env(const std::string& k, const std::string& v) {
#ifdef _WIN32
        std::wstring key=u8p(k).wstring(),value=u8p(v).wstring();
        if(_wputenv_s(key.c_str(),value.c_str())!=0 || !SetEnvironmentVariableW(key.c_str(),value.c_str()))
            throw PyError("OSError","Cannot set environment variable");
#else
        setenv(k.c_str(), v.c_str(), 1);
#endif
    }
    V getitem(const V& k) override { std::string v; if (!get_env(k.str(), v)) throw PyError("KeyError", k.str()); return V(v); }
    void setitem(const V& k, const V& v) override { set_env(k.str(), v.str()); }
    void delitem(const V& k) override {
        std::string value;if(!get_env(k.str(),value))throw PyError("KeyError",k.str());
#ifdef _WIN32
        std::wstring key=u8p(k.str()).wstring();
        if(_wputenv_s(key.c_str(),L"")!=0)throw PyError("OSError","Cannot remove environment variable");
        if(!SetEnvironmentVariableW(key.c_str(),nullptr) && GetLastError()!=ERROR_ENVVAR_NOT_FOUND)
            throw PyError("OSError","Cannot remove environment variable");
#else
        if(unsetenv(k.str().c_str())!=0)throw PyError("OSError","Cannot remove environment variable");
#endif
    }
    bool contains(const V& k) override { std::string v; return k.is_str() && get_env(k.str(), v); }
    V iterate() override {
        V snapshot;call_method(Sym("copy"),Args{},snapshot);
        std::vector<V> keys;for(const auto& item:snapshot.kv())keys.push_back(item.first);
        return V::list(keys);
    }
    size_t length() override { return iterate().len(); }

    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "get") { std::string v; out = get_env(a.pos.at(0).str(), v) ? V(v) : (a.pos.size() > 1 ? a.pos[1] : V::none()); return true; }
        if (n == "setdefault") {
            std::string v;
            if (!get_env(a.pos.at(0).str(), v)) { v = a.pos.size() > 1 ? a.pos[1].str() : ""; set_env(a.pos[0].str(), v); }
            out = V(v); return true;
        }
        if (n == "pop") {
            std::string value;bool had=get_env(a.pos.at(0).str(),value);
            if(had)delitem(a.pos[0]);
            else if(a.pos.size()<2)throw PyError("KeyError",a.pos[0].str());
            out=had?V(value):a.pos[1];return true;
        }
        if (n == "copy") {
            out = V::dict();
#ifdef _WIN32
            LPWCH block = GetEnvironmentStringsW();
            if (!block) throw PyError("OSError", "GetEnvironmentStringsW failed");
            for (const wchar_t* entry = block; *entry; entry += wcslen(entry) + 1) {
                std::wstring text(entry);
                size_t equals = text.find(L'=');
                if (equals == 0 || equals == std::wstring::npos) continue;
                out.at(V(p8(fs::path(text.substr(0, equals))))) = V(p8(fs::path(text.substr(equals + 1))));
            }
            FreeEnvironmentStringsW(block);
#else
            for (char** entry = ::environ; entry && *entry; ++entry) {
                std::string text(*entry);
                size_t equals = text.find('=');
                if (equals != std::string::npos) out.at(V(text.substr(0, equals))) = V(text.substr(equals + 1));
            }
#endif
            return true;
        }
        return false;
    }
};

V os_module() {
    V m = mod("os");
    Module* d = M(m);
    d->add("path", os_path_module());
    d->add("environ", V::inst(std::make_shared<Environ>()));
    d->add("sep", V("\\"));
    d->add("name", V("nt"));
    d->add("linesep", V("\r\n"));
    d->fn("getenv", [](const Args& a) { std::string v; return Environ::get_env(a.pos.at(0).str(), v) ? V(v) : (a.pos.size() > 1 ? a.pos[1] : V::none()); });
    d->fn("getcwd", [](const Args&) { return V(p8(fs::current_path())); });
    d->fn("chdir", [](const Args& a) { fs::current_path(u8p(path_str(a.pos.at(0)))); return V::none(); });
    d->fn("listdir", [](const Args& a) {
        std::vector<V> out; std::error_code ec;
        for (auto& e : fs::directory_iterator(u8p(a.pos.empty() ? "." : path_str(a.pos[0])), ec)) out.emplace_back(p8(e.path().filename()));
        if (ec) throw PyError("FileNotFoundError", a.pos.empty() ? "." : path_str(a.pos[0]));
        return V::list(out);
    });
    d->fn("makedirs", [](const Args& a) { std::error_code ec; fs::create_directories(u8p(path_str(a.pos.at(0))), ec); return V::none(); });
    d->fn("mkdir", [](const Args& a) { std::error_code ec; fs::create_directory(u8p(path_str(a.pos.at(0))), ec); return V::none(); });
    auto rm = [](const Args& a) {
        std::error_code ec;
        if (!fs::remove(u8p(path_str(a.pos.at(0))), ec)) throw PyError("FileNotFoundError", path_str(a.pos.at(0)));
        return V::none();
    };
    d->fn("remove", rm);
    d->fn("unlink", rm);
    d->fn("replace", [](const Args& a) {
        std::error_code ec;
        fs::rename(u8p(path_str(a.pos.at(0))), u8p(path_str(a.pos.at(1))), ec);
        if (ec) throw PyError("OSError", "replace: " + ec.message());
        return V::none();
    });
    d->fn("rename", [](const Args& a) {
        std::error_code ec; fs::rename(u8p(path_str(a.pos.at(0))), u8p(path_str(a.pos.at(1))), ec);
        if (ec) throw PyError("OSError", "rename: " + ec.message());
        return V::none();
    });
    d->fn("fsync", [](const Args& a) {
        if (a.pos.size() != 1 || (a.pos[0].t != V::NUM && a.pos[0].t != V::BOOL))
            throw PyError("TypeError", "fsync requires one integer file descriptor");
        double fd = a.pos[0].num();
        if (!std::isfinite(fd) || std::floor(fd) != fd)
            throw PyError("TypeError", "fsync requires an integer file descriptor");
        if (fd < 0 || fd > INT_MAX) native_file::error("fsync", EBADF);
        native_file::sync(int(fd));
        return V::none();
    });
    d->fn("getpid", [](const Args&) {
#ifdef _WIN32
        return V(double(_getpid()));
#else
        return V(1.0);
#endif
    });
    d->fn("cpu_count", [](const Args&) { return V(double(std::max(1u, std::thread::hardware_concurrency()))); });
    d->fn("startfile", [](const Args& a) {
#ifdef _WIN32
        ShellExecuteW(nullptr, L"open", u8p(path_str(a.pos.at(0))).wstring().c_str(), nullptr, nullptr, SW_SHOWNORMAL);
#endif
        return V::none();
    });
    d->fn("add_dll_directory", [](const Args&) { return py::noop_module(V("dll_directory")); });
    d->fn("urandom", [](const Args& a) {
        std::random_device rd; std::string s(size_t(a.pos.at(0).num()), '\0');
        for (auto& c : s) c = char(rd() & 255);
        return V::bytes(s);
    });
    return m;
}

// ------------------------------------------------------------------ time
double now_wall() { return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count(); }
double now_mono() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

V py_time_module() {
    V m = mod("time");
    Module* d = M(m);
    d->fn("time", [](const Args&) { return V(now_wall()); });
    d->fn("time_ns", [](const Args&) { return V(now_wall() * 1e9); });
    d->fn("monotonic", [](const Args&) { return V(now_mono()); });
    d->fn("perf_counter", [](const Args&) { return V(now_mono()); });
    d->fn("perf_counter_ns", [](const Args&) { return V(now_mono() * 1e9); });
    d->fn("process_time", [](const Args&) { return V(double(std::clock()) / CLOCKS_PER_SEC); });
    d->fn("sleep", [](const Args& a) { gil::Release g_; std::this_thread::sleep_for(std::chrono::duration<double>(std::max(0.0, a.pos.at(0).num()))); return V::none(); });
    d->fn("strftime", [](const Args& a) {
        std::time_t t = a.pos.size() > 1 && a.pos[1].is_list() ? std::time_t(a.pos[1].idx(0).num()) : std::time(nullptr);
        if (a.pos.size() > 1 && a.pos[1].t == V::INST) t = std::time_t(pvz::getattr(a.pos[1], Sym("_ts"), V(double(std::time(nullptr)))).num());
        std::tm tmv{};
#ifdef _WIN32
        localtime_s(&tmv, &t);
#else
        localtime_r(&t, &tmv);
#endif
        char buf[256];
        size_t n = std::strftime(buf, sizeof buf, a.pos.at(0).str().c_str(), &tmv);
        return V(std::string(buf, n));
    });
    d->fn("localtime", [](const Args& a) {
        std::time_t t = a.pos.empty() || a.pos[0].is_none() ? std::time(nullptr) : std::time_t(a.pos[0].num());
        std::tm tmv{};
#ifdef _WIN32
        localtime_s(&tmv, &t);
#else
        localtime_r(&t, &tmv);
#endif
        V st = mod("struct_time");
        Module* s = M(st);
        s->add("tm_year", V(double(tmv.tm_year + 1900))); s->add("tm_mon", V(double(tmv.tm_mon + 1))); s->add("tm_mday", V(double(tmv.tm_mday)));
        s->add("tm_hour", V(double(tmv.tm_hour))); s->add("tm_min", V(double(tmv.tm_min))); s->add("tm_sec", V(double(tmv.tm_sec)));
        s->add("tm_wday", V(double((tmv.tm_wday + 6) % 7))); s->add("tm_yday", V(double(tmv.tm_yday + 1)));
        s->add("_ts", V(double(t)));
        return st;
    });
    d->fn("get_clock_info", [](const Args&) {
        V info = mod("clock_info");
        M(info)->add("resolution", V(1e-7)); M(info)->add("monotonic", V(true)); M(info)->add("implementation", V("QueryPerformanceCounter()"));
        return info;
    });
    return m;
}

// ------------------------------------------------------------------ io
struct BytesIO : PyObj {
    std::string data; size_t pos = 0; bool text = false;
    const char* type_name() const override { return text ? "StringIO" : "BytesIO"; }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "getvalue") { out = V(data); return true; }
        if (n == "read") {
            size_t k = a.pos.empty() || a.pos[0].num() < 0 ? data.size() - pos : std::min(data.size() - pos, size_t(a.pos[0].num()));
            out = V(data.substr(pos, k)); pos += k; return true;
        }
        if (n == "write") {
            const std::string& s = a.pos.at(0).str();
            if (pos > data.size()) data.resize(pos, '\0');
            data.replace(pos, std::min(s.size(), data.size() - pos), s);
            pos += s.size(); out = V(double(s.size())); return true;
        }
        if (n == "seek") { size_t base = a.pos.size() > 1 ? (a.pos[1].num() == 1 ? pos : a.pos[1].num() == 2 ? data.size() : 0) : 0; pos = size_t(double(base) + a.pos.at(0).num()); out = V(double(pos)); return true; }
        if (n == "tell") { out = V(double(pos)); return true; }
        if (n == "close" || n == "flush") { out = V::none(); return true; }
        if (n == "__enter__") { out = self(); return true; }
        if (n == "__exit__") { out = V(false); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<BytesIO>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", name.str()); return out; });
    }
};

V io_module() {
    V m = mod("io");
    auto make = [](bool text) {
        return [text](const Args& a) {
            auto p = std::make_shared<BytesIO>();
            p->text = text;
            if (!a.pos.empty() && !a.pos[0].is_none()) p->data = a.pos[0].str();
            return V::inst(p);
        };
    };
    M(m)->fn("BytesIO", make(false));
    M(m)->fn("StringIO", make(true));
    return m;
}

// ------------------------------------------------------------------ base64
const char* B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
std::string b64enc(const std::string& in, bool url) {
    std::string out;
    out.reserve((in.size() + 2) / 3 * 4);
    for (size_t i = 0; i < in.size(); i += 3) {
        uint32_t v = uint8_t(in[i]) << 16;
        if (i + 1 < in.size()) v |= uint8_t(in[i + 1]) << 8;
        if (i + 2 < in.size()) v |= uint8_t(in[i + 2]);
        for (int k = 0; k < 4; ++k) {
            if (i + size_t(k) * 3 / 4 > in.size() || (k == 2 && i + 1 >= in.size()) || (k == 3 && i + 2 >= in.size())) { out += '='; continue; }
            char c = B64[(v >> (18 - 6 * k)) & 63];
            if (url) { if (c == '+') c = '-'; else if (c == '/') c = '_'; }
            out += c;
        }
    }
    return out;
}
std::string b64dec(const std::string& in) {
    int8_t rev[256];
    std::fill(rev, rev + 256, int8_t(-1));
    for (int i = 0; i < 64; ++i) rev[uint8_t(B64[i])] = int8_t(i);
    rev[uint8_t('-')] = 62; rev[uint8_t('_')] = 63;
    std::string out;
    uint32_t buf = 0; int bits = 0;
    for (char c : in) {
        if (c == '=') break;
        int8_t v = rev[uint8_t(c)];
        if (v < 0) continue;
        buf = (buf << 6) | uint32_t(v); bits += 6;
        if (bits >= 8) { bits -= 8; out += char((buf >> bits) & 255); }
    }
    return out;
}
V base64_module() {
    V m = mod("base64");
    M(m)->fn("b64encode", [](const Args& a) { return V(b64enc(a.pos.at(0).str(), false)); });
    M(m)->fn("b64decode", [](const Args& a) { return V::bytes(b64dec(a.pos.at(0).str())); });
    M(m)->fn("urlsafe_b64encode", [](const Args& a) { return V(b64enc(a.pos.at(0).str(), true)); });
    M(m)->fn("urlsafe_b64decode", [](const Args& a) { return V::bytes(b64dec(a.pos.at(0).str())); });
    M(m)->fn("standard_b64encode", [](const Args& a) { return V(b64enc(a.pos.at(0).str(), false)); });
    M(m)->fn("standard_b64decode", [](const Args& a) { return V(b64dec(a.pos.at(0).str())); });
    return m;
}

// ------------------------------------------------------------------ zlib
V zlib_decompress(const std::string& in) {
    std::vector<uint8_t> out;
    if (!png::inflate_zlib(reinterpret_cast<const uint8_t*>(in.data()), in.size(), out))
        throw PyError("error", "Error -3 while decompressing data: invalid stream");
    return V::bytes(std::string(out.begin(), out.end()));
}
struct Decomp : PyObj {
    std::string pending, tail;
    bool eof = false;
    const char* type_name() const override { return "Decompress"; }
    V property(Sym n, bool& found) override {
        found = true;
        if (n.str() == "eof") return V(eof);
        if (n.str() == "unused_data") return V("");
        if (n.str() == "unconsumed_tail") return V(tail);
        found = false;
        return V();
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        if (name.str() == "decompress") {   // whole-stream semantics: buffer until it inflates
            pending += py::bytes_data(a.pos.at(0));
            size_t max_length = a.pos.size() > 1 && a.pos[1].num() > 0 ? size_t(a.pos[1].num()) : 0;
            std::vector<uint8_t> o;
            if (png::inflate_zlib(reinterpret_cast<const uint8_t*>(pending.data()), pending.size(), o)) {
                pending.clear();
                eof = true;
                std::string r(o.begin(), o.end());
                if (max_length && r.size() > max_length) { tail = "x"; r.resize(max_length); }   // input left over (output limit hit)
                out = V::bytes(r);
            }
            else out = V::bytes("");
            return true;
        }
        if (name.str() == "flush") { out = V(""); return true; }
        return false;
    }
};
V zlib_module() {
    V m = mod("zlib");
    M(m)->fn("compress", [](const Args& a) {
        const std::string in = a.pos.at(0).str();
        static const V six(6.0);
        int level = int(a.get(1, Sym("level"), &six).num());
        std::string out;
        { gil::Release unlocked;
          out=snapshot_compress(in,level); }
        return V::bytes(std::move(out));
    });
    M(m)->fn("decompress", [](const Args& a) { return zlib_decompress(a.pos.at(0).str()); });
    M(m)->fn("decompressobj", [](const Args&) { return V::inst(std::make_shared<Decomp>()); });
    M(m)->fn("crc32", [](const Args& a) {
        const std::string& s = a.pos.at(0).str();
        uint32_t c = a.pos.size() > 1 ? ~uint32_t(a.pos[1].num()) : 0xFFFFFFFFu;
        for (unsigned char ch : s) { c ^= ch; for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); }
        return V(double(~c));
    });
    M(m)->fn("adler32", [](const Args& a) { const std::string& s = a.pos.at(0).str(); return V(double(png::adler32(reinterpret_cast<const uint8_t*>(s.data()), s.size()))); });
    M(m)->add("error", py::exc_type(V("error")));
    return m;
}

// ------------------------------------------------------------------ json (python json.dumps options)
struct JsonOpts { bool ascii = true, sort = false, allow_nan = true; std::string item_sep = ", ", key_sep = ": "; int indent = -1; };
void json_str(std::string& o, const std::string& s, bool ascii) {
    o += '"';
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        switch (c) {
            case '"': o += "\\\""; continue; case '\\': o += "\\\\"; continue;
            case '\n': o += "\\n"; continue; case '\r': o += "\\r"; continue; case '\t': o += "\\t"; continue;
            case '\b': o += "\\b"; continue; case '\f': o += "\\f"; continue;
        }
        if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; continue; }
        if (c < 0x80 || !ascii) { o += char(c); continue; }
        uint32_t cp; int len;
        if (c < 0xE0) { cp = c & 0x1F; len = 2; } else if (c < 0xF0) { cp = c & 0x0F; len = 3; } else { cp = c & 0x07; len = 4; }
        for (int k = 1; k < len && i + size_t(k) < s.size(); ++k) cp = (cp << 6) | (static_cast<unsigned char>(s[i + size_t(k)]) & 0x3F);
        i += size_t(len - 1);
        char b[16];
        if (cp >= 0x10000) { cp -= 0x10000; snprintf(b, sizeof b, "\\u%04x\\u%04x", 0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)); }
        else snprintf(b, sizeof b, "\\u%04x", cp);
        o += b;
    }
    o += '"';
}
std::string num_repr(double d) {
    if (std::isnan(d)) return "NaN";
    if (std::isinf(d)) return d > 0 ? "Infinity" : "-Infinity";
    if (d == std::floor(d) && std::fabs(d) < 1e16) { char b[32]; snprintf(b, sizeof b, "%lld", (long long)d); return b; }
    char b[32];
    for (int prec = 1; prec <= 17; ++prec) { snprintf(b, sizeof b, "%.*g", prec, d); if (std::strtod(b, nullptr) == d) break; }
    std::string s(b);
    if (s.find_first_of(".eEn") == std::string::npos) s += ".0";
    return s;
}
void json_dump(std::string& o, const V& v, const JsonOpts& op, int depth) {
    auto nl = [&](int d) { if (op.indent >= 0) { o += '\n'; o.append(size_t(op.indent * d), ' '); } };
    switch (v.t) {
        case V::ABSENT: case V::NONE: o += "null"; return;
        case V::BOOL: o += v.b ? "true" : "false"; return;
        case V::NUM:
            if (!op.allow_nan && !std::isfinite(v.n)) throw PyError("ValueError", "Out of range float values are not JSON compliant");
            o += num_repr(v.n); return;
        case V::STR: json_str(o, v.str(), op.ascii); return;
        case V::LIST: case V::TUPLE: case V::SET: {
            const auto& it = v.items();
            if (it.empty()) { o += "[]"; return; }
            o += '[';
            for (size_t i = 0; i < it.size(); ++i) {
                if (i) o += op.indent >= 0 ? std::string(",") : op.item_sep;
                nl(depth + 1);
                json_dump(o, it[i], op, depth + 1);
            }
            nl(depth); o += ']';
            return;
        }
        case V::DICT: case V::OBJ: {
            std::vector<std::pair<V, V>> kv = py::items_vec(v);
            if (op.sort) std::stable_sort(kv.begin(), kv.end(), [](auto& a, auto& b) { return py_lt(a.first, b.first); });
            if (kv.empty()) { o += "{}"; return; }
            o += '{';
            bool first = true;
            for (auto& [k, x] : kv) {
                if (!x.has()) continue;
                if (!first) o += op.indent >= 0 ? std::string(",") : op.item_sep;
                first = false;
                nl(depth + 1);
                std::string ks = k.t == V::STR ? k.str() : k.t == V::NUM ? num_repr(k.n) : k.t == V::BOOL ? (k.b ? "true" : "false") : k.is_none() ? "null" : py_str(k);
                json_str(o, ks, op.ascii);
                o += op.key_sep;
                json_dump(o, x, op, depth + 1);
            }
            nl(depth); o += '}';
            return;
        }
        default: throw PyError("TypeError", "Object of type " + v.type_name() + " is not JSON serializable");
    }
}
V json_from(const nlohmann::json& j) {
    if (j.is_null()) return V::none();
    if (j.is_boolean()) return V(j.get<bool>());
    if (j.is_number()) return V(j.get<double>());
    if (j.is_string()) return V(j.get<std::string>());
    if (j.is_array()) { std::vector<V> it; it.reserve(j.size()); for (auto& x : j) it.push_back(json_from(x)); return V::list(std::move(it)); }
    V d = V::dict();
    for (auto& [k, x] : j.items()) d.at(V(k)) = json_from(x);
    return d;
}
V json_module() {
    V m = mod("json");
    auto dumps = [](const Args& a) {
        JsonOpts op;
        op.indent = -1;
        for (auto& [k, v] : a.kw) {
            const std::string& n = k.str();
            if (n == "ensure_ascii") op.ascii = v.truthy();
            else if (n == "sort_keys") op.sort = v.truthy();
            else if (n == "allow_nan") op.allow_nan = v.truthy();
            else if (n == "indent") op.indent = v.is_none() ? -1 : int(v.num());
            else if (n == "separators" && !v.is_none()) { op.item_sep = v.idx(0).str(); op.key_sep = v.idx(1).str(); }
        }
        if (op.indent >= 0) { bool given = false; for (auto& [k, v] : a.kw) if (k.str() == "separators" && !v.is_none()) given = true; if (!given) op.item_sep = ","; }
        std::string o;
        json_dump(o, a.pos.at(0), op, 0);
        return V(std::move(o));
    };
    M(m)->fn("dumps", dumps);
    M(m)->fn("loads", [](const Args& a) {
        try { return json_from(nlohmann::json::parse(a.pos.at(0).str())); }
        catch (nlohmann::json::exception& e) { throw PyError("JSONDecodeError", e.what(), {"ValueError", "Exception"}); }
    });
    M(m)->fn("dump", [dumps](const Args& a) {
        Args b; b.pos.push_back(a.pos.at(0)); b.kw = a.kw;
        V s = dumps(b);
        callm(a.pos.at(1), Sym("write"), Args{s});
        return V::none();
    });
    M(m)->fn("load", [](const Args& a) { return json_from(nlohmann::json::parse(callm(a.pos.at(0), Sym("read"), Args{}).str())); });
    M(m)->add("JSONDecodeError", py::exc_type(V("JSONDecodeError")));
    return m;
}

// ------------------------------------------------------------------ secrets / hmac / struct
std::mt19937_64& sysrng() { static std::mt19937_64 r(std::random_device{}() ^ (uint64_t(now_wall() * 1e6) << 1)); return r; }
V secrets_module() {
    V m = mod("secrets");
    M(m)->fn("token_hex", [](const Args& a) {
        size_t n = a.pos.empty() ? 32 : size_t(a.pos[0].num()); std::string s; char b[3];
        for (size_t i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02x", unsigned(sysrng()() & 255)); s += b; }
        return V(s);
    });
    M(m)->fn("token_urlsafe", [](const Args& a) {
        size_t n = a.pos.empty() ? 32 : size_t(a.pos[0].num()); std::string raw;
        for (size_t i = 0; i < n; ++i) raw += char(sysrng()() & 255);
        std::string s = b64enc(raw, true);
        while (!s.empty() && s.back() == '=') s.pop_back();
        return V(s);
    });
    M(m)->fn("token_bytes", [](const Args& a) { size_t n = a.pos.empty() ? 32 : size_t(a.pos[0].num()); std::string s; for (size_t i = 0; i < n; ++i) s += char(sysrng()() & 255); return V::bytes(s); });
    M(m)->fn("randbelow", [](const Args& a) { return V(double(sysrng()() % uint64_t(a.pos.at(0).num()))); });
    M(m)->fn("choice", [](const Args& a) { V s = py::iter_list(a.pos.at(0)); return s.idx(int64_t(sysrng()() % s.len())); });
    M(m)->fn("SystemRandom", [](const Args&) { return py::make_random(int64_t(sysrng()() & 0x7fffffff)); });
    return m;
}
V hmac_module() {
    V m = mod("hmac");
    M(m)->fn("compare_digest", [](const Args& a) {
        const std::string &x = a.pos.at(0).str(), &y = a.pos.at(1).str();
        unsigned char d = x.size() == y.size() ? 0 : 1;
        for (size_t i = 0; i < std::min(x.size(), y.size()); ++i) d |= uint8_t(x[i] ^ y[i]);
        return V(d == 0);
    });
    return m;
}
// struct.pack/unpack for the format subset the PvP code uses: byte order prefix + B b H h I i Q q f d ?
size_t fmt_items(const std::string& f, bool& little, std::vector<std::pair<char, int>>& items) {
    size_t i = 0; little = true;
    if (!f.empty() && std::string("<>!=@").find(f[0]) != std::string::npos) { little = f[0] == '<' || f[0] == '=' || f[0] == '@'; i = 1; }
    size_t total = 0;
    while (i < f.size()) {
        int count = 0;
        while (i < f.size() && std::isdigit(static_cast<unsigned char>(f[i]))) count = count * 10 + (f[i++] - '0');
        if (i >= f.size()) break;
        char c = f[i++];
        int sz = c == 'B' || c == 'b' || c == '?' || c == 'x' || c == 's' ? 1 : c == 'H' || c == 'h' ? 2 : c == 'I' || c == 'i' || c == 'f' || c == 'L' || c == 'l' ? 4 : 8;
        if (c == 's') { items.push_back({'s', count ? count : 1}); total += size_t(count ? count : 1); continue; }
        for (int k = 0; k < (count ? count : 1); ++k) { items.push_back({c, sz}); total += size_t(sz); }
    }
    return total;
}
V struct_pack(const std::string& f, const Args& a, size_t first) {
    bool little; std::vector<std::pair<char, int>> items;
    fmt_items(f, little, items);
    std::string out; size_t ai = first;
    for (auto [c, sz] : items) {
        if (c == 'x') { out += '\0'; continue; }
        if (c == 's') { std::string s = a.pos.at(ai++).str(); s.resize(size_t(sz), '\0'); out += s; continue; }
        double v = a.pos.at(ai++).num();
        uint64_t bits;
        if (c == 'f') { float fv = float(v); uint32_t b32; std::memcpy(&b32, &fv, 4); bits = b32; }
        else if (c == 'd') std::memcpy(&bits, &v, 8);
        else bits = uint64_t(int64_t(v));
        for (int k = 0; k < sz; ++k) out += char((bits >> (8 * (little ? k : sz - 1 - k))) & 255);
    }
    return V::bytes(out);
}
V struct_unpack(const std::string& f, const std::string& d, size_t off) {
    bool little; std::vector<std::pair<char, int>> items;
    size_t total = fmt_items(f, little, items);
    if (d.size() < off + total) throw PyError("error", "unpack requires a buffer of " + std::to_string(total) + " bytes");
    std::vector<V> out; size_t p = off;
    for (auto [c, sz] : items) {
        if (c == 'x') { ++p; continue; }
        if (c == 's') { out.emplace_back(d.substr(p, size_t(sz))); p += size_t(sz); continue; }
        uint64_t bits = 0;
        for (int k = 0; k < sz; ++k) bits |= uint64_t(uint8_t(d[p + size_t(k)])) << (8 * (little ? k : sz - 1 - k));
        p += size_t(sz);
        double v;
        if (c == 'f') { uint32_t b32 = uint32_t(bits); float fv; std::memcpy(&fv, &b32, 4); v = fv; }
        else if (c == 'd') std::memcpy(&v, &bits, 8);
        else if (c == 'b' || c == 'h' || c == 'i' || c == 'l' || c == 'q') { int shift = 64 - 8 * sz; v = double(int64_t(bits << shift) >> shift); }
        else if (c == '?') { out.emplace_back(bits != 0); continue; }
        else v = double(bits);
        out.emplace_back(v);
    }
    return V::tuple(out);
}
V struct_module() {
    V m = mod("struct");
    M(m)->fn("pack", [](const Args& a) { return struct_pack(a.pos.at(0).str(), a, 1); });
    M(m)->fn("unpack", [](const Args& a) { return struct_unpack(a.pos.at(0).str(), py::bytes_data(a.pos.at(1)), 0); });
    M(m)->fn("unpack_from", [](const Args& a) { static const V z(0.0); return struct_unpack(a.pos.at(0).str(), py::bytes_data(a.pos.at(1)), size_t(a.get(2, Sym("offset"), &z).num())); });
    M(m)->fn("calcsize", [](const Args& a) { bool l; std::vector<std::pair<char, int>> it; return V(double(fmt_items(a.pos.at(0).str(), l, it))); });
    M(m)->fn("Struct", [](const Args& a) {
        std::string f = a.pos.at(0).str();
        V s = mod("Struct");
        bool l; std::vector<std::pair<char, int>> it;
        M(s)->add("size", V(double(fmt_items(f, l, it))));
        M(s)->add("format", V(f));
        M(s)->fn("pack", [f](const Args& b) { return struct_pack(f, b, 0); });
        M(s)->fn("unpack", [f](const Args& b) { return struct_unpack(f, py::bytes_data(b.pos.at(0)), 0); });
        M(s)->fn("unpack_from", [f](const Args& b) { static const V z(0.0); return struct_unpack(f, py::bytes_data(b.pos.at(0)), size_t(b.get(1, Sym("offset"), &z).num())); });
        return s;
    });
    M(m)->add("error", py::exc_type(V("error")));
    return m;
}

// ------------------------------------------------------------------ small modules
V platform_module() {
    V m = mod("platform");
    M(m)->fn("system", [](const Args&) { return V("Windows"); });
    M(m)->fn("release", [](const Args&) { return V("10"); });
    M(m)->fn("machine", [](const Args&) { return V("AMD64"); });
    M(m)->fn("processor", [](const Args&) { return V("x86_64"); });
    M(m)->fn("platform", [](const Args&) { return V("Windows-10"); });
    M(m)->fn("node", [](const Args&) { return V("pvz-native"); });
    M(m)->fn("python_version", [](const Args&) { return V("3.8.10"); });
    return m;
}
V errno_module() {
    V m = mod("errno");
#ifdef _WIN32   // winsock values (what python's socket calls report on windows)
    for (auto [n, v] : std::initializer_list<std::pair<const char*, double>>{{"EWOULDBLOCK", 10035}, {"EAGAIN", 11}, {"EINPROGRESS", 10036},
            {"ECONNRESET", 10054}, {"ECONNREFUSED", 10061}, {"ECONNABORTED", 10053}, {"EADDRINUSE", 10048}, {"ETIMEDOUT", 10060},
            {"EINTR", 4}, {"ENOENT", 2}, {"EEXIST", 17}, {"EACCES", 13}, {"EPIPE", 32}, {"ENOTCONN", 10057}, {"EALREADY", 10037},
            {"EISCONN", 10056}, {"EHOSTUNREACH", 10065}, {"ENETUNREACH", 10051}, {"ENOSPC", 28}, {"EIO", 5}, {"EROFS", 30}})
#else
    for (auto [n, v] : std::initializer_list<std::pair<const char*, double>>{{"EWOULDBLOCK", EWOULDBLOCK}, {"EAGAIN", EAGAIN}, {"EINPROGRESS", EINPROGRESS},
            {"ECONNRESET", ECONNRESET}, {"ECONNREFUSED", ECONNREFUSED}, {"ECONNABORTED", ECONNABORTED}, {"EADDRINUSE", EADDRINUSE}, {"ETIMEDOUT", ETIMEDOUT},
            {"EINTR", EINTR}, {"ENOENT", ENOENT}, {"EEXIST", EEXIST}, {"EACCES", EACCES}, {"EPIPE", EPIPE}, {"ENOTCONN", ENOTCONN}, {"EALREADY", EALREADY},
            {"EISCONN", EISCONN}, {"EHOSTUNREACH", EHOSTUNREACH}, {"ENETUNREACH", ENETUNREACH}, {"ENOSPC", ENOSPC}, {"EIO", EIO}, {"EROFS", EROFS}})
#endif
        M(m)->add(n, V(v));
    return m;
}
V traceback_module() {
    V m = mod("traceback");
    M(m)->fn("format_exc", [](const Args&) { return V(std::string("Traceback (C++ build): see crash log\n")); });
    M(m)->fn("print_exc", [](const Args&) { fprintf(stderr, "Traceback (C++ build)\n"); return V::none(); });
    M(m)->fn("format_exception", [](const Args&) { return V::list({V("Traceback (C++ build)\n")}); });
    return m;
}
V shutil_module() {
    V m = mod("shutil");
    M(m)->fn("rmtree", [](const Args& a) { std::error_code ec; fs::remove_all(u8p(path_str(a.pos.at(0))), ec); return V::none(); });
    M(m)->fn("copyfile", [](const Args& a) { std::error_code ec; fs::copy_file(u8p(path_str(a.pos.at(0))), u8p(path_str(a.pos.at(1))), fs::copy_options::overwrite_existing, ec); return a.pos.at(1); });
    M(m)->fn("copy2", [](const Args& a) { std::error_code ec; fs::copy_file(u8p(path_str(a.pos.at(0))), u8p(path_str(a.pos.at(1))), fs::copy_options::overwrite_existing, ec); return a.pos.at(1); });
    M(m)->fn("move", [](const Args& a) { std::error_code ec; fs::rename(u8p(path_str(a.pos.at(0))), u8p(path_str(a.pos.at(1))), ec); return a.pos.at(1); });
    return m;
}
// single-threaded stand-ins: the translated UI runs on one thread; the network layer is native C++
V threading_module() {
    V m = mod("threading");
    auto lock = [](const Args&) {
        V l = mod("Lock");
        M(l)->fn("acquire", [](const Args&) { return V(true); });
        M(l)->fn("release", [](const Args&) { return V::none(); });
        M(l)->fn("locked", [](const Args&) { return V(false); });
        M(l)->fn("__enter__", [](const Args&) { return V(true); });
        M(l)->fn("__exit__", [](const Args&) { return V(false); });
        return l;
    };
    M(m)->fn("Lock", lock);
    M(m)->fn("RLock", lock);
    M(m)->fn("Event", [](const Args&) {
        auto flag = std::make_shared<bool>(false);
        V e = mod("Event");
        M(e)->fn("set", [flag](const Args&) { *flag = true; return V::none(); });
        M(e)->fn("clear", [flag](const Args&) { *flag = false; return V::none(); });
        M(e)->fn("is_set", [flag](const Args&) { return V(*flag); });
        M(e)->fn("wait", [flag](const Args&) { return V(*flag); });
        return e;
    });
    M(m)->fn("current_thread", [](const Args&) { V t = mod("Thread"); M(t)->add("name", V("MainThread")); return t; });
    M(m)->fn("get_ident", [](const Args&) { return V(1.0); });
    M(m)->fn("Thread", [](const Args& a) {   // runs the target when start() is called (synchronously)
        V target; for (auto& kv : a.kw) if (kv.first.str() == "target") target = kv.second;
        V args = V::tuple({}); for (auto& kv : a.kw) if (kv.first.str() == "args") args = kv.second;
        V t = mod("Thread");
        M(t)->fn("start", [target, args](const Args&) { if (target.has()) { Args b; for (auto& x : py::iter_list(args).items()) b.pos.push_back(x); target.call(b); } return V::none(); });
        M(t)->fn("join", [](const Args&) { return V::none(); });
        M(t)->fn("is_alive", [](const Args&) { return V(false); });
        M(t)->add("daemon", V(true));
        return t;
    });
    return m;
}
V queue_module() {
    V m = mod("queue");
    M(m)->fn("Queue", [](const Args&) {
        auto q = std::make_shared<std::deque<V>>();
        V o = mod("Queue");
        M(o)->fn("put", [q](const Args& a) { q->push_back(a.pos.at(0)); return V::none(); });
        M(o)->fn("put_nowait", [q](const Args& a) { q->push_back(a.pos.at(0)); return V::none(); });
        auto get = [q](const Args&) {
            if (q->empty()) throw PyError("Empty", "queue empty", {"Exception"});
            V v = q->front(); q->pop_front(); return v;
        };
        M(o)->fn("get", get);
        M(o)->fn("get_nowait", get);
        M(o)->fn("empty", [q](const Args&) { return V(q->empty()); });
        M(o)->fn("qsize", [q](const Args&) { return V(double(q->size())); });
        return o;
    });
    M(m)->add("Empty", py::exc_type(V("Empty")));
    M(m)->add("Full", py::exc_type(V("Full")));
    return m;
}
V tempfile_module() {
    V m = mod("tempfile");
    M(m)->fn("gettempdir", [](const Args&) { return V(p8(fs::temp_directory_path())); });
    M(m)->fn("mkdtemp", [](const Args&) {
        fs::path p = fs::temp_directory_path() / ("pvz_" + std::to_string(sysrng()() % 1000000000));
        fs::create_directories(p);
        return V(p8(p));
    });
    return m;
}
V unicodedata_module() {
    V m = mod("unicodedata");
    M(m)->fn("category", [](const Args& a) {
        const std::string& s = a.pos.at(0).str();
        if (s.empty()) return V("Cn");
        unsigned char c = static_cast<unsigned char>(s[0]);
        if (c < 0x20 || c == 0x7f) return V("Cc");
        if (c < 0x80) return V(std::isalpha(c) ? (std::isupper(c) ? "Lu" : "Ll") : std::isdigit(c) ? "Nd" : c == ' ' ? "Zs" : "Po");
        return V("Lo");
    });
    M(m)->fn("east_asian_width", [](const Args& a) { return V(static_cast<unsigned char>(a.pos.at(0).str()[0]) >= 0xE0 ? "W" : "Na"); });
    return m;
}
// ------------------------------------------------------------------ re (python semantics on code points;
// own backtracking engine in ui/pyregex.*: lookbehind, lazy quantifiers, zero-width split, CJK classes)
struct Pattern : PyObj {
    std::string src;
    int flags = 0;
    rx::Regex re;
    const char* type_name() const override { return "Pattern"; }
    V make_match(const std::shared_ptr<std::u32string>& text, const std::string& orig, const rx::Match& m) const {
        V mo = mod("Match");
        auto spans = std::make_shared<std::vector<long>>(m.spans);
        auto names = re.names;
        auto gindex = [names](const V& g) -> size_t {
            if (g.t == V::STR) { for (auto& [n, i] : names) if (n == g.str()) return size_t(i); throw PyError("IndexError", "no such group"); }
            return size_t(g.num());
        };
        auto grp = [text, spans](size_t i) -> V {
            if (2 * i + 1 >= spans->size()) throw PyError("IndexError", "no such group");
            long a = (*spans)[2 * i], b = (*spans)[2 * i + 1];
            return a < 0 ? V::none() : V(rx::encode(*text, size_t(a), size_t(b)));
        };
        int ng = re.groups;
        M(mo)->fn("group", [grp, gindex](const Args& a) {
            if (a.pos.size() <= 1) return grp(a.pos.empty() ? 0 : gindex(a.pos[0]));
            std::vector<V> o; for (auto& g : a.pos) o.push_back(grp(gindex(g))); return V::tuple(o);
        });
        M(mo)->fn("__getitem__", [grp, gindex](const Args& a) { return grp(gindex(a.pos.at(0))); });
        M(mo)->fn("groups", [grp, ng](const Args& a) {
            std::vector<V> o; for (int i = 1; i <= ng; ++i) { V g = grp(size_t(i)); o.push_back(g.is_none() && !a.pos.empty() ? a.pos[0] : g); } return V::tuple(o);
        });
        M(mo)->fn("groupdict", [grp, names](const Args&) { V d = V::dict(); for (auto& [n, i] : names) d.at(V(n)) = grp(size_t(i)); return d; });
        M(mo)->fn("start", [spans, gindex](const Args& a) { return V(double((*spans)[2 * (a.pos.empty() ? 0 : gindex(a.pos[0]))])); });
        M(mo)->fn("end", [spans, gindex](const Args& a) { return V(double((*spans)[2 * (a.pos.empty() ? 0 : gindex(a.pos[0])) + 1])); });
        M(mo)->fn("span", [spans, gindex](const Args& a) { size_t i = a.pos.empty() ? 0 : gindex(a.pos[0]); return V::tuple({V(double((*spans)[2 * i])), V(double((*spans)[2 * i + 1]))}); });
        M(mo)->add("string", V(orig));
        return mo;
    }
    // python's iteration over non-overlapping matches (an empty match may follow a non-empty one)
    std::vector<rx::Match> all(const std::u32string& t, size_t limit = 0) const {
        std::vector<rx::Match> out;
        size_t pos = 0;
        while (pos <= t.size()) {
            rx::Match m = rx::search(re, t, pos, false);
            if (!m.ok) break;
            out.push_back(m);
            if (limit && out.size() >= limit) break;
            size_t a = size_t(m.spans[0]), b = size_t(m.spans[1]);
            pos = b == a ? b + 1 : b;
        }
        return out;
    }
    std::string expand(const std::string& tmpl, const std::u32string& t, const rx::Match& m) const {
        std::string o;
        auto grp = [&](size_t i) {
            if (2 * i + 1 >= m.spans.size()) throw PyError("error", "invalid group reference");
            long a = m.spans[2 * i], b = m.spans[2 * i + 1];
            return a < 0 ? std::string() : rx::encode(t, size_t(a), size_t(b));
        };
        const char bs = '\\';
        for (size_t i = 0; i < tmpl.size(); ++i) {
            char c = tmpl[i];
            if (c != bs || i + 1 >= tmpl.size()) { o += c; continue; }
            char d = tmpl[++i];
            if (d >= '1' && d <= '9') {
                size_t g = size_t(d - '0');
                if (i + 1 < tmpl.size() && isdigit((unsigned char)tmpl[i + 1])) g = g * 10 + size_t(tmpl[++i] - '0');
                o += grp(g);
            } else if (d == 'g' && i + 1 < tmpl.size() && tmpl[i + 1] == '<') {
                size_t close = tmpl.find('>', i);
                std::string name = tmpl.substr(i + 2, close - i - 2);
                i = close;
                size_t g = 0;
                bool num = !name.empty() && name.find_first_not_of("0123456789") == std::string::npos;
                if (num) g = size_t(std::stoul(name)); else { for (auto& [n, k] : re.names) if (n == name) g = size_t(k); }
                o += grp(g);
            } else if (d == 'n') o += char(10);
            else if (d == 't') o += char(9);
            else if (d == bs) o += bs;
            else { o += bs; o += d; }
        }
        return o;
    }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "search" || n == "match" || n == "fullmatch") {
            std::string str = a.pos.at(0).str();
            auto t = std::make_shared<std::u32string>(rx::decode(str));
            size_t start = a.pos.size() > 1 ? size_t(a.pos[1].num()) : 0;
            rx::Match m = rx::search(re, *t, start, n != "search", n == "fullmatch");
            out = m.ok ? make_match(t, str, m) : V::none();
            return true;
        }
        if (n == "findall" || n == "finditer") {
            std::string str = a.pos.at(0).str();
            auto t = std::make_shared<std::u32string>(rx::decode(str));
            std::vector<V> res;
            for (auto& m : all(*t)) {
                if (n == "finditer") { res.push_back(make_match(t, str, m)); continue; }
                auto g = [&](int i) { long x = m.spans[2 * i], y = m.spans[2 * i + 1]; return V(x < 0 ? std::string() : rx::encode(*t, size_t(x), size_t(y))); };
                if (re.groups == 0) res.push_back(g(0));
                else if (re.groups == 1) res.push_back(g(1));
                else { std::vector<V> tu; for (int i = 1; i <= re.groups; ++i) tu.push_back(g(i)); res.push_back(V::tuple(tu)); }
            }
            out = V::list(res);
            return true;
        }
        if (n == "sub" || n == "subn") {
            V repl = a.pos.at(0);
            std::string str = a.pos.at(1).str();
            auto t = std::make_shared<std::u32string>(rx::decode(str));
            size_t count = a.pos.size() > 2 ? size_t(a.pos[2].num()) : 0;
            for (auto& [k, v] : a.kw) if (k.str() == "count") count = size_t(v.num());
            std::string res; size_t last = 0; int done = 0;
            for (auto& m : all(*t, count)) {
                size_t x = size_t(m.spans[0]), y = size_t(m.spans[1]);
                res += rx::encode(*t, last, x);
                if (repl.t == V::STR) res += expand(repl.str(), *t, m);
                else res += py_str(repl.call(Args{make_match(t, str, m)}));
                last = y; ++done;
            }
            res += rx::encode(*t, last, t->size());
            out = n == "sub" ? V(res) : V::tuple({V(res), V(double(done))});
            return true;
        }
        if (n == "split") {
            std::string str = a.pos.at(0).str();
            std::u32string t = rx::decode(str);
            size_t maxsplit = a.pos.size() > 1 ? size_t(a.pos[1].num()) : 0;
            for (auto& [k, v] : a.kw) if (k.str() == "maxsplit") maxsplit = size_t(v.num());
            std::vector<V> res; size_t last = 0;
            for (auto& m : all(t, maxsplit)) {
                size_t x = size_t(m.spans[0]), y = size_t(m.spans[1]);
                res.emplace_back(rx::encode(t, last, x));
                for (int i = 1; i <= re.groups; ++i) {
                    long gx = m.spans[2 * i], gy = m.spans[2 * i + 1];
                    res.push_back(gx < 0 ? V::none() : V(rx::encode(t, size_t(gx), size_t(gy))));
                }
                last = y;
            }
            res.emplace_back(rx::encode(t, last, t.size()));
            out = V::list(res);
            return true;
        }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<Pattern>(shared_from_this());
        static const char* known[] = {"search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split"};
        for (const char* k : known) if (name.str() == k) return V::func([sp, name](const Args& a) { V out; sp->call_method(name, a, out); return out; });
        return V();
    }
    V property(Sym n, bool& found) override {
        found = true;
        if (n.str() == "pattern") return V(src);
        if (n.str() == "flags") return V(double(flags));
        if (n.str() == "groups") return V(double(re.groups));
        found = false; return V();
    }
};
V re_compile(const V& pat, int flags) {
    if (as<Pattern>(pat)) return pat;
    auto p = std::make_shared<Pattern>();
    p->src = pat.str(); p->flags = flags;
    try { p->re = rx::compile(p->src, flags); }
    catch (std::exception& e) { throw PyError("error", std::string("bad pattern: ") + e.what()); }
    return V::inst(p);
}
V re_module() {
    V m = mod("re");
    M(m)->fn("compile", [](const Args& a) { static const V z(0.0); return re_compile(a.pos.at(0), int(a.get(1, Sym("flags"), &z).num())); });
    for (const char* f : {"search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split"}) {
        std::string fn = f;
        M(m)->fn(f, [fn](const Args& a) {
            int fl = 0; for (auto& [k, v] : a.kw) if (k.str() == "flags") fl = int(v.num());
            V p = re_compile(a.pos.at(0), fl);
            Args rest; for (size_t i = 1; i < a.pos.size(); ++i) rest.pos.push_back(a.pos[i]);
            for (auto& kv : a.kw) if (kv.first.str() != "flags") rest.kw.push_back(kv);
            return callm(p, Sym(fn), rest);
        });
    }
    M(m)->fn("escape", [](const Args& a) {
        static const std::string special = "\\.^$*+?{}[]|()";
        std::string s = a.pos.at(0).str(), o;
        for (char c : s) { if (special.find(c) != std::string::npos) o += '\\'; o += c; }
        return V(o);
    });
    M(m)->add("IGNORECASE", V(2.0)); M(m)->add("I", V(2.0)); M(m)->add("MULTILINE", V(8.0)); M(m)->add("M", V(8.0));
    M(m)->add("DOTALL", V(16.0)); M(m)->add("S", V(16.0)); M(m)->add("UNICODE", V(32.0)); M(m)->add("U", V(32.0));
    M(m)->add("error", py::exc_type(V("error")));
    return m;
}

// sys: real process facts for the UI; _getframe stays the simulation's frame emulation
V sys_module() {
    V m = mod("sys");
    Module* d = M(m);
    std::string exe;
#ifdef _WIN32
    wchar_t buf[MAX_PATH]; DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
    exe = p8(fs::path(std::wstring(buf, n)));
#endif
    d->add("executable", V(exe));
    d->add("frozen", V(true));          // packaged native build (python checks getattr(sys, "frozen", False))
    d->add("argv", V::list({V(exe)}));
#ifdef _WIN32
    d->add("platform", V("win32"));
#else
    d->add("platform", V("linux"));
#endif
#ifdef __ANDROID__
    d->fn("getandroidapilevel", [](const Args&) { return V(double(SDL_GetAndroidSDKVersion())); });
#endif
    d->add("version", V("3.8.10 (PvZ PvP native C++ build)"));
    d->add("version_info", V::tuple({V(3.0), V(8.0), V(10.0), V("final"), V(0.0)}));
    d->add("maxsize", V(9007199254740991.0));
    d->add("byteorder", V("little"));
    d->add("path", V::list());
    d->add("modules", py::loaded_modules());   // shared with note_module_loaded
    d->add("stdout", py::noop_module(V("stdout")));
    d->add("stderr", py::noop_module(V("stderr")));
    d->add("float_info", py::noop_module(V("float_info")));
    d->fn("_getframe", [](const Args&) { return py::getframe(); });
    d->fn("getrecursionlimit", [](const Args&) { return V(100000.0); });
    d->fn("setrecursionlimit", [](const Args&) { return V::none(); });
    d->fn("getsizeof", [](const Args&) { return V(64.0); });
    d->fn("exc_info", [](const Args&) { return V::tuple({V::none(), V::none(), V::none()}); });
    d->fn("settrace", [](const Args&) { return V::none(); });
    d->fn("gettrace", [](const Args&) { return V::none(); });
    d->fn("intern", [](const Args& a) { return a.pos.at(0); });
    d->fn("exit", [](const Args&) -> V { throw PyError("SystemExit", "exit"); });
    return m;
}

V uuid_module() {
    V m = mod("uuid");
    M(m)->fn("uuid4", [](const Args&) {
        uint8_t b[16];
        for (auto& x : b) x = uint8_t(sysrng()() & 255);
        b[6] = uint8_t((b[6] & 0x0F) | 0x40); b[8] = uint8_t((b[8] & 0x3F) | 0x80);
        char hex[33]; for (int i = 0; i < 16; ++i) snprintf(hex + 2 * i, 3, "%02x", b[i]);
        std::string h(hex, 32);
        std::string str = h.substr(0, 8) + "-" + h.substr(8, 4) + "-" + h.substr(12, 4) + "-" + h.substr(16, 4) + "-" + h.substr(20);
        V u = mod("UUID");
        M(u)->add("hex", V(h));
        M(u)->fn("__str__", [str](const Args&) { return V(str); });
        return u;
    });
    return m;
}

// colorsys (CPython Lib/colorsys.py formulas)
V colorsys_module() {
    V m = mod("colorsys");
    M(m)->fn("rgb_to_hsv", [](const Args& a) {
        double r = a.pos.at(0).num(), g = a.pos.at(1).num(), b = a.pos.at(2).num();
        double maxc = std::max({r, g, b}), minc = std::min({r, g, b});
        double v = maxc;
        if (minc == maxc) return V::tuple({V(0.0), V(0.0), V(v)});
        double s = (maxc - minc) / maxc;
        double rc = (maxc - r) / (maxc - minc), gc = (maxc - g) / (maxc - minc), bc = (maxc - b) / (maxc - minc);
        double h = r == maxc ? bc - gc : g == maxc ? 2.0 + rc - bc : 4.0 + gc - rc;
        h = py::mod(h / 6.0, 1.0);
        return V::tuple({V(h), V(s), V(v)});
    });
    M(m)->fn("hsv_to_rgb", [](const Args& a) {
        double h = a.pos.at(0).num(), s = a.pos.at(1).num(), v = a.pos.at(2).num();
        if (s == 0.0) return V::tuple({V(v), V(v), V(v)});
        int i = int(h * 6.0);
        double f = (h * 6.0) - i, p = v * (1.0 - s), q = v * (1.0 - s * f), t = v * (1.0 - s * (1.0 - f));
        i = ((i % 6) + 6) % 6;
        switch (i) {
            case 0: return V::tuple({V(v), V(t), V(p)});
            case 1: return V::tuple({V(q), V(v), V(p)});
            case 2: return V::tuple({V(p), V(v), V(t)});
            case 3: return V::tuple({V(p), V(q), V(v)});
            case 4: return V::tuple({V(t), V(p), V(v)});
            default: return V::tuple({V(v), V(p), V(q)});
        }
    });
    M(m)->fn("rgb_to_hls", [](const Args& a) {
        double r = a.pos.at(0).num(), g = a.pos.at(1).num(), b = a.pos.at(2).num();
        double maxc = std::max({r, g, b}), minc = std::min({r, g, b});
        double l = (minc + maxc) / 2.0;
        if (minc == maxc) return V::tuple({V(0.0), V(l), V(0.0)});
        double s = l <= 0.5 ? (maxc - minc) / (maxc + minc) : (maxc - minc) / (2.0 - maxc - minc);
        double rc = (maxc - r) / (maxc - minc), gc = (maxc - g) / (maxc - minc), bc = (maxc - b) / (maxc - minc);
        double h = r == maxc ? bc - gc : g == maxc ? 2.0 + rc - bc : 4.0 + gc - rc;
        h = py::mod(h / 6.0, 1.0);
        return V::tuple({V(h), V(l), V(s)});
    });
    M(m)->fn("hls_to_rgb", [](const Args& a) {
        double h = a.pos.at(0).num(), l = a.pos.at(1).num(), s = a.pos.at(2).num();
        if (s == 0.0) return V::tuple({V(l), V(l), V(l)});
        double m2 = l <= 0.5 ? l * (1.0 + s) : l + s - (l * s), m1 = 2.0 * l - m2;
        auto v = [&](double hue) {
            hue = py::mod(hue, 1.0);
            if (hue < 1.0 / 6.0) return m1 + (m2 - m1) * hue * 6.0;
            if (hue < 0.5) return m2;
            if (hue < 2.0 / 3.0) return m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0;
            return m1;
        };
        return V::tuple({V(v(h + 1.0 / 3.0)), V(v(h)), V(v(h - 1.0 / 3.0))});
    });
    return m;
}

// tempfile.NamedTemporaryFile / TemporaryDirectory (real stdio descriptors)
struct TempFile : PyObj {
    std::string path; bool del = true, binary = true; native_file::File f;
    ~TempFile() override { try { f.close(); } catch (...) {} if (del) { std::error_code ec; fs::remove(u8p(path), ec); } }
    const char* type_name() const override { return "_TemporaryFileWrapper"; }
    V property(Sym n, bool& found) override { found = n.str() == "name"; return found ? V(path) : V(); }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "write") { out = V(double(f.write(binary ? py::bytes_data(a.pos.at(0)) : a.pos.at(0).str()))); return true; }
        if (n == "read") { std::string data = f.read(a.pos.empty() ? -1 : int64_t(a.pos[0].num())); out = binary ? V::bytes(data) : V(data); return true; }
        if (n == "fileno") { out = V(f.descriptor()); return true; }
        if (n == "flush") { f.flush(); out = V::none(); return true; }
        if (n == "seek") { out = V(double(f.seek(int64_t(a.pos.at(0).num()), a.pos.size() > 1 ? int(a.pos[1].num()) : SEEK_SET))); return true; }
        if (n == "tell") { out = V(double(f.tell())); return true; }
        if (n == "close") { f.close(); if (del) { std::error_code ec; fs::remove(u8p(path), ec); } out = V::none(); return true; }
        if (n == "__enter__") { (void)f.descriptor(); out = self(); return true; }
        if (n == "__exit__") { V r; call_method(Sym("close"), Args{}, r); out = V(false); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<TempFile>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", name.str()); return out; });
    }
};
struct TempDir : PyObj {
    std::string path;
    ~TempDir() override { std::error_code ec; fs::remove_all(u8p(path), ec); }
    const char* type_name() const override { return "TemporaryDirectory"; }
    V property(Sym n, bool& found) override { found = n.str() == "name"; return found ? V(path) : V(); }
    bool call_method(Sym name, const Args&, V& out) override {
        const std::string& n = name.str();
        if (n == "__enter__") { out = V(path); return true; }
        if (n == "__exit__" || n == "cleanup") { std::error_code ec; fs::remove_all(u8p(path), ec); out = V(false); return true; }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<TempDir>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", name.str()); return out; });
    }
};
std::string temp_name(const std::string& dir, const std::string& prefix, const std::string& suffix) {
    fs::path base = dir.empty() ? fs::temp_directory_path() : u8p(dir);
    return p8(base / u8p(prefix + std::to_string(sysrng()() % 100000000000ull) + suffix));
}
// array.array: typed sample buffers (UI click sound); stored as doubles, packed on tobytes()
struct ArrayObj : PyObj {
    char code = 'd'; std::vector<double> v;
    const char* type_name() const override { return "array"; }
    size_t length() override { return v.size(); }
    V iterate() override { std::vector<V> o; for (double x : v) o.emplace_back(x); return V::list(o); }
    bool call_method(Sym name, const Args& a, V& out) override {
        const std::string& n = name.str();
        if (n == "append") { v.push_back(a.pos.at(0).num()); out = V::none(); return true; }
        if (n == "extend") { for (auto& x : py::iter_list(a.pos.at(0)).items()) v.push_back(x.num()); out = V::none(); return true; }
        if (n == "__len__") { out = V(double(v.size())); return true; }
        if (n == "__getitem__") { int64_t i = int64_t(a.pos.at(0).num()); if (i < 0) i += int64_t(v.size()); out = V(v.at(size_t(i))); return true; }
        if (n == "tolist") { out = iterate(); return true; }
        if (n == "tobytes") {
            std::string b;
            auto put = [&](const void* p, size_t k) { b.append(reinterpret_cast<const char*>(p), k); };
            for (double x : v) switch (code) {
                case 'b': { int8_t y = int8_t(x); put(&y, 1); break; }
                case 'B': { uint8_t y = uint8_t(x); put(&y, 1); break; }
                case 'h': { int16_t y = int16_t(x); put(&y, 2); break; }
                case 'H': { uint16_t y = uint16_t(x); put(&y, 2); break; }
                case 'i': case 'l': { int32_t y = int32_t(x); put(&y, 4); break; }
                case 'I': case 'L': { uint32_t y = uint32_t(x); put(&y, 4); break; }
                case 'q': { int64_t y = int64_t(x); put(&y, 8); break; }
                case 'f': { float y = float(x); put(&y, 4); break; }
                default: put(&x, 8);
            }
            out = V(b); return true;
        }
        return false;
    }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<ArrayObj>(shared_from_this());
        return V::func([sp, name](const Args& a) { V out; if (!sp->call_method(name, a, out)) throw PyError("AttributeError", name.str()); return out; });
    }
};
V array_module() {
    V m = mod("array");
    M(m)->fn("array", [](const Args& a) {
        auto o = std::make_shared<ArrayObj>();
        o->code = a.pos.at(0).str().empty() ? 'd' : a.pos[0].str()[0];
        if (a.pos.size() > 1) for (auto& x : py::iter_list(a.pos[1]).items()) o->v.push_back(x.num());
        return V::inst(o);
    });
    return m;
}

V tempfile2_module() {
    V m = tempfile_module();
    M(m)->fn("NamedTemporaryFile", [](const Args& a) {
        auto t = std::make_shared<TempFile>();
        std::string suffix, prefix = "tmp", dir, mode = "w+b";
        for (auto& [k, v] : a.kw) {
            const std::string& n = k.str();
            if (n == "suffix" && !v.is_none()) suffix = v.str();
            else if (n == "prefix" && !v.is_none()) prefix = v.str();
            else if (n == "dir" && !v.is_none()) dir = path_str(v);
            else if (n == "delete") t->del = v.truthy();
            else if (n == "mode" && !v.is_none()) mode = v.str();
        }
        t->path = temp_name(dir, prefix, suffix);
        t->binary = mode.find('b') != std::string::npos;
        t->f.open(u8p(t->path), mode);
        return V::inst(t);
    });
    M(m)->fn("TemporaryDirectory", [](const Args& a) {
        auto t = std::make_shared<TempDir>();
        std::string dir, prefix = "tmp";
        for (auto& [k, v] : a.kw) { if (k.str() == "dir" && !v.is_none()) dir = path_str(v); if (k.str() == "prefix" && !v.is_none()) prefix = v.str(); }
        t->path = temp_name(dir, prefix, "");
        fs::create_directories(u8p(t->path));
        return V::inst(t);
    });
    return m;
}

V ctypes_module() {
    // Windows DPI / IME helpers in the UI: inert objects (SDL handles DPI and IME)
    return py::noop_module(V("ctypes"));
}

V resource_module72() {
    V module=mod("resource");M(module)->add("RUSAGE_SELF",V(0));
    M(module)->fn("getrusage",[](const Args& args) {
        if(!args.pos.empty() && args.pos[0]!=V(0))throw PyError("ValueError","Only RUSAGE_SELF is supported");
        double user=0,system=0,peak_kib=0;
#ifdef _WIN32
        FILETIME created,exited,kernel,u;
        PROCESS_MEMORY_COUNTERS counters{};counters.cb=sizeof(counters);
        if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&u) ||
            !GetProcessMemoryInfo(GetCurrentProcess(),&counters,sizeof(counters)))throw PyError("OSError","Process counters unavailable");
        auto seconds=[](FILETIME t){ULARGE_INTEGER v;v.LowPart=t.dwLowDateTime;v.HighPart=t.dwHighDateTime;return double(v.QuadPart)/1e7;};
        user=seconds(u);system=seconds(kernel);peak_kib=double(counters.PeakWorkingSetSize)/1024.;
#else
        struct rusage usage{};if(getrusage(RUSAGE_SELF,&usage))throw PyError("OSError","getrusage failed");
        user=double(usage.ru_utime.tv_sec)+usage.ru_utime.tv_usec/1e6;
        system=double(usage.ru_stime.tv_sec)+usage.ru_stime.tv_usec/1e6;peak_kib=usage.ru_maxrss;
#endif
        V out=py::new_object();pvz::setattr(out,SY("ru_utime"),V(user));pvz::setattr(out,SY("ru_stime"),V(system));
        pvz::setattr(out,SY("ru_maxrss"),V(peak_kib));return out;
    });
    return module;
}

}  // namespace

// modkit.android.*: the python APK's platform glue, as the native build needs it (no jnius)
V modkit_module() {
    V pa = mod("modkit.android.platform_android");
    M(pa)->fn("set_fullscreen", [](const Args&) {
        SDL_Window* w = SDL_GetKeyboardFocus(); if (!w) w = SDL_GetMouseFocus();
        if (w) SDL_SetWindowFullscreen(w, SDL_WINDOW_FULLSCREEN_DESKTOP);
        return V(true);
    });
    M(pa)->fn("export_performance", [](const Args& a) {
        auto source=fs::absolute(u8p(path_str(a.pos.at(0))));
        if(!fs::is_regular_file(source))throw PyError("FileNotFoundError","Performance report is missing");
#ifdef __ANDROID__
        const char* external=SDL_AndroidGetExternalStoragePath();
        if(!external)throw PyError("OSError","External app report directory unavailable");
        auto folder=u8p(external)/"reports";fs::create_directories(folder);
        auto destination=folder/source.filename();
        if(source!=destination) {
            if(fs::exists(destination))destination=folder/(p8(source.stem())+"-"+std::to_string(SDL_GetTicks64())+p8(source.extension()));
            fs::copy_file(source,destination,fs::copy_options::none);
            if(fs::file_size(source)!=fs::file_size(destination))throw PyError("OSError","Performance report export verification failed");
        }
        return V(p8(destination));
#else
        return V(p8(source));
#endif
    });
    V th = mod("modkit.android.touch_hotfix");
    M(th)->add("GUARD", py_dict({{V("on"), V(true)}}));   // SDL_HINT_TOUCH_MOUSE_EVENTS=0 already drops synthetic mice
    M(th)->fn("install", [](const Args&) { return V::none(); });
    M(th)->fn("release", [](const Args&) { return V(true); });
    V og = mod("modkit.android.original_game");
    M(og)->fn("pvp_display", [](const Args&) { return V::none(); });
    M(og)->fn("asset_root", [](const Args&) { return py::path_new(Args{V(".")}); });
    V android = mod("modkit.android");
    M(android)->add("platform_android", pa); M(android)->add("touch_hotfix", th); M(android)->add("original_game", og);
    V modkit = mod("modkit");
    M(modkit)->add("android", android);
    // modkit.pvp.<name>: the same translated client modules as pvp.<name> (imported on first access)
    struct PvpPackage : Module {
        V property(Sym n, bool& found) override {
            V v = Module::property(n, found);
            if (found) return v;
            try { v = py::import_pvp_module(n.str()); } catch (const PyError& e) { if (!e.matches("ModuleNotFoundError")) throw; return V(); }
            attrs.emplace_back(n, v);
            found = true;
            return v;
        }
    };
    auto pkg = std::make_shared<PvpPackage>();
    pkg->name = "modkit.pvp";
    M(modkit)->add("pvp", V::inst(pkg));
    return modkit;
}
void install_netstd();
void register_android_native_modules();
void install_stdlib() {
    py::register_module("resource",resource_module72());
    py::register_module("modkit", modkit_module());
    py::register_module("os", os_module());
    py::register_module("time", py_time_module());
    py::register_module("io", io_module());
    py::register_module("base64", base64_module());
    py::register_module("zlib", zlib_module());
    py::register_module("json", json_module());
    py::register_module("secrets", secrets_module());
    py::register_module("hmac", hmac_module());
    py::register_module("struct", struct_module());
    py::register_module("platform", platform_module());
    py::register_module("errno", errno_module());
    py::register_module("traceback", traceback_module());
    py::register_module("shutil", shutil_module());
    py::register_module("threading", threading_module());
    py::register_module("queue", queue_module());
    install_netstd();   // real threading / queue / socket / select (src/ui/netstd.cpp)

    py::register_module("unicodedata", unicodedata_module());
    py::register_module("ctypes", ctypes_module());
    py::register_module("tempfile", tempfile2_module());
    py::register_module("colorsys", colorsys_module());
    py::register_module("re", re_module());
    py::register_module("array", array_module());
    py::register_module("sys", sys_module());
    { V im = mod("importlib"); M(im)->fn("import_module", [](const Args& a) { return py::import_pvp_module(a.pos.at(0).str()); });
      // importlib.util file loading: only a production client file <...>/modkit/pvp/<name>.py has a native
      // equivalent (the translated module, shared rather than a fresh copy). Anything else (server/relay_server.py,
      // android probes, generated scripts) has no native code and fails loudly instead of yielding a stub.
      V util = mod("importlib.util");
      M(util)->fn("spec_from_file_location", [](const Args& a) {
          V spec = py::new_object();
          pvz::setattr(spec, Sym("name"), a.pos.at(0));
          pvz::setattr(spec, Sym("origin"), V(path_str(a.pos.at(1))));
          V loader = mod("importlib.loader");
          M(loader)->fn("exec_module", [](const Args&) { return V::none(); });   // native module already initialised
          pvz::setattr(spec, Sym("loader"), loader);
          return spec;
      });
      M(util)->fn("module_from_spec", [](const Args& a) {
          std::string origin = path_str(pvz::getattr(a.pos.at(0), Sym("origin")));
          fs::path p = u8p(origin);
          if (p.extension() == ".py" && p.parent_path().filename() == "pvp" && p.parent_path().parent_path().filename() == "modkit")
              return py::import_pvp_module(p8(p.stem()));
          if(p.extension()==".py" && p.stem()=="performance_probe" && p.parent_path().filename()=="android" && p.parent_path().parent_path().filename()=="modkit")
              return py::stdlib_module(V("modkit.android.performance_probe"));
          // test harnesses may provide out-of-process fixtures (the Python relay server); the game registers none
          try { V m = py::native_hook(V("importlib.file_module"), Args{V(origin)}); if (!m.is_none()) return m; }
          catch (const PyError& e) { if (!e.matches("NotImplementedError")) throw; }
          throw PyError("NotImplementedError", "importlib.util: no native module for " + origin);
      });
      pvz::setattr(im, Sym("util"), util);
      py::register_module("importlib", im); }
    py::register_module("uuid", uuid_module());
    register_android_native_modules();
}

}  // namespace pvz::pg
