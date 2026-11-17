"""Enumerate every code site in an MSVC x64 EXE that references a given exception text.

Finds RIP-relative LEA instructions whose target is the literal (e.g. MSVC STL's
"invalid map<K, T> key"), then resolves each site, including inlined frames, through DbgHelp.
Usage: throw_sites.py <exe> <out.json> [literal ...]
"""
import ctypes, ctypes.wintypes as wt, json, struct, sys, os, hashlib

exe = os.path.abspath(sys.argv[1]); out_path = sys.argv[2]
literals = sys.argv[3:] or ["invalid map<K, T> key"]
data = open(exe, "rb").read()
pe = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, pe + 6)[0]
opt = pe + 24
optsize = struct.unpack_from("<H", data, pe + 20)[0]
image_base = struct.unpack_from("<Q", data, opt + 24)[0]
secs = []
for i in range(nsec):
    o = opt + optsize + 40 * i
    name = data[o:o + 8].rstrip(b"\0").decode()
    vsize, va, rsize, raw = struct.unpack_from("<IIII", data, o + 8)
    chars = struct.unpack_from("<I", data, o + 36)[0]
    secs.append((name, va, vsize, raw, rsize, chars))

def rva_of(off):
    for name, va, vsize, raw, rsize, chars in secs:
        if raw <= off < raw + rsize:
            return va + off - raw
    return None

targets = {}
for lit in literals:
    needle = lit.encode() + b"\0"
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0: break
        # require the literal to start a string (preceded by NUL) so substrings are not matched
        if pos == 0 or data[pos - 1] == 0:
            targets[rva_of(pos)] = lit
        pos += 1
print("literal rvas:", {hex(k): v for k, v in targets.items()})

sites = []
for name, va, vsize, raw, rsize, chars in secs:
    if not chars & 0x20000000:  # executable
        continue
    blob = data[raw:raw + rsize]
    n = len(blob)
    i = blob.find(b"\x8d")
    while i >= 0:
        if i >= 1 and i + 6 <= n and blob[i - 1] in (0x48, 0x4C) and (blob[i + 1] & 0xC7) == 0x05:
            disp = struct.unpack_from("<i", blob, i + 2)[0]
            tgt = va + i + 6 + disp
            if tgt in targets:
                sites.append((va + i - 1, targets[tgt]))
        i = blob.find(b"\x8d", i + 1)
print("sites:", len(sites))

dbghelp = ctypes.WinDLL("dbghelp.dll")
k32 = ctypes.WinDLL("kernel32.dll")
class SYMBOL_INFOW(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wt.ULONG), ("TypeIndex", wt.ULONG), ("Reserved", ctypes.c_uint64 * 2), ("Index", wt.ULONG),
                ("Size", wt.ULONG), ("ModBase", ctypes.c_uint64), ("Flags", wt.ULONG), ("Value", ctypes.c_uint64),
                ("Address", ctypes.c_uint64), ("Register", wt.ULONG), ("Scope", wt.ULONG), ("Tag", wt.ULONG),
                ("NameLen", wt.ULONG), ("MaxNameLen", wt.ULONG), ("Name", ctypes.c_wchar * 4096)]
class LINEW(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wt.DWORD), ("Key", ctypes.c_void_p), ("LineNumber", wt.DWORD),
                ("FileName", ctypes.c_wchar_p), ("Address", ctypes.c_uint64)]
H = ctypes.c_void_p(0x1234)
dbghelp.SymSetOptions.argtypes = [wt.DWORD]
dbghelp.SymSetOptions(0x10 | 0x2 | 0x4)  # LOAD_LINES | UNDNAME | DEFERRED_LOADS
dbghelp.SymInitializeW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, wt.BOOL]
if not dbghelp.SymInitializeW(H, os.path.dirname(exe), False):
    raise SystemExit("SymInitialize failed")
dbghelp.SymLoadModuleExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint64, wt.DWORD, ctypes.c_void_p, wt.DWORD]
dbghelp.SymLoadModuleExW.restype = ctypes.c_uint64
base = dbghelp.SymLoadModuleExW(H, None, exe, None, image_base, len(data), None, 0)
if not base:
    raise SystemExit("SymLoadModuleEx failed %d" % k32.GetLastError())
dbghelp.SymFromAddrW.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYMBOL_INFOW)]
dbghelp.SymGetLineFromAddrW64.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(wt.DWORD), ctypes.POINTER(LINEW)]
dbghelp.SymAddrIncludeInlineTrace.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
dbghelp.SymAddrIncludeInlineTrace.restype = wt.DWORD
dbghelp.SymQueryInlineTrace.argtypes = [ctypes.c_void_p, ctypes.c_uint64, wt.DWORD, ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.DWORD)]
dbghelp.SymFromInlineContextW.argtypes = [ctypes.c_void_p, ctypes.c_uint64, wt.ULONG, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYMBOL_INFOW)]
dbghelp.SymGetLineFromInlineContextW.argtypes = [ctypes.c_void_p, ctypes.c_uint64, wt.ULONG, ctypes.c_uint64, ctypes.POINTER(wt.DWORD), ctypes.POINTER(LINEW)]

def sym(addr, ctx=None):
    s = SYMBOL_INFOW(); s.SizeOfStruct = 88; s.MaxNameLen = 4000
    d = ctypes.c_uint64()
    ok = dbghelp.SymFromInlineContextW(H, addr, ctx, ctypes.byref(d), ctypes.byref(s)) if ctx is not None else dbghelp.SymFromAddrW(H, addr, ctypes.byref(d), ctypes.byref(s))
    return s.Name if ok else "?"
def line(addr, ctx=None):
    l = LINEW(); l.SizeOfStruct = ctypes.sizeof(LINEW); d = wt.DWORD()
    ok = dbghelp.SymGetLineFromInlineContextW(H, addr, ctx, 0, ctypes.byref(d), ctypes.byref(l)) if ctx is not None else dbghelp.SymGetLineFromAddrW64(H, addr, ctypes.byref(d), ctypes.byref(l))
    return (l.FileName, l.LineNumber) if ok else ("?", 0)

rows = []
for rva, lit in sites:
    addr = base + rva
    frames = []
    n = dbghelp.SymAddrIncludeInlineTrace(H, addr)
    if n:
        ctx = wt.DWORD(); fi = wt.DWORD()
        if dbghelp.SymQueryInlineTrace(H, addr, 0, addr, addr, ctypes.byref(ctx), ctypes.byref(fi)):
            for k in range(n):
                f, ln = line(addr, ctx.value + k)
                frames.append({"fn": sym(addr, ctx.value + k), "file": f, "line": ln, "inline": True})
    f, ln = line(addr)
    frames.append({"fn": sym(addr), "file": f, "line": ln, "inline": False})
    rows.append({"rva": hex(rva), "literal": lit, "frames": frames})
json.dump({"exe": exe, "sha256": hashlib.sha256(data).hexdigest(), "literals": literals, "sites": rows},
          open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("sha256", hashlib.sha256(data).hexdigest())
