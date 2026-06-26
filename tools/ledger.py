#!/usr/bin/env python3
"""LLM Ledger CLI — validate and inspect the ledger. Zero dependencies.

Usage:
  python3 tools/ledger.py check [--repo .]     # validate; exit 1 on errors
  python3 tools/ledger.py search "<query>" [--as-of YYYY-MM-DD]
  python3 tools/ledger.py stats
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger_core as core  # noqa: E402

RED, YEL, GRN, DIM, RST = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[0m"


def _color(sev):
    return {"ERROR": RED, "WARN": YEL, "INFO": DIM}.get(sev, "")


def cmd_check(args):
    issues, claims = core.validate(args.repo)
    errors = [i for i in issues if i[0] == "ERROR"]
    warns = [i for i in issues if i[0] == "WARN"]
    for sev, msg in issues:
        print(f"{_color(sev)}{sev:5}{RST}  {msg}")
    print()
    n = len(claims)
    if errors:
        print(f"{RED}✖ {len(errors)} error(s), {len(warns)} warning(s) across {n} claims{RST}")
        return 1
    if warns:
        print(f"{YEL}⚠ 0 errors, {len(warns)} warning(s) across {n} claims{RST}")
        return 0
    print(f"{GRN}✔ ledger is consistent — {n} claims, 0 errors, 0 warnings{RST}")
    return 0


def cmd_search(args):
    claims, _ = core.load_claims(args.repo)
    hits = core.search(claims, args.query, as_of=args.as_of)
    if not hits:
        print("no matching claims")
        return 0
    for c in hits:
        flag = "" if c.get("status") == "active" else f" [{c.get('status')}]"
        print(f"{c.get('id')}{flag}  ({c.get('confidence')})")
        print(f"  {c.get('statement')}")
        vf, vu = c.get("valid_from"), c.get("valid_until")
        if vf or vu:
            print(f"  {DIM}valid: {vf or '?'} -> {vu or 'now'}{RST}")
    return 0


def cmd_stats(args):
    claims, _ = core.load_claims(args.repo)
    topics = {}
    status = {}
    for c in claims:
        topics[c.get("topic")] = topics.get(c.get("topic"), 0) + 1
        status[c.get("status")] = status.get(c.get("status"), 0) + 1
    print(f"claims: {len(claims)}")
    print(f"topics: {len(topics)}  -> {', '.join(sorted(t for t in topics if t))}")
    print("status: " + ", ".join(f"{k}={v}" for k, v in sorted(status.items())))
    return 0


def main():
    p = argparse.ArgumentParser(prog="ledger", description="LLM Ledger CLI")
    p.add_argument("--repo", default=".", help="repo root (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate the ledger")
    sp = sub.add_parser("search", help="search claims")
    sp.add_argument("query")
    sp.add_argument("--as-of", dest="as_of", default=None)
    sub.add_parser("stats", help="show counts")
    args = p.parse_args()

    if args.cmd == "check":
        sys.exit(cmd_check(args))
    elif args.cmd == "search":
        sys.exit(cmd_search(args))
    elif args.cmd == "stats":
        sys.exit(cmd_stats(args))


if __name__ == "__main__":
    main()
