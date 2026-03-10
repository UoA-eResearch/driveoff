from __future__ import annotations
from config import get_settings
from fastapi import FastAPI, Request
from types_boto3_s3 import S3Client
import boto3
from botocore.exceptions import ClientError


def init_activescale(app: FastAPI) -> None:
    """Initialize a ActiveScale S3 client and attach it to the FastAPI app state.

    TODO: look into boto3 session management and whether we should be using sessions instead of clients directly.
    """
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
    except Exception as e:
        raise ValueError("Failed to connect to ActiveScale S3 client.") from e
    app.state.activescale = client


def get_activescale_client(request: Request) -> S3Client:
    """FastAPI dependency to retrieve the initialized ActiveScale S3 client.

    Endpoints can use ``Depends(get_activescale_client)`` to receive the client.
    """
    client = getattr(request.app.state, "activescale", None)
    if client is None:
        raise RuntimeError("ActiveScale client not initialised on application state")
    return client
