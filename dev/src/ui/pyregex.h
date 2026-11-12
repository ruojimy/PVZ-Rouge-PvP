// A small backtracking regular-expression engine with python `re` semantics on code points
// (std::regex has no lookbehind and matches UTF-8 bytes, so "[。！？]" or "(?<=[。！？])" break).
// Supported: literals, ., [...] (ranges, negation, \d \w \s inside), \d \D \w \W \s \S \b \B \A \Z,
// ^ $ (MULTILINE), groups ( ), (?: ), (?P<name> ), lookahead (?= ) (?! ), lookbehind (?<= ) (?<! ),
// alternation, greedy / lazy * + ? {m} {m,} {m,n}, flags IGNORECASE / MULTILINE / DOTALL, backrefs \1.
#pragma once
#include <memory>
#include <string>
#include <vector>

namespace pvz::rx {

struct Node;
struct Regex {
    std::shared_ptr<Node> root;
    int groups = 0;
    std::vector<std::pair<std::string, int>> names;
    int flags = 0;   // python values: 2 IGNORECASE, 8 MULTILINE, 16 DOTALL
};
Regex compile(const std::string& pattern, int flags);   // throws std::runtime_error on a bad pattern

struct Match {
    bool ok = false;
    std::vector<long> spans;   // code-point offsets: 2*(groups+1), -1 when unset
};
// text as code points; search from `start`, anchored = match only at start
Match search(const Regex& re, const std::u32string& text, size_t start, bool anchored, bool full = false);

std::u32string decode(const std::string& utf8);
std::string encode(const std::u32string& s, size_t a, size_t b);

}  // namespace pvz::rx
