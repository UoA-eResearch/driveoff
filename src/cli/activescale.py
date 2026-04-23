"""Simple command-line interface for ActiveScale inspection tasks."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from api.activescale import (
    download_file,
    get_activescale_client_context,
    list_bucket_objects,
    list_buckets,
    object_exists,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the ActiveScale CLI."""
    parser = argparse.ArgumentParser(
        prog="activescale-cli",
        description="Run simple inspection commands against ActiveScale.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit structured JSON output instead of plain text.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-buckets", help="List buckets visible to this account.")

    list_objects_parser = subparsers.add_parser(
        "list-objects",
        help="List object keys in a bucket.",
    )
    list_objects_parser.add_argument("bucket", help="Bucket name to inspect.")
    list_objects_parser.add_argument(
        "--prefix",
        default="",
        help="Optional key prefix filter.",
    )

    object_exists_parser = subparsers.add_parser(
        "object-exists",
        help="Check whether an object exists and print its metadata when found.",
    )
    object_exists_parser.add_argument("bucket", help="Bucket name to inspect.")
    object_exists_parser.add_argument("key", help="Object key to look up.")

    download_object_parser = subparsers.add_parser(
        "download-object",
        help="Download an object to a local file path.",
    )
    download_object_parser.add_argument("bucket", help="Bucket name to inspect.")
    download_object_parser.add_argument("key", help="Object key to download.")
    download_object_parser.add_argument("output", help="Output file path.")

    return parser


def _print_output(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return

    if isinstance(payload, list):
        if not payload:
            print("No results.")
            return
        for item in payload:
            print(item)
        return

    if isinstance(payload, dict):
        exists = payload.get("exists")
        if exists is not None:
            print("FOUND" if exists else "NOT FOUND")
            metadata = payload.get("metadata") or {}
            for key, value in metadata.items():
                print(f"{key}: {value}")
            return

    print(payload)


def run_command(args: argparse.Namespace) -> int:
    """Execute a parsed CLI command."""
    with get_activescale_client_context() as client:
        if args.command == "list-buckets":
            buckets = list_buckets(client)
            payload = {"buckets": buckets} if args.as_json else buckets
            _print_output(payload, args.as_json)
            return 0

        if args.command == "list-objects":
            object_keys = list_bucket_objects(client, args.bucket, prefix=args.prefix)
            payload = (
                {
                    "bucket": args.bucket,
                    "prefix": args.prefix,
                    "objects": object_keys,
                }
                if args.as_json
                else object_keys
            )
            _print_output(payload, args.as_json)
            return 0

        if args.command == "object-exists":
            exists, metadata = object_exists(client, args.bucket, args.key)
            payload = {
                "bucket": args.bucket,
                "key": args.key,
                "exists": exists,
                "metadata": metadata,
            }
            _print_output(payload, args.as_json)
            return 0 if exists else 1

        if args.command == "download-object":
            file_content = download_file(client, args.bucket, args.key)
            if file_content is None:
                payload = {
                    "bucket": args.bucket,
                    "key": args.key,
                    "downloaded": False,
                }
                _print_output(payload, args.as_json)
                return 1

            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(file_content)

            payload = {
                "bucket": args.bucket,
                "key": args.key,
                "downloaded": True,
                "output": str(output_path),
                "bytes": len(file_content),
            }
            _print_output(payload, args.as_json)
            return 0

    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        return run_command(args)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
