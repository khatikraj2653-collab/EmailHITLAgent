import os

"""
LangGraph workflow for the Email HITL Agent.
Uses interrupt() to pause execution and wait for human input at three points:
  1. After listing recent emails -> wait for the user to pick ANY one (read or unread)
  2. After notifying about the picked email -> wait for Accept/Reject/Something else
  3. After drafts are ready -> wait for Short/Long/Redraft
"""

import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt

from state import EmailHITLState
from nodes import (
    list_emails,
    fetch_selected_email,
    summarize_email,
    notify_human,
    draft_reply,
    notify_drafts,
    send_final,
)


def route_after_list(state: EmailHITLState) -> str:
    """If the inbox has nothing to show at all, skip straight to END."""
    if not state.get("email_list"):
        return END
    return "wait_for_email_selection"


def wait_for_email_selection(state: EmailHITLState) -> EmailHITLState:
    """Pause and show the last 20 inbox emails (read and unread); resume value
    is the id of whichever one the user picked, or empty/blank to cancel."""
    selected_id = interrupt({
        "message": "Choose an email to act on.",
        "email_list": state.get("email_list", []),
    })
    return {**state, "selected_email_id": (selected_id or "").strip()}


def route_after_selection(state: EmailHITLState) -> str:
    if not state.get("selected_email_id"):
        return END
    return "fetch_selected_email"


def route_after_fetch(state: EmailHITLState) -> str:
    """If the selected email couldn't actually be loaded, skip straight to END instead of notifying with blank data."""
    if not state.get("email_id"):
        return END
    return "summarize_email"


def wait_for_email_decision(state: EmailHITLState) -> EmailHITLState:
    decision = interrupt({
        "message": "Waiting for your decision on the new email.",
        "sender": state["sender"],
        "subject": state["subject"],
        "body": state["body"],
        "email_summary": state.get("email_summary", ""),
    })

    raw = (decision or "").strip()
    decision_clean = raw.lower()

    if decision_clean in ("response", "accept"):
        return {**state, "human_decision": "accept"}

    if decision_clean in ("reject", "ignore", ""):
        return {**state, "human_decision": "reject"}

    # Anything else is a custom drafting instruction — treat it as an accept
    # and seed draft_reply's feedback with the raw text, instead of silently
    # discarding it as a rejection.
    return {**state, "human_decision": "accept", "redraft_feedback": raw}


def route_after_decision(state: EmailHITLState) -> str:
    decision = (state.get("human_decision") or "").strip().lower()
    if decision == "accept":
        return "draft_reply"
    if decision == "reject":
        return END
    # Anything else (custom instruction) gets treated as a drafting instruction
    if decision:
        return "draft_reply"
    return END


def wait_for_draft_choice(state: EmailHITLState) -> EmailHITLState:
    choice = interrupt({
        "message": "Waiting for your choice on the drafts.",
        "sender": state["sender"],
        "subject": state["subject"],
        "body": state["body"],
        "draft_short": state["draft_short"],
        "draft_long": state["draft_long"],
        "draft_history": state.get("draft_history", []),
    })

    choice_clean = choice.strip()
    if choice_clean.lower().startswith("redraft"):
        feedback = choice_clean.split(":", 1)[1].strip() if ":" in choice_clean else ""
        return {**state, "chosen_draft": None, "redraft_feedback": feedback}

    return {**state, "chosen_draft": choice_clean.lower(), "redraft_feedback": None}


def route_after_draft_choice(state: EmailHITLState) -> str:
    if state.get("chosen_draft") in ("short", "long"):
        return "send_final"
    return "draft_reply"


def build_graph():
    graph = StateGraph(EmailHITLState)

    graph.add_node("list_emails", list_emails)
    graph.add_node("wait_for_email_selection", wait_for_email_selection)
    graph.add_node("fetch_selected_email", fetch_selected_email)
    graph.add_node("summarize_email", summarize_email)
    graph.add_node("notify_human", notify_human)
    graph.add_node("wait_for_email_decision", wait_for_email_decision)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("notify_drafts", notify_drafts)
    graph.add_node("wait_for_draft_choice", wait_for_draft_choice)
    graph.add_node("send_final", send_final)

    graph.set_entry_point("list_emails")

    graph.add_conditional_edges(
        "list_emails",
        route_after_list,
        {"wait_for_email_selection": "wait_for_email_selection", END: END},
    )

    graph.add_conditional_edges(
        "wait_for_email_selection",
        route_after_selection,
        {"fetch_selected_email": "fetch_selected_email", END: END},
    )

    graph.add_conditional_edges(
        "fetch_selected_email",
        route_after_fetch,
        {"summarize_email": "summarize_email", END: END},
    )

    graph.add_edge("summarize_email", "notify_human")
    graph.add_edge("notify_human", "wait_for_email_decision")

    graph.add_conditional_edges(
        "wait_for_email_decision",
        route_after_decision,
        {"draft_reply": "draft_reply", END: END},
    )

    graph.add_edge("draft_reply", "notify_drafts")
    graph.add_edge("notify_drafts", "wait_for_draft_choice")

    graph.add_conditional_edges(
        "wait_for_draft_choice",
        route_after_draft_choice,
        {"send_final": "send_final", "draft_reply": "draft_reply"},
    )

    graph.add_edge("send_final", END)

    conn = sqlite3.connect("hitl_checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)