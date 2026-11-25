"""Command line: generate a report or ask a question without opening the app.

    eda report examples/data/heated_loop_run_042.csv --limits examples/limits.json --spectrum accel_pump_g -o report.pdf
    eda ask examples/data/heated_loop_run_042.csv --docs examples/docs "Does this run meet the acceptance criteria?"
"""

from __future__ import annotations

import argparse
import json
import sys

from .data import load_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eda", description="Engineering Data Assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="Generate a PDF test report")
    rep.add_argument("csv")
    rep.add_argument("-o", "--output", default="test_report.pdf")
    rep.add_argument("--limits", help="JSON file with acceptance limits per channel")
    rep.add_argument("--spectrum", nargs="*", default=[], help="Channels to include a frequency analysis for")
    rep.add_argument("--title")

    ask = sub.add_parser("ask", help="Ask a question about the data (needs Claude API credentials)")
    ask.add_argument("csv")
    ask.add_argument("question")
    ask.add_argument("--docs", help="Folder of Markdown/text documentation")

    args = parser.parse_args(argv)
    ds = load_csv(args.csv)

    if args.command == "report":
        from .report import build_report

        limits = json.loads(open(args.limits, encoding="utf-8").read()) if args.limits else None
        path = build_report(ds, args.output, limits=limits, spectrum_channels=args.spectrum, title=args.title)
        print(f"Report written to {path}")
        return 0

    from .assistant import EngineeringAssistant
    from .docs import DocumentIndex

    docs = DocumentIndex.from_folder(args.docs) if args.docs else None
    answer = EngineeringAssistant(ds, docs).ask(args.question)
    for call in answer.tool_calls:
        print(f"  [tool] {call.name}({json.dumps(call.input)})", file=sys.stderr)
    print(answer.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
