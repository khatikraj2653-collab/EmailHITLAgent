import os

"""
Gmail helper functions - read and send email via Gmail API.
Uses two separate token files:
  token_real.json  -> your real Gmail account (receives real mail, sends final replies)
  token_agent.json -> the agent account, AGENT_EMAIL in .env (sends notifications)
"""

import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_service(token_file: str):
    """Build a Gmail API service object from a saved token file."""
    creds = Credentials.from_authorized_user_file(token_file)
    return build("gmail", "v1", credentials=creds)


def list_unread(token_file: str, max_results: int = 5, exclude_sender: str = None):
    """Return a list of unread message metadata (id, snippet, sender, subject),
    skipping any messages sent by exclude_sender (used to avoid reprocessing our own notifications)."""
    service = get_service(token_file)
    results = service.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results * 3
    ).execute()

    messages = results.get("messages", [])
    parsed = []

    for msg in messages:
        full_msg = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        headers = {h["name"]: h["value"] for h in full_msg["payload"]["headers"]}
        sender = headers.get("From", "Unknown")

        if exclude_sender and exclude_sender.lower() in sender.lower():
            continue

        parsed.append({
            "id": msg["id"],
            "thread_id": full_msg["threadId"],
            "from": sender,
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": full_msg.get("snippet", ""),
        })

        if len(parsed) >= max_results:
            break

    return parsed


def list_recent(token_file: str, max_results: int = 20, exclude_sender: str = None):
    """Return metadata for the most recent inbox messages, read AND unread —
    unlike list_unread, this does not filter by the UNREAD label. Used to let
    the user pick any email to act on, not just the newest unread one."""
    service = get_service(token_file)
    results = service.users().messages().list(
        userId="me", labelIds=["INBOX"], maxResults=max_results * 2
    ).execute()

    messages = results.get("messages", [])
    parsed = []

    for msg in messages:
        full_msg = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        headers = {h["name"]: h["value"] for h in full_msg["payload"]["headers"]}
        sender = headers.get("From", "Unknown")

        if exclude_sender and exclude_sender.lower() in sender.lower():
            continue

        parsed.append({
            "id": msg["id"],
            "thread_id": full_msg["threadId"],
            "from": sender,
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": full_msg.get("snippet", ""),
            "unread": "UNREAD" in full_msg.get("labelIds", []),
        })

        if len(parsed) >= max_results:
            break

    return parsed


def get_full_message_body(token_file: str, message_id: str):
    """Fetch the full plain-text body of a specific message."""
    service = get_service(token_file)
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    def extract_text(payload):
        if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []):
            text = extract_text(part)
            if text:
                return text
        return ""

    return extract_text(msg["payload"])


def send_email(token_file: str, to: str, subject: str, body: str, thread_id: str = None):
    """Send a plain-text email from the account tied to token_file."""
    service = get_service(token_file)

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    sent = service.users().messages().send(userId="me", body=send_body).execute()
    return sent


def mark_as_read(token_file: str, message_id: str):
    """Remove the UNREAD label so we don't reprocess the same email."""
    service = get_service(token_file)
    service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()