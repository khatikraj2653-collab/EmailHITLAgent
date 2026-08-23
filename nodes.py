import os

"""
Node functions for the Email HITL Agent LangGraph workflow.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from gmail_helpers import list_recent, get_full_message_body, send_email, mark_as_read, AGENT_EMAIL
from state import EmailHITLState

load_dotenv(override=True)

llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.4, api_key=os.getenv("OPENAI_API_KEY"))


def list_emails(state: EmailHITLState) -> EmailHITLState:
    """List the 20 most recent inbox emails (read AND unread) for the user to pick from."""
    emails = list_recent("token_real.json", max_results=20, exclude_sender=AGENT_EMAIL)
    return {**state, "email_list": emails}


def fetch_selected_email(state: EmailHITLState) -> EmailHITLState:
    """Load the full body of whichever email the user picked, and mark it read."""
    selected_id = state.get("selected_email_id")
    meta = next((e for e in state.get("email_list", []) if e["id"] == selected_id), None)

    if not selected_id or not meta:
        return {**state, "email_id": "", "sender": "", "subject": "", "body": ""}

    body = get_full_message_body("token_real.json", selected_id)

    # Mark as read immediately so a re-run of the graph doesn't reprocess the same email
    mark_as_read("token_real.json", selected_id)

    return {
        **state,
        "email_id": selected_id,
        "thread_id": meta["thread_id"],
        "sender": meta["from"],
        "subject": meta["subject"],
        "body": body,
        "redraft_count": 0,
    }


def summarize_email(state: EmailHITLState) -> EmailHITLState:
    """Generate a short LLM summary of the incoming email."""
    if not state.get("email_id"):
        return state

    prompt = f"""Summarize this email in 1-2 short, plain sentences for a busy person deciding whether to respond.

From: {state['sender']}
Subject: {state['subject']}
Body: {state['body']}

Summary:"""

    try:
        summary_text = llm.invoke(prompt).content.strip()
    except Exception:
        summary_text = "(Summary unavailable — the AI model failed to respond. See the full email body below.)"

    return {**state, "email_summary": summary_text}


def notify_human(state: EmailHITLState) -> EmailHITLState:
    """Send a notification from the agent account describing the new email."""
    notification_body = f"""New email received:

From: {state["sender"]}
Subject: {state["subject"]}

Summary:
{state.get("email_summary", "")}

Preview:
{state["body"][:500]}

Reply with one of the following:
- RESPONSE  (yes, draft a reply)
- IGNORE  (no, do nothing)
"""

    send_email(
        "token_agent.json",
        "khatikraj1054@gmail.com",
        f"[Action Needed] {state['subject']}",
        notification_body,
    )

    return state


def draft_reply(state: EmailHITLState) -> EmailHITLState:
    """Generate short and long draft reply options using the LLM."""
    feedback_note = ""
    if state.get("redraft_feedback"):
        feedback_note = f"\n\nThe user asked for changes: {state['redraft_feedback']}\nPlease incorporate this feedback."

    prompt = f"""You are drafting a reply to this email on behalf of the user.

Original email from: {state['sender']}
Subject: {state['subject']}
Body: {state['body']}
{feedback_note}

Write two versions of a reply, signed as "Raj Khatik" (use this exact name, not a placeholder):
1. SHORT version (2-3 sentences, concise and professional)
2. LONG version (a fuller, more detailed professional reply)

Format your response exactly as:
SHORT:
<short reply text>

LONG:
<long reply text>
"""

    try:
        response = llm.invoke(prompt).content
        short_part = response.split("LONG:")[0].replace("SHORT:", "").strip()
        long_part = response.split("LONG:")[1].strip() if "LONG:" in response else ""
    except Exception:
        error_text = "(Draft unavailable — the AI model failed to respond. Try Redraft to retry.)"
        short_part = error_text
        long_part = error_text

    redraft_count = state.get("redraft_count", 0) + 1

    history = state.get("draft_history", [])
    history = history + [{
        "version": redraft_count,
        "short": short_part,
        "long": long_part,
        "feedback": state.get("redraft_feedback", "") or "",
    }]

    return {**state, "draft_short": short_part, "draft_long": long_part, "redraft_count": redraft_count, "draft_history": history}


def notify_drafts(state: EmailHITLState) -> EmailHITLState:
    """Send the two draft options to the human for review."""
    body = f"""Here are two draft reply options for your email from {state["sender"]}:

--- SHORT VERSION ---
{state["draft_short"]}

--- LONG VERSION ---
{state["draft_long"]}

Reply with:
- SHORT  (send the short version)
- LONG   (send the long version)
- REDRAFT: <your feedback>  (regenerate with changes)
"""

    send_email(
        "token_agent.json",
        "khatikraj1054@gmail.com",
        f"[Draft Ready] {state['subject']}",
        body,
    )

    return state


def send_final(state: EmailHITLState) -> EmailHITLState:
    """Send the chosen draft to the original sender, then summarize to the user."""
    final_text = state["draft_short"] if state["chosen_draft"] == "short" else state["draft_long"]

    send_email(
        "token_real.json",
        state["sender"],
        f"Re: {state['subject']}",
        final_text,
        thread_id=state.get("thread_id"),
    )

    summary = f"""The mail came from: {state["sender"]}

This is the full mail:
{state["body"]}

You selected: {state["chosen_draft"]}

We sent this reply:
{final_text}

Redraft cycles: {state.get("redraft_count", 0)}
"""

    send_email(
        "token_agent.json",
        "khatikraj1054@gmail.com",
        f"[Sent] {state['subject']}",
        summary,
    )

    return {**state, "summary": summary}