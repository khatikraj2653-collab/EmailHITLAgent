import os
os.environ['LANGCHAIN_TRACING_V2'] = 'false'

"""
Shared state schema for the Email HITL Agent LangGraph workflow.
"""

from typing import TypedDict, Optional, List, Dict


class EmailHITLState(TypedDict, total=False):
    email_id: str
    thread_id: str
    sender: str
    subject: str
    body: str

    human_decision: Optional[str]

    draft_short: Optional[str]
    draft_long: Optional[str]
    draft_history: List[Dict[str, str]]

    chosen_draft: Optional[str]
    redraft_feedback: Optional[str]

    redraft_count: int

    summary: Optional[str]