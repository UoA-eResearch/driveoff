"""S3/ActiveScale integration module for archival storage operations.

Provides functionality to initialize and interact with ActiveScale S3-compatible
storage, including session management, file upload/download, and bucket operations.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, cast

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, Request
from types_boto3_s3 import S3Client
from types_boto3_s3.type_defs import TagTypeDef

from config import get_settings

logger = logging.getLogger(__name__)

config = Config(
    retries={"total_max_attempts": 3, "mode": "standard"}, signature_version="s3v4"
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

        # Verify connectivity by attempting to access the bucket
        bucket_name = "research-archive-test"
        client = _activescale_session.client(
            "s3",
            endpoint_url=f"https://{get_settings().activescale_hostname}",
            config=config,
        )
        try:
            client.head_bucket(Bucket=bucket_name)
            logger.info(
                "ActiveScale connection successful. Bucket '%s' exists and is accessible.",
                bucket_name,
            )
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
            raise

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
        config=config,
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
            config=config,
        ),
    )
    try:
        yield client
    finally:
        # Clients are lightweight and don't hold significant resources
        # but closing explicitly is good practice
        client.close()


# S3 interactions - generic for any S3-compatible service. Pass in initialised client.


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
    except OSError as e:
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
    file_content: bytes,
    metadata: dict[str, str] | None = None,
    tags: dict[str, str] | None = None,
) -> bool:
    """Upload a file to an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        file_key (str): The key (path/filename) in the bucket.
        file_content (bytes): The content of the file to upload.
        metadata (dict[str, str] | None): Optional metadata for the object.
        tags (dict[str, str] | None): Optional dictionary of tags to apply to the uploaded object.

    Returns:
        bool: True if the upload is successful, False otherwise.
    """
    if metadata is None:
        metadata = {}
    if tags is None:
        tags = {}
    try:
        tag_string = "&".join(f"{key}={value}" for key, value in tags.items())
        client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=file_content,
            Metadata=metadata,
            Tagging=tag_string,
        )
        logger.info("Successfully uploaded '%s' to bucket '%s'", file_key, bucket_name)
        return True
    except ClientError as e:
        logger.error(
            "ClientError uploading '%s': %s - %s",
            file_key,
            e.response["Error"]["Code"],
            e.response["Error"]["Message"],
        )
        return False
    except OSError as e:
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
    except OSError as e:
        logger.error(
            "Unexpected error downloading '%s': %s: %s",
            file_key,
            type(e).__name__,
            str(e),
        )
        return None


def bulk_upload_files(
    client: S3Client, bucket_name: str, files: list[tuple[str, bytes]]
) -> dict[str, bool]:
    """Upload multiple files to an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        files (list[tuple[str, bytes]]): List of tuples with file key and content.

    Returns:
        dict[str, bool]: Mapping of file key to upload success status.
    """
    results = {}
    for file_key, file_content in files:
        success = upload_file(client, bucket_name, file_key, file_content)
        results[file_key] = success
    return results


def bulk_download_files(
    client: S3Client, bucket_name: str, file_keys: list[str]
) -> dict[str, bytes | None]:
    """Download multiple files from an S3 bucket.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to download from.
        file_keys (list[str]): List of file keys to download.

    Returns:
        dict[str, bytes | None]: Mapping of file key to content or None if failed.
    """
    results = {}
    for file_key in file_keys:
        content = download_file(client, bucket_name, file_key)
        results[file_key] = content
    return results


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
    except OSError as e:
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
    except OSError as e:
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
    except OSError as e:
        logger.error(
            "Unexpected error setting tags for '%s': %s: %s",
            bucket_name,
            type(e).__name__,
            str(e),
        )
        return False
