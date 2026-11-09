"""
FastAPI wrapper around the existing HITL LangGraph agent (graph.py).
This exposes the same list -> select -> notify -> decide -> draft -> decide
-> send flow as HTTP endpoints, so a Chrome extension (or any other
frontend) can drive it without needing to import LangGraph directly.

Run with:
    uvicorn api:app --reload --port 8000

Test it directly (no extension needed yet):
    curl -X POST http://localhost:8000/check-inbox
"""

import os
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_PROJECT'] = 'HITL-Email-Agent'

import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command

from graph import build_graph

app = FastAPI(title="HITL Email Agent API")

# The extension's content script runs inside the Gmail page, so its requests
# arrive with the https://mail.google.com origin; chrome-extension:// origins
# cover calls from the extension's own context. No other website gets CORS access.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https://mail\.google\.com|chrome-extension://[a-p]{32})$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

graph_app = build_graph()

# In-memory map of thread_id -> whether a session is active.
# (The actual state lives in SQLite via the checkpointer, this is just bookkeeping.)
active_sessions = {}


class DecisionRequest(BaseModel):
    thread_id: str
    decision: str  # an email id (selection stage) | "accept" | "reject" | free text | "short" | "long" | "redraft: ..."


def get_current_interrupt(thread_id: str):
    """Reads the graph's current paused state and returns the interrupt payload, if any."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph_app.get_state(config)
    if state.next and state.tasks and state.tasks[0].interrupts:
        return state.tasks[0].interrupts[0].value
    return None


def format_interrupt(thread_id: str, interrupt_data: dict):
    """Turns a raw interrupt payload into the response shape the extension/frontend expects,
    figuring out which of the three pause points we're at based on its keys."""
    if interrupt_data is None:
        return None

    if "draft_short" in interrupt_data:
        active_sessions[thread_id] = "awaiting_draft_choice"
        return {
            "status": "awaiting_draft_choice",
            "thread_id": thread_id,
            "draft_short": interrupt_data.get("draft_short"),
            "draft_long": interrupt_data.get("draft_long"),
            "draft_history": interrupt_data.get("draft_history", []),
        }

    if "email_list" in interrupt_data:
        active_sessions[thread_id] = "awaiting_selection"
        return {
            "status": "awaiting_selection",
            "thread_id": thread_id,
            "email_list": interrupt_data.get("email_list", []),
        }

    active_sessions[thread_id] = "awaiting_decision"
    return {
        "status": "awaiting_decision",
        "thread_id": thread_id,
        "sender": interrupt_data.get("sender"),
        "subject": interrupt_data.get("subject"),
        "body": interrupt_data.get("body"),
        "email_summary": interrupt_data.get("email_summary"),
    }


@app.get("/")
def root():
    return {"status": "HITL Agent API is running"}


@app.post("/check-inbox")
def check_inbox():
    """
    Starts a new graph run: lists the 20 most recent inbox emails (read and
    unread) and returns the first interrupt asking the user to pick one â€”
    or a message saying the inbox is empty.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    graph_app.invoke({}, config=config)

    interrupt_data = get_current_interrupt(thread_id)

    if interrupt_data is None:
        return {"status": "no_new_email"}

    return format_interrupt(thread_id, interrupt_data)


@app.post("/decide")
def decide(req: DecisionRequest):
    """
    Resumes a paused graph at whichever interrupt it's currently sitting at.
    Works for ALL THREE interrupt points (email selection, accept/reject/
    something-else, AND short/long/redraft) â€” the graph itself knows which
    one it's at; `req.decision` carries the selected email id, the decision
    text, or the draft choice depending on where we currently are.
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    graph_app.invoke(Command(resume=req.decision), config=config)

    interrupt_data = get_current_interrupt(req.thread_id)

    if interrupt_data is None:
        # Graph reached the end (send_final completed, or was cancelled) - fetch the final state for the summary
        final_state = graph_app.get_state(config).values
        active_sessions.pop(req.thread_id, None)
        return {
            "status": "done",
            "summary": final_state.get("summary", "No summary available."),
        }

    return format_interrupt(req.thread_id, interrupt_data)


@app.get("/status/{thread_id}")
def status(thread_id: str):
    """Lets a frontend check where a given session currently is, without resuming it."""
    interrupt_data = get_current_interrupt(thread_id)
    if interrupt_data is None:
        return {"status": "done_or_unknown"}
    return {"status": active_sessions.get(thread_id, "unknown"), "data": interrupt_data}
