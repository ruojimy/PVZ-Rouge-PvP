# Regex conformance: python's re vs the native build's re (app_run retest).
#   python38 tools/re_cases.py gen  <cases.json>     -> cases + python's expected results
#   python38 tools/re_cases.py diff <cases.json> <native_out.json>
import json, re, sys

CASES = [
    ("split", r"(?<=[。！？])", "第一句。第二句！第三句？尾巴", 0),
    ("split", r"(?<=[。！？])", "只有一句。", 0),
    ("split", r"\s+", " a  b c ", 0),
    ("split", r"(,)", "a,b,c", 0),
    ("split", r"\b", "ab cd", 0),
    ("split", r"x*", "axb", 0),
    ("findall", r"(?<![A-Za-z])(?:AI|A\.I\.|bot|Bot|BOT|robot|Robot|CPU|NPC|DeepSeek|deepseek|LLM)(?![A-Za-z])", "我是AI，不是robots也不是Bot。CPU!", 0),
    ("findall", r"(?<![A-Za-z0-9])r1[0-9](?:[a-z]+)?(?![0-9])|大脑\s*r?\d+|rv_[a-z0-9_]+", "大脑 r22 与 r15x 以及 rv_tactics15、r123", 0),
    ("fullmatch", r"[0-9a-f]{32}", "7f57645de1674736afd682a603cb3e11", 0),
    ("fullmatch", r"[0-9a-f]{32}", "7F57645de1674736afd682a603cb3e11", 0),
    ("fullmatch", r"[0-9a-f]{32}", "7f57645de1674736afd682a603cb3e1", 0),
    ("findall", r"(\d+)-(\d+)", "1-2 33-44 5-", 0),
    ("findall", r"\d+", "a12b345c", 0),
    ("sub", r"(\w+)@(\w+)", "x@y and foo@bar", 0, r"\2 at \1"),
    ("sub", r"x*", "abc", 0, "-"),
    ("sub", r"\s+", "  多个   空格 ", 0, " "),
    ("sub", r"(?P<n>\d)", "a1b2", 0, r"<\g<n>>"),
    ("search", r"b+?", "abbbc", 0),
    ("search", r"^\w+$", "line1\nline2", 8),
    ("search", r"HELLO", "say hello", 2),
    ("search", r"a.c", "a\nc", 16),
    ("search", r"[^。]+。", "前缀。后缀", 0),
    ("match", r"(a|ab)(c|bcd)(d*)", "abcd", 0),
    ("findall", r"[一-鿿]+", "abc中文def字", 0),
    ("split", r"[，,、]", "甲，乙,丙、丁", 0),
    ("findall", r"(?i)abc", "ABC abc AbC", 0),
    ("search", r"(\w)\1", "abccd", 0),
]

def run(case):
    op, pat, text, flags = case[:4]
    try:
        if op == "split": return re.split(pat, text, flags=flags)
        if op == "findall": return [list(x) if isinstance(x, tuple) else x for x in re.findall(pat, text, flags=flags)]
        if op == "sub": return re.sub(pat, case[4], text, flags=flags)
        m = getattr(re, op)(pat, text, flags=flags)
        return None if m is None else [m.group(0), list(m.groups()), list(m.span())]
    except Exception as e:
        return "error: " + type(e).__name__

if sys.argv[1] == "gen":
    out = [dict(case=list(c), expect=run(c)) for c in CASES]
    open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    print("cases", len(out))
else:
    cases = json.load(open(sys.argv[2], encoding="utf-8"))
    got = json.load(open(sys.argv[3], encoding="utf-8"))
    bad = 0
    for c, g in zip(cases, got):
        if c["expect"] != g:
            bad += 1
            print("MISMATCH", c["case"], "\n   python:", c["expect"], "\n   native:", g)
    print("regex cases: %d, mismatches: %d" % (len(cases), bad))
    sys.exit(1 if bad else 0)
