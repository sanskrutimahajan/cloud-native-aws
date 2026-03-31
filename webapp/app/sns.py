"""SNS publish helper."""

import json
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger("csye6225")


def publish_verification_email(email: str, first_name: str, token: str) -> bool:
    """Publish a verification email event to SNS. Returns True on success, False on failure."""
    topic_arn = settings.SNS_TOPIC_ARN
    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN is not configured; skipping email verification publish")
        return False

    message = json.dumps({"email": email, "first_name": first_name, "token": token})
    try:
        client = boto3.client("sns")
        client.publish(TopicArn=topic_arn, Message=message)
        logger.info("Published verification email event to SNS for: %s", email)
        return True
    except ClientError as e:
        logger.error("Failed to publish to SNS for %s: %s", email, e, exc_info=True)
        return False
