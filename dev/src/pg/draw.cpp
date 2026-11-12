// pygame.draw: primitives write the colour straight into the pixels (no blending), like pygame.
#include "pg/pg.h"
#include "core/pyops.h"
#include <algorithm>
#include <cmath>
#include <vector>
#include <map>

namespace pvz::pg {
namespace {

struct Canvas {
    Surface* s;
    uint32_t px;
    SDL_Rect clip;
    int minx = INT32_MAX, miny = INT32_MAX, maxx = INT32_MIN, maxy = INT32_MIN;
    Canvas(Surface* surface, SDL_Color c) : s(surface) {
        px = (uint32_t(c.a) << 24) | (uint32_t(c.r) << 16) | (uint32_t(c.g) << 8) | c.b;
        if (!s->srcalpha) px |= 0xFF000000u;
        SDL_GetClipRect(s->s, &clip);
    }
    void set(int x, int y) {
        if (x < clip.x || y < clip.y || x >= clip.x + clip.w || y >= clip.y + clip.h) return;
        reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(s->s->pixels) + size_t(y) * s->s->pitch)[x] = px;
        minx = std::min(minx, x); miny = std::min(miny, y); maxx = std::max(maxx, x); maxy = std::max(maxy, y);
    }
    void hline(int x0, int x1, int y) {
        if (x0 > x1) std::swap(x0, x1);
        if (y < clip.y || y >= clip.y + clip.h) return;
        x0 = std::max(x0, clip.x); x1 = std::min(x1, clip.x + clip.w - 1);
        if (x0 > x1) return;
        uint32_t* r = reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(s->s->pixels) + size_t(y) * s->s->pitch);
        for (int x = x0; x <= x1; ++x) r[x] = px;
        minx = std::min(minx, x0); miny = std::min(miny, y); maxx = std::max(maxx, x1); maxy = std::max(maxy, y);
    }
    void vline(int x, int y0, int y1) { if (y0 > y1) std::swap(y0, y1); for (int y = y0; y <= y1; ++y) set(x, y); }
    void line(int x0, int y0, int x1, int y1) {   // Bresenham, both ends inclusive
        // Match pygame-ce's integer midpoint and strict tie rules.
        int dx = std::abs(x1 - x0), dy = std::abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = (dx > dy ? dx : -dy) / 2;
        for (;;) {
            set(x0, y0);
            if (x0 == x1 && y0 == y1) break;
            int previous = err;
            if (previous > -dx) { err -= dy; x0 += sx; }
            if (previous < dy) { err += dx; y0 += sy; }
        }
    }
    void thick_line(int x0, int y0, int x1, int y1, int width) {
        if (width < 1) return;
        if (width == 1) { line(x0, y0, x1, y1); return; }
        // pygame: parallel lines offset across the minor axis
        bool steep = std::abs(y1 - y0) >= std::abs(x1 - x0);
        int lo = -(width - 1) / 2, hi = width / 2;
        for (int k = lo; k <= hi; ++k) {
            if (steep) line(x0 + k, y0, x1 + k, y1);
            else line(x0, y0 + k, x1, y1 + k);
        }
    }
    V bounds(int fx, int fy) const {
        if (maxx < minx) return make_rect(fx, fy, 0, 0);
        return make_rect(minx, miny, maxx - minx + 1, maxy - miny + 1);
    }
};

int iv(const V& v) { return int(v.num()); }
void pt(const V& p, int& x, int& y) { x = iv(p.idx(0)); y = iv(p.idx(1)); }

void fill_polygon(Canvas& c, const std::vector<std::pair<int, int>>& pts) {
    if (pts.empty()) return;
    int miny = pts[0].second, maxy = miny;
    for (auto& p : pts) { miny = std::min(miny, p.second); maxy = std::max(maxy, p.second); }
    size_t n = pts.size();
    std::vector<int> xs;
    for (int y = miny; y <= maxy; ++y) {
        xs.clear();
        for (size_t i = 0; i < n; ++i) {
            auto [x1, y1] = pts[i];
            auto [x2, y2] = pts[(i + 1) % n];
            if (y1 == y2) continue;
            if (y1 > y2) { std::swap(x1, x2); std::swap(y1, y2); }
            if (y >= y1 && y < y2) xs.push_back(int(std::floor(x1 + double(y - y1) * (x2 - x1) / (y2 - y1) + .5)));
            else if (y == maxy && y == y2 && y > y1) xs.push_back(x2);   // include the bottom edge like pygame
        }
        std::sort(xs.begin(), xs.end());
        for (size_t i = 0; i + 1 < xs.size(); i += 2) c.hline(xs[i], xs[i + 1], y);
    }
    // pygame also draws the horizontal edges and the outline
    for (size_t i = 0; i < n; ++i) c.line(pts[i].first, pts[i].second, pts[(i + 1) % n].first, pts[(i + 1) % n].second);
}

void ellipse_points(Canvas& c, int cx, int cy, int rx, int ry, bool filled, int ox, int oy) {
    // midpoint ellipse; (ox, oy) extend even-sized ellipses by one pixel
    if (rx < 0 || ry < 0) return;
    if (rx == 0 || ry == 0) { c.hline(cx - rx, cx + rx + ox, cy); c.vline(cx, cy - ry, cy + ry + oy); return; }
    long long a2 = (long long)rx * rx, b2 = (long long)ry * ry;
    long long x = 0, y = ry;
    long long px = 0, py = 2 * a2 * y;
    auto plot = [&](long long X, long long Y) {
        if (filled) {
            c.hline(int(cx - X), int(cx + X + ox), int(cy - Y));
            c.hline(int(cx - X), int(cx + X + ox), int(cy + Y + oy));
        } else {
            c.set(int(cx + X + ox), int(cy + Y + oy)); c.set(int(cx - X), int(cy + Y + oy));
            c.set(int(cx + X + ox), int(cy - Y)); c.set(int(cx - X), int(cy - Y));
        }
    };
    long long p = (long long)std::llround(b2 - a2 * ry + 0.25 * a2);
    while (px < py) {
        plot(x, y);
        ++x; px += 2 * b2;
        if (p < 0) p += b2 + px;
        else { --y; py -= 2 * a2; p += b2 + px - py; }
    }
    p = (long long)std::llround(b2 * (x + 0.5) * (x + 0.5) + a2 * (y - 1) * (y - 1) - a2 * b2);
    while (y >= 0) {
        plot(x, y);
        --y; py -= 2 * a2;
        if (p > 0) p += a2 - py;
        else { ++x; px += 2 * b2; p += a2 - py + px; }
    }
}

void draw_ellipse(Canvas& c, const IRect& r, int width) {
    if (r.w <= 0 || r.h <= 0) return;
    int rx = (r.w - 1) / 2, ry = (r.h - 1) / 2;
    int ox = (r.w % 2 == 0) ? 1 : 0, oy = (r.h % 2 == 0) ? 1 : 0;
    int cx = r.x + rx, cy = r.y + ry;
    if (width <= 0 || width * 2 >= std::min(r.w, r.h)) { ellipse_points(c, cx, cy, rx, ry, true, ox, oy); return; }
    for (int k = 0; k < width; ++k) ellipse_points(c, cx, cy, rx - k, ry - k, false, ox, oy);
}

void draw_circle(Canvas& c, int cx, int cy, int radius, int width) {
    if (radius < 1 || width < 0) return;
    // Filled and one-pixel circles follow a midpoint octant on a half-pixel center.
    // Thick bands use paired quarter-circle contours; the inner contour is sampled
    // before its next horizontal adjustment. These choices are checked independently
    // against the installed pygame-ce 2.4.0, not generated expected pixels.
    if (width == 0 || width >= radius || width == 1) {
        bool filled = width == 0 || width >= radius;
        int x = 0, y = radius, error = 1 - radius;
        while (x < y) {
            if (error >= 0) { --y; error -= 2 * y; }
            ++x; error += 2 * x + 1;
            for (auto [half, offset] : {std::pair<int,int>{x,y}, {y,x}}) {
                for (int row : {cy - offset, cy + offset - 1}) {
                    if (filled) c.hline(cx - half, cx + half - 1, row);
                    else { c.set(cx - half, row); c.set(cx + half - 1, row); }
                }
            }
        }
        return;
    }
    auto contour = [&](int r, bool inner) {
        std::map<int,int> rows;
        auto record = [&](int y, int half) {
            for (int row : {cy - y, cy + y - 1})
                if (row >= c.clip.y && row < c.clip.y + c.clip.h) rows[row] = std::max(rows[row], half);
        };
        int x = 0, y = r;
        double error = 1.25 - r;
        while (x < y) {
            if (inner) record(y, x);
            while (error < 0) { ++x; error += 2 * x + 1; }
            if (!inner) record(y, x);
            ++x; --y; error += 2 * x - 2 * y + 1;
        }
        error = (x + .5) * (x + .5) + double(y - 1) * (y - 1) - double(r) * r;
        while (y >= 0) {
            record(y, x);
            if (error > 0) { --y; error += 1 - 2 * y; }
            else { --y; ++x; error += 2 * x - 2 * y + 1; }
        }
        return rows;
    };
    auto outer = contour(radius, false), inner = contour(radius - width + 1, true);
    for (const auto& [row, half] : outer) {
        int hole = std::max(0, inner[row] - 1);
        if (hole == 0) c.hline(cx - half, cx + half - 1, row);
        else {
            c.hline(cx - half, cx - hole - 1, row);
            c.hline(cx + hole, cx + half - 1, row);
        }
    }
}

void draw_rect(Canvas& c, const IRect& r, int width, int radius) {
    if (r.w <= 0 || r.h <= 0) return;
    if (radius > 0) {
        radius = std::min({radius, r.w / 2, r.h / 2});
        auto rounded = [&](const IRect& q, int rad) {
            for (int y = q.y; y < q.y + q.h; ++y) {
                int inset = 0;
                int dy = y < q.y + rad ? q.y + rad - y : (y >= q.y + q.h - rad ? y - (q.y + q.h - rad - 1) : 0);
                if (dy > 0) inset = rad - int(std::floor(std::sqrt(std::max(0.0, double(rad) * rad - double(dy - .5) * (dy - .5))) + .5));
                c.hline(q.x + inset, q.x + q.w - 1 - inset, y);
            }
        };
        if (width <= 0) { rounded(r, radius); return; }
        // outline: draw the ring pixel by pixel (outer minus inner rounded rect)
        IRect in{r.x + width, r.y + width, r.w - 2 * width, r.h - 2 * width};
        int irad = std::max(0, radius - width);
        auto inside = [&](const IRect& q, int rad, int x, int y) {
            if (q.w <= 0 || q.h <= 0 || x < q.x || y < q.y || x >= q.x + q.w || y >= q.y + q.h) return false;
            int dx = x < q.x + rad ? q.x + rad - x : (x >= q.x + q.w - rad ? x - (q.x + q.w - rad - 1) : 0);
            int dy = y < q.y + rad ? q.y + rad - y : (y >= q.y + q.h - rad ? y - (q.y + q.h - rad - 1) : 0);
            return dx == 0 || dy == 0 || (dx - .5) * (dx - .5) + (dy - .5) * (dy - .5) <= double(rad) * rad;
        };
        for (int y = r.y; y < r.y + r.h; ++y)
            for (int x = r.x; x < r.x + r.w; ++x)
                if (inside(r, radius, x, y) && !inside(in, irad, x, y)) c.set(x, y);
        return;
    }
    if (width <= 0 || width * 2 >= r.w || width * 2 >= r.h) {
        if (width > 0 && (width * 2 >= r.w || width * 2 >= r.h)) { for (int y = r.y; y < r.y + r.h; ++y) c.hline(r.x, r.x + r.w - 1, y); return; }
        for (int y = r.y; y < r.y + r.h; ++y) c.hline(r.x, r.x + r.w - 1, y);
        return;
    }
    for (int k = 0; k < width; ++k) {
        c.hline(r.x, r.x + r.w - 1, r.y + k);
        c.hline(r.x, r.x + r.w - 1, r.y + r.h - 1 - k);
        c.vline(r.x + k, r.y, r.y + r.h - 1);
        c.vline(r.x + r.w - 1 - k, r.y, r.y + r.h - 1);
    }
}

void draw_arc(Canvas& c, const IRect& r, double a0, double a1, int width) {
    if (r.w <= 0 || r.h <= 0) return;
    while (a1 < a0) a1 += 2 * 3.141592653589793;
    double rx = r.w / 2.0, ry = r.h / 2.0, cx = r.x + rx, cy = r.y + ry;
    for (int k = 0; k < std::max(1, width); ++k) {
        double ax = rx - k, ay = ry - k;
        if (ax <= 0 || ay <= 0) break;
        int steps = std::max(8, int((a1 - a0) * std::max(ax, ay) * 2));
        int px = INT32_MIN, py = 0;
        for (int i = 0; i <= steps; ++i) {
            double t = a0 + (a1 - a0) * i / steps;
            int x = int(std::floor(cx + std::cos(t) * ax)), y = int(std::floor(cy - std::sin(t) * ay));
            if (px != INT32_MIN) c.line(px, py, x, y); else c.set(x, y);
            px = x; py = y;
        }
    }
}

}  // namespace

V draw_module() {
    static V m = [] {
        V mod = new_module("pygame.draw");
        Module* md = module_of(mod);
        md->fn("rect", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.get(1, Sym("color"), nullptr, "rect")));
            IRect r = rect_of(a.get(2, Sym("rect"), nullptr, "rect"));
            static const V zero(0.0);
            int width = int(a.get(3, Sym("width"), &zero).num());
            int radius = int(a.get(4, Sym("border_radius"), &zero).num());
            draw_rect(c, r, width, radius);
            return c.bounds(r.x, r.y);
        });
        md->fn("line", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            int x0, y0, x1, y1;
            pt(a.get(2, Sym("start_pos"), nullptr, "line"), x0, y0);
            pt(a.get(3, Sym("end_pos"), nullptr, "line"), x1, y1);
            static const V one(1.0);
            c.thick_line(x0, y0, x1, y1, int(a.get(4, Sym("width"), &one).num()));
            return c.bounds(x0, y0);
        });
        auto lines = [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            bool closed = a.get(2, Sym("closed"), nullptr, "lines").truthy();
            V pts = py::iter_list(a.get(3, Sym("points"), nullptr, "lines"));
            static const V one(1.0);
            int width = int(a.get(4, Sym("width"), &one).num());
            size_t n = pts.len();
            for (size_t i = 0; i + 1 < n; ++i) {
                int x0, y0, x1, y1; pt(pts.idx(int64_t(i)), x0, y0); pt(pts.idx(int64_t(i + 1)), x1, y1);
                c.thick_line(x0, y0, x1, y1, width);
            }
            if (closed && n > 2) { int x0, y0, x1, y1; pt(pts.idx(int64_t(n - 1)), x0, y0); pt(pts.idx(0), x1, y1); c.thick_line(x0, y0, x1, y1, width); }
            int fx = 0, fy = 0; if (n) pt(pts.idx(0), fx, fy);
            return c.bounds(fx, fy);
        };
        md->fn("lines", lines);
        md->fn("aalines", lines);
        md->fn("aaline", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            int x0, y0, x1, y1; pt(a.pos.at(2), x0, y0); pt(a.pos.at(3), x1, y1);
            c.line(x0, y0, x1, y1);
            return c.bounds(x0, y0);
        });
        md->fn("polygon", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            V pts = py::iter_list(a.get(2, Sym("points"), nullptr, "polygon"));
            static const V zero(0.0);
            int width = int(a.get(3, Sym("width"), &zero).num());
            std::vector<std::pair<int, int>> p;
            for (auto& q : pts.items()) { int x, y; pt(q, x, y); p.push_back({x, y}); }
            if (width > 0) {
                for (size_t i = 0; i < p.size(); ++i) c.thick_line(p[i].first, p[i].second, p[(i + 1) % p.size()].first, p[(i + 1) % p.size()].second, width);
            } else {
                fill_polygon(c, p);
            }
            return c.bounds(p.empty() ? 0 : p[0].first, p.empty() ? 0 : p[0].second);
        });
        md->fn("circle", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            int cx, cy; pt(a.get(2, Sym("center"), nullptr, "circle"), cx, cy);
            int radius = int(a.get(3, Sym("radius"), nullptr, "circle").num());
            static const V zero(0.0);
            draw_circle(c, cx, cy, radius, int(a.get(4, Sym("width"), &zero).num()));
            return c.bounds(cx, cy);
        });
        md->fn("ellipse", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            IRect r = rect_of(a.get(2, Sym("rect"), nullptr, "ellipse"));
            static const V zero(0.0);
            draw_ellipse(c, r, int(a.get(3, Sym("width"), &zero).num()));
            return c.bounds(r.x, r.y);
        });
        md->fn("arc", [](const Args& a) {
            Surface* s = surf(a.pos.at(0));
            Canvas c(s, color_of(a.pos.at(1)));
            IRect r = rect_of(a.pos.at(2));
            static const V one(1.0);
            draw_arc(c, r, a.pos.at(3).num(), a.pos.at(4).num(), int(a.get(5, Sym("width"), &one).num()));
            return c.bounds(r.x, r.y);
        });
        return mod;
    }();
    return m;
}

}  // namespace pvz::pg
