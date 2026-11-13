"""Translate PvP71 Python modules (modkit/pvp/*.py) to C++ over the pvz runtime.

    python tools/pvp2cpp.py <outdir> <module> [<module> ...]

Every module m becomes namespace pm_m (pm_m.h / pm_m.cpp):
  module variable X      -> V pm_m::X            (initialised in pm_m::init())
  module function f      -> V pm_m::f_f(const Args&)
  class C                -> struct pm_m::C_C : <base or PyObj>; V pm_m::new_C(const Args&)
      self.attr          -> member  V a_attr   (declared from every self.attr store in the class tree)
      method m           -> virtual V m_m(const Args&)
  generator function     -> C++20 coroutine returning a generator instance (see core/pygen.h)
Untranslatable constructs become PVZ_TODO("...") so the C++ compiler reports them.
"""
import ast, sys, json, re, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PVP = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvp")
TESTS = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\tests")
SHIM = Path(__file__).resolve().parent / "testshim"


def src_of(name):
    """Source file of a translatable module: modkit/pvp/<name>.py, tests/test_pvp_*.py, tools/testshim/*.py."""
    if name in EXTRA_SOURCES_EARLY:
        return EXTRA_SOURCES_EARLY[name]
    # PvP72 owns its changed generation inputs. The frozen Python71 reference
    # remains read-only, including when collecting the legacy test suite.
    native72 = ROOT / "tools" / "pvp72_sources" / (name + ".py")
    if native72.exists() and not os.environ.get('PVZ72_TRANSLATION_BASELINE'):
        return native72
    if name=='performance_probe':
        return PVP.parent / 'android' / 'performance_probe.py'
    if name.startswith("test_pvp_"):
        return TESTS / (name + ".py")
    if (SHIM / (name + ".py")).exists():
        return SHIM / (name + ".py")
    return PVP / (name + ".py")


EXTRA_SOURCES_EARLY = {}
OBJ_KEYS = set(re.findall(r"X\(([^)]+)\)", (ROOT / "src/core/obj_fields.inc").read_text(encoding="utf-8")))

CPP_KW = set("""OVERFLOW UNDERFLOW DOMAIN SING TLOSS PLOSS EOF NULL TRUE FALSE ERROR IN OUT DELETE alignas alignof and and_eq asm auto bitand bitor bool break case catch char class compl concept
const consteval constexpr constinit const_cast continue co_await co_return co_yield decltype default delete do
double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable
namespace new noexcept not not_eq nullptr operator or or_eq private protected public register
reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template
this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t
while xor xor_eq""".split())

BUILTIN_FUNCS = {
    "len": "py::len", "int": "py::int_", "float": "py::float_", "str": "py::str", "abs": "py::abs",
    "bool": "py::bool_", "round": "py::round", "repr": "py::repr", "sorted": None, "reversed": "py::reversed",
    "sum": "py::sum_it", "any": "py::any", "all": "py::all", "min": None, "max": None, "list": "py::list_it",
    "tuple": "py::tuple_it", "set": "py::set_it", "frozenset": "py::set_it", "dict": None, "enumerate": "py::enumerate",
    "zip": "py::zip", "range": None, "isinstance": None, "getattr": None, "setattr": None, "hasattr": None,
    "id": "py::id", "type": "py::type", "next": "py::next", "iter": "py::iter", "divmod": "py::divmod",
    "print": "py::print", "callable": "py::callable", "filter": "py::filter", "map": "py::map", "hash": "py::hash",
    "chr": "py::chr", "ord": "py::ord", "pow": "pow", "format": "py::format_spec",
    "vars": None, "dir": None,
}
BUILTIN_EXC = {"Exception", "RuntimeError", "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
               "ZeroDivisionError", "LookupError", "NotImplementedError", "StopIteration", "AssertionError",
               "OSError", "IOError", "ModuleNotFoundError", "ImportError", "ArithmeticError", "OverflowError",
               "BaseException", "KeyboardInterrupt", "UnicodeDecodeError", "FileNotFoundError", "PermissionError",
               "IsADirectoryError", "NotADirectoryError",
               "ConnectionError", "TimeoutError", "EOFError", "MemoryError", "RecursionError", "SystemExit"}
STDLIB = {"math", "random", "copy", "time", "json", "os", "sys", "hashlib", "functools", "itertools", "collections",
          "contextlib", "types", "dis", "marshal", "struct", "zlib", "base64", "weakref", "threading", "socket",
          "bisect", "heapq", "operator", "pathlib", "inspect", "gc", "traceback", "statistics", "string", "re",
          "array", "io", "queue", "select", "errno", "platform", "subprocess", "tempfile", "datetime", "warnings"}


# modules provided by hand-written C++ (src/sim/pvp/shim/pm_<m>.h)
SHIMS = {"cppcore", "gc_policy", "hero_guard", "native_candidates", "native_multiworker", "performance", "app",
         "native_assets", "expansion_assets", "content_assets", "world_view", "pvp67_assets",
         "pvp64_sprite_atlas", "native_loading", "game_audio", "native_style", "pvp64_assets", "pvp70_assets",
         "pvp56_plants_assets", "pvp56_zombie_assets", "pvp58_assets", "pvp61_assets", "pvp54_assets",
         "expansion_atlas_data", "content_atlas_data", "pvp66_material_data", "native_bytecode"}
# functions / methods whose bodies are hand-written in src/sim/pvp/hand (declared, not emitted)
SKIP = {
    "native_content": {"NativeContent.nearest", "NativeContent.route_target"},
    "test_pvp_legacy": {"load_real_patch"},
    "performance_window": {"process_memory"},
    "app": {"_workspace"},
    "native_runtime": {"original_regions", "load_patch", "NativeRuntime.__init__", "NativeRuntime.execute",
                       "NativeRuntime._install_periodic_bounds", "MatchCopy", "PeriodicRow"},
    "native_physics": {"slice_original", "_instruction", "_int_const_index", "flood_step", "_capture_displacement",
                       "_periodic_out", "_periodic_open_top", "NativePhysics.__init__", "NativePhysics._execute",
                       "NativePhysics._select", "NativePhysics._restore"},
    "native_animation": {"draw_dave", "NamespaceGraphics", "NativeImage", "DeferredImage", "_DeferredTransform",
                         "_Transforms", "_Draw", "_Pygame", "DrawRecorder"},
    "native_gate": {"replace_predicate", "_replace_predicate", "inject_iteration_gate"},
    "native_battle": {"_gated_regions"},
    "native_scale": {"install"},
    "native_protection": {"replace_damage_write", "_patch_damage_code", "NativeProtection.__init__"},
    "native_targets": {"NativeTargets.install", "HeroProxy"},
    "native_periodic_targets": {"NativePeriodicTargets", "PeriodicTargetsPy.begin", "PeriodicTargetsPy.restore"},
    "native_candidates": {"install"},
    "hero_guard": {"enabled", "install", "HeroGuard.violation"},
    "scripted_spawn_budget": {"ScriptedSpawnBudget.install_native_guards"},
    "world_view": {"WorldView._ensure_native_replay", "WorldView._native_asset"},
    "native_bridge": {"_literal_step", "_extract_literal_assignment", "_extract_literal_dictionary",
                      "_extract_secret_text", "NativeBridge.from_marshaled", "NativeBridge.combat_payload",
                      "NativeBridge._resolve_payload", "NativeBridge.generate_map", "NativeBridge.__init__",
                      "NativeBridge.surface", "NativeBridge.atlas_keys"},
}
EXTRA_SOURCES = {"patch1501": Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvzrouge_runtime_patch_source_20260904.py")}
DYNAMIC = {"patch1501"}


def fold_key_constants(tree):
    """Patch source: `__pvz_sb_K_X = "键"` assigned once at module level and never rebound anywhere
    (no other module writes them either) -> every read becomes the literal, so unit fields resolve to
    the fixed Obj member slots at translation time. The module-level assignment itself stays."""
    import collections
    stores = collections.Counter()
    glob = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            stores[n.id] += 1
        if isinstance(n, ast.Global):
            glob |= set(n.names)
    consts = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)                 and n.targets[0].id.startswith("__pvz_sb_K_") and isinstance(n.value, ast.Constant)                 and isinstance(n.value.value, str) and stores[n.targets[0].id] == 1 and n.targets[0].id not in glob:
            consts[n.targets[0].id] = n.value.value

    class Fold(ast.NodeTransformer):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in consts:
                return ast.copy_location(ast.Constant(value=consts[node.id]), node)
            return node
        def visit_FunctionDef(self, node):
            # a parameter or local with the same name would shadow the module constant
            local = {a.arg for a in node.args.args + node.args.kwonlyargs}
            if local & set(consts):
                return node
            self.generic_visit(node)
            return node
    for i, n in enumerate(tree.body):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in consts:
            continue
        tree.body[i] = Fold().visit(n)
    return consts


# math.X(...) inlined with the runtime's own formulas (pvprt.cpp stdlib_call) -> no dynamic dispatch
MATH_INLINE = {
    "hypot": (2, "V(std::hypot((%s).num(), (%s).num()))"), "floor": (1, "V(std::floor((%s).num()))"),
    "ceil": (1, "V(std::ceil((%s).num()))"), "sin": (1, "V(std::sin((%s).num()))"), "cos": (1, "V(std::cos((%s).num()))"),
    "tan": (1, "V(std::tan((%s).num()))"), "atan2": (2, "V(std::atan2((%s).num(), (%s).num()))"),
    "atan": (1, "V(std::atan((%s).num()))"), "asin": (1, "V(std::asin((%s).num()))"), "acos": (1, "V(std::acos((%s).num()))"),
    "sqrt": (1, "V(std::sqrt((%s).num()))"), "exp": (1, "V(std::exp((%s).num()))"),
    "degrees": (1, "V((%s).num() * (180.0 / 3.141592653589793))"), "radians": (1, "V((%s).num() * (3.141592653589793 / 180.0))"),
    "isfinite": (1, "V(std::isfinite((%s).num()))"), "isnan": (1, "V(std::isnan((%s).num()))"),
    "copysign": (2, "V(std::copysign((%s).num(), (%s).num()))"), "fabs": (1, "V(std::fabs((%s).num()))"),
}


def protect_patch_damage(tree):
    """native_protection._patch_damage_code, applied before translation (every PvP match does it)."""
    specs = {
        '__pvz_sb_damage_plant_from_fumeshroom': ('hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - __pvz_sb_float(damage, 0.0)'),
        '__pvz_sb_zombie_pea_hit': ('new_hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - __pvz_sb_PLANT_ZOMBIE_PEA_DAMAGE * __pvz_sb_zombie_pea_fire_mult(g, pea)'),
        '__pvz_sb_zombie_pea_fire_splash': ('new_hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - splash'),
        '__pvz_sb_update_gravebuster_zombie_plant_damage': ('desired',
            '__pvz_sb_float(__pvz_sb_GRAVEBUSTER_ZOMBIE_PLANT_DAMAGE, 6.0)'),
    }
    done = 0
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or function.name not in specs:
            continue
        name, expression = specs[function.name]
        expected = ast.dump(ast.parse(expression, mode='eval').body)
        matches = [node for node in ast.walk(function) if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == name and ast.dump(node.value) == expected]
        assert len(matches) == 1, function.name
        node = matches[0]
        value = node.value if name == 'desired' else node.value.right
        call = ast.Call(func=ast.Name(id='_pvp_damage_amount', ctx=ast.Load()),
                        args=[ast.Name(id='plant', ctx=ast.Load()), value], keywords=[])
        if name == 'desired':
            node.value = ast.copy_location(call, value)
        else:
            node.value.right = ast.copy_location(call, value)
        done += 1
    assert done == len(specs)


# exact text replacements applied before translation: bytecode/frame tricks -> hand-written hooks
SOURCE_PATCHES = {
    "native_targets": [("            exec(code, self.g)", "            __pvp_native__('run_target_index', code, self.g)")],
    "native_placement_extra": [],
    "native_placement": [
        ("            exec(self.region, self.g)", "            __pvp_native__('run_placement_region', self.g)"),
        ("""        self.g = dict(__builtins__=builtins.__dict__, ditu=rows,
                      植物=state["plants"], 秘籍=state["secrets"],
                      kong=state["empty_blocks"], 模式="正常模式")
        codes = {code.co_name: code for code in root.co_consts
                 if isinstance(code, types.CodeType)}
        for name in ("哪个植物", "哪个无南瓜植物", "出界"):
            self.g[name] = types.FunctionType(codes[name], self.g)
        original = self.g["出界"]
        self.g["出界"] = lambda row, col: original(row, 0)""",
         """        self.g = __pvp_native__('placement_namespace', rows, state["plants"], state["secrets"], state["empty_blocks"])"""),
    ],
    "pvp64_content": [
        ("__import__('copy').deepcopy", "__pvp_native__('copy_deepcopy')"),
        ("""        self.high_solver = types.FunctionType(solver.__code__.replace(
            co_names=tuple('max' if n == 'min' else n for n in solver.__code__.co_names)),
            solver.__globals__, solver.__name__, solver.__defaults__)""",
         """        self.high_solver = __pvp_native__('high_intercept_solver', ns)"""),
    ],
    "native_content": [
        ("""        constants=tuple({1.5:1.2,.3:.6,.75:.6,.2:.01}.get(c,c) if type(c) is float else c
                        for c in displacement.__code__.co_consts)
        code=displacement.__code__.replace(co_consts=constants)""", """        code=None"""),
        ("""        def barrel_samples():
            local=sys._getframe(1).f_locals;x,y=local['weizhi'][:2]
            local['dian'].extend([[x,y-g['比']*height] for height in (1.2,.6,.01)])
        g['_pvp_barrel_samples']=barrel_samples
        offset=len(code.co_code)
        code=inject_iteration_gate(code,268,'_pvp_barrel_samples')
        data=bytearray(code.co_code)
        assert data[offset]==dis.opmap['LOAD_NAME']
        data[offset]=dis.opmap['LOAD_GLOBAL']  # optimized function, not exec region
        code=code.replace(co_code=bytes(data))
        self.barrel_displacement=types.FunctionType(code,
            displacement.__globals__,displacement.__name__,displacement.__defaults__)""",
         """        self.barrel_displacement=__pvp_native__('barrel_displacement',g)"""),
        ("""        high_solver=types.FunctionType(solver.__code__.replace(
            co_names=tuple('max' if n=='min' else n for n in solver.__code__.co_names)),
            solver.__globals__,solver.__name__,solver.__defaults__)""",
         """        high_solver=__pvp_native__('high_intercept_solver',ns)"""),
        ("""        class ContentBaseDamage(dict):
            def get(table,key,default=None):
                e=sys._getframe(1).f_locals.get('entity')
                if isinstance(e,dict) and e.get('_pvp_content')=='甜椒投手':return 60.
                return dict.get(table,key,default)
        ns['__pvz_sb_BASE_DAMAGE']=ContentBaseDamage(ns['__pvz_sb_BASE_DAMAGE'])""",
         """        ns['__pvz_sb_BASE_DAMAGE']=__pvp_native__('content_base_damage',ns['__pvz_sb_BASE_DAMAGE'])"""),
    ],
}

# Native pickup owner identity must survive allocator address reuse.
SOURCE_PATCHES["zombie_secrets"] = list(SOURCE_PATCHES.get("zombie_secrets", ())) + [('dropper=id(z),', 'dropper=id(z), _native_dropper_uid=z.get("_pvp_id"),'), ("if id(z) == item['dropper'] or not self._zombie(z):continue", "if ((z.get('_pvp_id') == item['_native_dropper_uid']) if item.get('_native_dropper_uid') is not None else (id(z) == item['dropper'])) or not self._zombie(z):continue")]


# UI modules (tools/ui_modules.txt) are generated into src/ui/gen; inside them, references to other UI modules
# use the real translation even where the headless simulation build uses a shim (world_view, app, assets ...)
# ---- native build: the co-op entry moves into the lobby (there is no original game to return to)
SOURCE_PATCHES["menu_view"] = [
    ("""    button_w=min(152,(width-120)//4)
    buttons_width=button_w*4+18*3""", """    button_w=min(152,(width-120)//5)
    buttons_width=button_w*5+18*4"""),
    ("""(("对战图鉴","almanac"),("规则帮助","help"),("设置","settings"),("返回原游戏","exit"))):
        r.button(label,(bx+index*(button_w+18),by,button_w,37),("menu",action),size=16)""",
     """(("对战图鉴","almanac"),("规则帮助","help"),("设置","settings"),("合作闯关","coop_lobby"),("退出游戏","exit"))):
        r.button(label,(bx+index*(button_w+18),by,button_w,37),(action,) if action=="coop_lobby" else ("menu",action),size=16)"""),
]
SOURCE_PATCHES["rendering"] = [
    ("""        from .lobby_room import AI_ROOM_NAME, AI_DUO_ROOM_NAME
        for index, (name, duo) in enumerate(((AI_ROOM_NAME, False), (AI_DUO_ROOM_NAME, True))):""",
     """        from .lobby_room import AI_ROOM_NAME, AI_DUO_ROOM_NAME, AI_COOP_ROOM_NAME
        y = 157 + 2*65
        self.box((x, y, width-60, 57))
        self.text(AI_COOP_ROOM_NAME, (x+12, y+8), size=19, max_width=width-340)
        self.text(RULES["build"] + " · 合作闯关 · 等待加入", (x+12, y+34), COLORS["muted"], 13)
        self.button("进入合作", (width-305, y+8, 245, 40), ("coop_lobby",))
        for index, (name, duo) in enumerate(((AI_ROOM_NAME, False), (AI_DUO_ROOM_NAME, True))):"""),
    ("""        for index, room in enumerate(rooms[page*3:page*3+3]):
            y = 157 + (index+2)*65""", """        for index, room in enumerate(rooms[page*2:page*2+2]):
            y = 157 + (index+3)*65"""),
    ("""active=(page+1)*3<len(rooms))""", """active=(page+1)*2<len(rooms))"""),
]
SOURCE_PATCHES["pve_ui"] = [
    ("""        if kind == "coop_back":""", """        if kind == "coop_lobby":   # native build: co-op entry from the lobby / home screen
            self.native_entry = None
            self.state.update(screen="coop_entry", focus=None, network_mode="relay", room_public=True)
            return True
        if kind == "coop_back":"""),
]

UI_MODULES = set((Path(__file__).resolve().parent / "ui_modules.txt").read_text(encoding="utf-8").split())     if (Path(__file__).resolve().parent / "ui_modules.txt").exists() else set()
GEN_UI = [False]
DYNAMIC_METHOD_CLASSES = {("native_animation", "DrawReplay")}
OVERRIDABLE_METHOD_CLASSES = {("pvp70_content", "PvP70Content"), ("native_physics", "NativePhysics"), ("game_audio", "GameAudio"), ("native_content", "NativeContent"), ("pve", "WaveDirector"), ("pvp64_content", "PvP64Content"), ("native_battle", "NativeBattle"), ("simulation", "Battle"), ("native_targets", "NativeTargets")}


def is_shim(m):
    return m in SHIMS and not (GEN_UI[0] and m in UI_MODULES)


def header_path(m):
    if m.startswith("test_pvp_") or ((SHIM / (m + ".py")).exists() and not (GEN_UI[0] and m in UI_MODULES)):
        return "cpptests/gen/pm_%s.h" % m
    if GEN_UI[0] and m in UI_MODULES:
        return "ui/gen/pm_%s.h" % m
    return "sim/pvp/shim/pm_%s.h" % m if m in SHIMS else "sim/pvp/gen/pm_%s.h" % m


def skipped(mod, qual):
    if mod=='native_content' and os.environ.get('PVZ72_TRANSLATION_BASELINE'):
        return False
    return qual in SKIP.get(mod, ())


def ident(n):
    return n + "_" if n in CPP_KW else n


def cstr(s):
    parts = []
    for ch in s:
        cp = ord(ch)
        if cp < 32 or cp == 127 or 0xD800 <= cp <= 0xDFFF:
            parts.extend("\\%03o" % b for b in ch.encode("utf-8", "surrogatepass"))
        else:
            parts.append(json.dumps(ch, ensure_ascii=False)[1:-1])
    return '"' + "".join(parts) + '"' 


def big_lit(s):
    """std::string expression for a long text (MSVC caps one literal at 16 KB)."""
    chunks, cur, size = [], [], 0
    for ch in s:
        n = len(ch.encode("utf-8", "surrogatepass"))
        if size + n > 6000:
            chunks.append("".join(cur)); cur, size = [], 0
        cur.append(ch); size += n
    chunks.append("".join(cur))
    return "::pvz::py::cat_chunks({%s})" % ", ".join(cstr(c) for c in chunks)


# ======================================================================= pass 1
class ClassInfo:
    def __init__(self, module, node):
        self.module, self.node, self.name = module, node, node.name
        self.display_name = getattr(node, "_pvz_display_name", node.name)
        self.bases = [b for b in node.bases]
        self.methods = {}
        self.static = set()
        self.classmethods = set()
        self.properties = {}
        self.setters = {}
        self.attrs = []          # declared here (self.x stores, class vars)
        self.classvars = {}
        self.class_unpacks = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                decos = [d.id if isinstance(d, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else "?")
                         for d in item.decorator_list]
                if "property" in decos:
                    self.properties[item.name] = item
                elif "setter" in decos:
                    self.setters[item.name] = item
                else:
                    self.methods[item.name] = item
                    if "staticmethod" in decos:
                        self.static.add(item.name)
                    if "classmethod" in decos:
                        self.classmethods.add(item.name)
                    if "contextmanager" in decos:
                        item._pvz_ctxmgr = True
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name):
                        self.classvars[t.id] = item.value
                    elif isinstance(t,(ast.Tuple,ast.List)) and all(isinstance(n,ast.Name) for n in t.elts):
                        helper = "cv_unpack_%s_%d" % (ident(self.name),len(self.class_unpacks))
                        self.class_unpacks.append((helper,item.value,len(t.elts)))
                        for index, target in enumerate(t.elts):
                            value=ast.copy_location(ast.Constant(value=None),item.value)
                            value._pvz_cpp="%s().idx(%d)" % (helper,index)
                            self.classvars[target.id]=value
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                self.classvars[item.target.id] = item.value
        for fn in list(self.methods.values()) + list(self.properties.values()) + list(self.setters.values()):
            if not fn.args.args:
                continue
            selfname = fn.args.args[0].arg
            for n in ast.walk(fn):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == selfname \
                        and isinstance(n.ctx, ast.Store) and n.attr not in self.attrs:
                    self.attrs.append(n.attr)
        for cv in self.classvars:
            if cv not in self.attrs:
                self.attrs.append(cv)


class ModuleInfo:
    def __init__(self, name, tree):
        self.name, self.tree = name, tree
        self.funcs, self.classes, self.vars, self.imports = {}, {}, [], {}
        self.import_modules = {}
        for node in tree.body:
            self._scan(node)

    def _scan(self, node):
        if isinstance(node, ast.FunctionDef):
            self.funcs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            self.classes[node.name] = ClassInfo(self.name, node)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id not in self.vars:
                        self.vars.append(n.id)
        elif isinstance(node, ast.ImportFrom):
            if node.level >= 1:
                mod = node.module.split(".")[0] if node.module else None
                for a in node.names:
                    if mod is None:
                        self.import_modules[a.asname or a.name] = a.name
                    else:
                        self.imports[a.asname or a.name] = (mod, a.name)
            else:
                for a in node.names:
                    self.imports[a.asname or a.name] = ("@" + (node.module or ""), a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                self.import_modules[a.asname or a.name.split(".")[0]] = "@" + a.name
        elif isinstance(node, (ast.If, ast.Try)):
            for sub in ast.iter_child_nodes(node):
                if isinstance(sub, ast.stmt):
                    self._scan(sub)
                elif isinstance(sub, ast.ExceptHandler):
                    for s2 in sub.body:
                        self._scan(s2)
        elif isinstance(node, (ast.For, ast.While, ast.With)):
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id not in self.vars:
                    self.vars.append(n.id)


MODULES = {}

class NormalizeImports(ast.NodeTransformer):
    """Keep every alias when rewriting one import, and resolve helper re-exports."""
    def visit_Import(self, node):
        if len(node.names) <= 1:
            return node
        return [ast.copy_location(ast.Import(names=[alias]), node) for alias in node.names]

    def visit_ImportFrom(self, node):
        if node.level or not node.module or node.module in STDLIB or node.module.startswith("pvp"):
            return node
        helper = TESTS / (node.module.replace(".", "/") + ".py")
        if not helper.exists():
            return node
        exported = {}
        for statement in ast.parse(helper.read_text(encoding="utf-8")).body:
            if isinstance(statement, ast.ImportFrom) and statement.module and statement.module.startswith("pvp."):
                for alias in statement.names:
                    exported[alias.asname or alias.name] = (statement.module[4:], alias.name)
        result = []
        for alias in node.names:
            if alias.name in exported:
                module, original = exported[alias.name]
                result.append(ast.copy_location(ast.ImportFrom(module=module, names=[ast.alias(name=original, asname=alias.asname or alias.name)], level=1), node))
            else:
                result.append(ast.copy_location(ast.ImportFrom(module=node.module,names=[alias],level=node.level),node))
        return result


def load(name):
    if name not in MODULES:
        p = EXTRA_SOURCES.get(name, src_of(name))
        text = p.read_text(encoding="utf-8")
        for old, new in SOURCE_PATCHES.get(name, ()):
            if old not in text:
                raise SystemExit("source patch no longer matches %s: %r" % (name, old[:80]))
            text = text.replace(old, new, 1)
        tree = ast.parse(text)
        tree = NormalizeImports().visit(tree)
        if name == "test_pvp_flag_performance":
            # Preserve the original native-client assertions; this shared helper
            # constructs a real battle rather than running the Python test.
            import copy
            fixture_tree = ast.parse((TESTS / "probe_native_flag_performance.py").read_text(encoding="utf-8"))
            fixture = copy.deepcopy(next(n for n in fixture_tree.body if isinstance(n, ast.FunctionDef) and n.name == "make_battle"))
            for statement in tree.body:
                if isinstance(statement, ast.ImportFrom) and statement.module == "probe_native_flag_performance":
                    statement.names = [alias for alias in statement.names if alias.name != "make_battle"]
            tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.names]
            tree.body.extend([ast.ImportFrom(module="test_pvp_native_battle_combat",names=[ast.alias(name="field",asname=None)],level=0), ast.ImportFrom(module="catalog",names=[ast.alias(name="RULES",asname=None)],level=1), ast.ImportFrom(module="native_battle",names=[ast.alias(name="NativeBattle",asname=None)],level=1), fixture])
            ast.fix_missing_locations(tree)

        if name.startswith("test_pvp_"):
            # Python exposes nested helper classes as class attributes. Lift their implementation
            # to a unique C++ symbol and retain the actual binding in the enclosing class.
            lifted = []
            def lift_nested(parent, prefix):
                body = []
                aliases = {}
                class ClassBodyNames(ast.NodeTransformer):
                    def visit_Name(self, node):
                        if isinstance(node.ctx, ast.Load) and node.id in aliases:
                            return ast.copy_location(ast.Name(id=aliases[node.id], ctx=node.ctx), node)
                        return node
                    def visit_FunctionDef(self, node):
                        return node
                    def visit_Lambda(self, node):
                        return node
                for child in parent.body:
                    if isinstance(child, ast.ClassDef):
                        original_name = child.name
                        child.name = prefix + "__" + original_name
                        child._pvz_display_name = original_name
                        lift_nested(child, child.name)
                        lifted.append(child)
                        assignment = ast.Assign(targets=[ast.Name(id=original_name, ctx=ast.Store())],
                                                value=ast.Name(id=child.name, ctx=ast.Load()))
                        body.append(ast.copy_location(assignment, child))
                        aliases[original_name] = child.name
                    else:
                        body.append(ClassBodyNames().visit(child))
                        if isinstance(child, (ast.Assign, ast.AnnAssign)):
                            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                            for target in targets:
                                if isinstance(target, ast.Name): aliases.pop(target.id, None)
                parent.body = body
            reordered = []
            for statement in tree.body:
                if isinstance(statement, ast.ClassDef):
                    lifted = []; lift_nested(statement, statement.name); reordered.extend(lifted)
                reordered.append(statement)
            tree.body = reordered
        ast.fix_missing_locations(tree)
        # old-suite tests: `import unittest` -> the shim; `import test_pvp_x [as y]` -> sibling translated module
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "unittest" or a.name.startswith("test_pvp_"):
                        node.__class__ = ast.ImportFrom
                        node.module, node.level = None, 1
                        tgt = "pvzunit" if a.name == "unittest" else a.name
                        node.names = [ast.alias(name=tgt, asname=a.asname or a.name)]
                        break
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "unittest":
                if not any(a.name == "mock" for a in node.names):
                    node.module, node.level = "pvzunit", 1
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.startswith("test_pvp_"):
                node.level = 1
        # `from pvp.catalog import CARDS` (absolute package import) == `from .catalog import CARDS`
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and \
                    (node.module == "pvp" or node.module.startswith("pvp.")):
                node.level = 1
                node.module = node.module[4:] or None
        if name in DYNAMIC:
            # same filter as native_runtime.load_patch: imports, defs and plain assignments only
            body = []
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
                    body.append(node)
                elif isinstance(node, ast.Assign):
                    names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                    if not names & {"__pvz_sb_plant_zombie_test_enabled", "__pvz_sb_LOG_PATH"}:
                        body.append(node)
            tree.body = body
            if name == "patch1501":
                protect_patch_damage(tree)
                # native_content's pepper solver: the same interception solver choosing its high root
                import copy as _copy
                for node in list(tree.body):
                    if isinstance(node, ast.FunctionDef) and node.name == "__pvz_sb_solve_intercept":
                        high = _copy.deepcopy(node)
                        high.name = "__pvp_high_solve_intercept"
                        for n in ast.walk(high):
                            if isinstance(n, ast.Name) and n.id == "min":
                                n.id = "max"
                        tree.body.append(high)
                fold_key_constants(tree)
        MODULES[name] = ModuleInfo(name, tree)
    return MODULES[name]


def resolve_symbol(mod, name, depth=0):
    """-> ("var"|"func"|"class"|"module"|"stdlib"|"unknown", cpp, extra)"""
    m = load(mod)
    if name in m.vars and (name in m.funcs or name in m.classes):
        return ("var", "pm_%s::%s" % (mod, ident(name)), (mod, name))   # rebound at module level
    if name in m.classes:
        return ("class", "pm_%s::C_%s" % (mod, ident(name)), (mod, name))
    if name in m.funcs:
        return ("func", "pm_%s::f_%s" % (mod, ident(name)), (mod, name))
    if name in m.vars:
        return ("var", "pm_%s::%s" % (mod, ident(name)), (mod, name))
    if name in m.imports and depth < 8:
        src, orig = m.imports[name]
        if src.startswith("@"):
            return ("stdlib", src[1:] + "." + orig, None)
        if src_of(src).exists():
            return resolve_symbol(src, orig, depth + 1)
        return ("unknown", "%s.%s" % (src, orig), None)
    if name in m.import_modules and m.import_modules[name] == name and not name.startswith("@") \
            and not src_of(name).exists():
        # `from . import BUILD`: a constant of the package __init__
        return ("var", 'py::data_value("__init__", "%s")' % name, ("__init__", name))
    if name in m.import_modules:
        tgt = m.import_modules[name]
        if tgt.startswith("@"):
            return ("stdlib", tgt[1:], None)
        return ("module", tgt, None)
    if "*" in m.imports and depth < 8:
        src, _ = m.imports["*"]
        if not src.startswith("@") and src_of(src).exists():
            imported = load(src)
            exports = None
            for node in imported.tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                    try: exports = ast.literal_eval(node.value)
                    except (ValueError, TypeError): exports = []
            allowed = name in exports if exports is not None else not name.startswith("_")
            if allowed:
                resolved = resolve_symbol(src, name, depth + 1)
                if resolved[0] != "unknown":
                    return resolved
    return ("unknown", name, None)


def resolve_base(mod, b):
    """A class base: `Name` or `alias.Name` (from . import rv_r14 as r14; class Agent(r14.Agent))."""
    if isinstance(b, ast.Name):
        return resolve_symbol(mod, b.id)
    if isinstance(b, ast.Call) and isinstance(b.func, ast.Name) and b.func.id == "__import__" and b.args and isinstance(b.args[0], ast.Constant) and isinstance(b.args[0].value, str):
        target = b.args[0].value
        if src_of(target).exists():
            return ("module", target, None)
    if isinstance(b, ast.Attribute):
        k, cpp, key = resolve_base(mod, b.value)
        if k == "module":
            return resolve_symbol(cpp, b.attr)
        if k == "class":
            for owner in class_chain(class_info(key)):
                if b.attr in owner.classvars:
                    return resolve_base(owner.module, owner.classvars[b.attr])
    return ("unknown", None, None)


def class_info(cpp_or_key):
    mod, name = cpp_or_key
    ci = load(mod).classes[name]
    flatten_mixins(ci)
    return ci


def flatten_mixins(ci):
    """class A(B, M1, M2): C++ inherits B only; the mixins' members are copied into A in MRO order.

    Copied methods keep their home module for name resolution (ci.method_module)."""
    if getattr(ci, "_flat", False):
        return
    ci._flat = True
    ci.method_module = getattr(ci, "method_module", {})
    # A Python function assigned from another class is a descriptor on the new
    # class too. Copy the test helper body so it binds the receiving test object,
    # rather than C++-casting it to an unrelated fixture class.
    if ci.module.startswith("test_pvp_"):
        for mn, expr in list(ci.classvars.items()):
            if not isinstance(expr, ast.Attribute):
                continue
            kind, cpp, key = resolve_base(ci.module, expr.value)
            if kind != "class":
                continue
            owner = next((c for c in class_chain(class_info(key)) if expr.attr in c.methods), None)
            if owner is None:
                continue
            import copy
            fn = copy.deepcopy(owner.methods[expr.attr])
            fn.name = mn
            ci.methods[mn] = fn
            ci.method_module[mn] = owner.method_module.get(expr.attr, owner.module)
            if expr.attr in owner.static: ci.static.add(mn)
            if expr.attr in owner.classmethods: ci.classmethods.add(mn)
            del ci.classvars[mn]
            if mn in ci.attrs: ci.attrs.remove(mn)
            if fn.args.args:
                receiver = fn.args.args[0].arg
                for node in ast.walk(fn):
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == receiver and isinstance(node.ctx, ast.Store) and node.attr not in ci.attrs:
                        ci.attrs.append(node.attr)
    # Python tests sometimes rebind another class's unbound classmethod.
    # Copy its AST and home module; preserve the actual receiving class below.
    for mn, expr in list(ci.classvars.items()):
        if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "classmethod" and len(expr.args) == 1):
            continue
        ref = expr.args[0]
        if not (isinstance(ref, ast.Attribute) and ref.attr == "__func__" and isinstance(ref.value, ast.Attribute)):
            continue
        kind, cpp, key = resolve_base(ci.module, ref.value.value)
        if kind != "class":
            continue
        other = class_info(key)
        owner = next((c for c in class_chain(other) if ref.value.attr in c.methods), None)
        if owner is None:
            continue
        fn = owner.methods[ref.value.attr]
        import copy
        fn = copy.deepcopy(fn)
        fn.name = mn
        ci.methods[mn] = fn
        ci.classmethods.add(mn)
        ci.method_module[mn] = owner.method_module.get(ref.value.attr, owner.module)
        del ci.classvars[mn]
        if mn in ci.attrs: ci.attrs.remove(mn)
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == fn.args.args[0].arg and isinstance(node.ctx, ast.Store) and node.attr not in ci.attrs:
                ci.attrs.append(node.attr)
    ci.extra_isa = []
    tb = []
    for b in ci.bases:
        if True:
            kind, cpp, key = resolve_base(ci.module, b)
            if kind == "class":
                tb.append((b, class_info(key)))
    if len(tb) <= 1:
        return
    # primary C++ base: the first base with a translated ancestry (class X(Mixin, Base) inherits Base);
    # mixins listed before it come earlier in the MRO, so their methods override the primary chain and
    # their super() calls land on the primary (super() in a copied method resolves against X's base).
    pi = next((i for i, (_, c) in enumerate(tb) if len(class_chain(c)) > 1), 0)
    if pi:
        tb = [tb[pi]] + tb[:pi] + tb[pi + 1:]
    primary = class_chain(tb[0][1])
    own_attrs = list(ci.attrs)
    have_m = set(ci.methods)
    have_p = set(ci.properties)
    prim_m = set()
    for c in primary:
        prim_m |= set(c.methods); have_p |= set(c.properties)
    for idx, (_, sec) in enumerate(tb[1:]):
        before = idx < pi
        if not before:
            have_m |= prim_m
        for c in class_chain(sec):
            if c in primary:
                continue
            ci.extra_isa.append(c.name)
            for mn, fn in c.methods.items():
                if mn in have_m:
                    continue
                have_m.add(mn)
                ci.methods[mn] = fn
                ci.method_module[mn] = getattr(c, "method_module", {}).get(mn, c.module)
                if mn in c.static: ci.static.add(mn)
                if mn in c.classmethods: ci.classmethods.add(mn)
            for pn, fn in c.properties.items():
                if pn not in have_p:
                    have_p.add(pn); ci.properties[pn] = fn
                    ci.method_module["@p:" + pn] = c.module
                    if pn in c.setters: ci.setters[pn] = c.setters[pn]
            for a in c.attrs:
                if a not in ci.attrs:
                    ci.attrs.append(a)
    # attributes the primary chain already declares stay there
    prim_attrs = set()
    for c in primary:
        prim_attrs |= set(c.attrs)
    ci.attrs = own_attrs + [a for a in ci.attrs if a not in own_attrs and a not in prim_attrs]
    ci.bases = [tb[0][0]] + [b for b in ci.bases if not any(b is x for x, _ in tb)]


def class_chain(ci):
    """ClassInfo list from ci up through translated bases."""
    out = [ci]
    for b in ci.bases:
        if True:
            kind, cpp, key = resolve_base(ci.module, b)
            if kind == "class":
                out += class_chain(class_info(key))
    return out


def base_cpp(ci):
    for b in ci.bases:
        if True:
            kind, cpp, key = resolve_base(ci.module, b)
            if kind == "class":
                return cpp, key
    return None, None


def exc_bases(ci):
    """Ancestor names if the class derives from a builtin exception, else []."""
    names = []
    for b in ci.bases:
        if isinstance(b, ast.Name):
            if b.id in BUILTIN_EXC:
                names.append(b.id)
            else:
                kind, cpp, key = resolve_symbol(ci.module, b.id)
                if kind == "class":
                    sub = exc_bases(class_info(key))
                    if sub:
                        names.append(class_info(key).name)
                        names += sub
    return names


def is_exception_class(ci):
    return bool(exc_bases(ci))


# ======================================================================= pass 2
class Scope:
    def __init__(self, kind, locals_=(), parent=None, cls=None, selfname=None, gen=False):
        self.kind = kind                    # module | func | method | lambda
        self.locals = set(locals_)
        self.parent = parent
        self.cls = cls
        self.selfname = selfname
        self.globals_decl = set()
        self.nonlocal_decl = set()
        self.gen = gen
        self.method_scope = lambda: None
        self.tmp = 0
        self.local_modules = {}             # function-level `from . import m` aliases -> module name

    def local_module(self, n):
        s = self
        while s is not None:
            if n in s.local_modules:
                return s.local_modules[n]
            s = s.parent
        return None

    def lookup_local(self, n):
        s = self
        while s is not None:
            if n in s.globals_decl:
                return None
            if s.kind != "module" and n in s.locals and n not in s.nonlocal_decl:
                return s
            s = s.parent
        return None

    def new_tmp(self):
        root = self
        while root.parent is not None and root.kind == "lambda":
            root = root.parent
        root.tmp += 1
        return root.tmp


class Gen:
    def __init__(self, mod):
        self.mod = mod
        self.mi = load(mod)
        self.out = []
        self.todo = []
        self.syms = set()
        self.deps = set()
        self.gen_decls = []

    def todo_(self, what):
        self.todo.append(what)
        return 'PVZ_TODO(%s)' % cstr("%s (%s.py:%s)" % (what, self.mod, getattr(self, "cur_line", "?")))

    def sy(self, s):
        return "SY(%s)" % cstr(s)

    def sv(self, s):
        if "\x00" in s:
            return "V(std::string(%s, %d))" % (cstr(s), len(s.encode("utf-8", "surrogatepass")))
        if len(s.encode("utf-8", "surrogatepass")) > 8000:
            return "([]() -> const ::pvz::V& { static const ::pvz::V v_(%s); return v_; }())" % big_lit(s)
        return "SV(%s)" % cstr(s)

    # -------------------------------------------------------------- names
    def name_ref(self, n, sc):
        if self.mod == "test_pvp_integration" and n == "exec" and sc.lookup_local(n) is None:
            return 'V::func([](const Args& A){return py::native_hook(V("exec"),A);})'
        if self.mod == "test_pvp_integration" and n == "__builtins__":
            return 'py::stdlib_module(V("builtins"))'
        if getattr(sc, "recursive_name", None) == n:
            return 'py::native_hook(V("runtime.current_function"), Args{})'

        if n in ("True", "False"):
            return "V(%s)" % n.lower()
        if n == "None":
            return "V::none()"
        if n == "__name__":
            return self.sv(self.mod if self.mod.startswith("test_pvp_") else "pvp." + self.mod)
        if n == "open" and sc.lookup_local("open") is None and resolve_symbol(self.mod, "open")[0] == "unknown":
            return "V::func(py::open_file)"
        if n == "__package__":
            return self.sv("pvp")
        if n == "__file__":
            return "py::module_file(%s)" % self.sv(self.mod)
        own = sc.lookup_local(n)
        if own is not None:
            if own.kind == "method" and own.selfname == n:
                return "self_v()"
            return "L_" + ident(n)
        if sc.cls is not None and False:
            pass
        kind, cpp, key = resolve_symbol(self.mod, n)
        if kind == "var":
            if key[0] != "__init__":
                self.deps.add(key[0])
            return cpp
        if kind == "func":
            self.deps.add(key[0])
            if is_shim(key[0]):
                header = ROOT / "src" / header_path(key[0])
                symbol = "f_" + ident(key[1])
                if header.exists() and not re.search(r"\b" + re.escape(symbol) + r"\s*\(", header.read_text(encoding="utf-8")):
                    # Keep unrelated cases collectible. Calling an unported
                    # API fails explicitly rather than returning a placeholder.
                    message = cstr("missing production shim API %s.%s" % key)
                    return "V::func([](const Args&) -> V { return PVZ_TODO(%s); })" % message
            return "V::func(%s)" % cpp
        if kind == "class":
            self.deps.add(key[0])
            return self.production_call(key[0], "cls_" + ident(key[1]), "Args{}")
        if kind == "module":
            return "pm_%s::module_ns()" % cpp
        if kind == "stdlib":
            return "py::stdlib(%s)" % self.sv(cpp)
        if n in BUILTIN_EXC:
            return "py::exc_type(%s)" % self.sv(n)
        if n in BUILTIN_FUNCS or n in ("object", "dict", "list", "tuple", "set", "frozenset", "str", "int", "float", "bool",
                                       "bytes", "bytearray", "complex", "slice", "NotImplemented", "Ellipsis"):
            return "py::builtin(%s)" % self.sv(n)
        return self.todo_("unresolved name %s" % n)

    def const(self, v):
        if v is None:
            return "V::none()"
        if isinstance(v, bool):
            return "V(%s)" % ("true" if v else "false")
        if isinstance(v, int):
            return "V(%s.0)" % v if abs(v) < 2 ** 53 else "V(%r)" % float(v)
        if isinstance(v, float):
            r = repr(v)
            if r == "inf": return "V(INFINITY)"
            if r == "-inf": return "V(-INFINITY)"
            if r == "nan": return "V(NAN)"
            return "V(%s)" % r
        if isinstance(v, str):
            return self.sv(v)
        if isinstance(v, bytes):
            if len(v) > 3000:
                return "py::bytes_v(%s.c_str())" % big_lit(v.hex())
            return "py::bytes_v(%s)" % cstr(v.hex())
        if isinstance(v, tuple):
            return "V::tuple({%s})" % ", ".join(self.const(x) for x in v)
        return self.todo_("constant %r" % type(v))

    # -------------------------------------------------------------- expressions
    def expr(self, e, sc):
        if hasattr(e,"_pvz_cpp"):
            return e._pvz_cpp

        m = getattr(self, "e_" + type(e).__name__, None)
        if m is None:
            return self.todo_("expr " + type(e).__name__)
        return m(e, sc)

    def cond(self, e, sc):
        if isinstance(e, ast.BoolOp):
            op = " && " if isinstance(e.op, ast.And) else " || "
            return "(" + op.join(self.cond(v, sc) for v in e.values) + ")"
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            return "!" + self.cond(e.operand, sc)
        if isinstance(e, ast.Compare):
            return self.compare(e, sc)
        if isinstance(e, ast.Constant) and isinstance(e.value, bool):
            return "true" if e.value else "false"
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ("isinstance", "hasattr", "callable") \
                and sc.lookup_local(e.func.id) is None:
            return "(%s).truthy()" % self.expr(e, sc)
        return "(%s).truthy()" % self.expr(e, sc)

    def e_Constant(self, e, sc):
        return self.const(e.value)

    def e_Num(self, e, sc):
        return self.const(e.n)

    def e_Str(self, e, sc):
        return self.const(e.s)

    def e_NameConstant(self, e, sc):
        return self.const(e.value)

    def e_Name(self, e, sc):
        if sc.selfname and e.id == sc.selfname and sc.lookup_local(e.id) is sc.method_scope():
            return "self_v()"
        return self.name_ref(e.id, sc)

    def e_BinOp(self, e, sc):
        a, b = self.expr(e.left, sc), self.expr(e.right, sc)
        op = type(e.op).__name__
        if op == "Mod" and isinstance(e.left, (ast.Constant, ast.Str)) and isinstance(getattr(e.left, "value", getattr(e.left, "s", None)), str):
            return "py::percent(%s, %s)" % (a, b)
        if op == "FloorDiv":
            return "floordiv(%s, %s)" % (a, b)
        if op == "Pow":
            return "pow(%s, %s)" % (a, b)
        if op in ("BitAnd", "BitOr", "BitXor", "LShift", "RShift"):
            return "py::bitop(%s, %s, %s)" % (cstr(op), a, b)
        sym = {"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "Mod": "%"}.get(op)
        if sym is None:
            return self.todo_("binop " + op)
        return "(%s %s %s)" % (a, sym, b)

    def e_UnaryOp(self, e, sc):
        if isinstance(e.op, ast.Not):
            return "V(%s)" % self.cond(e, sc)
        if isinstance(e.op, ast.USub):
            if isinstance(e.operand, ast.Constant) and isinstance(e.operand.value, (int, float)) and not isinstance(e.operand.value, bool):
                return self.const(-e.operand.value)
            return "(-%s)" % self.expr(e.operand, sc)
        if isinstance(e.op, ast.UAdd):
            return self.expr(e.operand, sc)
        if isinstance(e.op, ast.Invert):
            return "py::invert(%s)" % self.expr(e.operand, sc)
        return self.todo_("unary")

    def lam(self, body, sc):
        """[&] thunk for short-circuit value expressions."""
        return "[&]() -> V { return %s; }" % body

    def e_BoolOp(self, e, sc):
        vals = [self.expr(v, sc) for v in e.values]
        out = vals[-1]
        for v in reversed(vals[:-1]):
            fn = "py_and" if isinstance(e.op, ast.And) else "py_or"
            out = "%s(%s, %s)" % (fn, v, self.lam(out, sc))
        return out

    def compare(self, e, sc):
        parts = []
        left = self.expr(e.left, sc)
        n = len(e.ops)
        pre = []
        for i, (op, rn) in enumerate(zip(e.ops, e.comparators)):
            right = self.expr(rn, sc)
            if n > 1 and i < n - 1 and not isinstance(rn, (ast.Constant, ast.Name)):
                t = sc.new_tmp()
                pre.append((t, right))
                right = "ct%d_" % t
            o = type(op).__name__
            if o == "In":
                parts.append("py::in(%s, %s)" % (left, right))
            elif o == "NotIn":
                parts.append("!py::in(%s, %s)" % (left, right))
            elif o == "Is":
                parts.append("py_is(%s, %s)" % (left, right))
            elif o == "IsNot":
                parts.append("!py_is(%s, %s)" % (left, right))
            else:
                sym = {"Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">="}[o]
                parts.append("(%s %s %s)" % (left, sym, right))
            left = right
        if not pre:
            return parts[0] if len(parts) == 1 else "(" + " && ".join(parts) + ")"
        # chained compare with evaluated-once middles
        body = " && ".join(parts)
        binds = "".join("V ct%d_ = %s; " % (t, r) for t, r in pre)
        return "[&]() -> bool { %sreturn %s; }()" % (binds, body)

    def e_Compare(self, e, sc):
        return "V(%s)" % self.compare(e, sc)

    def slice_parts(self, sl, sc):
        lo = self.expr(sl.lower, sc) if sl.lower else "V::none()"
        hi = self.expr(sl.upper, sc) if sl.upper else "V::none()"
        if sl.step is not None:
            return lo, hi, self.expr(sl.step, sc)
        return lo, hi, None

    def e_Subscript(self, e, sc):
        base = self.expr(e.value, sc)
        sl = e.slice.value if isinstance(e.slice, ast.Index) else e.slice
        if isinstance(sl, ast.Slice):
            lo, hi, st = self.slice_parts(sl, sc)
            if st is not None:
                return "py::slice_step(%s, %s, %s, %s)" % (base, lo, hi, st)
            return "py::slice(%s, %s, %s)" % (base, lo, hi)
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in OBJ_KEYS:
            return "rdm(%s, &Obj::%s, %s)" % (base, sl.value, self.sv(sl.value))
        if isinstance(sl, ast.Tuple):
            return "rd(%s, %s)" % (base, self.e_Tuple(sl, sc))
        return "rd(%s, %s)" % (base, self.expr(sl, sc))

    # attribute of self -> member
    def self_descriptor(self, e, sc):
        if not (sc.selfname and isinstance(e.value, ast.Name) and e.value.id == sc.selfname
                and sc.lookup_local(sc.selfname) is sc.method_scope()):
            return False
        # A subclass property overrides a base instance field in Python. Reads
        # and writes in the base must still invoke that descriptor on self.
        for candidate in self.mi.classes.values():
            if e.attr in candidate.properties and any(
                    base.module == sc.cls.module and base.name == sc.cls.name
                    for base in class_chain(candidate)):
                return True
        return False

    def self_attr(self, e, sc):
        if self.self_descriptor(e, sc):
            return None
        if sc.selfname and isinstance(e.value, ast.Name) and e.value.id == sc.selfname \
                and sc.lookup_local(sc.selfname) is sc.method_scope():
            chain = class_chain(sc.cls)
            for ci in chain:
                if e.attr in ci.attrs:
                    return "a_" + ident(e.attr)
        return None

    def local_module_attr(self, e, sc):
        """`m.attr` where m was bound by a function-level `from . import m`: the module's real symbol."""
        if not (isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name)):
            return None
        mod = sc.local_module(e.value.id)
        if mod is None:
            return None
        k2, c2, key2 = resolve_symbol(mod, e.attr)
        if is_shim(mod):
            # a shim provides only what its header declares; the rest stays the no-op module attribute
            header = (Path(__file__).resolve().parents[1] / "src" / "sim" / "pvp" / "shim" / ("pm_%s.h" % mod))
            text = header.read_text(encoding="utf-8") if header.exists() else ""
            if k2 != "func" or (" f_%s(" % ident(e.attr)) not in text:
                return None
        self.deps.add(mod)
        if k2 in ("var", "func", "class"):
            return k2, c2, key2
        return None

    def e_Attribute(self, e, sc):
        if self.self_descriptor(e, sc):
            return "pvz::getattr(%s, %s)" % (self.expr(e.value, sc), self.sy(e.attr))
        m = self.self_attr(e, sc)
        if m:
            return m
        lm = self.local_module_attr(e, sc)
        if lm:
            k2, c2, key2 = lm
            return c2 if k2 == "var" else ("V::func(%s)" % c2 if k2 == "func" else "pm_%s::cls_%s()" % (key2[0], ident(key2[1])))
        if isinstance(e.value, ast.Name) and sc.lookup_local(e.value.id) is None:
            kind, cpp, key = resolve_symbol(self.mod, e.value.id)
            if kind == "module":
                self.deps.add(cpp)
                k2, c2, key2 = resolve_symbol(cpp, e.attr)
                if k2 == "var":
                    return c2
                if k2 == "func":
                    return "V::func(%s)" % c2
                if k2 == "class":
                    return self.production_call(key2[0], "cls_" + ident(key2[1]), "Args{}")
            if kind == "stdlib":
                return "py::stdlib_attr(%s, %s)" % (self.sv(cpp), self.sv(e.attr))
            if kind == "class":
                ci = class_info(key)
                for c in class_chain(ci):
                    if e.attr in c.classvars:
                        self.deps.add(c.module)
                        if skipped(c.module, c.name):
                            return "pvz::getattr(pm_%s::cls_%s(), %s)" % (c.module,ident(c.name),self.sy(e.attr))
                        return "pm_%s::C_%s::cv_%s()" % (c.module, ident(c.name), ident(e.attr))
                    if e.attr in c.methods and e.attr in c.static:
                        return "V::func(&pm_%s::C_%s::m_%s)" % (c.module, ident(c.name), ident(e.attr))
        if sc.selfname and isinstance(e.value, ast.Name) and e.value.id == sc.selfname \
                and sc.lookup_local(sc.selfname) is sc.method_scope():
            for c in class_chain(sc.cls):
                if e.attr in c.properties:
                    return "pr_%s()" % ident(e.attr)
                if e.attr in c.methods:
                    if sc.cls.module.startswith("rv_") or sc.cls.module in ("app", "room"):
                        return "pvz::getattr(self(), %s)" % self.sy(e.attr)
                    return "method(%s)" % self.sy(e.attr)
        return "pvz::getattr(%s, %s)" % (self.expr(e.value, sc), self.sy(e.attr))

    # -------------------------------------------------------------- calls
    def args(self,e,sc):
        if not any(isinstance(x,ast.Starred) for x in e.args) and not any(k.arg is None for k in e.keywords):
            pos=[self.expr(x,sc) for x in e.args]
            kws=['{%s, %s}'%(self.sy(k.arg),self.expr(k.value,sc)) for k in e.keywords]
            return 'Args({%s}, {%s})'%(', '.join(pos),', '.join(kws)) if kws else 'Args{%s}'%', '.join(pos)
        code=['[&]() -> Args { Args expanded_;']
        for i,arg in enumerate(e.args):
            if isinstance(arg,ast.Starred):
                code.append('{ V spread_=py::iter_list(%s); for(const V& item_:spread_.items())expanded_.pos.push_back(item_); }'%self.expr(arg.value,sc))
            else:code.append('expanded_.pos.push_back(%s);'%self.expr(arg,sc))
        code.append('auto keyword_=[&](Sym key_,const V& value_){ for(const auto& present_:expanded_.kw)if(present_.first==key_)throw PyError("TypeError","multiple values for keyword argument "+key_.str());expanded_.kw.emplace_back(key_,value_); };')
        for keyword in e.keywords:
            if keyword.arg is not None:code.append('keyword_(%s,%s);'%(self.sy(keyword.arg),self.expr(keyword.value,sc)))
            else:
                code.append('{ V mapping_=%s; V keys_; if(mapping_.t==V::DICT || mapping_.t==V::OBJ) keys_=py::keys(mapping_); else if(mapping_.t==V::INST && pvz::hasattr(mapping_,SY("keys")))keys_=callm(mapping_,SY("keys"),Args{});else throw PyError("TypeError","argument after ** must be a mapping");V held_=py::iter_list(keys_);for(const V& key_:held_.items()){if(!key_.is_str() || key_.byt)throw PyError("TypeError","keywords must be strings");keyword_(key_.sym(),rd(mapping_,key_));} }'%self.expr(keyword.value,sc))
        code.append('return expanded_; }()')
        return ' '.join(code)

    def production_call(self, module, symbol, args):
        header = ROOT / "src" / header_path(module)
        own_definition = module == self.mod and ((symbol.startswith("new_") and symbol[4:] in {ident(n) for n in self.mi.classes}) or (symbol.startswith("f_") and symbol[2:] in {ident(n) for n in self.mi.funcs}))
        if not own_definition and "/shim/" in header.as_posix() and header.exists():
            text = header.read_text(encoding="utf-8")
            if not re.search(r"\b" + re.escape(symbol) + r"\s*\(", text):
                if symbol.startswith("new_") and re.search(r"\bcls_" + re.escape(symbol[4:]) + r"\s*\(", text):
                    return "pm_%s::cls_%s().call(%s)" % (module,symbol[4:],args)
                return self.todo_("missing production shim API %s.%s" % (module,symbol))
        if symbol.startswith("cls_"):
            return "pm_%s::%s()" % (module,symbol)
        if GEN_UI[0] and "/shim/" not in header.as_posix() and header.exists() and "V module_ns();" in header.read_text(encoding="utf-8"):
            if symbol.startswith("f_") or symbol.startswith("new_"):
                attr = symbol[2:] if symbol.startswith("f_") else symbol[4:]
                return "callm(pm_%s::module_ns(), %s, %s)" % (module, self.sy(attr), args)
        return "pm_%s::%s(%s)" % (module,symbol,args)

    def e_Call(self, e, sc):
        f = e.func
        # An unbound classmethod takes an explicit receiving class.
        if isinstance(f, ast.Attribute) and f.attr == "__func__" and isinstance(f.value, ast.Attribute):
            kind, cpp, key = resolve_base(self.mod, f.value.value)
            if kind == "class":
                owner = next((c for c in class_chain(class_info(key)) if f.value.attr in c.methods), None)
                if owner is not None and f.value.attr in owner.classmethods:
                    self.deps.add(owner.module)
                    return '[&]() -> V { Args bound = %s; if (bound.pos.empty()) throw PyError("TypeError", "unbound classmethod requires a class"); V receiver=bound.pos.front(); bound.pos.erase(bound.pos.begin()); bound.kw.emplace_back(SY("__pvz_cls"),receiver); return pm_%s::C_%s::m_%s(bound); }()' % (self.args(e, sc), owner.module, ident(owner.name), ident(f.value.attr))
        if isinstance(f, ast.Name) and sc.lookup_local(f.id) is None:
            special = self.builtin_call(f.id, e, sc)
            if special is not None:
                return special
            kind, cpp, key = resolve_symbol(self.mod, f.id)
            if GEN_UI[0] and ((f.id in self.mi.imports and kind in ("func", "class")) or (kind == "func" and key[0] == self.mod)):
                return "callm(pm_%s::module_ns(), %s, %s)" % (self.mod, self.sy(f.id), self.args(e, sc))
            if kind == "func":
                self.deps.add(key[0])
                return self.production_call(key[0], "f_" + ident(key[1]), self.args(e, sc))
            if kind == "class":
                self.deps.add(key[0])
                ci = class_info(key)
                if is_exception_class(ci):
                    return "py::make_exc(%s, %s, %s)" % (self.sv(ci.name), self.args(e, sc), cstr(",".join(exc_bases(ci))))
                return self.production_call(key[0], "new_" + ident(key[1]), self.args(e, sc))
            if kind == "stdlib":
                return "py::stdlib_call(%s, %s)" % (self.sv(cpp), self.args(e, sc))
            if f.id in BUILTIN_EXC:
                return "py::make_exc(%s, %s, \"\")" % (self.sv(f.id), self.args(e, sc))
        inl = self.stdlib_inline(f, e, sc)
        if inl:
            return inl
        lm = self.local_module_attr(f, sc) if isinstance(f, ast.Attribute) else None
        if lm:
            k2, c2, key2 = lm
            if k2 == "func":
                if key2: self.deps.add(key2[0])
                return self.production_call(key2[0], "f_" + ident(key2[1]), self.args(e, sc))
            if k2 == "class":
                if key2: self.deps.add(key2[0])
                return self.production_call(key2[0], "new_" + ident(key2[1]), self.args(e, sc))
            return "(%s).call(%s)" % (c2, self.args(e, sc))
        if isinstance(f, ast.Attribute):
            # super().m(...)
            if isinstance(f.value, ast.Call) and isinstance(f.value.func, ast.Name) and f.value.func.id == "super":
                bcpp, bkey = base_cpp(sc.cls)
                if bcpp is None:
                    if f.attr == "__init__":
                        return "V::none()"
                    return self.todo_("super() without translated base")
                if bkey is not None and getattr(sc, "class_receiver", None):
                    for base in class_chain(class_info(bkey)):
                        if f.attr in base.methods:
                            if f.attr in base.classmethods:
                                return '[&]() -> V { Args bound = %s; bound.kw.emplace_back(SY("__pvz_cls"), L_%s); return %s::m_%s(bound); }()' % (self.args(e, sc), ident(sc.class_receiver), bcpp, ident(f.attr))
                            break
                return "%s::m_%s(%s)" % (bcpp, ident(f.attr), self.args(e, sc))
            # Base.method(self, ...)
            if (isinstance(f.value, ast.Name) and sc.lookup_local(f.value.id) is None) or \
                    (isinstance(f.value, ast.Attribute) and isinstance(f.value.value, ast.Name)
                     and sc.lookup_local(f.value.value.id) is None):   # also alias.Base.method(self, ...)
                if isinstance(f.value, ast.Name):
                    kind, cpp, key = resolve_symbol(self.mod, f.value.id)
                else:
                    kind, cpp, key = resolve_base(self.mod, f.value)
                    if kind != "class":
                        kind = None
                if kind == "class":
                    ci = class_info(key)
                    for c in class_chain(ci):
                        if f.attr in c.methods:
                            if f.attr in c.static or f.attr in c.classmethods:
                                self.deps.add(c.module)
                                return "pm_%s::C_%s::m_%s(%s)" % (c.module, ident(c.name), ident(f.attr), self.args(e, sc))
                            # Python permits explicitly invoking a test helper on an unrelated
                            # TestCase. Emit that helper's original body over its explicit V self,
                            # rather than incorrectly requiring C++ inheritance.
                            if self.mod.startswith("test_pvp_") and c.module.startswith("test_pvp_"):
                                args_code = self.args(e, sc)
                                saved = (self.mod, self.mi)
                                self.mod, self.mi = c.module, load(c.module)
                                self.deps.add(c.module)
                                try:
                                    helper_lines, gen, ctx = self.function_body(c.methods[f.attr], Scope("module"), cls=None, method=False)
                                finally:
                                    self.mod, self.mi = saved
                                if not gen:
                                    return "V::func([](const Args& A) -> V {\n%s\nreturn V::none(); }).call(%s)" % ("\n".join(helper_lines), args_code)
                            # unbound call with explicit self as first arg
                            a = self.args(e, sc)
                            # qualified (non-virtual) call: Base.m(self) must not dispatch back to the override
                            q = "pm_%s::C_%s" % (c.module, ident(c.name))
                            return "py::unbound_call<%s>([](%s* s_, const Args& r_) { return s_->%s::m_%s(r_); }, %s)" % (q, q, q, ident(f.attr), a)
                if kind == "module":
                    self.deps.add(cpp)
                    k2, c2, key2 = resolve_symbol(cpp, f.attr)
                    if k2 == "func":
                        if key2: self.deps.add(key2[0])
                        return self.production_call(key2[0], "f_" + ident(key2[1]), self.args(e, sc))
                    if k2 == "class":
                        if key2: self.deps.add(key2[0])
                        return self.production_call(key2[0], "new_" + ident(key2[1]), self.args(e, sc))
                if kind == "stdlib":
                    return "py::stdlib_call(%s, %s)" % (self.sv(cpp + "." + f.attr), self.args(e, sc))
                if isinstance(f.value, ast.Name) and f.value.id in ("dict", "list", "str", "set", "float", "int", "object") and kind == "unknown":
                    return "py::type_method(%s, %s, %s)" % (self.sv(f.value.id), self.sv(f.attr), self.args(e, sc))
            # self.method(...)
            if sc.selfname and isinstance(f.value, ast.Name) and f.value.id == sc.selfname \
                    and sc.lookup_local(sc.selfname) is sc.method_scope():
                attr_member = self.self_attr(f, sc)
                for c in class_chain(sc.cls):
                    if f.attr in c.methods and not attr_member:
                        if GEN_UI[0] or (sc.cls.module, sc.cls.name) in DYNAMIC_METHOD_CLASSES:
                            return "callm(self(), %s, %s)" % (self.sy(f.attr), self.args(e, sc))
                        if (sc.cls.module, sc.cls.name) in OVERRIDABLE_METHOD_CLASSES or sc.cls.module.startswith("rv_") or sc.cls.module == "room":
                            args = self.args(e, sc)
                            return "[&]() -> V { if (this->find_dyn(SY(\"__native_local_class__\"))) return callm(self(), %s, %s); if (V* replacement = this->find_dyn(%s)) return replacement->call(%s); return m_%s(%s); }()" % (self.sy(f.attr), args, self.sy(f.attr), args, ident(f.attr), args)
                        return "m_%s(%s)" % (ident(f.attr), self.args(e, sc))
                if attr_member:
                    if sc.cls.module.startswith("rv_"):
                        return "callm(self(), %s, %s)" % (self.sy(f.attr), self.args(e, sc))
                    return "%s.call(%s)" % (attr_member, self.args(e, sc))
            if f.attr == "sort" and e.keywords:
                return "py::sort_inplace(%s, %s)" % (self.expr(f.value, sc), self.args(e, sc))
            fast = self.fast_method(f, e, sc)
            if fast:
                return fast
            return "callm(%s, %s, %s)" % (self.expr(f.value, sc), self.sy(f.attr), self.args(e, sc))
        return "(%s).call(%s)" % (self.expr(f, sc), self.args(e, sc))

    def stdlib_inline(self, f, e, sc):
        """math.X(...) / sys._getframe(1) through a module-level stdlib import (any alias)."""
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)) or e.keywords                 or any(isinstance(x, ast.Starred) for x in e.args) or sc.lookup_local(f.value.id) is not None:
            return None
        tgt = self.mi.import_modules.get(f.value.id)
        if tgt == "@math" and f.attr in MATH_INLINE and MATH_INLINE[f.attr][0] == len(e.args):
            return MATH_INLINE[f.attr][1] % tuple(self.expr(x, sc) for x in e.args)
        if tgt == "@sys" and f.attr == "_getframe" and len(e.args) == 1 and isinstance(e.args[0], ast.Constant) and e.args[0].value == 1:
            return "py::getframe()"
        return None

    def fast_method(self, f, e, sc):
        """x.get(k[, d]) / x.append(v): inline dict/list path, callm fallback for everything else."""
        if e.keywords or any(isinstance(x, ast.Starred) for x in e.args):
            return None
        if f.attr == "get" and len(e.args) in (1, 2):
            a = [self.expr(x, sc) for x in e.args]
            k = e.args[0]
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in OBJ_KEYS:
                return "py::m_get_slot(%s, &Obj::%s, %s)" % (self.expr(f.value, sc), k.value, ", ".join(a))
            return "py::m_get(%s, %s)" % (self.expr(f.value, sc), ", ".join(a))
        if f.attr == "append" and len(e.args) == 1:
            return "py::m_append(%s, %s)" % (self.expr(f.value, sc), self.expr(e.args[0], sc))
        return None

    def builtin_call(self, n, e, sc):
        if n == "__import__" and len(e.args) == 1 and isinstance(e.args[0], ast.Constant) and isinstance(e.args[0].value, str):
            target = e.args[0].value
            if target.startswith("test_pvp_") and src_of(target).exists():
                self.deps.add(target)
                return "pm_%s::module_ns()" % target
            if target.startswith("pvp.") and any(k.arg == "fromlist" for k in e.keywords):
                module = target.split(".", 1)[1]
                if "." not in module and src_of(module).exists() and not is_shim(module):
                    self.deps.add(module)
                    return "pm_%s::module_ns()" % module
            if target in STDLIB or target == "pygame":
                return "py::stdlib_module(%s)" % self.sv(target)
        kind = resolve_symbol(self.mod, n)[0]
        if kind != "unknown":
            return None
        a = [self.expr(x, sc) for x in e.args if not isinstance(x, ast.Starred)]
        kw = {k.arg: k.value for k in e.keywords}
        if n == "range":
            if any(isinstance(x, ast.Starred) for x in e.args):
                return "py::builtin_call(%s, %s)" % (self.sv("range"), self.args(e, sc))
            return "py::range(%s)" % ", ".join("(int64_t)(%s).num()" % x for x in a)
        if n in ("min", "max"):
            key = ("py::keyfn(%s)" % self.expr(kw["key"], sc)) if "key" in kw else "py::Key()"
            dflt = self.expr(kw["default"], sc) if "default" in kw else "V()"
            if len(a) == 1:
                return "py::%s_it(%s, %s, %s)" % (n, a[0], key, dflt)
            return "py::%s_it(V::list({%s}), %s, %s)" % (n, ", ".join(a), key, dflt)
        if n == "sorted":
            key = ("py::keyfn(%s)" % self.expr(kw["key"], sc)) if "key" in kw else "py::Key()"
            rev = self.cond(kw["reverse"], sc) if "reverse" in kw else "false"
            return "py::sorted_it(%s, %s, %s)" % (a[0], key, rev)
        if n == "isinstance":
            types = e.args[1]
            elts = types.elts if isinstance(types, ast.Tuple) else [types]
            tests = []
            for t in elts:
                tests.append(self.type_test(a[0], t, sc))
            return "V(%s)" % " || ".join("(%s)" % t for t in tests)
        if n == "getattr" and len(e.args) >= 2 and isinstance(e.args[1], ast.Constant) and isinstance(e.args[1].value, str)                 and isinstance(e.args[0], ast.Name) and sc.cls is not None:
            # getattr(self, "declared_attr"[, default]) -> the member slot
            m = self.self_attr(ast.Attribute(value=e.args[0], attr=e.args[1].value, ctx=ast.Load()), sc)
            if m and len(a) == 3:
                return "(%s.has() ? V(%s) : V(%s))" % (m, m, a[2])
        if n == "getattr":
            if len(a) == 3:
                return "pvz::getattr(%s, (%s).sym(), %s)" % (a[0], a[1], a[2])
            return "pvz::getattr(%s, (%s).sym())" % (a[0], a[1])
        if n == "setattr":
            return "(pvz::setattr(%s, (%s).sym(), %s), V::none())" % (a[0], a[1], a[2])
        if n == "hasattr":
            return "V(pvz::hasattr(%s, (%s).sym()))" % (a[0], a[1])
        if n == "dict":
            if any(isinstance(x, ast.Starred) for x in e.args) or any(k.arg is None for k in e.keywords):
                return "py::builtin_call(%s, %s)" % (self.sv("dict"), self.args(e, sc))
            if not e.args and e.keywords:
                return "py_dict({%s})" % ", ".join("{%s, %s}" % (self.sv(k.arg), self.expr(k.value, sc)) for k in e.keywords)
            if not e.args:
                return "V::dict()"
            extra = "".join(", {%s, %s}" % (self.sv(k.arg), self.expr(k.value, sc)) for k in e.keywords)
            return "py::dict_of(%s%s)" % (a[0], (", {" + extra[2:] + "}") if extra else "")
        if n in ("vars", "dir"):
            return "py::builtin_call(%s, %s)" % (self.sv(n), self.args(e, sc))
        if n == "super":
            return self.todo_("bare super()")
        if n == "iter" and len(e.args) == 2 and not e.keywords:
            return "py::iter2(%s, %s)" % (a[0], a[1])
        if n in ("any", "all") and len(e.args) == 1 and not e.keywords and isinstance(e.args[0], ast.GeneratorExp):
            return self.comp(e.args[0], sc, n)
        if n == "open" and sc.lookup_local("open") is None:
            return "py::open_file(%s)" % self.args(e, sc)
        if n in BUILTIN_FUNCS and BUILTIN_FUNCS[n]:
            if e.keywords or n == "print":
                return "%s(%s)" % (BUILTIN_FUNCS[n], self.args(e, sc))
            return "%s(%s)" % (BUILTIN_FUNCS[n], ", ".join(a))
        if n in BUILTIN_EXC:
            return "py::make_exc(%s, %s, \"\")" % (self.sv(n), self.args(e, sc))
        if n == "object":
            return "py::new_object()"
        if n == "exec" and sc.lookup_local("exec") is None:
            # executing CPython code objects has no native equivalent: the hook is registered only by the old-suite
            # test harness (replay of independently captured CPython reference runs); the game registers none
            return "py::native_hook(V(\"exec\"), Args{%s})" % ", ".join(self.expr(x, sc) for x in e.args)
        if n == "__pvp_native__":
            rest = Args_rest = ", ".join(self.expr(x, sc) for x in e.args[1:])
            return "py::native_hook(%s, Args{%s})" % (self.expr(e.args[0], sc), rest)
        return None

    def type_test(self, v, t, sc):
        if isinstance(t, ast.Name):
            if sc.lookup_local(t.id) is not None:
                return "py::isinstance_v(%s, %s)" % (v, self.expr(t, sc))
            if sc.lookup_local(t.id) is None:
                kind, cpp, key = resolve_symbol(self.mod, t.id)
                if kind == "class" and skipped(key[0], key[1]):
                    return "isinstance(%s, %s)" % (v, cstr(key[1]))   # hand-written class: runtime type name
                if kind == "class":
                    # translated exception classes are raised as py::make_exc values (ExcObj), never as C_<Class>
                    # instances: test the runtime type name / bases, exactly what `except <Class>` matches
                    if is_exception_class(class_info(key)):
                        return "isinstance(%s, %s)" % (v, cstr(key[1]))
                    return "as<%s>(%s) != nullptr" % (cpp, v)
                if kind == "stdlib":
                    return "isinstance(%s, %s)" % (v, cstr(cpp.split(".")[-1]))
            return "isinstance(%s, %s)" % (v, cstr(t.id))
        if isinstance(t, ast.Attribute):
            return "isinstance(%s, %s)" % (v, cstr(t.attr))
        return "py::isinstance_v(%s, %s)" % (v, self.expr(t, sc))

    # -------------------------------------------------------------- literals
    def e_List(self, e, sc):
        if any(isinstance(x, ast.Starred) for x in e.elts):
            return "py::concat_star({%s})" % ", ".join(("py::star(%s)" % self.expr(x.value, sc)) if isinstance(x, ast.Starred) else ("py::one(%s)" % self.expr(x, sc)) for x in e.elts)
        return "V::list({%s})" % ", ".join(self.expr(x, sc) for x in e.elts)

    def e_Tuple(self, e, sc):
        if any(isinstance(x, ast.Starred) for x in e.elts):
            return "py::tuple_it(py::concat_star({%s}))" % ", ".join(("py::star(%s)" % self.expr(x.value, sc)) if isinstance(x, ast.Starred) else ("py::one(%s)" % self.expr(x, sc)) for x in e.elts)
        return "V::tuple({%s})" % ", ".join(self.expr(x, sc) for x in e.elts)

    def e_Set(self, e, sc):
        return "V::set({%s})" % ", ".join(self.expr(x, sc) for x in e.elts)

    def e_Dict(self, e, sc):
        parts = []
        for k, v in zip(e.keys, e.values):
            if k is None:
                parts.append("{py::dict_spread_marker(), %s}" % self.expr(v, sc))
            else:
                parts.append("{%s, %s}" % (self.expr(k, sc), self.expr(v, sc)))
        if any(k is None for k in e.keys):
            return "py::dict_with_spread({%s})" % ", ".join(parts)
        return "py_dict({%s})" % ", ".join(parts)

    def e_IfExp(self, e, sc):
        return "(%s ? V(%s) : V(%s))" % (self.cond(e.test, sc), self.expr(e.body, sc), self.expr(e.orelse, sc))

    def e_JoinedStr(self, e, sc):
        parts = []
        for v in e.values:
            if isinstance(v, ast.Constant) or isinstance(v, ast.Str):
                parts.append(self.sv(v.value if isinstance(v, ast.Constant) else v.s))
            elif isinstance(v, ast.FormattedValue):
                spec = ""
                if v.format_spec is not None:
                    spec = "".join(x.value for x in v.format_spec.values if isinstance(x, ast.Constant))
                parts.append("py::format_spec(%s, %s)" % (self.expr(v.value, sc), self.sv(spec)))
        return "py::concat_str({%s})" % ", ".join(parts)

    def e_Starred(self, e, sc):
        return self.todo_("starred expression")

    def comp(self, e, sc, kind):
        sub = Scope("lambda", parent=sc, cls=sc.cls, selfname=sc.selfname)
        for g in e.generators:
            for n in ast.walk(g.target):
                if isinstance(n, ast.Name):
                    sub.locals.add(n.id)
        sub.method_scope = sc.method_scope
        code = ["V L_%s; " % ident(n) for n in sorted(sub.locals)]
        depth = 0
        for g in e.generators:
            t = sc.new_tmp()
            ip = self.items_pair(g.target, g.iter)
            ep = self.enum_pair(g.target, g.iter, sub if depth else sc)
            if ep:
                seq = self.expr(ep[2], sub if depth else sc)
                st = "(%s).num()" % self.expr(ep[3], sub if depth else sc) if ep[3] is not None else "0.0"
                code.append("{ V it%d_ = py::iter_list(%s); const double st%d_ = %s; for (size_t i%d_ = 0; i%d_ < it%d_.len(); ++i%d_) { " % (t, seq, t, st, t, t, t, t))
                code.append(self.bind_target(ep[0], "V(st%d_ + double(i%d_))" % (t, t), sub, declare=True))
                code.append(self.bind_target(ep[1], "it%d_.idx(int64_t(i%d_))" % (t, t), sub, declare=True))
            elif ip:
                recv = self.expr(ip[2], sub if depth else sc)
                code.append("{ auto it%d_ = py::items_vec(%s); for (size_t i%d_ = 0; i%d_ < it%d_.size(); ++i%d_) { " % (t, recv, t, t, t, t))
                code.append(self.bind_target(ip[0], "it%d_[i%d_].first" % (t, t), sub, declare=True))
                code.append(self.bind_target(ip[1], "it%d_[i%d_].second" % (t, t), sub, declare=True))
            else:
                it = self.expr(g.iter, sub if depth else sc)
                code.append("{ V it%d_ = py::iter_list(%s); for (size_t i%d_ = 0; i%d_ < it%d_.len(); ++i%d_) { " % (t, it, t, t, t, t))
                code.append(self.bind_target(g.target, "it%d_.idx(int64_t(i%d_))" % (t, t), sub, declare=True))
            for c in g.ifs:
                code.append("if (!(%s)) continue; " % self.cond(c, sub))
            depth += 1
        if kind in ("any", "all"):
            if kind == "any":
                code.append("if (%s) return V(true); " % self.cond(e.elt, sub))
            else:
                code.append("if (!(%s)) return V(false); " % self.cond(e.elt, sub))
            code.append("}}" * depth)
            return "[&]() -> V { %sreturn V(%s); }()" % ("".join(code), "false" if kind == "any" else "true")
        if kind == "list":
            code.append("out_.append(%s); " % self.expr(e.elt, sub))
            init = "V out_ = V::list(); "
        elif kind == "set":
            code.append("py::set_add(out_, %s); " % self.expr(e.elt, sub))
            init = "V out_ = V::set(); "
        else:
            code.append("out_.at(%s) = %s; " % (self.expr(e.key, sub), self.expr(e.value, sub)))
            init = "V out_ = V::dict(); "
        code.append("}}" * depth)
        return "[&]() -> V { %s%sreturn out_; }()" % (init, "".join(code))

    def e_ListComp(self, e, sc):
        return self.comp(e, sc, "list")

    def e_GeneratorExp(self, e, sc):
        return self.comp(e, sc, "list")

    def e_SetComp(self, e, sc):
        return self.comp(e, sc, "set")

    def e_DictComp(self, e, sc):
        return self.comp(e, sc, "dict")

    def e_Lambda(self, e, sc):
        sub = Scope("lambda", parent=sc, cls=sc.cls, selfname=sc.selfname)
        sub.method_scope = sc.method_scope
        params = [a.arg for a in e.args.args]
        sub.locals.update(params)
        if e.args.vararg: sub.locals.add(e.args.vararg.arg)
        if e.args.kwarg: sub.locals.add(e.args.kwarg.arg)
        sub.locals.update(a.arg for a in e.args.kwonlyargs)
        defaults = e.args.defaults
        binds = []
        caps = []
        for i, p in enumerate(params):
            di = i - (len(params) - len(defaults))
            if di >= 0:
                k = sc.new_tmp()
                caps.append("dv%d_ = V(%s)" % (k, self.expr(defaults[di], sc)))   # defaults bind at definition time
                binds.append("V L_%s = A.get(%d, %s, &dv%d_); " % (ident(p), i, self.sy(p), k))
            else:
                binds.append("V L_%s = A.get(%d, %s, nullptr); " % (ident(p), i, self.sy(p)))
        if e.args.vararg:
            binds.append("V L_%s = A.rest(%d); " % (ident(e.args.vararg.arg), len(params)))
        for i, arg in enumerate(e.args.kwonlyargs):
            default = e.args.kw_defaults[i]
            if default is None:
                binds.append("V L_%s = A.get(999999, %s, nullptr); " % (ident(arg.arg), self.sy(arg.arg)))
            else:
                k = sc.new_tmp()
                caps.append("dv%d_ = V(%s)" % (k, self.expr(default,sc)))
                binds.append("V L_%s = A.get(999999, %s, &dv%d_); " % (ident(arg.arg), self.sy(arg.arg), k))
        if e.args.kwarg:
            names=params+[a.arg for a in e.args.kwonlyargs]
            binds.append("V L_%s = A.kwrest({%s}); " % (ident(e.args.kwarg.arg), ",".join(cstr(n) for n in names)))
        owners = ["=", "this"] if sc.cls is not None else ["="]
        if sc.cls is not None and sc.selfname and sc.selfname not in sub.locals and any(isinstance(n, ast.Name) and n.id == sc.selfname for n in ast.walk(e.body)):
            owners.append("self_owner_ = shared_from_this()")
        cap = ", ".join(owners + caps)
        return "V::func([%s](const Args& A) -> V { %sreturn %s; })" % (cap, "".join(binds), self.expr(e.body, sub))

    def e_Await(self, e, sc):
        return self.todo_("await")

    def e_Yield(self, e, sc):
        return self.todo_("yield as expression")

    def e_NamedExpr(self, e, sc):
        return self.todo_("walrus")

    # -------------------------------------------------------------- statements
    def bind_target(self, t, value, sc, declare=False):
        if isinstance(t, ast.Name):
            return "%s = %s; " % (self.name_ref(t.id, sc), value)
        if isinstance(t, (ast.Tuple, ast.List)):
            k = sc.new_tmp()
            s = "{ V ut%d_ = py::as_seq(%s); " % (k, value)
            for i, el in enumerate(t.elts):
                if isinstance(el, ast.Starred):
                    s += self.bind_target(el.value, "py::slice(ut%d_, V(%d.0), V(%d.0))" % (k, i, i - len(t.elts) + 1 if i - len(t.elts) + 1 < 0 else 0), sc)
                else:
                    s += self.bind_target(el, "ut%d_.idx(%d)" % (k, i - len(t.elts) if any(isinstance(x, ast.Starred) for x in t.elts[:i]) else i), sc)
            return s + "} "
        return "%s; " % self.assign_to(t, value, sc)

    def assign_to(self, t, value, sc):
        if isinstance(t, ast.Name):
            return "%s = %s" % (self.name_ref(t.id, sc), value)
        if isinstance(t, ast.Attribute):
            if self.self_descriptor(t, sc):
                return "pvz::setattr(%s, %s, %s)" % (self.expr(t.value, sc), self.sy(t.attr), value)
            m = self.self_attr(t, sc)
            if m:
                return "%s = %s" % (m, value)
            if sc.selfname and isinstance(t.value, ast.Name) and t.value.id == sc.selfname:
                for c in class_chain(sc.cls):
                    if t.attr in c.setters:
                        return "prset_%s(%s)" % (ident(t.attr), value)
            return "pvz::setattr(%s, %s, %s)" % (self.expr(t.value, sc), self.sy(t.attr), value)
        if isinstance(t, ast.Subscript):
            base = self.expr(t.value, sc)
            sl = t.slice.value if isinstance(t.slice, ast.Index) else t.slice
            if isinstance(sl, ast.Slice):
                lo, hi, st = self.slice_parts(sl, sc)
                return "py::set_slice(%s, %s, %s, %s)" % (base, lo, hi, value)
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in OBJ_KEYS:
                return "setm(%s, &Obj::%s, %s, %s)" % (base, sl.value, self.sv(sl.value), value)
            key = self.e_Tuple(sl, sc) if isinstance(sl, ast.Tuple) else self.expr(sl, sc)
            return "pvz::setitem(%s, %s, %s)" % (base, key, value)
        if isinstance(t, (ast.Tuple, ast.List)):
            return "/*unpack*/ " + self.bind_target(t, value, sc).rstrip("; ")
        return self.todo_("assign to " + type(t).__name__)

    def block(self, stmts, sc, ind):
        out = []
        for s in stmts:
            try:
                out += self.stmt(s, sc, ind)
            except RecursionError:
                out.append(ind + self.todo_("recursion") + ";")
        return out

    def stmt(self, s, sc, ind):
        self.cur_line = getattr(s, "lineno", "?")
        m = getattr(self, "s_" + type(s).__name__, None)
        if m is None:
            return [ind + self.todo_("stmt " + type(s).__name__) + ";"]
        return m(s, sc, ind)

    def s_Expr(self, s, sc, ind):
        v = s.value
        if isinstance(v, (ast.Constant, ast.Str)) and isinstance(getattr(v, "value", getattr(v, "s", None)), str):
            return []
        if isinstance(v, ast.Yield):
            return [ind + "co_yield %s;" % (self.expr(v.value, sc) if v.value else "V::none()")]
        if isinstance(v, ast.YieldFrom):
            k = sc.new_tmp()
            return [ind + "{ V yf%d_ = py::iter_list(%s); for (auto& y_ : yf%d_.items()) co_yield y_; }" % (k, self.expr(v.value, sc), k)]
        return [ind + "(void)(%s);" % self.expr(v, sc)]

    def s_Assign(self, s, sc, ind):
        if self.mod == "test_pvp_integration" and len(s.targets)==1 and isinstance(s.targets[0],ast.Name) and s.targets[0].id in {"encode","decode","native_refresh"} and isinstance(s.value,ast.Call) and isinstance(s.value.func,ast.Attribute) and s.value.func.attr=="FunctionType":
            value=self.expr(s.value,sc)
            prefix='py::stdlib_call(SV("types.FunctionType"), '
            assert value.startswith(prefix),value
            value='py::native_hook(V("test.compiled_original.function"), '+value[len(prefix):]
            return [ind+self.assign_to(s.targets[0],value,sc)+";"]

        if self.mod in {"rv_r11","rv_r13","rv_r18","rv_r22"} and len(s.targets)==1 and isinstance(s.targets[0],ast.Attribute) and s.targets[0].attr=="__class__" and isinstance(s.targets[0].value,ast.Attribute) and s.targets[0].value.attr=="drafter" and isinstance(s.value,ast.Name) and s.value.id=="Drafter":
            destination=self.expr(s.targets[0].value,sc);target=self.expr(s.value,sc)
            value='[&]()->V { V previous=%s, type=%s; if(previous.t!=V::INST)throw PyError("TypeError","drafter upgrade requires an initialized native instance"); V next=pvz::getattr(type,SY("__new__")).call(Args{type}); V names=next.box->inst->method(SY("__native_slot_names__")).call(Args{}); for(const V& name:names.items()){if(name==V("evaluator") || name==V("extra_weights"))continue; V held=pvz::getattr(previous,name.sym(),V()); if(held.has())pvz::setattr(next,name.sym(),held);} for(const auto& field:previous.box->inst->dyn)if(field.first!=SY("__class__"))pvz::setattr(next,field.first,field.second); return next; }()' % (destination,target)
            return [ind+destination+' = '+value+';']

        if isinstance(s.value, ast.Yield):
            return [ind + self.todo_("x = yield") + ";"]
        if len(s.targets) == 1 and isinstance(s.targets[0], (ast.Tuple, ast.List)) and isinstance(s.value, (ast.Tuple, ast.List))                 and len(s.targets[0].elts) == len(s.value.elts)                 and not any(isinstance(x, ast.Starred) for x in s.targets[0].elts + s.value.elts):
            k = sc.new_tmp()
            vals = [self.expr(x, sc) for x in s.value.elts]
            code = "{ " + "".join("V tv%d_%d = %s; " % (k, i, v) for i, v in enumerate(vals))
            for i, el in enumerate(s.targets[0].elts):
                code += self.bind_target(el, "std::move(tv%d_%d)" % (k, i), sc)
            return [ind + code + "}"]
        val = self.expr(s.value, sc)
        if len(s.targets) == 1:
            t = s.targets[0]
            if isinstance(t, (ast.Tuple, ast.List)):
                return [ind + self.bind_target(t, val, sc)]
            out = [ind + self.assign_to(t, val, sc) + ";"]
            # Compile only the original-namespace fixture's two dictionary
            # constructors. Original test bodies/assertions remain unchanged;
            # all draw/asset work runs actual original C++ function bodies.
            if self.mod == "test_pvp_native_animation" and isinstance(t,ast.Name) and t.id == "g" and isinstance(s.value,ast.Call) and isinstance(s.value.func,ast.Name) and s.value.func.id == "dict":
                out.append(ind + "(void)py::native_hook(V(\"test.compiled_original.mark\"),Args{L_g});")
            return out
        k = sc.new_tmp()
        out = [ind + "{ V as%d_ = %s;" % (k, val)]
        for t in s.targets:
            out.append(ind + "  " + (self.bind_target(t, "as%d_" % k, sc) if isinstance(t, (ast.Tuple, ast.List)) else self.assign_to(t, "as%d_" % k, sc) + ";"))
        out.append(ind + "}")
        return out

    def s_AnnAssign(self, s, sc, ind):
        if s.value is None:
            return []
        return [ind + self.assign_to(s.target, self.expr(s.value, sc), sc) + ";"]

    def s_AugAssign(self, s, sc, ind):
        op = type(s.op).__name__
        val = self.expr(s.value, sc)
        t = s.target
        sym = {"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "Mod": "%"}.get(op)
        def combine(cur):
            if op == "FloorDiv":
                return "floordiv(%s, %s)" % (cur, val)
            if op == "Pow":
                return "pow(%s, %s)" % (cur, val)
            if op in ("BitAnd", "BitOr", "BitXor", "LShift", "RShift"):
                return "py::bitop(%s, %s, %s)" % (cstr(op), cur, val)
            if op == "Add":
                return "py::iadd(%s, %s)" % (cur, val)
            return "(%s %s %s)" % (cur, sym, val)
        if isinstance(t, ast.Name):
            ref = self.name_ref(t.id, sc)
            return [ind + "%s = %s;" % (ref, combine(ref))]
        if isinstance(t, ast.Attribute):
            m = self.self_attr(t, sc)
            if m:
                return [ind + "%s = %s;" % (m, combine(m))]
            k = sc.new_tmp()
            obj = self.expr(t.value, sc)
            return [ind + "{ V ao%d_ = %s; pvz::setattr(ao%d_, %s, %s); }" % (k, obj, k, self.sy(t.attr), combine("pvz::getattr(ao%d_, %s)" % (k, self.sy(t.attr))))]
        if isinstance(t, ast.Subscript):
            k = sc.new_tmp()
            base = self.expr(t.value, sc)
            sl = t.slice.value if isinstance(t.slice, ast.Index) else t.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in OBJ_KEYS:
                return [ind + "{ V ab%d_ = %s; setm(ab%d_, &Obj::%s, %s, %s); }" % (
                    k, base, k, sl.value, self.sv(sl.value), combine("rdm(ab%d_, &Obj::%s, %s)" % (k, sl.value, self.sv(sl.value))))]
            key = self.expr(sl, sc)
            return [ind + "{ V ab%d_ = %s; V ak%d_ = %s; pvz::setitem(ab%d_, ak%d_, %s); }" % (k, base, k, key, k, k, combine("rd(ab%d_, ak%d_)" % (k, k)))]
        return [ind + self.todo_("augassign target") + ";"]

    def s_If(self, s, sc, ind):
        out = [ind + "if (%s) {" % self.cond(s.test, sc)]
        out += self.block(s.body, sc, ind + "    ")
        orelse = s.orelse
        while len(orelse) == 1 and isinstance(orelse[0], ast.If):
            e = orelse[0]
            out.append(ind + "} else if (%s) {" % self.cond(e.test, sc))
            out += self.block(e.body, sc, ind + "    ")
            orelse = e.orelse
        if orelse:
            out.append(ind + "} else {")
            out += self.block(orelse, sc, ind + "    ")
        out.append(ind + "}")
        return out

    def s_While(self, s, sc, ind):
        out = []
        flag = None
        if s.orelse:
            flag = sc.new_tmp()
            out.append(ind + "{ bool wb%d_ = false;" % flag)
        out.append(ind + "while (%s) {" % self.cond(s.test, sc))
        body = self.block(s.body, sc, ind + "    ")
        if flag:
            body = [l.replace("break;", "{ wb%d_ = true; break; }" % flag) if l.strip() == "break;" else l for l in body]
        out += body
        out.append(ind + "}")
        if flag:
            out.append(ind + "if (!wb%d_) {" % flag)
            out += self.block(s.orelse, sc, ind + "    ")
            out.append(ind + "}}")
        return out

    @staticmethod
    def items_pair(target, it):
        """`k, v in X.items()` -> (k, v, X) so the loop can walk key/value pairs without tuples."""
        if isinstance(target, ast.Tuple) and len(target.elts) == 2 and not any(isinstance(x, ast.Starred) for x in target.elts)                 and isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "items"                 and not it.args and not it.keywords:
            return target.elts[0], target.elts[1], it.func.value
        return None

    def enum_pair(self, target, it, sc):
        """`i, x in enumerate(seq[, start])` -> (i, x, seq, start) for an index loop without tuples."""
        if isinstance(target, ast.Tuple) and len(target.elts) == 2 and not any(isinstance(x, ast.Starred) for x in target.elts)                 and isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "enumerate"                 and resolve_symbol(self.mod, "enumerate")[0] == "unknown" and sc.lookup_local("enumerate") is None                 and 1 <= len(it.args) <= 2 and not it.keywords and not any(isinstance(x, ast.Starred) for x in it.args):
            return target.elts[0], target.elts[1], it.args[0], (it.args[1] if len(it.args) > 1 else None)
        return None

    def s_For(self, s, sc, ind):
        k = sc.new_tmp()
        it = s.iter
        out = []
        flag = None
        if s.orelse:
            flag = k
            out.append(ind + "{ bool fb%d_ = false;" % k)
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range" \
                and resolve_symbol(self.mod, "range")[0] == "unknown" and sc.lookup_local("range") is None and not it.keywords:
            a = [self.expr(x, sc) for x in it.args]
            if len(a) == 1:
                start, stop, step = "0", "(int64_t)(%s).num()" % a[0], "1"
            else:
                start, stop = "(int64_t)(%s).num()" % a[0], "(int64_t)(%s).num()" % a[1]
                step = "(int64_t)(%s).num()" % a[2] if len(a) > 2 else "1"
            out.append(ind + "{ const int64_t b%d_ = %s, e%d_ = %s, s%d_ = %s;" % (k, start, k, stop, k, step))
            out.append(ind + "for (int64_t i%d_ = b%d_; s%d_ > 0 ? i%d_ < e%d_ : i%d_ > e%d_; i%d_ += s%d_) {" % (k, k, k, k, k, k, k, k, k))
            out.append(ind + "    " + self.bind_target(s.target, "V(double(i%d_))" % k, sc))
        elif self.enum_pair(s.target, it, sc):
            itg, xt, seq, start = self.enum_pair(s.target, it, sc)
            st = "(%s).num()" % self.expr(start, sc) if start is not None else "0.0"
            out.append(ind + "{ V it%d_ = py::iter_list(%s); const double st%d_ = %s;" % (k, self.expr(seq, sc), k, st))
            out.append(ind + "for (size_t i%d_ = 0; i%d_ < it%d_.len(); ++i%d_) {" % (k, k, k, k))
            out.append(ind + "    " + self.bind_target(itg, "V(st%d_ + double(i%d_))" % (k, k), sc) + self.bind_target(xt, "it%d_.idx(int64_t(i%d_))" % (k, k), sc))
        elif self.items_pair(s.target, it):
            kt, vt, recv = self.items_pair(s.target, it)
            out.append(ind + "{ auto it%d_ = py::items_vec(%s);" % (k, self.expr(recv, sc)))
            out.append(ind + "for (size_t i%d_ = 0; i%d_ < it%d_.size(); ++i%d_) {" % (k, k, k, k))
            out.append(ind + "    " + self.bind_target(kt, "it%d_[i%d_].first" % (k, k), sc) + self.bind_target(vt, "it%d_[i%d_].second" % (k, k), sc))
        else:
            out.append(ind + "{ V it%d_ = py::iter_list(%s);" % (k, self.expr(it, sc)))
            out.append(ind + "for (size_t i%d_ = 0; i%d_ < it%d_.len(); ++i%d_) {" % (k, k, k, k))
            out.append(ind + "    " + self.bind_target(s.target, "it%d_.idx(int64_t(i%d_))" % (k, k), sc))
        body = self.block(s.body, sc, ind + "    ")
        if flag:
            body = [l.replace("break;", "{ fb%d_ = true; break; }" % flag) if l.strip() == "break;" else l for l in body]
        out += body
        out.append(ind + "}}")
        if flag:
            out.append(ind + "if (!fb%d_) {" % flag)
            out += self.block(s.orelse, sc, ind + "    ")
            out.append(ind + "}}")
        return out

    def s_Break(self, s, sc, ind):
        return [ind + "break;"]

    def s_Continue(self, s, sc, ind):
        return [ind + "continue;"]

    def s_Pass(self, s, sc, ind):
        return []

    def s_Return(self, s, sc, ind):
        v = self.expr(s.value, sc) if s.value is not None else "V::none()"
        if sc.gen_root():
            return [ind + "co_return;"] if s.value is None else [ind + "{ (void)(%s); co_return; }" % v]
        if sc.kind == "module":
            return [ind + "return;"]
        return [ind + "return %s;" % v]

    def s_Delete(self, s, sc, ind):
        out = []
        for t in s.targets:
            if isinstance(t, ast.Subscript):
                sl = t.slice.value if isinstance(t.slice, ast.Index) else t.slice
                if isinstance(sl, ast.Slice):
                    lo, hi, st = self.slice_parts(sl, sc)
                    out.append(ind + "py::set_slice(%s, %s, %s, V::list());" % (self.expr(t.value, sc), lo, hi))
                else:
                    out.append(ind + "pvz::delitem(%s, %s);" % (self.expr(t.value, sc), self.expr(sl, sc)))
            elif isinstance(t, ast.Name):
                out.append(ind + "%s.del();" % self.name_ref(t.id, sc))
            elif isinstance(t, ast.Attribute):
                out.append(ind + "py::delattr(%s, %s);" % (self.expr(t.value, sc), self.sy(t.attr)))
        return out

    def s_Global(self, s, sc, ind):
        sc.globals_decl.update(s.names)
        return []

    def s_Nonlocal(self, s, sc, ind):
        return []

    def s_Import(self, s, sc, ind):
        if sc.kind == "module":
            return []   # module-level imports resolve statically (resolve_symbol -> stdlib)
        out = []
        for a in s.names:   # function-level `import x[.y] [as z]`: bind the local to the module object
            local = a.asname or a.name.split(".")[0]
            if sc.lookup_local(local) is not None:
                target = a.name if a.asname else a.name.split(".")[0]
                native = target[4:] if target.startswith("pvp.") and a.asname and target.count(".")==1 else None
                if native and native not in SHIMS and native not in DYNAMIC and src_of(native).exists():
                    self.deps.add(native)
                    out.append(ind + "L_%s = pm_%s::module_ns();" % (ident(local), native))
                else:
                    out.append(ind + "L_%s = py::stdlib_module(%s);" % (ident(local), self.sv(target)))
        return out

    def s_ImportFrom(self, s, sc, ind):
        if sc.kind == "module":
            # an imported name that the module later rebinds is also a module variable
            out = []
            for a in s.names:
                local = a.asname or a.name
                if local in self.mi.vars:
                    if s.level >= 1 and s.module and src_of(s.module.split(".")[0]).exists():
                        mod = s.module.split(".")[0]
                        kind, cpp, key = resolve_symbol(mod, a.name)
                        self.deps.add(mod)
                        if key: self.deps.add(key[0])
                        val = cpp if kind == "var" else ("V::func(%s)" % cpp if kind == "func" else
                              ("pm_%s::cls_%s()" % (key[0], ident(key[1])) if kind == "class" else "V::none()"))
                    elif s.level == 0:
                        val = "py::stdlib_attr(%s, %s)" % (self.sv(s.module or ""), self.sv(a.name))
                    else:
                        val = "V::none()"
                    out.append(ind + "pm_%s::%s = %s;" % (self.mod, ident(local), val))
            return out
        # function-local import: bind names
        out = []
        for a in s.names:
            local = a.asname or a.name
            if s.level >= 1 and s.module:
                mod = s.module.split(".")[0]
                if src_of(mod).exists():
                    kind, cpp, key = resolve_symbol(mod, a.name)
                    self.deps.add(mod)
                    if key: self.deps.add(key[0])
                    if mod not in SHIMS and mod not in DYNAMIC and kind in ("var", "func", "class"):
                        out.append(ind + "L_%s = pvz::getattr(pm_%s::module_ns(), %s);" % (ident(local), mod, self.sy(a.name)))
                    elif kind == "var":
                        out.append(ind + "L_%s = %s;" % (ident(local), cpp))
                    elif kind == "func":
                        out.append(ind + "L_%s = V::func(%s);" % (ident(local), cpp))
                    elif kind == "class":
                        out.append(ind + "L_%s = pm_%s::cls_%s();" % (ident(local), key[0], ident(key[1])))
                    else:
                        out.append(ind + "L_%s = %s;" % (ident(local), self.todo_("local import " + a.name)))
                    continue
            elif s.level >= 1 and s.module is None and not src_of(a.name).exists():
                # `from . import BUILD`: a constant of the package __init__
                out.append(ind + "L_%s = py::data_value(\"__init__\", %s);" % (ident(local), cstr(a.name)))
                continue
            elif s.level >= 1 and s.module is None:
                out.append(ind + "L_%s = pm_%s::module_ns();" % (ident(local), a.name))
                self.deps.add(a.name)
                if src_of(a.name).exists():
                    sc.local_modules[local] = a.name   # alias.attr resolves statically (see local_module_attr)
                continue
            out.append(ind + "L_%s = py::stdlib(%s);" % (ident(local), self.sv((s.module or "") + "." + a.name)))
        return out

    def s_Raise(self, s, sc, ind):
        if s.exc is None:
            return [ind + "throw;"]
        return [ind + "py::raise(%s);" % self.expr(s.exc, sc)]

    def s_Assert(self, s, sc, ind):
        return [ind + "if (!(%s)) throw PyError(\"AssertionError\", \"assert\");" % self.cond(s.test, sc)]

    def s_Try(self, s, sc, ind):
        out = []
        has_finally = bool(s.finalbody)
        if has_finally:
            k = sc.new_tmp()
            out.append(ind + "{ auto fin%d_ = py::finally([&]() {" % k)
            out += self.block(s.finalbody, sc, ind + "    ")
            out.append(ind + "});")
            ind2 = ind + "  "
        else:
            ind2 = ind
        if s.handlers:
            out.append(ind2 + "try {")
            out += self.block(s.body, sc, ind2 + "    ")
            if s.orelse:
                k2 = sc.new_tmp()
                out.insert(len(out) - len(self.block(s.body, sc, ind2 + "    ")) - 1, ind2 + "bool ok%d_ = false;" % k2)
                out.append(ind2 + "    ok%d_ = true;" % k2)
            out.append(ind2 + "} catch (PyError& exc_) {")
            first = True
            for h in s.handlers:
                types = []
                if h.type is None:
                    cond = "true"
                else:
                    elts = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
                    for t in elts:
                        nm = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else "?")
                        types.append("exc_.matches(%s)" % cstr(nm))
                    cond = " || ".join(types)
                out.append(ind2 + "    %sif (%s) {" % ("" if first else "else ", cond))
                if h.name:
                    sc.locals.add(h.name)
                    out.append(ind2 + "        L_%s = py::exc_value(exc_);" % ident(h.name))
                out += self.block(h.body, sc, ind2 + "        ")
                out.append(ind2 + "    }")
                first = False
            out.append(ind2 + "    else throw;")
            out.append(ind2 + "}")
            if s.orelse:
                out.append(ind2 + "if (ok%d_) {" % k2)
                out += self.block(s.orelse, sc, ind2 + "    ")
                out.append(ind2 + "}")
        else:
            out += self.block(s.body, sc, ind2)
        if has_finally:
            out.append(ind + "}")
        return out

    def s_With(self, s, sc, ind):
        if self.mod.startswith("test_pvp_") and len(s.items) == 1:
            item = s.items[0]
            context = item.context_expr
            if isinstance(context, ast.Call) and isinstance(context.func, ast.Attribute) and context.func.attr in ("assertRaises", "assertRaisesRegex"):
                k = sc.new_tmp()
                out = [ind + "{", ind + "  V raises_mgr%d_ = %s;" % (k,self.expr(context,sc)), ind + "  V raises_value%d_ = callm(raises_mgr%d_, SY(\"__enter__\"), Args{});" % (k,k),ind + "  bool raises_caught%d_ = false;" % k]
                if item.optional_vars is not None:
                    out.append(ind + "  " + self.bind_target(item.optional_vars,"raises_value%d_" % k,sc))
                out.append(ind + "  try {")
                out += self.block(s.body,sc,ind+"    ")
                out.append(ind + "  } catch (const PyError& e) {")
                out.append(ind + "    raises_caught%d_ = true;" % k)
                out.append(ind + '    std::string message = e.what(); size_t colon = message.find(": "); if (colon != std::string::npos) message = message.substr(colon + 2);')
                out.append(ind + "    if (!callm(raises_mgr%d_, SY(\"__exit__\"), Args{py::exc_type(V(e.kind)), py::exc_value(e), V::none()}).truthy()) throw;" % k)
                out.append(ind + "  }")
                out.append(ind + "  if (!raises_caught%d_) callm(raises_mgr%d_, SY(\"__exit__\"), Args{V::none(), V::none(), V::none()});" % (k,k))
                out.append(ind + "}")
                return out
        out = [ind + "{"]
        guards = []
        for i, item in enumerate(s.items):
            k = sc.new_tmp()
            out.append(ind + "  py::WithGuard wg%d_(%s);" % (k, self.expr(item.context_expr, sc)))
            if item.optional_vars is not None:
                out.append(ind + "  " + self.bind_target(item.optional_vars, "wg%d_.value" % k, sc))
        out += self.block(s.body, sc, ind + "    ")
        out.append(ind + "}")
        return out

    def s_AsyncFunctionDef(self, node, sc, ind):
        allowed={("test_pvp_66_room_admission_oct16","legacy_send"):"original_send",("test_pvp_spectators49","legacy_send"):"original_send",("test_pvp_network_memory67","inspect"):"relay"}
        capture=allowed.get((self.mod,node.name))
        if capture is None:return [ind+self.todo_("async function outside supported original server fixture "+node.name)+";"]
        import hashlib
        source=src_of(self.mod).read_bytes();source_sha=hashlib.sha256(source).hexdigest();digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode('utf-8')).hexdigest()
        identity=self.mod+":"+str(node.lineno)+":"+node.name
        declared=node.name in sc.locals;sc.locals.add(node.name)
        return [ind+("" if declared else "V ")+"L_"+ident(node.name)+" = py::native_hook(V(\"test.relay_async_fixture\"),Args{"+self.sv(identity)+","+self.sv(digest)+","+self.sv(source_sha)+","+self.name_ref(capture,sc)+"});"]

    def s_FunctionDef(self, s, sc, ind):
        # nested function -> closure value
        sc.locals.add(s.name)
        code = self.function_body(s, sc, nested=True)
        out = [ind + "L_%s = %s;" % (ident(s.name), code)]
        for decorator in reversed(s.decorator_list):
            decname = decorator.id if isinstance(decorator,ast.Name) else decorator.attr if isinstance(decorator,ast.Attribute) else None
            if decname == "contextmanager":
                continue  # context-generators already own the actual native context protocol
            out.append(ind + "L_%s = (%s).call(Args{L_%s});" % (ident(s.name), self.expr(decorator,sc), ident(s.name)))
        return out

    def s_ClassDef(self, s, sc, ind):
        """Class defined inside a function: a runtime class whose methods are closures (self explicit)."""
        if len(s.bases)>1 or s.keywords:
            return [ind + self.todo_("nested class requires one native base " + s.name) + ";"]
        sc.locals.add(s.name)
        members = []
        if s.bases:
            members.append("{%s, V::tuple({%s})}" % (self.sv("__bases__"), ", ".join(self.expr(base, sc) for base in s.bases)))
        for item in s.body:
            if isinstance(item, ast.FunctionDef):
                if item.decorator_list:
                    return [ind + self.todo_("decorated method in nested class " + s.name) + ";"]
                members.append("{%s, %s}" % (self.sv(item.name), self.function_body(item, sc, nested=True)))
            elif isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                members.append("{%s, %s}" % (self.sv(item.targets[0].id), self.expr(item.value, sc)))
            elif isinstance(item, (ast.Pass, ast.Expr)):
                continue
            else:
                return [ind + self.todo_("statement in nested class " + s.name) + ";"]
        return [ind + "L_%s = py::local_class(%s, {%s});" % (ident(s.name), self.sv(s.name), ", ".join(members))]

    # -------------------------------------------------------------- functions
    def collect_locals(self, fn):
        params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
        if fn.args.vararg:
            params.append(fn.args.vararg.arg)
        if fn.args.kwarg:
            params.append(fn.args.kwarg.arg)
        assigned = set(params)
        gdecl, ndecl = set(), set()
        stack = list(ast.iter_child_nodes(fn))
        is_gen = False
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                    assigned.add(n.name)
                continue
            if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                # comprehension targets are their own scope; still scan iterables of the first generator
                stack.append(n.generators[0].iter)
                continue
            if isinstance(n, ast.Global):
                gdecl.update(n.names)
            elif isinstance(n, ast.Nonlocal):
                ndecl.update(n.names)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                assigned.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                assigned.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    assigned.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, (ast.Yield, ast.YieldFrom)):
                is_gen = True
            stack.extend(ast.iter_child_nodes(n))
        return params, assigned - gdecl, gdecl, ndecl, is_gen

    def param_binds(self, fn, sc, skip_self=False, fname=""):
        out = []
        args = fn.args.args[1:] if skip_self else fn.args.args
        defaults = fn.args.defaults
        nd = len(defaults)
        allargs = fn.args.args
        offset = 1 if skip_self else 0
        for i, a in enumerate(allargs):
            if skip_self and i == 0:
                continue
            di = i - (len(allargs) - nd)
            idx = i - offset
            if di >= 0:
                dflt = self.expr(defaults[di], sc.parent if sc.parent is not None else sc)
                if sc.kind == "func" and sc.parent is not None and sc.parent.kind != "module":
                    # nested def: default evaluated once at definition (captured), not per call
                    k = sc.parent.new_tmp() if hasattr(sc.parent, "new_tmp") else 0
                    self._nested_default_caps = getattr(self, "_nested_default_caps", []) + ["nd%d_ = V(%s)" % (k, dflt)]
                    dflt = "nd%d_" % k
                out.append("V L_%s = (A.size() > %d || A.has_kw(%s)) ? A.get(%d, %s, nullptr) : V(%s);" % (ident(a.arg), idx, self.sy(a.arg), idx, self.sy(a.arg), dflt))
            else:
                out.append("V L_%s = A.get(%d, %s, nullptr, %s);" % (ident(a.arg), idx, self.sy(a.arg), cstr(fname)))
        for j, a in enumerate(fn.args.kwonlyargs):
            d = fn.args.kw_defaults[j]
            dflt = self.expr(d, sc.parent if sc.parent is not None else sc) if d is not None else None
            if dflt:
                out.append("V L_%s = A.has_kw(%s) ? A.get(99999, %s, nullptr) : V(%s);" % (ident(a.arg), self.sy(a.arg), self.sy(a.arg), dflt))
            else:
                out.append("V L_%s = A.get(99999, %s, nullptr, %s);" % (ident(a.arg), self.sy(a.arg), cstr(fname)))
        if fn.args.vararg:
            out.append("V L_%s = A.rest(%d);" % (ident(fn.args.vararg.arg), len(allargs) - offset))
        if fn.args.kwarg:
            known = ", ".join(cstr(a.arg) for a in allargs + fn.args.kwonlyargs)
            out.append("V L_%s = A.kwrest({%s});" % (ident(fn.args.kwarg.arg), known))
        return out

    def function_body(self, fn, parent, nested=False, cls=None, method=False, static=False):
        params, locals_, gdecl, ndecl, is_gen = self.collect_locals(fn)
        selfname = fn.args.args[0].arg if (method and not static and fn.args.args) else None
        if nested and parent is not None and cls is None:
            cls = parent.cls
        sc = Scope("method" if method else "func", locals_, parent=parent, cls=cls, selfname=selfname, gen=is_gen)
        # Only a direct self-reference to a single, undecorated, un-rebound local
        # function is intrinsic. Mutable/nonlocal closure cells remain separate.
        definitions = {}
        for item in ast.walk(fn):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item is not fn:
                definitions[item.name] = definitions.get(item.name, 0) + 1
        stores = {item.id for item in ast.walk(fn) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        sc.stable_function_names = {name for name, count in definitions.items() if count == 1 and name not in stores}
        if nested and not fn.decorator_list and fn.name not in locals_ and fn.name not in gdecl and fn.name not in ndecl and fn.name in getattr(parent, "stable_function_names", set()):
            sc.recursive_name = fn.name

        sc.globals_decl = gdecl
        sc.nonlocal_decl = ndecl
        sc.method_scope = (lambda: sc) if method else (parent.method_scope if parent is not None and hasattr(parent, "method_scope") else (lambda: None))
        if nested and parent is not None and getattr(parent, "selfname", None) and parent.selfname not in params:
            sc.selfname = parent.selfname
        sc.gen_root = (lambda: is_gen)
        self._nested_default_caps = []
        is_classmethod = bool(method and cls is not None and fn.name in cls.classmethods and fn.args.args and not nested)
        sc.class_receiver = fn.args.args[0].arg if is_classmethod else None
        lines = self.param_binds(fn, sc, skip_self=bool(selfname) or is_classmethod, fname=fn.name)
        if is_classmethod:
            # callers pass no cls (Class.m(args) and instance.m(args) both bind the class here)
            lines.insert(0, "V cv_cls_ = pm_%s::cls_%s(); V L_%s = A.get(999999, SY(\"__pvz_cls\"), &cv_cls_);" % (cls.module, ident(cls.name), ident(fn.args.args[0].arg)))
        my_caps = list(self._nested_default_caps)
        self._nested_default_caps = []
        for n in sorted(locals_ - set(params)):
            if n != selfname:
                lines.append("V L_%s;" % ident(n))
        body = self.block(fn.body, sc, "    ")
        if self.mod.startswith("test_pvp_"):
            for dec in fn.decorator_list:
                dn = (dec.func.attr if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) else dec.func.id if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) else dec.id if isinstance(dec, ast.Name) else dec.attr if isinstance(dec, ast.Attribute) else "unknown")
                if dn in ("classmethod", "staticmethod", "property", "contextmanager"):
                    continue
                if dn in ("skip", "skipIf", "skipUnless") and isinstance(dec, ast.Call):
                    cond = "true" if dn == "skip" else "(%s).truthy()" % self.expr(dec.args[0], sc)
                    if dn == "skipUnless": cond = "!(%s)" % cond
                    reason = self.expr(dec.args[-1], sc)
                    body.insert(0, "    if (%s) throw PyError(\"SkipTest\", py_str(%s));" % (cond, reason))
                else:
                    patch_alias = False
                    if isinstance(dec, ast.Name):
                        for statement in self.mi.tree.body:
                            if not isinstance(statement, ast.Assign) or not any(isinstance(t,ast.Name) and t.id==dec.id for t in statement.targets):
                                continue
                            value = statement.value
                            if not isinstance(value, ast.Call): continue
                            target = value.func; parts = []
                            while isinstance(target, ast.Attribute):
                                parts.insert(0,target.attr); target = target.value
                            if isinstance(target,ast.Name):
                                kind, module, unused = resolve_symbol(self.mod,target.id)
                                qualified = module + ('.'+'.'.join(parts) if parts else '')
                                patch_alias = kind=='stdlib' and qualified in ('unittest.mock.patch','unittest.mock.patch.object','unittest.mock.patch.dict')
                    if patch_alias:
                        body.insert(0, "    py::WithGuard decorator_scope_%d_(%s);" % (sc.new_tmp(),self.name_ref(dec.id,sc)))
                    else:
                        body.insert(0, "    throw PyError(\"NotImplementedError\", %s);" % cstr("test decorator not yet supported: " + dn))
        is_ctx = getattr(fn, "_pvz_ctxmgr", False) or any(
            (isinstance(d, ast.Name) and d.id == "contextmanager") or (isinstance(d, ast.Attribute) and d.attr == "contextmanager")
            for d in fn.decorator_list)
        lines = ["    " + l for l in lines] + body
        if is_gen:
            kind = "py::GenKind::CONTEXT" if is_ctx else "py::GenKind::ITER"
            text = "py::make_test_gen(%s, [=](py::GenCtl& gc_) -> py::PyGen {\n%s\n    co_return;\n})" % (kind, "\n".join(lines))
            fn._pvz_gen = True
        else:
            text = None
        if nested:
            cap = "=, this" if cls is not None or (parent and parent.cls is not None) else "="
            root = parent.method_scope() if parent is not None else None
            if root is not None and root.selfname and root.selfname not in params and any(isinstance(n, ast.Name) and n.id == root.selfname for n in ast.walk(fn)):
                cap += ", self_owner_ = shared_from_this()"
            if my_caps:
                cap += ", " + ", ".join(my_caps)
            if is_gen:
                return "V::func([%s](const Args& A) -> V { %s\n%s\n    return %s; })" % (
                    cap, "", "", text.replace("[=](py::GenCtl", "[=](py::GenCtl"))
            # This source closure has three actual capture cells. Preserve them
            # as native cells and a C++ body blueprint so instrumentation can
            # rebind a capture without inventing CPython wordcode/CodeType.
            if self.mod == "pvp58_vines" and fn.name == "pea_hit":
                captures = ("hit", "shell_cells", "shells")
                assert not is_gen and not my_caps
                used_outer = {n.id for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in parent.locals and n.id not in locals_}
                assert used_outer == set(captures), used_outer
                names = "V::tuple({%s})" % ", ".join(self.sv(n) for n in captures)
                values = "V::tuple({%s})" % ", ".join(self.name_ref(n,parent) for n in captures)
                binds = ["    V L_%s = native_cell_value(cells.idx(%d));" % (ident(n),i) for i,n in enumerate(captures)]
                return "make_native_closure(%s,%s,%s,py::stdlib_module(V(\"pvp.pvp58_vines\")),[](const V& cells,const Args& A) -> V {\n%s\n    return V::none();\n})" % (self.sv(fn.name),names,values,"\n".join(binds+lines))
            return "V::func([%s](const Args& A) mutable -> V {\n%s\n    return V::none();\n})" % (cap, "\n".join(lines))
        return lines, is_gen, is_ctx

    def emit_function(self, fn, decl_prefix, qual, cls=None, method=False, static=False):
        res = self.function_body(fn, Scope("module"), cls=cls, method=method, static=static)
        lines, is_gen, is_ctx = res
        if self.mod == "native_battle" and cls and cls.name == "NativeBattle" and fn.name in ("_step_original", "spawn"):
            scope = "TickScope" if fn.name == "_step_original" else "SpawnScope"
            lines.insert(0, "    pm_hero_guard::%s hero_scope_(self_v());" % scope)
        if is_gen:
            kind = "py::GenKind::CONTEXT" if is_ctx else "py::GenKind::ITER"
            binds = [l for l in lines if l.strip().startswith("V L_") and "= " in l and ("A.get(" in l or "A.rest(" in l or "A.kwrest(" in l or "A.has_kw(" in l)]
            rest = [l for l in lines if l not in binds]
            pnames = [l.strip().split()[1] for l in binds]
            gq = qual.replace("::m_", "::g_").replace("f_", "g_", 1) if "::m_" in qual else "g_" + qual[2:]
            self.gen_decls.append((cls, gq.split("::")[-1], pnames, static))
            owner = "" if (cls is None or static) else ", shared_from_this()"
            co = "py::PyGen %s(%s) {\n%s\n    co_return;\n}\n" % (gq, ", ".join("V " + n for n in pnames), "\n".join(rest))
            outer = "V %s(const Args& A) {\n%s\n    return py::make_gen(%s, %s(%s)%s);\n}\n" % (
                qual, "\n".join(binds), kind, gq.split("::")[-1], ", ".join(pnames), owner)
            return co + outer
        if self.mod == "test_pvp_native_animation" and fn.name == "pixels":
            returns=[i for i,line in enumerate(lines) if line.startswith("    return ")]
            assert len(returns)==1
            i=returns[0];expression=lines[i][len("    return "):-1]
            lines[i]="    V observed_pixels="+expression+"; (void)py::native_hook(V(\"test.animation.observe_pixels\"),Args{L_surface,observed_pixels});return observed_pixels;"
        return "V %s(const Args& A) {\n%s\n    return V::none();\n}\n" % (qual, "\n".join(lines))

    # -------------------------------------------------------------- module
    def run(self):
        mi = self.mi
        m = self.mod
        h, c = [], []
        h.append("// Generated by tools/pvp2cpp.py from modkit/pvp/%s.py - do not edit by hand." % m)
        h.append("#pragma once")
        h.append('#include "sim/pvp/pvprt.h"')
        h.append("namespace pvz { namespace pm_%s {" % m)
        h.append("V module_ns();")
        h.append("void init();")
        for v in mi.vars:
            h.append("extern V %s;" % ident(v))
        for f, fnode in mi.funcs.items():
            h.append("V f_%s(const Args& A);" % ident(f))
            if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fnode)):
                params = [a.arg for a in fnode.args.args] + ([fnode.args.vararg.arg] if fnode.args.vararg else []) + [a.arg for a in fnode.args.kwonlyargs] + ([fnode.args.kwarg.arg] if fnode.args.kwarg else [])
                h.append("py::PyGen g_%s(%s);" % (ident(f), ", ".join("V L_" + ident(p) for p in params)))
        # classes: forward declare all first
        for cn in mi.classes:
            h.append("struct C_%s;" % ident(cn))
            h.append("V new_%s(const Args& A);" % ident(cn))
            h.append("V cls_%s();" % ident(cn))
        for cn, ci in self.ordered_classes():
            h += self.class_decl(ci)
            if not is_exception_class(ci):
                h.append("void initcv_%s(C_%s* p);" % (ident(cn), ident(cn)))
        h.append("}}  // namespace pvz::pm_%s" % m)
        base_mods = set()
        for cn, ci in mi.classes.items():
            bcpp, bkey = base_cpp(ci)
            if bkey is not None and bkey[0] != m:
                base_mods.add(bkey[0])
        for bm in sorted(base_mods):
            h.insert(3, '#include "%s"' % header_path(bm))
        # ---- source
        c.append("// Generated by tools/pvp2cpp.py from modkit/pvp/%s.py - do not edit by hand." % m)
        c.append('#include "%s"' % header_path(m))
        if m == "pvp58_vines": c.append('#include "core/native_closure.h"')
        if GEN_UI[0]:
            c.append('#include "sim/pvp/dynamic_bindings.h"')
        if m == "native_battle":
            c.append('#include "sim/pvp/hand/hero_monitor.h"')
        if m.startswith("test_pvp_"):
            c.append('#include "cpptests/generator_adapter.h"')
        dep_marker = len(c)
        c.append("namespace pvz { namespace pm_%s {" % m)
        for v in mi.vars:
            c.append("V %s;" % ident(v))
        for fname, fn in mi.funcs.items():
            if fname.startswith("_install_native") and not skipped(m, fname):
                # hooks for the retired CPython C++ core (_pvpcore): nothing to install natively
                c.append("V f_%s(const Args& A) { return V::none(); }" % ident(fname))
                continue
            if skipped(m, fname):
                c.append("// f_%s: hand-written (src/sim/pvp/hand)" % ident(fname))
                continue
            c.append(self.emit_function(fn, "", "f_%s" % ident(fname)))
        for cn, ci in self.ordered_classes():
            c += self.class_impl(ci)
        # module init: top-level statements in order
        sc = Scope("module")
        sc.method_scope = lambda: None
        sc.gen_root = lambda: False
        body = []
        for node in mi.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in mi.vars:
                body.append("    pm_%s::%s = %s;" % (m, ident(node.name), ("V::func(f_%s)" % ident(node.name)) if isinstance(node, ast.FunctionDef) else "cls_%s()" % ident(node.name)))
                continue
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import)):
                continue
            body += self.stmt(node, sc, "    ")
        c.append("static bool inited_ = false;")
        c.append("void init() {\n    if (inited_) return;\n    inited_ = true;\n    py::note_module_loaded(\"pvp.%s\");\n    py::init_deps_%s();\n%s\n}" % (m, m, "\n".join(body)))
        if m.startswith("test_pvp_"):
            c[-1] = c[-1].replace('    py::init_deps_', '    py::register_module(%s, module_ns());\n    py::init_deps_' % cstr(m), 1)
        # module attribute table: a module value (importlib.import_module, `from . import x` passed around) resolves names
        rows = []
        for v in mi.vars:
            rows.append("    if (s == %s) return pm_%s::%s;" % (cstr(v), m, ident(v)))
        for f in mi.funcs:
            if f in mi.vars:
                continue
            rows.append("    if (s == %s) return V::func(f_%s);" % (cstr(f), ident(f)))
        for cn in mi.classes:
            if cn in mi.vars:
                continue
            rows.append("    if (s == %s) return cls_%s();" % (cstr(cn), ident(cn)))
        # Python imports remain public module attributes. Resolve them to the same
        # native module/function used by generated call sites, so patch.object
        # replaces the actual binding (e.g. ui_data.socket.socket).
        for imported in sorted(set(mi.import_modules) | set(mi.imports)):
            if imported == "*" or imported in mi.vars or imported in mi.funcs or imported in mi.classes:
                continue
            if resolve_symbol(m, imported)[0] != "unknown":
                rows.append("    if (s == %s) return %s;" % (cstr(imported), self.name_ref(imported, sc)))
        c.append("static V modattr_(Sym n) {\n    init();\n    const std::string& s = n.str();\n%s\n    return V();\n}" % "\n".join(rows))
        writes = ["    if (s == %s) { pm_%s::%s = A.pos.at(1); return V(true); }" % (cstr(v), m, ident(v)) for v in mi.vars]
        c.append("static V modwrite_(const Args& A) {\n    init();\n    const std::string& s = A.pos.at(0).str();\n%s\n    return V(false);\n}" % "\n".join(writes))
        c.append("V module_ns() { static const bool reg_ = (py::register_module_attrs(%s, modattr_), py::register_native_hook(%s, modwrite_), true); (void)reg_; init(); return py::module_ns(%s); }" % (cstr(m), cstr("module.write." + m), self.sv(m)))
        c.append("}}  // namespace pvz::pm_%s" % m)
        referenced = set(re.findall(r"\bpm_(\w+)::", "\n".join(c)))
        deps = sorted(d for d in self.deps | referenced if d != m)
        c.insert(dep_marker, "\n".join('#include "%s"' % header_path(d) for d in deps))
        c.insert(dep_marker + 1, "namespace pvz { namespace py { inline void init_deps_%s() { %s } } }" % (
            m, " ".join("pm_%s::init();" % d for d in deps)))
        return "\n".join(h) + "\n", "\n".join(c) + "\n"

    def ordered_classes(self):
        return [(cn, ci) for cn, ci in self._ordered_classes() if not skipped(self.mod, cn)]

    def _ordered_classes(self):
        done, order = set(), []
        def visit(cn):
            if cn in done:
                return
            ci = self.mi.classes[cn]
            flatten_mixins(ci)
            for b in ci.bases:
                if isinstance(b, ast.Name) and b.id in self.mi.classes:
                    visit(b.id)
            done.add(cn)
            order.append((cn, ci))
        for cn in self.mi.classes:
            visit(cn)
        return order

    def class_decl(self, ci):
        bcpp, bkey = base_cpp(ci)
        if bkey is not None and bkey[0] != self.mod:
            self.deps.add(bkey[0])
        base = bcpp or "PyObj"
        name = "C_" + ident(ci.name)
        out = ["struct %s : %s {" % (name, base)]
        inherited = set()
        for c in class_chain(ci)[1:]:
            inherited.update(c.attrs)
        for a in ci.attrs:
            if a not in inherited and a not in ci.classvars:
                out.append("    V a_%s;" % ident(a))
        for cv in ci.classvars:
            out.append("    static V& cv_%s();" % ident(cv))
            if cv not in inherited:
                out.append("    V a_%s;   // class variable (instance copy)" % ident(cv))
        out.append("    const char* type_name() const override { return %s; }" % cstr(ci.display_name))
        out.append("    bool isa(const char* c) const override;")
        out.append("    V* slot(Sym name) override;")
        out.append("    V method(Sym name) override;")
        out.append("    bool call_method(Sym name, const Args& A, V& out) override;")
        if ci.properties:
            out.append("    V property(Sym name, bool& found) override;")
            out.append("    bool set_property(Sym name, const V& v) override;")
        out.append("    V self_v() { return self(); }")
        for mn, fn in ci.methods.items():
            if mn in ci.static or mn in ci.classmethods:
                out.append("    static V m_%s(const Args& A);" % ident(mn))
            else:
                out.append("    virtual V m_%s(const Args& A);" % ident(mn))
            if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn)):
                params = [a.arg for a in fn.args.args[(0 if mn in ci.static else 1):]] + ([fn.args.vararg.arg] if fn.args.vararg else []) + [a.arg for a in fn.args.kwonlyargs] + ([fn.args.kwarg.arg] if fn.args.kwarg else [])
                out.append("    %spy::PyGen g_%s(%s);" % ("static " if mn in ci.static else "", ident(mn), ", ".join("V L_" + ident(p) for p in params)))
        for pn in ci.properties:
            out.append("    V pr_%s();" % ident(pn))
        for pn in ci.setters:
            out.append("    void prset_%s(const V& v);" % ident(pn))
        if "__call__" in ci.methods:
            out.append("    V call_self(const Args& A) override { return m___call__(A); }")
        dunders = {"__getitem__": "V getitem(const V& k) override { return m___getitem__(Args{k}); }",
                   "__setitem__": "void setitem(const V& k, const V& v) override { m___setitem__(Args{k, v}); }",
                   "__delitem__": "void delitem(const V& k) override { m___delitem__(Args{k}); }",
                   "__contains__": "bool contains(const V& k) override { return m___contains__(Args{k}).truthy(); }",
                   "__len__": "size_t length() override { return size_t(m___len__(Args{}).num()); }",
                   "__iter__": "V iterate() override { return py::iter_list(m___iter__(Args{})); }"}
        for dn, decl in dunders.items():
            if any(dn in c.methods for c in class_chain(ci)):
                out.append("    " + decl)
        out.append("};")
        return out

    def class_impl(self, ci):
        name = "C_" + ident(ci.name)
        bcpp, bkey = base_cpp(ci)
        out = []
        chain = class_chain(ci)
        names = [c.display_name for c in chain] + getattr(ci, "extra_isa", [])
        out.append("bool %s::isa(const char* c) const { std::string s(c); return %s || s == \"object\"; }" % (
            name, " || ".join("s == %s" % cstr(n) for n in names)))
        # flattened dispatch over the whole translated chain: one hash lookup + switch per call
        # (own members first, like python attribute lookup; unqualified names resolve through inheritance)
        attrs, seen_a = [], set()
        meths, seen_m = [], set()
        for c in chain:
            for a in c.attrs:
                if a not in seen_a:
                    seen_a.add(a); attrs.append(a)
            for mn in c.methods:
                if mn not in seen_m:
                    seen_m.add(mn); meths.append((mn, c))
        def table(names):
            return "static const SymIndex idx_({%s});" % ", ".join(self.sy(n) for n in names)
        out.append("V* %s::slot(Sym name) {" % name)
        if attrs:
            out.append("    " + table(attrs))
            out.append("    const int k_ = idx_.find(name);")
            out.append("    if (k_ < 0) return nullptr;")
            out.append("    switch (k_) {")
            for k, a in enumerate(attrs):
                out.append("        case %d: return &a_%s;" % (k, ident(a)))
            out.append("    }")
        out.append("    return nullptr;")
        out.append("}")
        def is_static(mn, c):
            return mn in c.static or mn in c.classmethods
        out.append("V %s::method(Sym name) {" % name)
        out.append('    if (name == SY("__native_type__")) { V metadata=V::func([](const Args&) { return pm_%s::cls_%s(); }); metadata.box->fattrs.emplace_back(Sym("__native_type_metadata__"),V(true)); return metadata; }' % (ci.module, ident(ci.name)))
        out.append('    if (name == SY("__native_slot_names__")) return V::func([](const Args&) { return V::tuple({%s}); });' % ', '.join(self.sv(a) for a in attrs))
        if GEN_UI[0] and not is_exception_class(ci):
            for owner in chain:
                out.append("    if (V replacement = py::class_method_override(pm_%s::cls_%s(), name, self()); replacement.has()) return replacement;" % (owner.module, ident(owner.name)))
        if meths:
            out.append("    " + table([m for m, _ in meths]))
            out.append("    const int k_ = idx_.find(name);")
            out.append("    if (k_ < 0) return V();")
            out.append("    auto sp = std::static_pointer_cast<%s>(shared_from_this());" % name)
            out.append("    switch (k_) {")
            for k, (mn, c) in enumerate(meths):
                if is_static(mn, c):
                    out.append("        case %d: return V::func([](const Args& A) { return pm_%s::C_%s::m_%s(A); });" % (k, c.module, ident(c.name), ident(mn)))
                else:
                    out.append('        case %d: { V method=V::func([sp](const Args& A) { return sp->m_%s(A); }); method.box->fattrs.emplace_back(Sym("__self__"), V::inst(sp)); method.box->fattrs.emplace_back(Sym("__native_bound_name__"), V(name)); return method; }' % (k, ident(mn)))
            out.append("    }")
        out.append("    return V();")
        out.append("}")
        out.append("bool %s::call_method(Sym name, const Args& A, V& out) {" % name)
        if GEN_UI[0] and not is_exception_class(ci):
            for owner in chain:
                out.append("    if (V replacement = py::class_method_override(pm_%s::cls_%s(), name, self()); replacement.has()) { out = replacement.call(A); return true; }" % (owner.module, ident(owner.name)))
        if meths:
            out.append("    " + table([m for m, _ in meths]))
            out.append("    const int k_ = idx_.find(name);")
            out.append("    if (k_ < 0) return false;")
            out.append("    switch (k_) {")
            for k, (mn, c) in enumerate(meths):
                if is_static(mn, c):
                    out.append("        case %d: out = pm_%s::C_%s::m_%s(A); return true;" % (k, c.module, ident(c.name), ident(mn)))
                else:
                    out.append("        case %d: out = m_%s(A); return true;" % (k, ident(mn)))
            out.append("    }")
        out.append("    return false;")
        out.append("}")
        if ci.properties:
            out.append("V %s::property(Sym name, bool& found) {" % name)
            for pn in ci.properties:
                out.append("    if (name == %s) { found = true; return pr_%s(); }" % (self.sy(pn), ident(pn)))
            out.append("    %s" % (("return %s::property(name, found);" % bcpp) if bcpp else "found = false; return V();"))
            out.append("}")
            out.append("bool %s::set_property(Sym name, const V& v) {" % name)
            for pn in ci.setters:
                out.append("    if (name == %s) { prset_%s(v); return true; }" % (self.sy(pn), ident(pn)))
            out.append("    return %s;" % (("%s::set_property(name, v)" % bcpp) if bcpp else "false"))
            out.append("}")
        for helper, value, count in getattr(ci,"class_unpacks",[]):
            scope=Scope("class",cls=ci)
            out.append('static V& %s() { static V value=[] { V result=py::as_seq(%s); if(result.len()!=%d)throw PyError("ValueError","class assignment unpack length mismatch");return result; }();return value; }' % (helper,self.expr(value,scope),count))
        for cv, expr in ci.classvars.items():
            sc = Scope("module")
            sc.method_scope = lambda: None
            sc.gen_root = lambda: False
            out.append("V& %s::cv_%s() { static V v = %s; return v; }" % (name, ident(cv), self.expr(expr, sc) if expr is not None else "V::none()"))
        for mn, fn in ci.methods.items():
            static = mn in ci.static or mn in ci.classmethods
            if skipped(self.mod, "%s.%s" % (ci.name, mn)):
                out.append("// %s::m_%s: hand-written (src/sim/pvp/hand)" % (name, ident(mn)))
                continue
            home = getattr(ci, "method_module", {}).get(mn)
            saved = (self.mod, self.mi)
            if home and home != self.mod:
                self.mod, self.mi = home, load(home)   # a mixin method resolves names in its own module
                self.deps.add(home)
            try:
                out.append(self.emit_function(fn, "", "%s::m_%s" % (name, ident(mn)), cls=ci, method=True, static=static))
            finally:
                self.mod, self.mi = saved
        for pn, fn in ci.properties.items():
            home = getattr(ci, "method_module", {}).get("@p:" + pn)
            saved = (self.mod, self.mi)
            if home and home != self.mod:
                self.mod, self.mi = home, load(home)
                self.deps.add(home)
            try:
                res = self.function_body(fn, Scope("module"), cls=ci, method=True)
            finally:
                self.mod, self.mi = saved
            lines = res[0]
            out.append("V %s::pr_%s() {\n    Args A;\n%s\n    return V::none();\n}\n" % (name, ident(pn), "\n".join(lines)))
        for pn, fn in ci.setters.items():
            home = getattr(ci, "method_module", {}).get("@p:" + pn)
            saved = (self.mod, self.mi)
            if home and home != self.mod:
                self.mod, self.mi = home, load(home)
                self.deps.add(home)
            try:
                res = self.function_body(fn, Scope("module"), cls=ci, method=True)
            finally:
                self.mod, self.mi = saved
            lines = res[0]
            out.append("void %s::prset_%s(const V& v_) {\n    Args A{v_};\n%s\n}\n" % (name, ident(pn), "\n".join(lines)))
        # constructor
        init_cv = []
        for c in reversed(chain):
            for cv in c.classvars:
                init_cv.append("    p->a_%s = C_%s::cv_%s();" % (ident(cv), ident(c.name), ident(cv)) if c.module == self.mod
                               else "    p->a_%s = pm_%s::C_%s::cv_%s();" % (ident(cv), c.module, ident(c.name), ident(cv)))
        if self.mod.startswith("test_pvp_"):
            attrs = sorted({a for c in chain for a in c.attrs})
            for a in attrs:
                for c in chain:
                    init_cv.append("    if (!p->a_%s.has()) { V v = pvz::getattr(pm_%s::cls_%s(), SY(%s), V()); if (v.has()) p->a_%s = v; }" % (ident(a), c.module, ident(c.name), cstr(a), ident(a)))
        has_init = any("__init__" in c.methods for c in chain)
        if is_exception_class(ci):
            out.append("V new_%s(const Args& A) { return py::make_exc(%s, A, %s); }" % (ident(ci.name), self.sv(ci.name), cstr(",".join(exc_bases(ci)))))
        elif ci.module == "expansion_assets" and ci.name == "TemplateAtlas":
            out.append('V new_TemplateAtlas(const Args& A) { init(); if(A.pos.size()>1) throw PyError("TypeError","TemplateAtlas expected one input"); V input=V::dict();if(!A.pos.empty())for(const auto& item:py::items_vec(py::dict_of(A.pos[0])))input.at(item.first)=item.second;for(const auto& item:A.kw)input.at(V(item.first))=item.second;return py::native_hook(V("core.template_atlas"),Args{input,cls_TemplateAtlas(),V::func([](const Args&){return TEMPLATE_ART;})}); }')
        else:
            out.append("void initcv_%s(%s* p) {\n%s\n}" % (ident(ci.name), name, "\n".join(init_cv)))
            initialization = ('callm(self, SY("__init__"), A);' if GEN_UI[0] else "p->m___init__(A);") if has_init else ""
            out.append("V new_%s(const Args& A) {\n    init();\n    auto p = std::make_shared<%s>();\n    V self = V::inst(p);\n    initcv_%s(p.get());\n    %s\n    return self;\n}" % (
                ident(ci.name), name, ident(ci.name), initialization))
        owner_module = ci.module if ci.module.startswith("test_") else "pvp." + ci.module
        attach = ' c.box->fattrs.emplace_back(Sym("__module__"), %s);' % self.sv(owner_module)
        if (self.mod,ci.name) in DYNAMIC_METHOD_CLASSES and not GEN_UI[0] and not self.mod.startswith("test_pvp_"):
            for cv in ci.classvars:
                attach += " c.box->fattrs.emplace_back(Sym(%s), C_%s::cv_%s());" % (cstr(cv),ident(ci.name),ident(cv))

        if not is_exception_class(ci) and "__new__" not in ci.methods:
            attach += " c.box->fattrs.emplace_back(Sym(\"__new__\"), V::func([](const Args& A) { if (A.pos.size() != 1 || !py_is(A.pos[0], cls_%s())) throw PyError(\"TypeError\", \"native __new__ requires its exact class\"); auto p = std::make_shared<C_%s>(); initcv_%s(p.get()); return V::inst(p); }));" % (ident(ci.name), ident(ci.name), ident(ci.name))
        bound_members = {}
        for c in reversed(chain):
            for mn in c.static | c.classmethods:
                if mn in c.methods:
                    bound_members[mn] = (c, c.methods[mn])
        for mn, (home, fn) in sorted(bound_members.items()):
            if getattr(fn, "_pvz_gen", False) or any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn)):
                continue
            target = "pm_%s::C_%s" % (home.module, ident(home.name))
            if mn in home.classmethods:
                attach += " c.box->fattrs.emplace_back(Sym(%s), V::func([](const Args& A) { Args bound = A; bound.kw.emplace_back(SY(\"__pvz_cls\"), cls_%s()); return %s::m_%s(bound); }));" % (cstr(mn), ident(ci.name), target, ident(mn))
            else:
                attach += " c.box->fattrs.emplace_back(Sym(%s), V::func([](const Args& A) { return %s::m_%s(A); }));" % (cstr(mn), target, ident(mn))
        if self.mod.startswith("test_pvp_") or GEN_UI[0]:
            seen = set(bound_members)
            for c in chain:
                for mn in c.methods:
                    if mn in seen: continue
                    seen.add(mn)
                    if mn in c.static or mn in c.classmethods: continue
                    target = "pm_%s::C_%s" % (c.module,ident(c.name))
                    attach += " c.box->fattrs.emplace_back(Sym(%s), V::func([](const Args& A) { return py::unbound_call<%s>([](%s* self, const Args& args) { return self->%s::m_%s(args); }, A); }));" % (cstr(mn),target,target,target,ident(mn))
            seen_attrs = set()
            for c in chain:
                for cv in c.classvars:
                    if cv in seen_attrs: continue
                    seen_attrs.add(cv)
                    attach += " c.box->fattrs.emplace_back(Sym(%s), pm_%s::C_%s::cv_%s());" % (cstr(cv),c.module,ident(c.name),ident(cv))
        if GEN_UI[0] and not is_exception_class(ci):
            attach += ' for (auto& item : c.box->fattrs) if (item.second.t == V::FUNC) item.second.box->fattrs.emplace_back(Sym("__native_declared_method__"), V(true));'
            attach += ' c.box->fattrs.emplace_back(Sym("__native_class_dispatch__"), V(true));'
            attach += ' c.box->fattrs.emplace_back(Sym("__native_static_methods__"), V::set({%s}));' % ', '.join(self.sv(n) for n in sorted(set(bound_members) | {"__new__"}))
        out.append("V cls_%s() { static V c = [] { V c = py::class_value(%s, [](const Args& A) { return new_%s(A); });%s return c; }(); return c; }" % (
            ident(ci.name), self.sv(ci.display_name), ident(ci.name), attach))
        return out


class DynGen(Gen):
    """Module whose globals live in a per-instance namespace object (python exec'd source).

    load() builds a fresh namespace (DynNS) each call, like native_runtime.load_patch.
    Every global reference goes through ns_ so runtime replacement of entries works.
    """
    BUILTIN_NAMES = set(BUILTIN_FUNCS) | {"object", "dict", "list", "tuple", "set", "frozenset", "str", "int",
                                          "float", "bool", "range", "isinstance", "getattr", "setattr", "hasattr",
                                          "min", "max", "sorted", "super", "len", "print", "Exception"} | BUILTIN_EXC

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gslots = {}      # global name -> slot index cached per namespace (DynNS::gslot_)

    def is_global(self, n, sc):
        return sc.lookup_local(n) is None and n not in ("True", "False", "None")

    def name_ref(self, n, sc):
        if getattr(sc, "recursive_name", None) == n:
            return 'py::native_hook(V("runtime.current_function"), Args{})'

        if n in ("True", "False", "None", "__name__"):
            return Gen.name_ref(self, n, sc)
        if sc.lookup_local(n) is not None:
            return "L_" + ident(n)
        if n in self.BUILTIN_NAMES and n not in self.mi.vars and n not in self.mi.funcs:
            if n in BUILTIN_EXC:
                return "py::exc_type(%s)" % self.sv(n)
            return "py::builtin(%s)" % self.sv(n)
        idx = self.gslots.setdefault(n, len(self.gslots))
        return "ns_->gslot_(%d, %s)" % (idx, self.sy(n))

    def e_Attribute(self, e, sc):
        if isinstance(e.value, ast.Name) and self.is_global(e.value.id, sc) and e.value.id not in self.BUILTIN_NAMES:
            return "pvz::getattr(%s, %s)" % (self.name_ref(e.value.id, sc), self.sy(e.attr))
        return Gen.e_Attribute(self, e, sc)

    def frame_wrap(self, sc, f_expr, args_expr):
        """Calls made by a patch function that has a local `entity` carry a frame (sys._getframe emulation)."""
        fn = getattr(self, "cur_function", None)
        if fn is None or "entity" not in getattr(self, "cur_function_locals", ()):
            return None
        return "py::call_site(V(%s), 0, py_dict({{V(\"entity\"), L_entity}}), %s, %s)" % (self.sv("patch:" + fn), f_expr, args_expr)

    def e_Call(self, e, sc):
        f = e.func
        inl = self.stdlib_inline(f, e, sc)
        if inl:
            return inl
        if isinstance(f, ast.Name) and sc.lookup_local(f.id) is not None and f.id not in self.BUILTIN_NAMES:
            w = self.frame_wrap(sc, "L_" + ident(f.id), self.args(e, sc))
            if w:
                return w
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.attr == "get" and f.value.id == "__pvz_sb_BASE_DAMAGE":
            w = self.frame_wrap(sc, "pvz::getattr(%s, %s)" % (self.name_ref(f.value.id, sc), self.sy("get")), self.args(e, sc))
            if w:
                return w
        if isinstance(f, ast.Name) and self.is_global(f.id, sc):
            if f.id in self.BUILTIN_NAMES and f.id not in self.mi.vars and f.id not in self.mi.funcs:
                special = self.builtin_call(f.id, e, sc)
                if special is not None:
                    return special
                if f.id in BUILTIN_EXC:
                    return "py::make_exc(%s, %s, \"\")" % (self.sv(f.id), self.args(e, sc))
            return "call(%s, %s)" % (self.name_ref(f.id, sc), self.args(e, sc))
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and self.is_global(f.value.id, sc) \
                and f.value.id not in self.BUILTIN_NAMES:
            return "callm(%s, %s, %s)" % (self.name_ref(f.value.id, sc), self.sy(f.attr), self.args(e, sc))
        return Gen.e_Call(self, e, sc)

    def builtin_call(self, n, e, sc):
        if n in self.mi.vars or n in self.mi.funcs:
            return None
        saved = resolve_symbol
        return Gen.builtin_call(self, n, e, sc)

    def assign_to(self, t, value, sc):
        if isinstance(t, ast.Name) and sc.lookup_local(t.id) is None:
            return "ns_->set_(%s, %s)" % (self.sy(t.id), value)
        return Gen.assign_to(self, t, value, sc)

    def s_AugAssign(self, s_, sc, ind):
        t = s_.target
        if isinstance(t, ast.Name) and sc.lookup_local(t.id) is None:
            val = self.expr(s_.value, sc)
            op = type(s_.op).__name__
            sym = {"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "Mod": "%"}.get(op, "+")
            cur = self.name_ref(t.id, sc)
            comb = ("py::iadd(%s, %s)" % (cur, val)) if op == "Add" else ("(%s %s %s)" % (cur, sym, val))
            return [ind + "ns_->set_(%s, %s);" % (self.sy(t.id), comb)]
        return Gen.s_AugAssign(self, s_, sc, ind)

    def s_FunctionDef(self, s_, sc, ind):
        if sc.kind == "module":
            return [ind + "ns_->set_(%s, py::with_globals(V::func([ns_](const Args& A) -> V { return f_%s(ns_, A); }), nsv, %s));" % (self.sy(s_.name), ident(s_.name), self.sv(s_.name))]
        return Gen.s_FunctionDef(self, s_, sc, ind)

    def s_Import(self, s_, sc, ind):
        out = []
        for a in s_.names:
            local = a.asname or a.name.split(".")[0]
            out.append(ind + "ns_->set_(%s, py::stdlib_module(%s));" % (self.sy(local), self.sv(a.name)))
        return out

    def s_ImportFrom(self, s_, sc, ind):
        out = []
        for a in s_.names:
            local = a.asname or a.name
            out.append(ind + "ns_->set_(%s, py::stdlib_attr(%s, %s));" % (self.sy(local), self.sv(s_.module or ""), self.sv(a.name)))
        return out

    def emit_function(self, fn, decl_prefix, qual, cls=None, method=False, static=False):
        self.cur_function = fn.name
        self.cur_function_locals = self.collect_locals(fn)[1]
        res = self.function_body(fn, Scope("module"), cls=None, method=False)
        self.cur_function = None
        lines, is_gen, is_ctx = res
        if is_gen:
            return "V %s(DynNS* ns_, const Args& A) { return PVZ_TODO(\"generator in dynamic module\"); }\n" % qual
        return "V %s(DynNS* ns_, const Args& A) {\n%s\n    return V::none();\n}\n" % (qual, "\n".join(lines))

    def run(self):
        mi, m = self.mi, self.mod
        h = ["// Generated by tools/pvp2cpp.py (dynamic module) - do not edit by hand.", "#pragma once",
             '#include "sim/pvp/pvprt.h"', "namespace pvz { namespace pm_%s {" % m,
             "// fresh namespace per call (python: exec(source, {}))", "V load();"]
        for f in mi.funcs:
            h.append("V f_%s(DynNS* ns_, const Args& A);" % ident(f))
        h.append("}}  // namespace pvz::pm_%s" % m)
        c = ["// Generated by tools/pvp2cpp.py (dynamic module) - do not edit by hand.",
             '#include "%s"' % header_path(m), "namespace pvz { namespace pm_%s {" % m]
        for fname, fn in mi.funcs.items():
            c.append(self.emit_function(fn, "", "f_%s" % ident(fname)))
        sc = Scope("module")
        sc.method_scope = lambda: None
        sc.gen_root = lambda: False
        body = []
        for node in mi.tree.body:
            body += self.stmt(node, sc, "    ")
        c.append("V load() {\n    auto nsp = std::make_shared<DynNS>();\n    DynNS* ns_ = nsp.get();\n    V nsv = V::inst(nsp);\n%s\n    return nsv;\n}" % "\n".join(body))
        c.append("}}  // namespace pvz::pm_%s" % m)
        return "\n".join(h) + "\n", "\n".join(c) + "\n"


def main():
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    failed = 0
    for m in sys.argv[2:]:
        GEN_UI[0] = (m in UI_MODULES and outdir.as_posix().rstrip("/").endswith("ui/gen")) or outdir.as_posix().rstrip("/").endswith("cpptests/gen")
        g = DynGen(m) if m in DYNAMIC else Gen(m)
        try:
            h, c = g.run()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print("FAILED", m, ex)
            failed += 1
            continue
        (outdir / ("pm_%s.h" % m)).write_text(h, encoding="utf-8")
        (outdir / ("pm_%s.cpp" % m)).write_text(c, encoding="utf-8")
        total += len(g.todo)
        sys.stdout.reconfigure(encoding="utf-8")
        print("%-28s todo=%d %s" % (m, len(g.todo), "; ".join(sorted(set(g.todo))[:6])))
    print("total TODO", total)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
