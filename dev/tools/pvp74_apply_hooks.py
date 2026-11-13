"""Reviewed native PvP74 hooks; reapply after translating UI modules. --check is build gate."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
check='--check' in sys.argv
changed=[]
def edit(file,fn):
 p=ROOT/file;old=p.read_text('utf8');new=fn(old)
 if old!=new:
  changed.append(file)
  if not check:p.write_text(new,'utf8')
def insert(text,marker,anchor,addition,before=False):
 if marker in text:return text
 if anchor not in text:raise RuntimeError('Missing hook anchor: '+marker)
 return text.replace(anchor,(addition+anchor) if before else (anchor+addition),1)
def ui_include(t):return insert(t,'#include "ui/hand/texture_pack.h"','\n','#include "ui/hand/texture_pack.h"\n')
def app(t):
 t=ui_include(t)
 start=t.index('V C_Application::m___init__(');end=t.index('\nV C_Application::',start+1)
 body=t[start:end]
 if 'texture74::initialize' not in body:
  at=body.rfind('    return V::none();');body=body[:at]+'    texture74::initialize(self()); // PvP74 owned native initialization\n'+body[at:];t=t[:start]+body+t[end:]
 t=insert(t,'texture74::action(self()', '    V L_action = A.get(0, SY("action"), nullptr, "action");\n','    if(texture74::action(self(),L_action))return V::none(); // PvP74\n')
 t=insert(t,'texture74::update(self()', '    V L_dt = A.get(0, SY("dt"), nullptr, "poll_network");\n','    texture74::update(self(),L_dt.num()); // PvP74 bounded cosmetic transfer\n')
 t=insert(t,'texture74::receive(self()', '            L_payload = py::m_get(L_event, SV("payload"), py_dict({}));\n','            if(texture74::receive(self(),py::m_get(L_event,SV("peer_id")),L_payload))continue; // PvP74\n')
 start=t.index('V C_Application::m_handle_events(');at=t.index('        L_event = it3_.idx(int64_t(i3_)); \n',start)
 if 'texture74::event(self()' not in t:t=t[:at]+t[at:].replace('        L_event = it3_.idx(int64_t(i3_)); \n','        L_event = it3_.idx(int64_t(i3_)); \n        if(texture74::event(self(),L_event))continue; // PvP74\n',1)
 t=insert(t,'texture74::sync_renderer(a_renderer)', '    L_prof = a_profiler;\n','    texture74::sync_renderer(a_renderer); // PvP74 cache generation\n')
 t=insert(t,'texture74::overlay(self()', '    if (!py_is(pvz::getattr(a_renderer, SY("screen")), a_surface)) {','    texture74::overlay(self()); // PvP74 host material status\n',before=True)
 t=insert(t,'texture74::draw(self()', '    } else if ((callm(self(), SY("render_map_screen"), Args{})).truthy()) {','    } else if (texture74::draw(self())) {\n',before=True)
 # The previous insertion includes the existing closing brace; normalize its branch.
 t=t.replace('    } else if (texture74::draw(self())) {\n    } else if ((callm(self(), SY("render_map_screen")','    } else if (texture74::draw(self())) {\n    } else if ((callm(self(), SY("render_map_screen")')
 t=insert(t,'texture74::sync_text_input(self()', 'V C_Application::m__sync_text_input(const Args& A) {\n','    if(texture74::sync_text_input(self()))return V::none(); // PvP74 IME\n')
 for method in ('close','app_background'):
  t=insert(t,'texture74::persist_editor(self()); // PvP74 '+method,'V C_Application::m_'+method+'(const Args& A) {\n','    texture74::persist_editor(self()); // PvP74 '+method+'\n')
 t=insert(t,'texture74::close_connection(self()', 'V C_Application::m_close(const Args& A) {\n','    texture74::close_connection(self()); // PvP74 per-application transport lifetime\n')
 return t
edit('src/ui/gen/pm_app.cpp',app)
def art(t):
 t=ui_include(t)
 t=insert(t,'texture74::artwork(py_str(L_name))', '    V L_name = A.get(0, SY("name"), nullptr, "raw");\n','    texture74::sync_art(self());\n    if(V custom=texture74::artwork(py_str(L_name));!custom.is_none())return custom; // PvP74\n')
 t=insert(t,'texture74::sync_art(self()); // PvP74 image', 'V C_NativeArt::m_image(const Args& A) {\n','    texture74::sync_art(self()); // PvP74 image cache\n')
 t=insert(t,'DisplayScope texture74_art', 'V C_NativeArt::m_raw(const Args& A) {\n','    texture74::DisplayScope texture74_art; // PvP74\n')
 return t
edit('src/ui/gen/pm_native_style.cpp',art)
def rendering(t):
 t=ui_include(t);start=t.index('V C_Renderer::m_artwork(');anchor='    V L_name = A.get(0, SY("name"), nullptr, "artwork");\n';at=t.index(anchor,start)
 if 'texture74::artwork(py_str(L_name))' not in t:t=t[:at]+t[at:].replace(anchor,anchor+'    if(V custom=texture74::artwork(py_str(L_name));!custom.is_none())return custom; // PvP74\n',1)
 anchor='    V L_flip = (A.size() > 2 || A.has_kw(SY("flip"))) ? A.get(2, SY("flip"), nullptr) : V(V(false));\n'
 t=insert(t,'texture74::icon(a_screen',anchor,'    if(texture74::icon(a_screen,py_str(L_name),L_rect,L_flip.truthy()))return V::none(); // PvP74 complete card icon\n')
 return insert(t,'DisplayScope texture74_card','V C_Renderer::m_artwork(const Args& A) {\n','    texture74::DisplayScope texture74_card; // PvP74\n')
edit('src/ui/gen/pm_rendering.cpp',rendering)
def menu(t):
 if 'texture74_open' in t:return t
 anchor='    (void)(callm(L_r, SY("button"), Args({SV("对局回放")'
 at=t.index(anchor);t=t[:at]+'    (void)callm(L_r,SY("button"),Args({SV("材质工坊"),V::tuple({V(190),V(18),V(150),V(39)}),V::tuple({SV("texture74_open")})},{{SY("size"),V(17)}})); // PvP74\n'+t[at:]
 t=t.replace('SV("对局回放"), V::tuple({V(190.0)','SV("对局回放"), V::tuple({V(355.0)',1);return t
edit('src/ui/gen/pm_menu_view.cpp',menu)
def replay(t):
 t=insert(t,'texture74.surface', '        L_source = py::m_get(a_assets, L_key);\n','        if(py::has_native_hook("texture74.surface")){V custom=py::native_hook(V("texture74.surface"),Args{L_key,rd(L_recipe,SV("size")),a_resolver});if(!custom.is_none())L_source=custom;} // PvP74 display resolver only\n')
 return insert(t,'texture74.render_begin', '    V L_local_pixels = (A.size() > 7 || A.has_kw(SY("local_pixels"))) ? A.get(7, SY("local_pixels"), nullptr) : V(V::none());\n','    if(py::has_native_hook("texture74.render_begin")&&py::native_hook(V("texture74.render_begin"),Args{self()}).truthy())L_local_pixels=V::none(); // PvP74\n')
edit('src/sim/pvp/gen/pm_native_animation.cpp',replay)
def world(t):
 old='        a__native_replay=pm_native_animation::new_DrawReplay(Args({a_pg},{{Sym("asset_resolver"),pvz::getattr(self(),Sym("_native_asset"))}}));'
 new='        V cosmetic_resolver=pvz::getattr(self(),Sym("_native_asset"));cosmetic_resolver.box->fattrs.emplace_back(Sym("__texture74_display_resolver__"),V(true)); // PvP74\n        a__native_replay=pm_native_animation::new_DrawReplay(Args({a_pg},{{Sym("asset_resolver"),cosmetic_resolver}}));'
 t=t if '__texture74_display_resolver__' in t else t.replace(old,new)
 t=ui_include(t)
 return insert(t,'OriginalScope texture74_original','    py::register_native_hook("graphics.materialize_image", [](const Args& a) {\n','        texture74::OriginalScope texture74_original; // PvP74 never override authoritative pixels\n')
edit('src/ui/hand/draw_replay.cpp',world)
def world_scope(t):
 t=ui_include(t)
 return insert(t,'DisplayScope texture74_world','V C_WorldView::m_render(const Args& A) {\n','    texture74::DisplayScope texture74_world; // PvP74\n')
edit('src/ui/gen/pm_world_view.cpp',world_scope)
def system(t):
 t=insert(t,'case SDL_DROPFILE:', '        case SDL_MOUSEWHEEL: {','        case SDL_DROPFILE: {\n            V ev=make_event(SDL_DROPFILE);set(ev,"file",V(e.drop.file?e.drop.file:""));if(e.drop.file)SDL_free(e.drop.file);out.push_back(ev);break;\n        }\n',True)
 return insert(t,'texture74.image_path','        std::string p = path_str(src);\n','        if(py::has_native_hook("texture74.image_path")){V image=py::native_hook(V("texture74.image_path"),Args{V(p)});if(!image.is_none())return image;} // PvP74 display-only raw files\n')
edit('src/pg/system.cpp',system)
def network(t):
 old='SV("request_full_snapshot"), SV("leave"), SV("result_received"), SV("role_change")'
 if 'SV("texture74_request")' in t:return t
 if old not in t:raise RuntimeError('Missing spectator control whitelist')
 return t.replace(old,old+', SV("texture74_hello"), SV("texture74_request"), SV("texture74_ack"), SV("spectator_watch")',1)
edit('src/ui/gen/pm_network.cpp',network)
print(('Stale hooks: ' if check else 'Applied hooks: ')+', '.join(changed))
raise SystemExit(bool(changed) if check else 0)
