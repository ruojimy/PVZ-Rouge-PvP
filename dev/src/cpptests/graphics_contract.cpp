// Native SDL facade inspection for an independent comparison with the pinned original pygame.
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "cpptests/gen/pm_test_pvp_66_native_seed_bank_oct15.h"
#include "ui/gen/pm_rendering.h"
#include "core/resource_paths.h"
#include "core/fsutil.h"
#include "sim/pvp/hand/graphics.h"
#include <nlohmann/json.hpp>
#include <fstream>

namespace pvz::cpptests {
void install_graphics_contract() {
    py::register_native_hook("test.graphics.font", [](const Args& a) {
        using json = nlohmann::json;
        std::ifstream input(a.pos.at(0).str(), std::ios::binary);
        if (!input) throw PyError("OSError", "Cannot read font inputs");
        json cases=json::parse(input), result=json::array();
        V pygame=pg::pygame_module(); callm(pygame,Sym("init"),Args{});
        V fonts=pvz::getattr(pygame,Sym("font")), images=pvz::getattr(pygame,Sym("image"));
        for (const auto& item:cases) {
            try {
                V font=callm(fonts,Sym("Font"),Args{item.at("font").is_null()?V::none():V(item.at("font").get<std::string>()),V(item.at("size").get<int>())});
                V text(item.at("text").get<std::string>());
                V image=callm(font,Sym("render"),Args{text,V(item.at("aa").get<bool>()),V::tuple({V(231),V(179),V(67)})});
                V rgba=callm(images,Sym("tobytes"),Args{image,V("RGBA")});
                V encoded=py::stdlib_call(V("base64.b64encode"),Args{rgba});
                auto pair=[](const V& value){return json::array({int(value.idx(0).num()),int(value.idx(1).num())});};
                result.push_back(json{{"height",int(callm(font,Sym("get_height"),Args{}).num())},
                    {"linesize",int(callm(font,Sym("get_linesize"),Args{}).num())},
                    {"ascent",int(callm(font,Sym("get_ascent"),Args{}).num())},
                    {"descent",int(callm(font,Sym("get_descent"),Args{}).num())},
                    {"size",pair(callm(font,Sym("size"),Args{text}))},
                    {"image_size",pair(callm(image,Sym("get_size"),Args{}))},{"rgba",encoded.str()}});
            } catch(const PyError& error) { result.push_back(json{{"error",error.kind}}); }
        }
        std::ofstream output(a.pos.at(1).str(),std::ios::binary);if(!output)throw PyError("OSError","Cannot write font report");
        output<<result.dump();return V::none();
    });
    py::register_native_hook("test.graphics.frombytes", [](const Args& a) {
        using json = nlohmann::json;
        std::ifstream input(a.pos.at(0).str(), std::ios::binary);
        if (!input) throw PyError("OSError", "Cannot read image bytes inputs");
        json cases = json::parse(input), result = json::array();
        V pygame = pg::pygame_module(), module = pvz::getattr(pygame, Sym("image"));
        callm(pygame, Sym("init"), Args{});
        for (const auto& item : cases) {
            try {
                V buffer = py::stdlib_call(V("base64.b64decode"), Args{V(item.at("base64").get<std::string>())});
                std::string kind=item.value("buffer",std::string("bytes"));
                if (kind=="bytearray") buffer=py::builtin_call(V("bytearray"),Args{buffer});
                if (kind=="str") buffer=V(buffer.str());
                V size = py::json_loads(V(item.at("size").dump()));
                V surface=callm(module,Sym("frombytes"),Args{buffer,size,V(item.at("format").get<std::string>()),V(item.value("flipped",false))});
                V rgba=callm(module,Sym("tobytes"),Args{surface,V("RGBA")});
                V encoded=py::stdlib_call(V("base64.b64encode"),Args{rgba});
                V alpha=callm(surface,Sym("get_alpha"),Args{});
                result.push_back(json{{"rgba",encoded.str()},{"size",item.at("size")},
                    {"alpha",alpha.is_none()?json():json(int(alpha.num()))},
                    {"flags",int(callm(surface,Sym("get_flags"),Args{}).num())&65536}});
            } catch(const PyError& error) { result.push_back(json{{"error",error.kind}}); }
        }
        std::ofstream output(a.pos.at(1).str(),std::ios::binary);output<<result.dump();
        if(!output)throw PyError("OSError","Cannot write image bytes report");
        callm(pygame,Sym("quit"),Args{});
        return V::none();
    });
    py::register_native_hook("test.graphics.recipes", [](const Args& a) {
        using json = nlohmann::json;
        std::ifstream input(a.pos.at(0).str(), std::ios::binary);
        if (!input) throw PyError("OSError", "Cannot read recipe comparison inputs");
        json cases = json::parse(input), result = json::array();
        V pygame = pg::pygame_module(), facade = gfx::make_pygame();
        callm(pygame, Sym("init"), Args{});
        callm(pvz::getattr(pygame, Sym("display")), Sym("set_mode"), Args{V::tuple({V(1), V(1)})});
        auto value = [](const json& item) { return py::json_loads(V(item.dump())); };
        for (auto& steps : cases) {
            V images = V::dict();
            for (auto& step : steps) {
                V key(step.at("target").get<std::string>());
                std::string op = step.at("op").get<std::string>();
                if (op == "new") images.at(key) = callm(facade, Sym("Surface"), Args{value(step["size"]), value(step["flags"])});
                else if (op == "fill") callm(rd(images, key), Sym("fill"), Args{value(step["color"])});
                else if (op == "set_alpha") callm(rd(images, key), Sym("set_alpha"), Args{value(step["value"])});
                else if (op == "copy") images.at(key) = callm(rd(images, key), Sym("copy"), Args{});
                else if (op == "blit") callm(rd(images, key), Sym("blit"), Args{rd(images, V(step["source"].get<std::string>())), value(step["dest"]), value(step["area"]), value(step["flags"])});
                else if (op == "draw") {
                    Args draw; draw.pos.push_back(rd(images, key));
                    for (auto& arg : step["args"]) draw.pos.push_back(value(arg));
                    callm(pvz::getattr(facade, Sym("draw")), Sym(step["name"].get<std::string>()), draw);
                }
                else if (op == "crop") images.at(key) = callm(callm(rd(images, key), Sym("subsurface"), Args{value(step["rect"])}), Sym("copy"), Args{});
                else if (op == "scale") images.at(key) = callm(pvz::getattr(facade, Sym("transform")), Sym("scale"), Args{rd(images, key), value(step["size"])});
                else if (op == "flip") images.at(key) = callm(pvz::getattr(facade, Sym("transform")), Sym("flip"), Args{rd(images, key), value(step["x"]), value(step["y"])});
                else throw PyError("ValueError", "Unknown recipe comparison operation: " + op);
            }
            V image = rd(images, V("base")), pixels = pvz::getattr(image, Sym("pixels"));
            V bytes = callm(pvz::getattr(pygame, Sym("image")), Sym("tobytes"), Args{pixels, V("RGBA")});
            V base64 = py::stdlib_call(V("base64.b64encode"), Args{bytes});
            V description = callm(image, Sym("describe"), Args{});
            V alpha = callm(image, Sym("get_alpha"), Args{});
            result.push_back(json{{"rgba", base64.str()}, {"description", json::parse(py::stdlib_call(V("json.dumps"), Args{description}).str())},
                {"alpha", alpha.is_none() ? json() : json(int(alpha.num()))}, {"flags", int(callm(image, Sym("get_flags"), Args{}).num()) & 65536}});
        }
        std::ofstream output(a.pos.at(1).str(), std::ios::binary); output << result.dump();
        if (!output) throw PyError("OSError", "Cannot write recipe comparison report");
        callm(pygame, Sym("quit"), Args{});
        return V::none();
    });
    py::register_native_hook("test.seedbank.report", [](const Args& a) {
        using json = nlohmann::json;
        std::string folder = a.pos.at(0).str();
        V pygame = pg::pygame_module();
        V type = pm_test_pvp_66_native_seed_bank_oct15::cls_NativeSeedBankPixels();
        callm(type, Sym("setUpClass"), Args{});
        V fixture = call(type, Args{}), report = V::list({});
        json result = json::array();
        V image = pvz::getattr(pygame, Sym("image")), transform = pvz::getattr(pygame, Sym("transform"));
        for (int count : {3, 7, 13}) for (double factor : {1.0, .625, 1.37}) {
            V reference = callm(fixture, Sym("fixture"), Args{V(count)});
            int w = int(py::round(V(callm(reference, Sym("get_width"), Args{}).num() * factor)).num());
            int h = int(py::round(V(callm(reference, Sym("get_height"), Args{}).num() * factor)).num());
            V expected = pg::new_surface(w + 34, h + 22, true), actual = pg::new_surface(w + 34, h + 22, true);
            callm(expected, Sym("blit"), Args{callm(transform, Sym("scale"), Args{reference, V::tuple({V(w), V(h)})}), V::tuple({V(17), V(11)})});
            V renderer = pm_rendering::new_Renderer(Args({pygame, actual}, {{Sym("asset_dir"), py::path_new(Args{V(p8(native_image_directory()))})}}));
            callm(renderer, Sym("native_seed_bank"), Args{V::tuple({V(17), V(11), V(w), V(h)}), V(count)});
            std::string x = callm(image, Sym("tobytes"), Args{expected, V("RGBA")}).str(), y = callm(image, Sym("tobytes"), Args{actual, V("RGBA")}).str();
            size_t differences = 0; json first = json::array();
            for (size_t i = 0; i < x.size(); ++i) if (x[i] != y[i]) { ++differences; if (first.size() < 12) first.push_back(json{{"x", (i / 4) % (w + 34)}, {"y", (i / 4) / (w + 34)}, {"channel", i % 4}, {"expected", uint8_t(x[i])}, {"actual", uint8_t(y[i])}}); }
            std::string name = folder + "/" + std::to_string(count) + "-" + std::to_string(w);
            if (differences) { callm(image, Sym("save"), Args{expected, V(name + "-expected.png")}); callm(image, Sym("save"), Args{actual, V(name + "-actual.png")}); }
            result.push_back(json{{"count", count}, {"factor", factor}, {"size", {w, h}}, {"different_channels", differences}, {"first", first}});
        }
        std::ofstream(folder + "/report.json", std::ios::binary) << result.dump(2);
        callm(type, Sym("tearDownClass"), Args{});
        return V::none();
    });
    py::register_native_hook("test.graphics.report", [](const Args& a) {
        using json = nlohmann::json;
        std::ifstream input(a.pos.at(0).str(), std::ios::binary);
        if (!input) throw PyError("OSError", "Cannot read graphics comparison inputs");
        json cases = json::parse(input), result = json::array();
        V pygame = pg::pygame_module();
        callm(pygame, Sym("init"), Args{});
        callm(pvz::getattr(pygame, Sym("display")), Sym("set_mode"), Args{V::tuple({V(1), V(1)})});
        auto color = [](const json& value) { std::vector<V> items; for (auto& item : value) items.push_back(V(item.get<int>())); return V::tuple(items); };
        for (auto& item : cases) {
            V source = pg::new_surface(1, 1, item.at("source_alpha").get<bool>());
            V destination = pg::new_surface(1, 1, item.at("destination_alpha").get<bool>());
            callm(source, Sym("fill"), Args{color(item.at("source"))});
            callm(destination, Sym("fill"), Args{color(item.at("destination"))});
            if (item.contains("modulation")) callm(source, Sym("set_alpha"), Args{item["modulation"].is_null() ? V::none() : V(item["modulation"].get<int>())});
            std::string transform = item.value("transform", std::string());
            if (transform == "copy" || transform == "convert" || transform == "convert_alpha") source = callm(source, Sym(transform), Args{});
            else if (transform == "scale") source = callm(pvz::getattr(pygame, Sym("transform")), Sym("scale"), Args{source, V::tuple({V(1), V(1)})});
            callm(destination, Sym("blit"), Args{source, V::tuple({V(0), V(0)})});
            V pixel = callm(destination, Sym("get_at"), Args{V::tuple({V(0), V(0)})});
            json rgba = json::array(); for (auto& channel : pixel.items()) rgba.push_back(int(channel.num()));
            V alpha = callm(source, Sym("get_alpha"), Args{});
            result.push_back(json{{"rgba", rgba}, {"alpha", alpha.is_none() ? json() : json(int(alpha.num()))},
                                  {"srcalpha_flag", (int(callm(source, Sym("get_flags"), Args{}).num()) & 0x10000) != 0}});
        }
        std::ofstream output(a.pos.at(1).str(), std::ios::binary); output << result.dump();
        if (!output) throw PyError("OSError", "Cannot write graphics comparison report");
        callm(pygame, Sym("quit"), Args{});
        return V::none();
    });
}
}
