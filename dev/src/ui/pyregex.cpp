#include "ui/pyregex.h"
#include <functional>
#include <stdexcept>

namespace pvz::rx {

std::u32string decode(const std::string& s) {
    std::u32string o;
    o.reserve(s.size());
    for (size_t i = 0; i < s.size();) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        char32_t cp; int n;
        if (c < 0x80) { cp = c; n = 1; }
        else if ((c >> 5) == 6) { cp = c & 0x1F; n = 2; }
        else if ((c >> 4) == 14) { cp = c & 0x0F; n = 3; }
        else if ((c >> 3) == 30) { cp = c & 0x07; n = 4; }
        else { cp = c; n = 1; }
        for (int k = 1; k < n && i + k < s.size(); ++k) cp = (cp << 6) | (static_cast<unsigned char>(s[i + k]) & 0x3F);
        o.push_back(cp);
        i += size_t(n);
    }
    return o;
}
std::string encode(const std::u32string& s, size_t a, size_t b) {
    std::string o;
    for (size_t i = a; i < b && i < s.size(); ++i) {
        char32_t c = s[i];
        if (c < 0x80) o += char(c);
        else if (c < 0x800) { o += char(0xC0 | (c >> 6)); o += char(0x80 | (c & 0x3F)); }
        else if (c < 0x10000) { o += char(0xE0 | (c >> 12)); o += char(0x80 | ((c >> 6) & 0x3F)); o += char(0x80 | (c & 0x3F)); }
        else { o += char(0xF0 | (c >> 18)); o += char(0x80 | ((c >> 12) & 0x3F)); o += char(0x80 | ((c >> 6) & 0x3F)); o += char(0x80 | (c & 0x3F)); }
    }
    return o;
}

enum Kind { LIT, ANY, SET, SEQ, ALT, GROUP, REPEAT, BOL, EOL, WORDB, NWORDB, LOOK, BACKREF, BOS, EOS };
struct Range { char32_t a, b; };
struct Node {
    Kind k;
    char32_t ch = 0;
    std::vector<Range> ranges; bool neg = false; int cls = 0;   // cls bits: 1 \d 2 \w 4 \s 8 \D 16 \W 32 \S
    std::vector<std::shared_ptr<Node>> kids;
    int group = -1;
    int mn = 0, mx = -1; bool greedy = true;
    bool ahead = true, negate = false;
};
using P = std::shared_ptr<Node>;

static bool is_digit(char32_t c) { return c >= '0' && c <= '9'; }
static bool is_word(char32_t c) { return is_digit(c) || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_' || (c >= 0x80 && c != 0x3000 && !(c >= 0x3000 && c <= 0x303F) && !(c >= 0xFF00 && c <= 0xFF0F)); }
static bool is_space(char32_t c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v' || c == 0x3000 || c == 0xA0; }
static char32_t lower(char32_t c) { return (c >= 'A' && c <= 'Z') ? c + 32 : c; }

struct Parser {
    std::u32string p; size_t i = 0; int groups = 0; int flags = 0;
    std::vector<std::pair<std::string, int>> names;
    [[noreturn]] void bad(const char* m) { throw std::runtime_error(std::string(m) + " at position " + std::to_string(i)); }
    bool eof() const { return i >= p.size(); }
    P alt() {
        auto n = std::make_shared<Node>(); n->k = ALT;
        n->kids.push_back(seq());
        while (!eof() && p[i] == '|') { ++i; n->kids.push_back(seq()); }
        return n->kids.size() == 1 ? n->kids[0] : n;
    }
    P seq() {
        auto n = std::make_shared<Node>(); n->k = SEQ;
        while (!eof() && p[i] != '|' && p[i] != ')') {
            P a = atom();
            if (!a) continue;
            n->kids.push_back(quant(a));
        }
        return n;
    }
    int number() { int v = 0; bool any = false; while (!eof() && is_digit(p[i])) { v = v * 10 + int(p[i++] - '0'); any = true; } return any ? v : -1; }
    P quant(P a) {
        while (!eof()) {
            int mn, mx;
            char32_t c = p[i];
            if (c == '*') { mn = 0; mx = -1; ++i; }
            else if (c == '+') { mn = 1; mx = -1; ++i; }
            else if (c == '?') { mn = 0; mx = 1; ++i; }
            else if (c == '{') {
                size_t save = i; ++i;
                int a1 = number();
                if (a1 < 0 && !(i < p.size() && p[i] == ',')) { i = save; return a; }
                mn = a1 < 0 ? 0 : a1; mx = mn;
                if (!eof() && p[i] == ',') { ++i; int b = number(); mx = b; }
                if (eof() || p[i] != '}') { i = save; return a; }
                ++i;
            } else return a;
            auto r = std::make_shared<Node>(); r->k = REPEAT; r->mn = mn; r->mx = mx; r->kids.push_back(a);
            if (!eof() && p[i] == '?') { r->greedy = false; ++i; }
            a = r;
        }
        return a;
    }
    char32_t escape_char(char32_t c) {
        switch (c) { case 'n': return '\n'; case 't': return '\t'; case 'r': return '\r'; case 'f': return '\f'; case 'v': return '\v'; case '0': return 0; }
        return c;
    }
    int class_bit(char32_t c) { switch (c) { case 'd': return 1; case 'w': return 2; case 's': return 4; case 'D': return 8; case 'W': return 16; case 'S': return 32; } return 0; }
    P set() {
        auto n = std::make_shared<Node>(); n->k = SET;
        if (!eof() && p[i] == '^') { n->neg = true; ++i; }
        bool first = true;
        while (!eof() && (p[i] != ']' || first)) {
            first = false;
            char32_t a = p[i++];
            if (a == '\\' && !eof()) {
                char32_t e = p[i++];
                if (int b = class_bit(e)) { n->cls |= b; continue; }
                a = escape_char(e);
            }
            char32_t b = a;
            if (i + 1 < p.size() && p[i] == '-' && p[i + 1] != ']') {
                ++i; b = p[i++];
                if (b == '\\' && !eof()) b = escape_char(p[i++]);
            }
            n->ranges.push_back({a, b});
        }
        if (eof()) bad("unterminated character set");
        ++i;
        return n;
    }
    P atom() {
        char32_t c = p[i++];
        auto n = std::make_shared<Node>();
        switch (c) {
            case '.': n->k = ANY; return n;
            case '^': n->k = BOL; return n;
            case '$': n->k = EOL; return n;
            case '[': return set();
            case '(': {
                if (!eof() && p[i] == '?') {
                    ++i;
                    if (eof()) bad("unexpected end of pattern");
                    char32_t t = p[i++];
                    if (t == ':') { P x = alt(); close(); auto g = std::make_shared<Node>(); g->k = GROUP; g->group = -1; g->kids.push_back(x); return g; }
                    if (t == '=' || t == '!') { P x = alt(); close(); n->k = LOOK; n->ahead = true; n->negate = t == '!'; n->kids.push_back(x); return n; }
                    if (t == '<' && !eof() && (p[i] == '=' || p[i] == '!')) { bool ng = p[i++] == '!'; P x = alt(); close(); n->k = LOOK; n->ahead = false; n->negate = ng; n->kids.push_back(x); return n; }
                    if (t == 'P' && !eof() && p[i] == '<') {
                        ++i; std::string name;
                        while (!eof() && p[i] != '>') name += char(p[i++]);
                        ++i;
                        int g = ++groups; names.emplace_back(name, g);
                        P x = alt(); close(); n->k = GROUP; n->group = g; n->kids.push_back(x); return n;
                    }
                    if (t == '#') { while (!eof() && p[i] != ')') ++i; ++i; return nullptr; }
                    // inline flags (?i) (?m) (?s)
                    --i;
                    while (!eof() && p[i] != ')') { char32_t f = p[i++]; if (f == 'i') flags |= 2; else if (f == 'm') flags |= 8; else if (f == 's') flags |= 16; }
                    ++i;
                    return nullptr;
                }
                int g = ++groups;
                P x = alt(); close();
                n->k = GROUP; n->group = g; n->kids.push_back(x); return n;
            }
            case '\\': {
                if (eof()) bad("bad escape (end of pattern)");
                char32_t e = p[i++];
                if (int b = class_bit(e)) { n->k = SET; n->cls = b; return n; }
                if (e == 'b') { n->k = WORDB; return n; }
                if (e == 'B') { n->k = NWORDB; return n; }
                if (e == 'A') { n->k = BOS; return n; }
                if (e == 'Z') { n->k = EOS; return n; }
                if (is_digit(e) && e != '0') { n->k = BACKREF; n->group = int(e - '0'); return n; }
                n->k = LIT; n->ch = escape_char(e); return n;
            }
            default: n->k = LIT; n->ch = c; return n;
        }
    }
    void close() { if (eof() || p[i] != ')') bad("missing ), unterminated subpattern"); ++i; }
};

Regex compile(const std::string& pattern, int flags) {
    Parser ps; ps.p = decode(pattern); ps.flags = flags;
    Regex r;
    r.root = ps.alt();
    if (!ps.eof()) throw std::runtime_error("unbalanced parenthesis");
    r.groups = ps.groups; r.names = ps.names; r.flags = ps.flags;
    return r;
}

namespace {
struct M {
    const std::u32string& s; int flags; std::vector<long>& cap;
    bool icase() const { return flags & 2; }
    bool set_has(const Node& n, char32_t c) const {
        bool in = false;
        if ((n.cls & 1) && is_digit(c)) in = true;
        if ((n.cls & 2) && is_word(c)) in = true;
        if ((n.cls & 4) && is_space(c)) in = true;
        if ((n.cls & 8) && !is_digit(c)) in = true;
        if ((n.cls & 16) && !is_word(c)) in = true;
        if ((n.cls & 32) && !is_space(c)) in = true;
        for (auto& r : n.ranges) {
            if (c >= r.a && c <= r.b) { in = true; break; }
            if (icase()) { char32_t l = lower(c); if (l >= lower(r.a) && l <= lower(r.b)) { in = true; break; } }
        }
        return n.neg ? !in : in;
    }
    bool word_at(size_t pos) const { return pos < s.size() && is_word(s[pos]); }
    // match node at pos, then continuation k(newpos)
    bool m(const Node& n, size_t pos, const std::function<bool(size_t)>& k) {
        switch (n.k) {
            case LIT: if (pos < s.size() && (s[pos] == n.ch || (icase() && lower(s[pos]) == lower(n.ch)))) return k(pos + 1); return false;
            case ANY: if (pos < s.size() && (s[pos] != '\n' || (flags & 16))) return k(pos + 1); return false;
            case SET: if (pos < s.size() && set_has(n, s[pos])) return k(pos + 1); return false;
            case BOS: return pos == 0 && k(pos);
            case EOS: return pos == s.size() && k(pos);
            case BOL: return (pos == 0 || ((flags & 8) && s[pos - 1] == '\n')) && k(pos);
            case EOL: return (pos == s.size() || (pos + 1 == s.size() && s[pos] == '\n') || ((flags & 8) && s[pos] == '\n')) && k(pos);
            case WORDB: case NWORDB: {
                bool b = (pos > 0 && word_at(pos - 1)) != word_at(pos);
                return (n.k == WORDB ? b : !b) && k(pos);
            }
            case SEQ: return seq(n, 0, pos, k);
            case ALT: for (auto& c : n.kids) if (m(*c, pos, k)) return true; return false;
            case GROUP: {
                if (n.group < 0) return m(*n.kids[0], pos, k);
                long o0 = cap[2 * n.group], o1 = cap[2 * n.group + 1];
                bool r = m(*n.kids[0], pos, [&](size_t e) {
                    long s0 = cap[2 * n.group], s1 = cap[2 * n.group + 1];
                    cap[2 * n.group] = long(pos); cap[2 * n.group + 1] = long(e);
                    if (k(e)) return true;
                    cap[2 * n.group] = s0; cap[2 * n.group + 1] = s1;
                    return false;
                });
                if (!r) { cap[2 * n.group] = o0; cap[2 * n.group + 1] = o1; }
                return r;
            }
            case REPEAT: return rep(n, pos, 0, size_t(-1), k);
            case LOOK: {
                std::vector<long> save = cap;
                bool found;
                if (n.ahead) found = m(*n.kids[0], pos, [](size_t) { return true; });
                else {
                    found = false;
                    for (size_t st = pos + 1; st-- > 0 && !found;)
                        found = m(*n.kids[0], st, [pos](size_t e) { return e == pos; });
                }
                if (n.negate) { cap = save; return !found && k(pos); }
                if (!found) { cap = save; return false; }
                if (k(pos)) return true;
                cap = save;
                return false;
            }
            case BACKREF: {
                long a = cap[2 * n.group], b = cap[2 * n.group + 1];
                if (a < 0) return false;
                size_t len = size_t(b - a);
                if (pos + len > s.size()) return false;
                for (size_t t = 0; t < len; ++t) if (s[pos + t] != s[size_t(a) + t]) return false;
                return k(pos + len);
            }
        }
        return false;
    }
    bool seq(const Node& n, size_t idx, size_t pos, const std::function<bool(size_t)>& k) {
        if (idx == n.kids.size()) return k(pos);
        return m(*n.kids[idx], pos, [&](size_t e) { return seq(n, idx + 1, e, k); });
    }
    bool rep(const Node& n, size_t pos, int count, size_t last, const std::function<bool(size_t)>& k) {
        bool can_more = n.mx < 0 || count < n.mx;
        auto more = [&]() {
            if (!can_more) return false;
            return m(*n.kids[0], pos, [&](size_t e) {
                if (e == pos && count >= n.mn) return false;   // empty iteration: stop looping
                return rep(n, e, count + 1, pos, k);
            });
        };
        (void)last;
        if (count < n.mn) return more();
        if (n.greedy) return more() || k(pos);
        return k(pos) || more();
    }
};
}  // namespace

Match search(const Regex& re, const std::u32string& text, size_t start, bool anchored, bool full) {
    Match out;
    std::vector<long> cap(size_t(2 * (re.groups + 1)), -1);
    M mm{text, re.flags, cap};
    for (size_t st = start; st <= text.size(); ++st) {
        std::fill(cap.begin(), cap.end(), -1);
        size_t end = 0;
        bool ok = mm.m(*re.root, st, [&](size_t e) { if (full && e != text.size()) return false; end = e; return true; });
        if (ok) {
            cap[0] = long(st); cap[1] = long(end);
            out.ok = true; out.spans = cap;
            return out;
        }
        if (anchored) break;
    }
    return out;
}

}  // namespace pvz::rx
