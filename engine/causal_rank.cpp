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
                        const std::string& start) {
    std::map<std::string, bool> seen;
    std::vector<std::string> stack{start};
    seen[start] = true;
    int count = 0;
    while (!stack.empty()) {
        std::string cur = stack.back();
        stack.pop_back();
        auto it = adj.find(cur);
        if (it == adj.end()) continue;
        for (std::size_t ei : it->second) {
            const std::string& nxt = g.edges[ei].dst;
            if (!seen[nxt]) {
                seen[nxt] = true;
                ++count;
                stack.push_back(nxt);
            }
        }
    }
    return count;
}

// The core ranking routine. Blame flows backward from failed/degraded sinks
// along incoming edges, attenuated by coupling strength and the temporal
// kernel. We iterate a fixed number of propagation rounds so the algorithm
// is deterministic and terminates without a convergence oracle.
void rank(CausalGraph& g, int rounds = 6, double half_life = 5.0) {
    auto in = g.in_adj();
    auto out = g.out_adj();

    // Seed: failing sinks inject blame proportional to severity.
    for (auto& n : g.nodes) {
        if (n.status == 2) n.blame = 1.0;
        else if (n.status == 1) n.blame = 0.4;
        else n.blame = 0.0;
    }

    // Propagate blame upstream over several damped rounds.
    for (int r = 0; r < rounds; ++r) {
        std::unordered_map<std::string, double> delta;
        for (const auto& n : g.nodes) {
            if (n.blame <= 1e-9) continue;
            auto it = in.find(n.id);
            if (it == in.end()) continue;
            for (std::size_t ei : it->second) {
                const Edge& e = g.edges[ei];
                Node* up = g.find(e.src);
                if (!up) continue;
                double k = temporal_kernel(up->t_end, n.t_start, half_life);
                double transfer = n.blame * e.coupling * k * 0.55;
                delta[up->id] += transfer;
            }
        }
        for (auto& kv : delta) {
            Node* up = g.find(kv.first);
            if (up) up->blame += kv.second;
        }
    }

    // Fold in local error evidence and blast radius; compute final score.
    for (auto& n : g.nodes) {
        n.reachable = blast_radius(g, out, n.id);
        double radius_factor = 1.0 + std::log1p(static_cast<double>(n.reachable)) * 0.25;
        n.score = (n.blame + n.error_weight) * radius_factor;
    }
}

// Parse the compact line format into a graph. Returns false on malformed input
// but tolerates comments and blank lines.
bool parse(std::istream& in, CausalGraph& g, std::string& err) {
    std::string line;
    std::size_t lineno = 0;
    while (std::getline(in, line)) {
        ++lineno;
        // Trim leading whitespace.
        std::size_t s = line.find_first_not_of(" \t\r\n");
        if (s == std::string::npos) continue;
        if (line[s] == '#') continue;
        std::istringstream ss(line);
        char kind = 0;
        ss >> kind;
        if (kind == 'N') {
            Node n;
            if (!(ss >> n.id >> n.t_start >> n.t_end >> n.status >> n.error_weight)) {
                err = "malformed N record at line " + std::to_string(lineno);
                return false;
            }
            g.add_node(n);
        } else if (kind == 'E') {
            Edge e;
            if (!(ss >> e.src >> e.dst >> e.coupling)) {
                err = "malformed E record at line " + std::to_string(lineno);
                return false;
            }
            g.add_edge(e);
        } else {
            err = "unknown record kind at line " + std::to_string(lineno);
            return false;
        }
    }
    return true;
}

// Emit a ranked report to stdout. Deterministic ordering: score desc, then id.
void report(const CausalGraph& g) {
    std::vector<const Node*> ranked;
    ranked.reserve(g.nodes.size());
    for (const auto& n : g.nodes) ranked.push_back(&n);
    std::sort(ranked.begin(), ranked.end(), [](const Node* a, const Node* b) {
        if (std::abs(a->score - b->score) > 1e-9) return a->score > b->score;
        return a->id < b->id;
    });

    std::cout << "CausalForge ranking report\n";
    std::cout << "nodes=" << g.nodes.size() << " edges=" << g.edges.size() << "\n";
    std::cout << "----------------------------------------------------------\n";
    std::cout << "rank  node                score    blame   errW  radius\n";
    int rank = 1;
    for (const Node* n : ranked) {
        std::ostringstream row;
        row << (rank < 10 ? " " : "") << rank << "   ";
        std::string id = n->id;
        if (id.size() < 18) id.append(18 - id.size(), ' ');
        row << id << "  ";
        char buf[128];
        std::snprintf(buf, sizeof(buf), "%7.3f  %6.3f  %5.2f  %4d",
                      n->score, n->blame, n->error_weight, n->reachable);
        row << buf;
        std::cout << row.str() << "\n";
        ++rank;
    }
    if (!ranked.empty()) {
        std::cout << "----------------------------------------------------------\n";
        std::cout << "primary_suspect=" << ranked.front()->id
                  << " score=" << ranked.front()->score << "\n";
    }
}

}  // namespace causalforge

int main(int argc, char** argv) {
    using namespace causalforge;
    CausalGraph g;
    std::string err;

    if (argc > 1) {
        std::ifstream f(argv[1]);
        if (!f) {
            std::cerr << "causal_rank: cannot open " << argv[1] << "\n";
            return 2;
        }
        if (!parse(f, g, err)) {
            std::cerr << "causal_rank: " << err << "\n";
            return 3;
        }
    } else {
        if (!parse(std::cin, g, err)) {
            std::cerr << "causal_rank: " << err << "\n";
            return 3;
        }
    }

    if (g.nodes.empty()) {
        std::cerr << "causal_rank: no nodes parsed\n";
        return 4;
    }

    rank(g);
    report(g);
    return 0;
}
