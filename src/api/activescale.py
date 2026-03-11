from __future__ import annotations
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from config import get_settings
from fastapi import FastAPI, Request
from types_boto3_s3 import S3Client
import boto3


config = Config(
    retries={"total_max_attempts": 3, "mode": "standard"}, signature_version="s3v4"
)

# TODO: make this more generic and reusable for other S3-compatible services, not just ActiveScale. E.g. ability to create different sessions/clients with specific credentials
# TODO: make a standardized way to handle s3 errors.
# TODO: look into boto3 sessions and whether we should be using sessions instead of clients directly. Also thread safety of the client/session.


def init_activescale(app: FastAPI) -> None:
    """Initialize a ActiveScale S3 client and attach it to the FastAPI app state."""
    print("Initializing ActiveScale S3 client...")
    settings = get_settings()

    hostname = settings.activescale_hostname
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
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{hostname}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )
    bucket_name = "test-temp"
    try:
        client.head_bucket(Bucket=bucket_name)
        print(
            f"Connection successful. Bucket '{bucket_name}' exists and is accessible."
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            print(f"Bucket '{bucket_name}' does not exist.")
        elif error_code == "403":
            print(f"Access denied for bucket '{bucket_name}'. Check IAM permissions.")
        else:
            print(f"A ClientError occurred: {e.response['Error']['Message']}")
    except EndpointConnectionError:
        print("Could not connect to the S3 endpoint. Check network connectivity.")
    except Exception as e:
        raise ValueError("Failed to connect to ActiveScale S3 client.") from e
    app.state.activescale = client  # TODO: check if this is best practice / may need to change for thread safety


def get_activescale_client(request: Request) -> S3Client:
    """FastAPI dependency to retrieve the initialized ActiveScale S3 client.

    Endpoints can use ``Depends(get_activescale_client)`` to receive the client.
    """
    client = getattr(request.app.state, "activescale", None)
    if client is None:
        raise RuntimeError("ActiveScale client not initialised on application state")
    return client


# *** S3 interactions - generic for any S3-compatible service, not just ActiveScale. Pass in initialised client. ***


def list_buckets(client: S3Client) -> list[str]:
    """List buckets in an S3 account using the provided client."""
    try:
        response = client.list_buckets()
        buckets = [
            bucket["Name"] for bucket in response.get("Buckets", []) if "Name" in bucket
        ]
        return buckets
    except ClientError as e:
        print(
            f"An error occurred while listing buckets: {e.response['Error']['Message']}"
        )
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return []


def upload_file(
    client: S3Client, bucket_name: str, file_key: str, file_content: bytes
) -> bool:
    """Upload a file to an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        file_key (str): The key (path/filename) to use for the uploaded file in the bucket.
        file_content (bytes): The content of the file to upload.

    Returns:
        bool: True if the upload is successful, False otherwise.
    """
    try:
        client.put_object(Bucket=bucket_name, Key=file_key, Body=file_content)
        print(f"File '{file_key}' uploaded successfully to bucket '{bucket_name}'.")
        return True
    except ClientError as e:
        print(
            f"An error occurred while uploading the file: {e.response['Error']['Message']}"
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return False


def download_file(client: S3Client, bucket_name: str, file_key: str) -> bytes | None:
    """Download a file from an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to download from.
        file_key (str): The key (path/filename) of the file to download.

    Returns:
        bytes | None: The content of the downloaded file as bytes if successful, None otherwise.
    """
    try:
        response = client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response["Body"].read()
        print(f"File '{file_key}' downloaded successfully from bucket '{bucket_name}'.")
        return file_content
    except ClientError as e:
        print(
            f"An error occurred while downloading the file: {e.response['Error']['Message']}"
        )
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None


def bulk_upload_files(
    client: S3Client, bucket_name: str, files: list[tuple[str, bytes]]
) -> dict[str, bool]:
    """Upload multiple files to an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to upload to.
        files (list[tuple[str, bytes]]): A list of tuples where each tuple contains a file key and its content.

    Returns:
        dict[str, bool]: A dictionary mapping each file key to a boolean indicating whether the upload was successful.
    """
    results = {}
    for file_key, file_content in files:
        success = upload_file(client, bucket_name, file_key, file_content)
        results[file_key] = success
    return results


def bulk_download_files(
    client: S3Client, bucket_name: str, file_keys: list[str]
) -> dict[str, bytes | None]:
    """Download multiple files from an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to download from.
        file_keys (list[str]): A list of file keys to download.

    Returns:
        dict[str, bytes | None]: A dictionary mapping each file key to its content as bytes if successful, or None if the download failed.
    """
    results = {}
    for file_key in file_keys:
        content = download_file(client, bucket_name, file_key)
        results[file_key] = content
    return results


def create_bucket(client: S3Client, bucket_name: str) -> bool:
    """Create a new S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to create.

    Returns:
        bool: True if the bucket was created successfully, False otherwise.
    """
    try:
        client.create_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' created successfully.")
        return True
    except ClientError as e:
        print(
            f"An error occurred while creating the bucket: {e.response['Error']['Message']}"
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return False


def set_bucket_policy(client: S3Client, bucket_name: str, policy_json: str) -> bool:
    """Set the bucket policy for an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to set the policy for.
        policy_json (str): The bucket policy in JSON format.

    Returns:
        bool: True if the bucket policy was set successfully, False otherwise.
    """
    try:
        client.put_bucket_policy(Bucket=bucket_name, Policy=policy_json)
        print(f"Bucket policy for '{bucket_name}' set successfully.")
        return True
    except ClientError as e:
        print(
            f"An error occurred while setting the bucket policy: {e.response['Error']['Message']}"
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return False


def set_bucket_tags(
    client: S3Client, bucket_name: str, tag_set: list[dict[str, str]]
) -> bool:
    """Set tags for an S3 bucket using the provided client.

    Args:
        client (S3Client): An initialized S3 client.
        bucket_name (str): The name of the S3 bucket to set tags for.
        tag_set (list[dict[str, str]]): A list of dictionaries containing tag key-value pairs with "Key" and "Value" fields.

    Returns:
        bool: True if the bucket tags were set successfully, False otherwise.
    """
    try:
        client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                "TagSet": [
                    {"Key": k, "Value": v} for tag in tag_set for k, v in tag.items()
                ]
            },
        )
        print(f"Bucket tags for '{bucket_name}' set successfully.")
        return True
    except ClientError as e:
        print(
            f"An error occurred while setting the bucket tags: {e.response['Error']['Message']}"
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return False
