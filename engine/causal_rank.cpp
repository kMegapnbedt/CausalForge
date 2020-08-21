// causal_rank.cpp — CausalForge ranking core (portable C++17)
//
// A dependency-free root-cause ranking demo that mirrors the scoring model
// implemented in the Python `causalforge` package. It reads a compact,
// line-oriented incident description from stdin (or a file argument), builds
// an in-memory causal graph, propagates temporal blame from failing sinks
// back toward upstream sources, folds in local error evidence, and prints a
// ranked list of suspect nodes together with a blast-radius estimate.
//
// The on-wire format is intentionally trivial so the engine stays free of any
// third-party parser. Lines are one of:
//
//   N <id> <t_start> <t_end> <status> <error_weight>
//   E <src> <dst> <coupling>
//
// where `status` is 0 (ok), 1 (degraded) or 2 (failed) and every numeric
// field is whitespace separated. Blank lines and lines starting with '#' are
// ignored. See engine/README or the top-level docs for the full grammar.
//
// Build:  g++ -std=c++17 -Wall -Wextra -pedantic -O2 -o causal_rank engine/causal_rank.cpp
// Syntax: g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only engine/causal_rank.cpp

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace causalforge {

// A single execution event / node in the causal graph.
struct Node {
    std::string id;
    double t_start = 0.0;
    double t_end = 0.0;
    int status = 0;          // 0 ok, 1 degraded, 2 failed
    double error_weight = 0.0;
    // Derived / accumulated fields.
    double blame = 0.0;      // propagated temporal blame
    double score = 0.0;      // final ranking score
    int reachable = 0;       // downstream reachable count (blast radius)
};

// A directed causal dependency edge: src influences dst.
struct Edge {
    std::string src;
    std::string dst;
    double coupling = 1.0;   // 0..1 strength of causal coupling
};

