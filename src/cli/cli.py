#!/usr/bin/env python3
"""Simple CLI to create RO-Crates via the running API.

Usage examples are in the package README. This is intentionally small and
dependency-free (uses stdlib) so it can be run without installing extra
packages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def load_json(path: str) -> Any:
    """Load JSON data from a file."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def post_json(url: str, payload: Any, api_key: str | None = None) -> None:
    """POST JSON data to a URL, optionally with an API key."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
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
        except UnicodeDecodeError:
            print("Error decoding response body.")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        sys.exit(1)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="driveoff-cli", description="Driveoff CLI: create RO crates via API"
    )
    sub = parser.add_subparsers(dest="command")

    def add_common_args(p: argparse.ArgumentParser) -> None:
        """Add common arguments for the subcommands."""
        p.add_argument("json_file", help="Path to JSON file with payload to send")
        p.add_argument(
            "--api-url",
            default="http://localhost:8000",
            help="Base API URL (default: http://localhost:8000)",
        )
        p.add_argument(
            "--api-key",
            default=None,
            help="API key to send as Authorization Bearer token (or set DRIVEOFF_API_KEY)",
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Print payload and exit without sending",
        )
        p.add_argument(
            "--pretty", action="store_true", help="Pretty-print payload on dry-run"
        )

    create = sub.add_parser(
        "create-crate", help="Create an RO-Crate by POSTing JSON to the API"
    )
    add_common_args(create)

    post = sub.add_parser(
        "post-resdriveinfo",
        help="""
            POST research drive/project info to /resdriveinfo endpoint.
            You will want to do this before create-crate to send the initial
            metadata to the API.
        """,
    )
    add_common_args(post)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # prefer explicit arg, otherwise read from env var
    env_api_key = os.environ.get("DRIVEOFF_API_KEY")

    if args.command == "create-crate":
        payload = load_json(args.json_file)
        if args.dry_run:
            if args.pretty:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(payload, ensure_ascii=False))
            return

        # fixed endpoint for create-crate
        endpoint = "/api/v1/submission"
        target = args.api_url.rstrip("/") + endpoint

        print(f"Posting payload from {args.json_file} to {target}")
        post_json(target, payload, args.api_key or env_api_key)
    elif args.command == "post-resdriveinfo":
        payload = load_json(args.json_file)
        if args.dry_run:
            if args.pretty:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(payload, ensure_ascii=False))
            return

        # fixed endpoint for post-resdriveinfo
        endpoint = "/api/v1/resdriveinfo"
        target = args.api_url.rstrip("/") + endpoint

        print(f"Posting payload from {args.json_file} to {target}")
        post_json(target, payload, args.api_key or env_api_key)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
