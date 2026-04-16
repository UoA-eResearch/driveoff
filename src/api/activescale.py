"""S3/ActiveScale integration module for archival storage operations.

Provides functionality to initialize and interact with ActiveScale S3-compatible
storage, including session management, file upload/download, and bucket operations.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, cast

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, Request
from types_boto3_s3 import S3Client
from types_boto3_s3.type_defs import TagTypeDef

from config import get_settings

logger = logging.getLogger(__name__)


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
    return session


def init_activescale(app: FastAPI) -> None:
    """Initialize ActiveScale session during app startup and attach it to the FastAPI app state.

    The session is thread-safe and manages connection pooling efficiently.
    Clients created from this session can be safely used from multiple threads and in
    background tasks.
    """
    global _activescale_session  # pylint: disable=global-statement
    logger.info("Initializing ActiveScale session...")
    try:
        _activescale_session = _create_activescale_session()
        app.state.activescale_session = _activescale_session
    except ValueError:
        raise
    except Exception as e:
        logger.error("Failed to initialize ActiveScale: %s", str(e))
        raise ValueError("Failed to initialize ActiveScale session.") from e


def get_activescale_client(request: Request) -> S3Client:
    """FastAPI dependency to create an ActiveScale S3 client for a request.

    Clients created from the session are thread-safe and lightweight.
    Multiple concurrent requests can safely use separate clients.
    """
    session = getattr(request.app.state, "activescale_session", None)
    if session is None:
        logger.error("ActiveScale session not initialized on application state")
        raise RuntimeError("ActiveScale session not initialised on application state")

    client = session.client(
        "s3",
        endpoint_url=f"https://{get_settings().activescale_hostname}",
        config=_get_client_config(),
    )
    return client


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
        logger.error("ActiveScale session not initialized globally")
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


class ProgressTracker:
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
            logger.info(
                "Upload progress for '%s': %.1f%% (%d MB / %d MB)",
                self.file_key,
                percent,
                mb_transferred,
                mb_total,
            )
            self.last_update_time = current_time
            self.last_update_bytes = self.bytes_transferred
            self.stall_warned = False

        # Detect stalls: no progress for stall_timeout seconds
        if bytes_since_update == 0 and time_since_update >= self.stall_timeout:
            if not self.stall_warned:
                logger.warning(
                    "Upload stall detected for '%s': no progress for %d seconds. "
                    "Network may be experiencing issues.",
                    self.file_key,
                    self.stall_timeout,
                )
                self.stall_warned = True


def verify_connection(client: S3Client, bucket_name: str) -> bool:
    """Verify S3 client connectivity by attempting to access bucket"""

    # bucket_name = "research-archive-test"
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info(
            "ActiveScale connection successful. Bucket '%s' exists and is accessible.",
            bucket_name,
        )
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            logger.warning("Bucket '%s' does not exist.", bucket_name)
        elif error_code == "403":
            logger.warning(
                "Access denied for bucket '%s'. Check IAM permissions.",
                bucket_name,
            )
        else:
            logger.error(
                "ClientError accessing bucket: %s",
                e.response["Error"]["Message"],
            )
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
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
        logger.debug("Successfully listed %d buckets", len(buckets))
        return buckets
    except ClientError as e:
        logger.error(
            "ClientError while listing buckets: %s - %s",
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return []
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return []
    except Exception as e:
        logger.error(
            "Unexpected error while listing buckets: %s: %s",
            type(e).__name__,
            str(e),
        )
        return []


def upload_file(
    client: S3Client,
    bucket_name: str,
    file_key: str,
    file_path: str,
    metadata: dict[str, str] | None = None,
    tags: dict[str, str] | None = None,
    timeout: int = 300,
) -> bool:
    """Upload a file to an S3 bucket using streaming for large files.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        file_key (str): The key (path/filename) in the bucket.
        file_path (str | None): Path to file on disk (for large files, preferred).
        metadata (dict[str, str] | None): Optional metadata for the object.
        tags (dict[str, str] | None): Optional dictionary of tags.
        timeout (int): Timeout in seconds for the upload operation. Defaults to 300
            (5 minutes). Use higher values for very large files.

    Returns:
        bool: True if the upload is successful, False otherwise.

    Note:
        For large files, use file_path instead of file_content to avoid loading
        the entire file into memory. The upload_file method with file_path handles
        multipart uploads automatically for files larger than 8 MB.

        If the upload operation exceeds the timeout, it will be aborted and logged
        as an error. This prevents indefinite hangs due to poor network connectivity.

        Progress is logged every 5 seconds or every 100 MB. Stalls (no progress for
        30 seconds) are detected and logged as warnings.
    """
    if metadata is None:
        metadata = {}
    if tags is None:
        tags = {}

    try:
        tag_string = "&".join(f"{key}={value}" for key, value in tags.items())

        # Get file size for progress tracking
        file_size = Path(file_path).stat().st_size

        logger.info(
            "Uploading file from disk '%s' to '%s' in bucket '%s' using streaming "
            "(size: %d MB, timeout: %d seconds)",
            file_path,
            file_key,
            bucket_name,
            file_size / (1024 * 1024),
            timeout,
        )

        # Create progress tracker with stall detection
        progress_tracker = ProgressTracker(file_key, file_size, stall_timeout=30)

        # Use a threading-based timeout to prevent indefinite hangs
        upload_result: list[bool | None] = [None]
        upload_exception: list[Exception | None] = [None]

        def perform_upload() -> None:
            try:
                client.upload_file(
                    file_path,
                    bucket_name,
                    file_key,
                    ExtraArgs={
                        "Metadata": metadata,
                        "Tagging": tag_string,
                    },
                    Callback=progress_tracker,
                )
                upload_result[0] = True
            except Exception as e:  # pylint: disable=broad-except
                upload_exception[0] = e

        upload_thread = threading.Thread(target=perform_upload, daemon=False)
        upload_thread.start()
        upload_thread.join(timeout=timeout)

        if upload_thread.is_alive():
            logger.error(
                "Upload operation for '%s' timed out after %d seconds. "
                "The network may be experiencing issues. Transferred %d MB of %d MB.",
                file_key,
                timeout,
                progress_tracker.bytes_transferred / (1024 * 1024),
                file_size / (1024 * 1024),
            )
            return False

        if upload_exception[0] is not None:
            raise upload_exception[0]

        if upload_result[0]:
            logger.info(
                "Successfully uploaded '%s' to bucket '%s'", file_key, bucket_name
            )
            return True

        return False

    except ClientError as e:
        logger.error(
            "ClientError uploading '%s': %s - %s",
            file_key,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return False
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error uploading '%s': %s: %s",
            file_key,
            type(e).__name__,
            str(e),
        )
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
        file_content = response["Body"].read()
        logger.info(
            "Successfully downloaded '%s' from bucket '%s'", file_key, bucket_name
        )
        return file_content
    except ClientError as e:
        logger.error(
            "ClientError downloading '%s': %s - %s",
            file_key,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return None
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return None
    except Exception as e:
        logger.error(
            "Unexpected error downloading '%s': %s: %s",
            file_key,
            type(e).__name__,
            str(e),
        )
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
        logger.info(
            "Object '%s' exists in bucket '%s': %d bytes, last modified %s",
            file_key,
            bucket_name,
            metadata.get("content_length", 0),
            metadata.get("last_modified"),
        )
        return True, metadata
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            logger.info(
                "Object '%s' does not exist in bucket '%s'", file_key, bucket_name
            )
            return False, None
        logger.error(
            "ClientError checking if object '%s' exists: %s - %s",
            file_key,
            error_code,
            e.response["Error"]["Message"],
        )
        return False, None
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return False, None
    except Exception as e:
        logger.error(
            "Unexpected error checking object '%s': %s: %s",
            file_key,
            type(e).__name__,
            str(e),
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
        logger.info(
            "Successfully created bucket '%s' with object lock %s",
            bucket_name,
            lock_status,
        )
        return True
    except ClientError as e:
        logger.error(
            "ClientError creating bucket '%s': %s - %s",
            bucket_name,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return False
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error creating bucket '%s': %s: %s",
            bucket_name,
            type(e).__name__,
            str(e),
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
        logger.info("Successfully set bucket policy for '%s'", bucket_name)
        return True
    except ClientError as e:
        logger.error(
            "ClientError setting policy for '%s': %s - %s",
            bucket_name,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return False
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error setting policy for '%s': %s: %s",
            bucket_name,
            type(e).__name__,
            str(e),
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
        logger.info("Successfully set %d tags for bucket '%s'", len(tags), bucket_name)
        return True
    except ClientError as e:
        logger.error(
            "ClientError setting tags for '%s': %s - %s",
            bucket_name,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return False
    except EndpointConnectionError:
        logger.error(
            "Could not connect to the S3 endpoint. Check network connectivity."
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error setting tags for '%s': %s: %s",
            bucket_name,
            type(e).__name__,
            str(e),
        )
        return False
