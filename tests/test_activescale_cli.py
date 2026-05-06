"""Tests for the ActiveScale CLI."""

from __future__ import annotations

from contextlib import contextmanager

from cli.activescale import main


@contextmanager
def fake_client_context():
    """Yield a sentinel client object for CLI tests."""
    yield object()


def test_list_buckets_outputs_bucket_names(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "cli.activescale.get_activescale_client_context", fake_client_context
    )
    monkeypatch.setattr(
        "cli.activescale.list_buckets",
        lambda client: ["archive-a", "archive-b"],
    )

    exit_code = main(["list-buckets"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.splitlines() == ["archive-a", "archive-b"]


def test_list_objects_supports_json_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "cli.activescale.get_activescale_client_context", fake_client_context
    )
    monkeypatch.setattr(
        "cli.activescale.list_bucket_objects",
        lambda client, bucket, prefix="": [f"{prefix}crate.zip"],
    )

    exit_code = main(
        ["--json", "list-objects", "research-archive", "--prefix", "ro-crates/"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"bucket": "research-archive"' in captured.out
    assert '"objects": [' in captured.out
    assert '"ro-crates/crate.zip"' in captured.out


def test_object_exists_returns_non_zero_for_missing_object(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "cli.activescale.get_activescale_client_context", fake_client_context
    )
    monkeypatch.setattr(
        "cli.activescale.object_exists",
        lambda client, bucket, key: (False, None),
    )

    exit_code = main(["object-exists", "research-archive", "missing.zip"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out.strip() == "NOT FOUND"
