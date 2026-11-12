"""Extract the existing native raster algorithms with a typed pixel sink.

Only the sink changes: integer point conversion, clipping and primitive
iteration are the same as src/pg/draw.cpp, with no V or SDL object protocol.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[3]
source=(root/'src/pg/draw.cpp').read_text(encoding='utf8')
polygon=source[source.index('void fill_polygon('):source.index('\nvoid ellipse_points(')]
circle=source[source.index('void draw_circle('):source.index('\nvoid draw_rect(')]
line=source[source.index('    void line('):source.index('    V bounds(')]
header='''#pragma once
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
'''+line+'''};
'''+polygon+'\n'+circle+'''
inline void lines(Canvas& canvas,const std::vector<Point>& points,int width) {
    for(size_t i=1;i<points.size();++i)canvas.thick_line(int(points[i-1].x),int(points[i-1].y),int(points[i].x),int(points[i].y),width);
}
inline void polygon(Canvas& canvas,const std::vector<Point>& points) {
    std::vector<std::pair<int,int>> converted;converted.reserve(points.size());
    for(const auto& p:points)converted.emplace_back(int(p.x),int(p.y));fill_polygon(canvas,converted);
}
} // namespace pvz::typed72::content_raster
'''
(Path(__file__).resolve().parent/'content_raster.h').write_text(header,encoding='utf8')
