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


def test_download_object_writes_file(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(
        "cli.activescale.get_activescale_client_context", fake_client_context
    )
    monkeypatch.setattr(
        "cli.activescale.download_file",
        lambda client, bucket, key: b"crate-bytes",
    )

    output_path = tmp_path / "downloads" / "archive.zip"
    exit_code = main(
        [
            "download-object",
            "research-archive",
            "ro-crates/archive.zip",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_path.read_bytes() == b"crate-bytes"
    assert "'downloaded': True" in captured.out
    assert "'bytes': 11" in captured.out


def test_download_object_returns_non_zero_when_missing(
    monkeypatch, capsys, tmp_path
) -> None:
    monkeypatch.setattr(
        "cli.activescale.get_activescale_client_context", fake_client_context
    )
    monkeypatch.setattr(
        "cli.activescale.download_file",
        lambda client, bucket, key: None,
    )

    output_path = tmp_path / "downloads" / "missing.zip"
    exit_code = main(
        [
            "download-object",
            "research-archive",
            "ro-crates/missing.zip",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert not output_path.exists()
    assert "downloaded" in captured.out
