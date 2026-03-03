#!/usr/bin/env python3
"""Simple CLI to create RO-Crates via the running API.

Usage examples are in the package README. This is intentionally small and
dependency-free (uses stdlib) so it can be run without installing extra
packages.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Any


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def post_json(url: str, payload: Any) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            print(f"{resp.status} {getattr(resp, 'reason', '')}")
            if body:
                print(body)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} {e.reason}")
        try:
            print(e.read().decode("utf-8"))
        except Exception:
            pass
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        sys.exit(1)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driveoff-cli", description="Driveoff CLI: create RO crates via API"
    )
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser(
        "create-crate", help="Create an RO-Crate by POSTing JSON to the API"
    )
    create.add_argument("json_file", help="Path to JSON file with payload to send")
    create.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)",
    )
    create.add_argument(
        "--endpoint",
        default="/api/v1/submission",
        help="API endpoint path or full URL (default: /api/v1/submission)",
    )
    create.add_argument(
        "--dry-run", action="store_true", help="Print payload and exit without sending"
    )
    create.add_argument(
        "--pretty", action="store_true", help="Pretty-print payload on dry-run"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "create-crate":
        payload = load_json(args.json_file)
        if args.dry_run:
            if args.pretty:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(payload, ensure_ascii=False))
            return

        # build target URL
        if args.endpoint.startswith("http://") or args.endpoint.startswith("https://"):
            target = args.endpoint
        else:
            target = args.api_url.rstrip("/") + "/" + args.endpoint.lstrip("/")

        print(f"Posting payload from {args.json_file} to {target}")
        post_json(target, payload)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
