#pragma once
#include "ui/hand/texture_pack.h"
#include "pg/pg.h"
#include <map>
#include <deque>
#include <set>
namespace pvz::texture74 {
using J=nlohmann::json;
constexpr size_t MAX_PACK=32*1024*1024, MAX_PIXELS=32*1024*1024;
struct Resource {std::string key,name,file,scope,category;int w=0,h=0;bool projectile=false;std::vector<std::string> cards,heroes;};
struct Layer {std::string name;bool visible=true;int opacity=255;std::vector<uint32_t> pixels;};
struct Canvas {
    int w=0,h=0,selected=0;std::vector<Layer> layers;
    struct History {std::vector<Layer> layers;int selected;};
    std::deque<History> undo,redo;size_t history_bytes=0;
    void checkpoint();bool undo_step(bool forward=false);
    std::vector<uint32_t> flatten()const;
    void dot(int x,int y,int size,uint32_t color,bool erase=false);
    void line(int x,int y,int x2,int y2,int size,uint32_t color,bool erase=false);
    void fill(int x,int y,uint32_t color);
    void shape(int x,int y,int x2,int y2,int size,uint32_t color,bool ellipse,bool solid);
};
struct Transfer {std::string hash,bytes,name;size_t offset=0;int chunks=0;std::map<int,std::string> parts;double elapsed=0;};
struct Connection {
    std::string transport_id,mode;double retry=0;
    std::map<std::string,std::string> offered,acked;std::map<std::string,Transfer> sending;Transfer receiving;
    J local_before_remote;int rejected=0,received_packs=0,sent_chunks=0;bool guest_ready=false,remote=false;
};
struct State {
    bool initialized=false;std::filesystem::path root;std::vector<Resource> resources;std::map<std::string,size_t> by_key;
    std::set<std::string> excluded_keys;
    J heroes=J::array(),cards=J::array(),document={{"format","pvz-texture-pack-v1"},{"name","我的材质包"},{"entries",J::object()}};
    std::string local_id="default",active_name="原版材质",selected_key,filter="卡牌",query,card_filter,hero_filter,focus,notice;
    bool local_enabled=true;
    std::vector<std::string> pack_files;int page=0,card_page=0;bool show_packs=false;
    J pack_choices=J::array();
    Canvas canvas;std::string tool="pencil";int brush=1,import_mode=0;uint32_t color=0x66cc66ff;
    bool solid=false,grid=true,dirty=false,dragging=false,panning=false,remote=false;
    bool erasing=false,space_down=false,fit_pending=false;int active_slider=-1;std::string hex_input="66cc66ff";
    int sx=0,sy=0,lastx=0,lasty=0,pan_mouse_x=0,pan_mouse_y=0;double zoom=4,panx=0,pany=0;
    SDL_Rect viewport{},image_rect{},selection{};std::vector<uint32_t> preview,clipboard;int clip_w=0,clip_h=0;
    std::vector<SDL_Rect> sliders;
    uint64_t generation=1;std::map<std::string,V> overrides,derived;
    std::string wire,wire_hash,transport_id,mode;double retry=0;
    std::map<std::string,std::string> offered,acked;std::map<std::string,Transfer> sending;Transfer receiving;
    J local_before_remote;int rejected=0,received_packs=0,sent_chunks=0;bool guest_ready=false;
    std::string selected_connection;std::map<std::string,Connection> connections;
};
State& state();
void load_inventory();
const Resource* resource(const std::string& key);
V original(const Resource& r);
std::vector<uint32_t> pixels(const V& image);
V surface(int w,int h,const std::vector<uint32_t>& data);
std::string png_encode(const V& image);
V png_decode(const std::string& bytes,int w,int h);
std::string b64(const std::string& bytes);std::string unb64(const std::string& text);
std::string digest(const std::string& bytes);
J load_file(const std::filesystem::path& p);
void save_file(const std::filesystem::path& p,const J& j);
void activate(const J& doc,bool remote=false);
void save_current(bool enable=true);void activate_local();void open_resource(const std::string& key);void commit_canvas();
void new_pack();void set_notice(const std::string& text);void fit_canvas();
std::string choose_file(bool save,const std::string& suggested,bool pack);
void android_export(const std::filesystem::path& path);
std::string poll_file();
void import_image(const std::filesystem::path& path);
void choose_import(const std::filesystem::path& path);
void select_connection(const V& app);
}
