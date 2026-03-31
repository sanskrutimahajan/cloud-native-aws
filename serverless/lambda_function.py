import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb = boto3.resource("dynamodb")


def lambda_handler(event, context):
    """
    Lambda handler triggered by SNS to send user email verification messages.
    Uses DynamoDB to track sent emails and prevent duplicates.
    """
    table_name = os.environ["DYNAMODB_TABLE"]
    table = dynamodb.Table(table_name)

    logger.info("Received event with %d record(s)", len(event.get("Records", [])))

    for record in event.get("Records", []):
        if record.get("EventSource") != "aws:sns":
            logger.warning("Skipping non-SNS record: %s", record.get("EventSource"))
            continue

        sns_payload = record["Sns"]
        message_id = sns_payload.get("MessageId", "unknown")

        try:
            message = json.loads(sns_payload["Message"])
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to parse SNS message (id=%s): %s", message_id, exc)
            continue

        email = message.get("email")
        first_name = message.get("first_name", "")
        token = message.get("token")

        if not email or not token:
            logger.error(
                "Missing required fields in SNS message (id=%s): "
                "email_present=%s token_present=%s",
                message_id,
                bool(email),
                bool(token),
            )
            continue

        logger.info("Processing verification for %s (message_id=%s)", email, message_id)

        # --- Duplicate check ---
        try:
            response = table.get_item(Key={"email": email})
        except Exception:
            logger.exception("DynamoDB GetItem failed for %s", email)
            raise

        if "Item" in response:
            logger.info(
                "Duplicate detected — verification email already sent to %s, skipping",
                email,
            )
            continue

        # --- Build verification link ---
        base_url = os.environ["BASE_URL"].rstrip("/")
        verification_link = (
            f"{base_url}/validateEmail"
            f"?email={urllib.parse.quote(email, safe='')}"
            f"&token={urllib.parse.quote(token, safe='')}"
        )

        # --- Send email ---
        try:
            _send_email(email, first_name, verification_link)
        except Exception:
            logger.exception("Failed to send email to %s", email)
            raise

        # --- Record in DynamoDB to prevent future duplicates ---
        try:
            table.put_item(
                Item={
                    "email": email,
                    "token": token,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "message_id": message_id,
                    "status": "sent",
                }
            )
        except Exception:
            logger.exception("DynamoDB PutItem failed for %s", email)
            raise

        logger.info("Verification email sent and recorded successfully for %s", email)

    return {"statusCode": 200, "body": "Email processing complete"}


def _send_email(to_email: str, first_name: str, verification_link: str) -> None:
    """Send a verification email via the SendGrid v3 API using only stdlib."""
    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["FROM_EMAIL"]

    subject = "Verify Your Email Address"
    body_text = _build_text_body(first_name, verification_link)

    payload = json.dumps({
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": subject,
            }
        ],
        "from": {"email": from_email},
        "content": [
            {
                "type": "text/plain",
                "value": body_text,
            }
        ],
    }).encode("utf-8")

    endpoint = "https://api.sendgrid.com/v3/mail/send"

    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            logger.info("SendGrid response: status=%s body=%s", status, body)
            if status not in (200, 201, 202):
                raise RuntimeError(f"SendGrid returned unexpected status {status}: {body}")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8") if exc.fp else ""
        logger.error("SendGrid HTTP error: status=%s body=%s", exc.code, error_body)
        raise RuntimeError(f"SendGrid API error {exc.code}: {error_body}") from exc


def _build_text_body(first_name: str, verification_link: str) -> str:
    name = first_name.strip() if first_name and first_name.strip() else "there"
    return (
        f"Hello {name},\n\n"
        "Thank you for registering! Please verify your email address "
        "by visiting the link below:\n\n"
        f"{verification_link}\n\n"
        "This link is valid for 1 minute only. After expiry you will need "
        "to create a new account.\n\n"
        "If you did not create this account, you can safely ignore this email.\n\n"
        "Best regards,\n"
        "The Team"
    )