import os
os.environ['LANGCHAIN_TRACING_V2'] = 'false'

"""
LangGraph workflow for the Email HITL Agent.
Uses interrupt() to pause execution and wait for human input at two points:
  1. After notifying about a new email -> wait for Accept/Reject/Something else
  2. After drafts are ready -> wait for Short/Long/Redraft
"""

import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt

from state import EmailHITLState
from nodes import fetch_email, notify_human, draft_reply, notify_drafts, send_final


def route_after_fetch(state: EmailHITLState) -> str:
    """If no unread email was found, skip straight to END instead of notifying with blank data."""
    if not state.get("email_id"):
        return END
    return "notify_human"


def wait_for_email_decision(state: EmailHITLState) -> EmailHITLState:
    decision = interrupt({
        "message": "Waiting for your decision on the new email.",
        "sender": state["sender"],
        "subject": state["subject"],
        "body": state["body"],
    })

    decision_clean = (decision or "").strip()
    is_standard = decision_clean.lower() in ("accept", "reject")

    if is_standard:
        return {**state, "human_decision": decision_clean.lower()}

    # Custom "something else" instruction -> treat as accept + feedback for drafting
    return {**state, "human_decision": "accept" if decision_clean else "reject", "redraft_feedback": decision_clean}


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

    graph.add_node("fetch_email", fetch_email)
    graph.add_node("notify_human", notify_human)
    graph.add_node("wait_for_email_decision", wait_for_email_decision)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("notify_drafts", notify_drafts)
    graph.add_node("wait_for_draft_choice", wait_for_draft_choice)
    graph.add_node("send_final", send_final)

    graph.set_entry_point("fetch_email")

    graph.add_conditional_edges(
        "fetch_email",
        route_after_fetch,
        {"notify_human": "notify_human", END: END},
    )

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