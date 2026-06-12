"""Unit tests for activescale S3 integration helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from service.activescale import verify_uploaded_part_size


def _make_client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "test error"}}, "HeadObject"
    )


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
