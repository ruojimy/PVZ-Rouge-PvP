#pragma once
#include "sim/typed/native_art.h"
#include <algorithm>
#include <cmath>
#include <map>
namespace pvz::typed72::content_raster {
// Native integer raster operations from src/pg/draw.cpp. The pixel sink owns
// the same RGBA representation as the authoritative NativeArtStore.
struct Canvas {
    NativeArt image;
    std::shared_ptr<SpritePixels> data;
    struct Clip {int x,y,w,h;} clip;
    Color color{};
    Canvas(int width,int height):image(NativeArtStore::canvas(width,height)),data(std::make_shared<SpritePixels>()),clip{0,0,width,height} {
        data->width=width;data->height=height;data->pixels.resize(size_t(width)*height);image->pixels=data;
    }
    void set(int x,int y) {
        if(x<0||y<0||x>=clip.w||y>=clip.h)return;
        data->pixels[size_t(y)*clip.w+x]=color;
    }
    void hline(int x0,int x1,int y) {
        if(x0>x1)std::swap(x0,x1);if(y<0||y>=clip.h)return;
        x0=std::max(0,x0);x1=std::min(clip.w-1,x1);
        for(int x=x0;x<=x1;++x)set(x,y);
    }
    void fill(Color value){std::fill(data->pixels.begin(),data->pixels.end(),value);}
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
};
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

inline void lines(Canvas& canvas,const std::vector<Point>& points,int width) {
    for(size_t i=1;i<points.size();++i)canvas.thick_line(int(points[i-1].x),int(points[i-1].y),int(points[i].x),int(points[i].y),width);
}
inline void polygon(Canvas& canvas,const std::vector<Point>& points) {
    std::vector<std::pair<int,int>> converted;converted.reserve(points.size());
    for(const auto& p:points)converted.emplace_back(int(p.x),int(p.y));fill_polygon(canvas,converted);
}
} // namespace pvz::typed72::content_raster
