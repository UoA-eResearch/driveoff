"""S3/ActiveScale integration module for archival storage operations.

Provides functionality to initialize and interact with ActiveScale S3-compatible
storage, including session management, file upload/download, and bucket operations.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError
from fastapi import FastAPI, Request
from types_boto3_s3 import S3Client
from types_boto3_s3.type_defs import TagTypeDef

from config import get_settings

logger = logging.getLogger(__name__)


def _redact_secret(value: str | None) -> str | None:
    """Return a non-sensitive representation of a secret-like value."""
    if value is None:
        return None
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _log_event(level: int, event: str, **context: Any) -> None:
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, default=str))


def _extract_client_error(error: ClientError) -> tuple[str, str]:
    """Extract normalized code/message fields from botocore ClientError."""
    error_payload = error.response.get("Error", {})
    error_code = str(error_payload.get("Code", "Unknown"))
    error_message = str(error_payload.get("Message", "Unknown client error"))
    return error_code, error_message


def _log_client_error(event: str, error: ClientError, **context: Any) -> None:
    """Log a structured ClientError event with common fields."""
    error_code, error_message = _extract_client_error(error)
    _log_event(
        logging.ERROR,
        event,
        error_code=error_code,
        error_message=error_message,
        **context,
    )


def _log_endpoint_connection_error(**context: Any) -> None:
    """Log a structured endpoint connectivity failure."""
    _log_event(logging.ERROR, "s3.endpoint.connection_error", **context)


def _log_unexpected_error(event: str, error: Exception, **context: Any) -> None:
    """Log a structured unexpected exception event."""
    _log_event(
        logging.ERROR,
        event,
        error_type=type(error).__name__,
        error=str(error),
        **context,
    )


def _get_client_config() -> Config:
    """Build botocore client config from runtime settings."""
    settings = get_settings()
    retry_attempts = max(settings.activescale_retry_attempts, 1)
    connect_timeout = max(settings.activescale_connect_timeout, 1)
    read_timeout = max(settings.activescale_read_timeout, 1)

    return Config(
        retries={"total_max_attempts": retry_attempts, "mode": "standard"},
        signature_version="s3v4",
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_pool_connections=10,
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        s3={
            "addressing_style": "path",
            "payload_signing_enabled": False,
        },
        # Explicitly bypass any system proxy env vars (HTTP_PROXY / HTTPS_PROXY).
        # ActiveScale is accessed directly and must not be tunnelled through the proxy.
        proxies={},
    )


# THREAD SAFETY NOTES:
# - Boto3 S3 clients are thread-safe for concurrent requests (urllib3 connection
#   pooling is thread-safe)
# - We use boto3.Session to manage connection pools efficiently
# - Clients created from a session are lightweight and reusable
# - This pattern works for both sync request handlers and async background tasks

# NOTE: Currently handles ActiveScale and S3-compatible services. Future work:
# - Make this more generic and reusable for other S3-compatible services
# - Implement ability to create different sessions/clients with specific credentials
# - Standardize S3 error handling across the codebase


_activescale_session: boto3.Session | None = None


def _create_activescale_session() -> boto3.Session:
    """Create a boto3 Session with ActiveScale credentials from environment settings."""
    settings = get_settings()

    hostname = settings.activescale_hostname
    region = settings.activescale_region
    access_key = (
        settings.activescale_access_key.get_secret_value()
        if settings.activescale_access_key
        else None
    )
    secret_key = (
        settings.activescale_secret_key.get_secret_value()
        if settings.activescale_secret_key
        else None
    )
    if not all([hostname, access_key, secret_key]):
        raise ValueError(
            "ActiveScale credentials are not fully set in environment variables."
        )

    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    _log_event(
        logging.INFO,
        "activescale.credentials.loaded",
        endpoint=hostname,
        region=region,
        access_key_preview=_redact_secret(access_key),
        secret_key_set=bool(secret_key),
    )
    return session


def init_activescale(app: FastAPI) -> None:
    """Initialize ActiveScale session during app startup and attach it to the FastAPI app state.

    The session is thread-safe and manages connection pooling efficiently.
    Clients created from this session can be safely used from multiple threads and in
    background tasks.
    """
    global _activescale_session  # pylint: disable=global-statement
    _log_event(logging.INFO, "activescale.session.init_start")
    try:
        _activescale_session = _create_activescale_session()
        app.state.activescale_session = _activescale_session
    except ValueError:
        raise
    except Exception as e:
        _log_event(logging.ERROR, "activescale.session.init_failed", error=str(e))
        raise ValueError("Failed to initialize ActiveScale session.") from e


def get_activescale_client(request: Request) -> S3Client:
    """FastAPI dependency to create an ActiveScale S3 client for a request.

    Clients created from the session are thread-safe and lightweight.
    Multiple concurrent requests can safely use separate clients.
    """
    session = getattr(request.app.state, "activescale_session", None)
    if session is None:
        _log_event(logging.ERROR, "activescale.session.missing_on_app_state")
        raise RuntimeError("ActiveScale session not initialised on application state")

    client = session.client(
        "s3",
        endpoint_url=f"https://{get_settings().activescale_hostname}",
        config=_get_client_config(),
    )
    return cast(S3Client, client)


@contextmanager
def get_activescale_client_context() -> Generator[S3Client, None, None]:
    """Context manager for creating a temporary ActiveScale S3 client.

    Use this in background tasks or other contexts where you don't have access to the
    FastAPI request object.

    Example:
        with get_activescale_client_context() as client:
            upload_file(client, bucket, key, content)
    """
    if _activescale_session is None:
        _log_event(logging.ERROR, "activescale.session.missing_global")
        raise RuntimeError(
            "ActiveScale session not initialized. Call init_activescale first."
        )

    client: S3Client = cast(
        S3Client,
        _activescale_session.client(
            "s3",
            endpoint_url=f"https://{get_settings().activescale_hostname}",
            config=_get_client_config(),
        ),
    )
    try:
        yield client
    finally:
        # Clients are lightweight and don't hold significant resources
        # but closing explicitly is good practice
        client.close()


# S3 interactions - generic for any S3-compatible service. Pass in initialised client.


class ProgressTracker:  # pylint: disable=too-few-public-methods
    """Tracks upload progress and logs periodic updates with stall detection."""

    def __init__(self, file_key: str, file_size: int, stall_timeout: int = 30):
        """Initialize progress tracker.

        Args:
            file_key (str): S3 object key for logging
            file_size (int): Total file size in bytes
            stall_timeout (int): Log warning if no progress for this many seconds
        """
        self.file_key = file_key
        self.file_size = file_size
        self.bytes_transferred = 0
        self.last_update_time = time.time()
        self.last_update_bytes = 0
        self.stall_timeout = stall_timeout
        self.stall_warned = False

    def __call__(self, chunk_bytes: int) -> None:
        """Called by boto3 for each uploaded chunk.

        Args:
            chunk_bytes (int): Number of bytes transferred in this chunk
        """
        self.bytes_transferred += chunk_bytes
        current_time = time.time()
        time_since_update = current_time - self.last_update_time

        # Log progress every 5 seconds or every 100MB
        bytes_since_update = self.bytes_transferred - self.last_update_bytes
        if time_since_update >= 5 or bytes_since_update >= 100 * 1024 * 1024:
            percent = (
                (self.bytes_transferred / self.file_size * 100) if self.file_size else 0
            )
            mb_transferred = self.bytes_transferred / (1024 * 1024)
            mb_total = self.file_size / (1024 * 1024)
            _log_event(
                logging.INFO,
                "s3.upload.progress",
                file_key=self.file_key,
                percent=round(percent, 1),
                mb_transferred=round(mb_transferred, 1),
                mb_total=round(mb_total, 1),
            )
            self.last_update_time = current_time
            self.last_update_bytes = self.bytes_transferred
            self.stall_warned = False

        # Detect stalls: no progress for stall_timeout seconds
        if bytes_since_update == 0 and time_since_update >= self.stall_timeout:
            if not self.stall_warned:
                _log_event(
                    logging.WARNING,
                    "s3.upload.stall_detected",
                    file_key=self.file_key,
                    stall_timeout_seconds=self.stall_timeout,
                )
                self.stall_warned = True


def verify_connection(client: S3Client, bucket_name: str) -> bool:
    """Verify S3 client connectivity by attempting to access bucket"""

    # bucket_name = "research-archive-test"
    try:
        client.head_bucket(Bucket=bucket_name)
        _log_event(
            logging.INFO,
            "s3.connection.verified",
            bucket_name=bucket_name,
        )
        return True
    except ClientError as e:
        error_code, _ = _extract_client_error(e)
        if error_code == "404":
            _log_event(
                logging.WARNING,
                "s3.bucket.not_found",
                bucket_name=bucket_name,
            )
        elif error_code == "403":
            _log_event(
                logging.WARNING,
                "s3.bucket.access_denied",
                bucket_name=bucket_name,
            )
        else:
            _log_client_error(
                "s3.bucket.head.client_error",
                e,
                bucket_name=bucket_name,
            )
    except EndpointConnectionError:
        _log_endpoint_connection_error()
    return False


def list_buckets(client: S3Client) -> list[str]:
    """List buckets in an S3 account using the provided client.

    Returns:
        list[str]: List of bucket names, or empty list if operation fails.
    """
    try:
        response = client.list_buckets()
        buckets = [
            bucket["Name"] for bucket in response.get("Buckets", []) if "Name" in bucket
        ]
        _log_event(logging.DEBUG, "s3.buckets.listed", bucket_count=len(buckets))
        return buckets
    except ClientError as e:
        _log_client_error("s3.buckets.list.client_error", e)
        return []
    except EndpointConnectionError:
        _log_endpoint_connection_error()
        return []
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error("s3.buckets.list.unexpected_error", e)
        return []


# pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-locals
def upload_file(
    client: S3Client,
    bucket_name: str,
    file_key: str,
    file_path: str,
    metadata: dict[str, str] | None = None,
    tags: dict[str, str] | None = None,
    timeout: int = 300,
) -> bool:
    """Upload a file to an S3 bucket using a simple put_object call.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        file_key (str): The key (path/filename) in the bucket.
        file_path (str | None): Path to file on disk.
        metadata (dict[str, str] | None): Optional metadata (currently unused for ActiveScale compatibility).
        tags (dict[str, str] | None): Optional tags (currently unused for ActiveScale compatibility).
        timeout (int): Timeout in seconds for the upload operation. Defaults to 300 (5 minutes).

    Returns:
        bool: True if the upload is successful, False otherwise.

    Note:
        Uses put_object with a file stream to avoid multipart complexity and
        unsupported headers that trigger ActiveScale "NotImplemented" errors.
        The file is streamed from disk, not loaded into memory.

        If the upload operation exceeds the timeout, it will be aborted and logged
        as an error. This prevents indefinite hangs due to poor network connectivity.
    """
    try:
        # Get file size for logging
        file_size = Path(file_path).stat().st_size

        _log_event(
            logging.INFO,
            "s3.upload.start",
            file_path=file_path,
            file_key=file_key,
            bucket_name=bucket_name,
            size_mb=round(file_size / (1024 * 1024), 1),
            timeout_seconds=timeout,
        )

        # Use a threading-based timeout to prevent indefinite hangs
        upload_result: list[bool | None] = [None]
        upload_exception: list[Exception | None] = [None]

        def perform_upload() -> None:
            try:
                # Use put_object with file body instead of upload_file to avoid
                # multipart complexity and unsupported headers that trigger
                # ActiveScale "NotImplemented" errors.
                # For very large files this streams from disk, not memory.
                with open(file_path, "rb") as f:
                    client.put_object(
                        Bucket=bucket_name,
                        Key=file_key,
                        Body=f,
                        ContentLength=file_size,
                    )
                upload_result[0] = True
            except (ClientError, EndpointConnectionError, BotoCoreError, OSError) as e:
                upload_exception[0] = e

        upload_thread = threading.Thread(target=perform_upload, daemon=False)
        upload_thread.start()
        upload_thread.join(timeout=timeout)

        if upload_thread.is_alive():
            _log_event(
                logging.ERROR,
                "s3.upload.timeout",
                file_key=file_key,
                timeout_seconds=timeout,
                total_mb=round(file_size / (1024 * 1024), 1),
            )
            return False

        upload_error = upload_exception[0]
        if upload_error is not None:
            raise upload_error

        if upload_result[0]:
            _log_event(
                logging.INFO,
                "s3.upload.completed",
                file_key=file_key,
                bucket_name=bucket_name,
            )
            return True

        return False

    except ClientError as e:
        _log_client_error("s3.upload.client_error", e, file_key=file_key)
        return False
    except EndpointConnectionError:
        _log_endpoint_connection_error(file_key=file_key)
        return False
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error("s3.upload.unexpected_error", e, file_key=file_key)
        return False


def download_file(client: S3Client, bucket_name: str, file_key: str) -> bytes | None:
    """Download a file from an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to download from.
        file_key (str): The key (path/filename) of the file to download.

    Returns:
        bytes | None: The downloaded file content or None if unsuccessful.
    """
    try:
        response = client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = cast(bytes, response["Body"].read())
        _log_event(
            logging.INFO,
            "s3.download.completed",
            file_key=file_key,
            bucket_name=bucket_name,
        )
        return file_content
    except ClientError as e:
        _log_client_error("s3.download.client_error", e, file_key=file_key)
        return None
    except EndpointConnectionError:
        _log_endpoint_connection_error(file_key=file_key)
        return None
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error("s3.download.unexpected_error", e, file_key=file_key)
        return None


def object_exists(
    client: S3Client, bucket_name: str, file_key: str
) -> tuple[bool, dict[str, Any] | None]:
    """Check if an object exists in an S3 bucket and return its metadata if it does.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The key (path/filename) of the object to check.

    Returns:
        tuple[bool, dict | None]: (True, metadata_dict) if object exists, (False, None) otherwise.
            Metadata includes: ContentLength, LastModified, ETag, Metadata (custom metadata dict).
    """
    try:
        response = client.head_object(Bucket=bucket_name, Key=file_key)
        metadata = {
            "content_length": response.get("ContentLength"),
            "last_modified": response.get("LastModified"),
            "etag": response.get("ETag"),
            "custom_metadata": response.get("Metadata", {}),
        }
        _log_event(
            logging.INFO,
            "s3.object.exists",
            file_key=file_key,
            bucket_name=bucket_name,
            content_length=metadata.get("content_length", 0),
            last_modified=metadata.get("last_modified"),
        )
        return True, metadata
    except ClientError as e:
        error_code, _ = _extract_client_error(e)
        if error_code == "404":
            _log_event(
                logging.INFO,
                "s3.object.not_found",
                file_key=file_key,
                bucket_name=bucket_name,
            )
            return False, None
        _log_client_error(
            "s3.object.exists.client_error",
            e,
            file_key=file_key,
            bucket_name=bucket_name,
        )
        return False, None
    except EndpointConnectionError:
        _log_endpoint_connection_error(file_key=file_key, bucket_name=bucket_name)
        return False, None
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error(
            "s3.object.exists.unexpected_error",
            e,
            file_key=file_key,
            bucket_name=bucket_name,
        )
        return False, None


def create_bucket(
    client: S3Client,
    bucket_name: str,
    tags: list[TagTypeDef] | None = None,
    enable_object_lock: bool = True,
) -> bool:
    """Create a new S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to create.
        tags (list[TagTypeDef] | None): List of tag dictionaries with Key/Value.
        enable_object_lock (bool): Whether to enable object lock.

    Returns:
        bool: True if successful, False otherwise.
    """
    if tags is None:
        tags = []
    try:
        client.create_bucket(
            Bucket=bucket_name,
            ObjectLockEnabledForBucket=enable_object_lock,
            CreateBucketConfiguration={"Tags": tags},
        )
        lock_status = "enabled" if enable_object_lock else "disabled"
        _log_event(
            logging.INFO,
            "s3.bucket.created",
            bucket_name=bucket_name,
            object_lock=lock_status,
        )
        return True
    except ClientError as e:
        _log_client_error("s3.bucket.create.client_error", e, bucket_name=bucket_name)
        return False
    except EndpointConnectionError:
        _log_endpoint_connection_error(bucket_name=bucket_name)
        return False
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error(
            "s3.bucket.create.unexpected_error", e, bucket_name=bucket_name
        )
        return False


def set_bucket_policy(client: S3Client, bucket_name: str, policy_json: str) -> bool:
    """Set the bucket policy for an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket.
        policy_json (str): The bucket policy in JSON format.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        client.put_bucket_policy(Bucket=bucket_name, Policy=policy_json)
        _log_event(logging.INFO, "s3.bucket.policy_set", bucket_name=bucket_name)
        return True
    except ClientError as e:
        _log_client_error(
            "s3.bucket.policy_set.client_error",
            e,
            bucket_name=bucket_name,
        )
        return False
    except EndpointConnectionError:
        _log_endpoint_connection_error(bucket_name=bucket_name)
        return False
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error(
            "s3.bucket.policy_set.unexpected_error",
            e,
            bucket_name=bucket_name,
        )
        return False


def set_bucket_tags(
    client: S3Client, bucket_name: str, tags: list[TagTypeDef] | None = None
) -> bool:
    """Set tags for an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket.
        tags (list[TagTypeDef] | None): List of tag dictionaries with Key/Value.

    Returns:
        bool: True if successful, False otherwise.
    """
    if tags is None:
        tags = []
    try:
        client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={"TagSet": tags},
        )
        _log_event(
            logging.INFO,
            "s3.bucket.tags_set",
            bucket_name=bucket_name,
            tag_count=len(tags),
        )
        return True
    except ClientError as e:
        _log_client_error("s3.bucket.tags_set.client_error", e, bucket_name=bucket_name)
        return False
    except EndpointConnectionError:
        _log_endpoint_connection_error(bucket_name=bucket_name)
        return False
    except (BotoCoreError, OSError, ValueError, TypeError) as e:
        _log_unexpected_error(
            "s3.bucket.tags_set.unexpected_error", e, bucket_name=bucket_name
        )
        return False
