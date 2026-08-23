# Email HITL Agent

A human-in-the-loop (HITL) email agent built with LangGraph: it drafts email responses and pauses for approval, either via in-app buttons in the Streamlit UI or by reply to a notification email.

## Stack
- Streamlit (`app.py`) — approval UI
- LangGraph (`graph.py`, `nodes.py`, `state.py`) — agent workflow with interrupt/resume for human approval
- Gmail API (`gmail_helpers.py`, `auth_setup.py`) — reading and sending email
- `api.py` — backend API
- `extension/` — companion browser extension
- SQLite (`hitl_checkpoints.db`) — LangGraph checkpointing

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires Gmail API credentials (`credentials.json`) — not committed to this repo.
