"""Per-test ownership for relay-related old-suite tests (decision 2026-11-02, relay = option C).

    python tools/relay_ownership.py <native run dir> <out.md> [<out.json>]

Classification is derived from the ORIGINAL test source (AST of the test method and its class setUp chain):
  server-implementation   touches relay server internals that the out-of-process fixture deliberately does
                          not expose (server.send replacement, server_module.* mocks). Owned by the Python
                          server suite; NOT counted as native coverage.
  native-client+relay     uses LocalRelay / a relay endpoint: the client under test is the native C++ code,
                          the server is the real Python relay in a subprocess (tools/relay_fixture_server.py).
  native-client           no relay involved.
The outcome column is the native run's result for that test id (worst of repeats).
"""
import ast, json, sys
from pathlib import Path

TESTS = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\tests")
SERVER_MARKERS = ("server.send", "server_module.")
RELAY_MARKERS = ("LocalRelay", "relay.endpoint", "spectator_relay", "local_relay", "PVP_TEST_RELAY_ENDPOINT", "RelayServer")


def sources(mod):
    tree = ast.parse((TESTS / (mod + ".py")).read_text(encoding="utf-8"))
    text = (TESTS / (mod + ".py")).read_text(encoding="utf-8")
    out = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        setup = "".join(ast.get_source_segment(text, f) or "" for f in cls.body
                        if isinstance(f, ast.FunctionDef) and f.name in ("setUp", "setUpClass", "connected", "host", "guest", "raw"))
        bases = " ".join(ast.get_source_segment(text, b) or "" for b in cls.bases)
        for f in cls.body:
            if isinstance(f, ast.FunctionDef) and f.name.startswith("test"):
                out[(cls.name, f.name)] = (ast.get_source_segment(text, f) or "", setup, bases)
    return out


def classify(body, setup, bases, module_text):
    if any(m in body for m in SERVER_MARKERS):
        return "server-implementation"
    # a class helper that swaps server methods behind a flag (test_pvp_66_room_admission_oct16.host(legacy=True))
    if "legacy=True" in body and "server.server.send" in module_text:
        return "server-implementation"
    joined = body + setup + bases
    if any(m in joined for m in RELAY_MARKERS) or "native_match.MatchNetworkTests" in bases:
        return "native-client+relay"
    return "native-client"


def main():
    run, out_md = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    rank = {"PASS": 0, "SKIP": 1, "FAIL": 2, "ERROR": 3}
    for f in sorted(run.glob("test_*.json")):
        if f.name.endswith(".status.json"):
            continue
        mod = f.stem
        try:
            src = sources(mod)
        except OSError:
            src = {}
        module_text = (TESTS / (mod + ".py")).read_text(encoding="utf-8")
        best = {}
        for r in json.loads(f.read_text(encoding="utf-8")):
            k = (r["class"], r["test"])
            if k not in best or rank[r["outcome"]] > rank[best[k]["outcome"]]:
                best[k] = r
        for (cls, test), r in sorted(best.items()):
            body, setup, bases = src.get((cls, test), ("", "", ""))
            if not body:   # inherited test: classify by the bound class's setUp chain
                body = ""
            owner = classify(body, setup, bases, module_text)
            detail = (r["detail"].strip().splitlines() or [""])[-1][:160]
            rows.append(dict(module=mod, cls=cls, test=test, owner=owner, outcome=r["outcome"], detail=detail))
    lines = ["# relay 相关测试归属（自动生成：tools/relay_ownership.py %s）" % run.name, "",
             "分类依据见脚本说明；`server-implementation` 不计入原生覆盖。", "",
             "| 模块 | 类.用例 | 归属 | 原生结果 | 说明 |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| %s | %s.%s | %s | %s | %s |" % (r["module"], r["cls"], r["test"], r["owner"], r["outcome"], r["detail"].replace("|", "/")))
    summary = {}
    for r in rows:
        summary.setdefault(r["owner"], {}).setdefault(r["outcome"], 0)
        summary[r["owner"]][r["outcome"]] += 1
    lines += ["", "汇总：`" + json.dumps(summary, ensure_ascii=False) + "`"]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(json.dumps(dict(rows=rows, summary=summary), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
