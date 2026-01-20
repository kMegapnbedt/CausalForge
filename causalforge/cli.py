"""CausalForge command-line interface.

Subcommands
-----------
``analyze``   Rank root causes for an incident and print a report.
``timeline``  Reconstruct and print the incident timeline.
``blast``     Report the blast radius of a specific node.
``convert``   Convert a JSON incident into the compact event stream (for the
              C++ engine) or vice versa.
``validate``  Structural validation of an incident graph.

All commands read the canonical JSON incident schema unless ``--events`` is
passed, in which case the compact line format is used.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .graph import CausalGraph
from .blast import blast_radius, reachable_set, weighted_blast
from .ingest import load_incident, parse_events, to_events
from .rank import RankConfig, rank_incident
from .report import render_json, render_markdown
from .timeline import build_timeline, timeline_text


def _read_incident(args) -> "Incident":  # noqa: F821 - forward ref for docs
    if args.events:
        with open(args.input, "r", encoding="utf-8") as fh:
            return parse_events(fh.read())
    return load_incident(args.input)


def _cmd_analyze(args) -> int:
    incident = _read_incident(args)
    graph = CausalGraph(incident)
    cfg = RankConfig(
        rounds=args.rounds,
        half_life=args.half_life,
        damping=args.damping,
        radius_gain=args.radius_gain,
    )
    suspects = rank_incident(graph, cfg)
    if args.format == "json":
        out = render_json(incident, graph, suspects)
    else:
        out = render_markdown(incident, graph, suspects)
    _emit(out, args.output)
    return 0


def _cmd_timeline(args) -> int:
    incident = _read_incident(args)
    graph = CausalGraph(incident)
    out = timeline_text(build_timeline(graph))
    _emit(out + "\n", args.output)
    return 0


def _cmd_blast(args) -> int:
    incident = _read_incident(args)
    graph = CausalGraph(incident)
    if not graph.has_node(args.node):
        print(f"error: unknown node '{args.node}'", file=sys.stderr)
        return 1
    radius = blast_radius(graph, args.node)
    weighted = weighted_blast(graph, args.node)
    downstream = sorted(reachable_set(graph, args.node))
    print(f"node: {args.node}")
    print(f"blast_radius: {radius}")
    print(f"weighted_blast: {weighted:.3f}")
    print("downstream:")
    for d in downstream:
        print(f"  - {d}")
    return 0


def _cmd_convert(args) -> int:
    if args.events:
        with open(args.input, "r", encoding="utf-8") as fh:
            incident = parse_events(fh.read())
        # Emit JSON when reading events.
        out = render_json(incident, CausalGraph(incident),
                           rank_incident(CausalGraph(incident)))
    else:
        incident = load_incident(args.input)
        out = to_events(incident)
    _emit(out, args.output)
    return 0


def _cmd_validate(args) -> int:
    incident = _read_incident(args)
    graph = CausalGraph(incident)
    warnings = graph.validate()
    print(f"nodes={graph.order()} edges={graph.size()} "
          f"sources={len(graph.sources())} sinks={len(graph.sinks())} "
          f"failing={len(graph.failing())}")
    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")
        return 1
    print("ok: no structural warnings")
    return 0


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="causalforge",
        description="CausalForge — AI Failure Causality Explorer",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    def add_common(p):
        p.add_argument("input", help="incident file (JSON, or compact with --events)")
        p.add_argument("--events", action="store_true",
                       help="treat input as the compact event stream format")
        p.add_argument("-o", "--output", help="write to file instead of stdout")

    p_analyze = sub.add_parser("analyze", help="rank likely root causes")
    add_common(p_analyze)
    p_analyze.add_argument("--format", choices=["markdown", "json"],
                           default="markdown")
    p_analyze.add_argument("--rounds", type=int, default=6)
    p_analyze.add_argument("--half-life", dest="half_life", type=float, default=5.0)
    p_analyze.add_argument("--damping", type=float, default=0.55)
    p_analyze.add_argument("--radius-gain", dest="radius_gain", type=float, default=0.25)
    p_analyze.set_defaults(func=_cmd_analyze)

    p_timeline = sub.add_parser("timeline", help="print the incident timeline")
    add_common(p_timeline)
    p_timeline.set_defaults(func=_cmd_timeline)

    p_blast = sub.add_parser("blast", help="report blast radius of a node")
    add_common(p_blast)
    p_blast.add_argument("--node", required=True, help="node id to inspect")
    p_blast.set_defaults(func=_cmd_blast)

    p_convert = sub.add_parser("convert", help="convert between JSON and events")
    add_common(p_convert)
    p_convert.set_defaults(func=_cmd_convert)

    p_validate = sub.add_parser("validate", help="structural validation")
    add_common(p_validate)
    p_validate.set_defaults(func=_cmd_validate)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        from . import __version__
        print(f"causalforge {__version__}")
        return 0
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
