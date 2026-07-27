"""
FastAPI wrapper around the existing HITL LangGraph agent (graph.py).
This exposes the same fetch -> notify -> decide -> draft -> decide -> send
flow as HTTP endpoints, so a Chrome extension (or any other frontend)
can drive it without needing to import LangGraph directly.

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

# Allow requests from a Chrome extension (extensions use chrome-extension:// origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your specific extension ID once built
    allow_methods=["*"],
    allow_headers=["*"],
)

graph_app = build_graph()

# In-memory map of thread_id -> whether a session is active.
# (The actual state lives in SQLite via the checkpointer, this is just bookkeeping.)
active_sessions = {}


class DecisionRequest(BaseModel):
    thread_id: str
    decision: str  # "accept" | "reject" | free text | "short" | "long" | "redraft: ..."


def get_current_interrupt(thread_id: str):
    """Reads the graph's current paused state and returns the interrupt payload, if any."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph_app.get_state(config)
    if state.next and state.tasks and state.tasks[0].interrupts:
        return state.tasks[0].interrupts[0].value
    return None


@app.get("/")
def root():
    return {"status": "HITL Agent API is running"}


@app.post("/check-inbox")
def check_inbox():
    """
    Starts a new graph run: fetches the latest unread email (if any),
    sends the notification, and returns the first interrupt (waiting for
    accept/reject/something-else) â€” or a message saying nothing new was found.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    graph_app.invoke({}, config=config)

    interrupt_data = get_current_interrupt(thread_id)

    if interrupt_data is None:
        return {"status": "no_new_email"}

    active_sessions[thread_id] = "awaiting_decision"

    return {
        "status": "awaiting_decision",
        "thread_id": thread_id,
        "sender": interrupt_data.get("sender"),
        "subject": interrupt_data.get("subject"),
        "body": interrupt_data.get("body"),
        "email_summary": interrupt_data.get("email_summary"),
    }


@app.post("/decide")
def decide(req: DecisionRequest):
    """
    Resumes a paused graph at whichever interrupt it's currently sitting at.
    Works for BOTH interrupt points (accept/reject/something-else, AND
    short/long/redraft) â€” the graph itself knows which one it's at.
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    graph_app.invoke(Command(resume=req.decision), config=config)

    interrupt_data = get_current_interrupt(req.thread_id)

    if interrupt_data is None:
        # Graph reached the end (send_final completed) - fetch the final state for the summary
        final_state = graph_app.get_state(config).values
        active_sessions.pop(req.thread_id, None)
        return {
            "status": "done",
            "summary": final_state.get("summary", "No summary available."),
        }

    # Still paused - figure out which interrupt we're at based on its keys
    if "draft_short" in interrupt_data:
        active_sessions[req.thread_id] = "awaiting_draft_choice"
        return {
            "status": "awaiting_draft_choice",
            "thread_id": req.thread_id,
            "draft_short": interrupt_data.get("draft_short"),
            "draft_long": interrupt_data.get("draft_long"),
            "draft_history": interrupt_data.get("draft_history", []),
        }
    else:
        active_sessions[req.thread_id] = "awaiting_decision"
        return {
            "status": "awaiting_decision",
            "thread_id": req.thread_id,
            "sender": interrupt_data.get("sender"),
            "subject": interrupt_data.get("subject"),
            "body": interrupt_data.get("body"),
            "email_summary": interrupt_data.get("email_summary"),
        }


@app.get("/status/{thread_id}")
def status(thread_id: str):
    """Lets a frontend check where a given session currently is, without resuming it."""
    interrupt_data = get_current_interrupt(thread_id)
    if interrupt_data is None:
        return {"status": "done_or_unknown"}
    return {"status": active_sessions.get(thread_id, "unknown"), "data": interrupt_data}
