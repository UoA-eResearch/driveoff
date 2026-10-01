"""Unit tests for activescale S3 integration helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from service.activescale import set_object_retention, upload_file, verify_uploaded_part_size


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, "HeadObject")


class TestUploadFile:
    """upload_file is a thin, honest wrapper: it calls boto3's upload_file
    directly (no wall-clock timeout thread) and maps errors to False."""

    def _make_source_file(self, tmp_path: Path) -> Path:
        source = tmp_path / "part-00001"
        source.write_bytes(b"payload")
        return source

    def test_returns_true_and_passes_metadata(self, tmp_path: Path) -> None:
        client = MagicMock()
        source = self._make_source_file(tmp_path)

        result = upload_file(client, "bucket", "drive/part-00001", str(source), metadata={"division": "CTRERSH"})

        assert result is True
        _args, kwargs = client.upload_file.call_args
        assert client.upload_file.call_args.args == (str(source), "bucket", "drive/part-00001")
        assert kwargs["ExtraArgs"] == {"Metadata": {"division": "CTRERSH"}}
        assert kwargs["Callback"] is not None

    def test_no_metadata_omits_extra_args(self, tmp_path: Path) -> None:
        client = MagicMock()
        source = self._make_source_file(tmp_path)

        assert upload_file(client, "bucket", "drive/part-00001", str(source)) is True
        assert client.upload_file.call_args.kwargs["ExtraArgs"] is None

    def test_returns_false_on_client_error(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.upload_file.side_effect = _make_client_error("500")

        assert upload_file(client, "bucket", "drive/part-00001", str(self._make_source_file(tmp_path))) is False

    def test_returns_false_on_endpoint_connection_error(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.upload_file.side_effect = EndpointConnectionError(endpoint_url="https://example.invalid")

        assert upload_file(client, "bucket", "drive/part-00001", str(self._make_source_file(tmp_path))) is False

    def test_returns_false_when_local_file_missing(self, tmp_path: Path) -> None:
        client = MagicMock()

        assert upload_file(client, "bucket", "drive/part-00001", str(tmp_path / "missing")) is False
        client.upload_file.assert_not_called()


class TestVerifyUploadedPartSize:
    def test_returns_true_when_sizes_match(self) -> None:
        client = MagicMock()
        client.head_object.return_value = {"ContentLength": 512}

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is True
        client.head_object.assert_called_once_with(Bucket="bucket", Key="key/part-00001")

    def test_returns_false_when_sizes_differ(self) -> None:
        client = MagicMock()
        client.head_object.return_value = {"ContentLength": 100}

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_returns_false_when_content_length_absent(self) -> None:
        # head_object response missing ContentLength — treated as -1 != expected
        client = MagicMock()
        client.head_object.return_value = {}

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_returns_false_on_client_error(self) -> None:
        client = MagicMock()
        client.head_object.side_effect = _make_client_error("403")

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_returns_false_on_404(self) -> None:
        client = MagicMock()
        client.head_object.side_effect = _make_client_error("404")

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_returns_false_on_endpoint_connection_error(self) -> None:
        client = MagicMock()
        client.head_object.side_effect = EndpointConnectionError(endpoint_url="https://example.com")

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_returns_false_on_botocore_error(self) -> None:
        client = MagicMock()
        client.head_object.side_effect = BotoCoreError()

        assert verify_uploaded_part_size(client, "bucket", "key/part-00001", 512) is False

    def test_zero_byte_object(self) -> None:
        client = MagicMock()
        client.head_object.return_value = {"ContentLength": 0}

        assert verify_uploaded_part_size(client, "bucket", "key/empty", 0) is True


class TestSetObjectRetention:
    _RETAIN_UNTIL = datetime(2032, 1, 1, tzinfo=UTC)

    def _make_client_error(self, code: str) -> ClientError:
        return ClientError({"Error": {"Code": code, "Message": "test error"}}, "PutObjectRetention")

    def test_returns_true_on_success(self) -> None:
        client = MagicMock()
        client.put_object_retention.return_value = {}

        assert set_object_retention(client, "bucket", "key/part-00001", self._RETAIN_UNTIL) is True
        client.put_object_retention.assert_called_once_with(
            Bucket="bucket",
            Key="key/part-00001",
            Retention={"Mode": "COMPLIANCE", "RetainUntilDate": self._RETAIN_UNTIL},
        )

    def test_naive_datetime_is_made_utc(self) -> None:
        client = MagicMock()
        client.put_object_retention.return_value = {}
        naive = datetime(2032, 1, 1)  # no tzinfo

        assert set_object_retention(client, "bucket", "key/part-00001", naive) is True
        _, kwargs = client.put_object_retention.call_args
        called_date = kwargs["Retention"]["RetainUntilDate"]
        assert called_date.tzinfo is not None

    def test_returns_false_on_client_error(self) -> None:
        client = MagicMock()
        client.put_object_retention.side_effect = self._make_client_error("AccessDenied")

        assert set_object_retention(client, "bucket", "key/part-00001", self._RETAIN_UNTIL) is False

    def test_returns_false_when_object_lock_not_enabled(self) -> None:
        client = MagicMock()
        client.put_object_retention.side_effect = self._make_client_error("InvalidRequest")

        assert set_object_retention(client, "bucket", "key/part-00001", self._RETAIN_UNTIL) is False

    def test_returns_false_on_endpoint_connection_error(self) -> None:
        client = MagicMock()
        client.put_object_retention.side_effect = EndpointConnectionError(endpoint_url="https://example.com")

        assert set_object_retention(client, "bucket", "key/part-00001", self._RETAIN_UNTIL) is False

    def test_returns_false_on_botocore_error(self) -> None:
        client = MagicMock()
        client.put_object_retention.side_effect = BotoCoreError()

        assert set_object_retention(client, "bucket", "key/part-00001", self._RETAIN_UNTIL) is False
