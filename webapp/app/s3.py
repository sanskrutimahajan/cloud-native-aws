"""S3 client for syllabus file storage.

Uses IAM role credentials (no hardcoded keys).
The bucket name is injected via environment variable from EC2 user data.
"""

import logging
import uuid

import boto3

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize S3 client — uses IAM role on EC2, or ~/.aws/credentials locally
_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def get_bucket_name() -> str:
    return settings.S3_BUCKET_NAME


def build_object_key(course_id: str, file_name: str) -> str:
    """Build a unique S3 object key: {course_id}/{uuid}/{original_file_name}"""
    return f"{course_id}/{uuid.uuid4()}/{file_name}"


def build_object_url(bucket: str, key: str) -> str:
    """Build the S3 URL for the object."""
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def upload_file(key: str, file_content: bytes, content_type: str) -> None:
    """Upload a file to the S3 bucket."""
    client = get_s3_client()
    client.put_object(
        Bucket=get_bucket_name(),
        Key=key,
        Body=file_content,
        ContentType=content_type,
    )
    logger.info(f"Uploaded s3://{get_bucket_name()}/{key}")


def delete_file(key: str) -> None:
    """Delete a file from the S3 bucket."""
    client = get_s3_client()
    client.delete_object(Bucket=get_bucket_name(), Key=key)
    logger.info(f"Deleted s3://{get_bucket_name()}/{key}")
