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

// The graph plus fast lookup indices.
class CausalGraph {
public:
    std::vector<Node> nodes;
    std::vector<Edge> edges;
    std::unordered_map<std::string, std::size_t> index;

    void add_node(const Node& n) {
        index[n.id] = nodes.size();
        nodes.push_back(n);
    }

    void add_edge(const Edge& e) { edges.push_back(e); }

    Node* find(const std::string& id) {
        auto it = index.find(id);
        if (it == index.end()) return nullptr;
        return &nodes[it->second];
    }

    // Outgoing adjacency (src -> list of edge indices).
    std::unordered_map<std::string, std::vector<std::size_t>> out_adj() const {
        std::unordered_map<std::string, std::vector<std::size_t>> adj;
        for (std::size_t i = 0; i < edges.size(); ++i) {
            adj[edges[i].src].push_back(i);
        }
        return adj;
    }

    // Incoming adjacency (dst -> list of edge indices).
    std::unordered_map<std::string, std::vector<std::size_t>> in_adj() const {
        std::unordered_map<std::string, std::vector<std::size_t>> adj;
        for (std::size_t i = 0; i < edges.size(); ++i) {
            adj[edges[i].dst].push_back(i);
        }
        return adj;
    }
};

// Temporal decay kernel: upstream events that occur *before* a failing sink
// are more suspicious the closer they are in time. We use a bounded
// exponential so ordering never produces negative or exploding weights.
static double temporal_kernel(double upstream_end, double downstream_start,
                              double half_life) {
    double dt = downstream_start - upstream_end;
    if (dt < 0.0) {
        // Upstream ended after downstream started: weak causal support.
        return 0.15;
    }
    if (half_life <= 0.0) half_life = 1.0;
    return std::exp(-0.6931471805599453 * dt / half_life);
}

// Count downstream-reachable nodes for a given start via BFS. This is the
// blast radius: how much of the graph a failure at `start` can influence.
static int blast_radius(const CausalGraph& g,
                        const std::unordered_map<std::string, std::vector<std::size_t>>& adj,
