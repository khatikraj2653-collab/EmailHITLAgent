# Email HITL Agent

**Status:** open-source repository, not deployed. Gmail OAuth credentials (`credentials.json`, tokens) are git-ignored and must be supplied locally. The agent never sends an email without explicit human approval.

A human-in-the-loop (HITL) email agent built with LangGraph: it drafts email responses and pauses for approval, given via in-app buttons in the Streamlit UI, the Chrome extension's panel inside Gmail (through the local API), or the terminal script.

## Stack
- Streamlit (`app.py`) — approval UI
- LangGraph (`graph.py`, `nodes.py`, `state.py`) — agent workflow with interrupt/resume for human approval
- Gmail API (`gmail_helpers.py`, `auth_setup.py`) — reading and sending email
- `api.py` — backend API
- `extension/` — companion browser extension
- SQLite (`hitl_checkpoints.db`) — LangGraph checkpointing

## Architecture

```mermaid
flowchart TD
    START([Start]) --> list_emails["list_emails\n(fetch last 20 inbox emails)"]

    list_emails -->|route_after_list| route1{email_list empty?}
    route1 -->|yes| END1([END])
    route1 -->|no| wait_for_email_selection

    subgraph HITL1["Human-in-the-loop: interrupt()"]
        wait_for_email_selection["wait_for_email_selection\n(pause, show inbox list)"]
    end

    wait_for_email_selection -->|route_after_selection| route2{selected_email_id set?}
    route2 -->|no| END2([END])
    route2 -->|yes| fetch_selected_email["fetch_selected_email\n(load body, mark as read)"]

    fetch_selected_email -->|route_after_fetch| route3{email_id set?}
    route3 -->|no| END3([END])
    route3 -->|yes| summarize_email["summarize_email\n(LLM summary)"]

    summarize_email --> notify_human["notify_human\n(email notification: summary + preview)"]
    notify_human --> wait_for_email_decision

    subgraph HITL2["Human-in-the-loop: interrupt()"]
        wait_for_email_decision["wait_for_email_decision\n(pause, wait for accept/reject/custom)"]
    end

    wait_for_email_decision -->|route_after_decision| route4{human_decision}
    route4 -->|reject / empty| END4([END])
    route4 -->|accept or custom instruction| draft_reply["draft_reply\n(LLM: generate SHORT + LONG drafts)"]

    draft_reply --> notify_drafts["notify_drafts\n(email notification: SHORT + LONG drafts)"]
    notify_drafts --> wait_for_draft_choice

    subgraph HITL3["Human-in-the-loop: interrupt()"]
        wait_for_draft_choice["wait_for_draft_choice\n(pause, wait for short/long/redraft)"]
    end

    wait_for_draft_choice -->|route_after_draft_choice| route5{chosen_draft}
    route5 -->|short or long| send_final["send_final\n(send reply to sender, notify summary)"]
    route5 -->|redraft| draft_reply

    send_final --> END5([END])
```

The graph pauses at three `interrupt()` points (`wait_for_email_selection`, `wait_for_email_decision`, `wait_for_draft_choice`) using LangGraph's `SqliteSaver` checkpointer, so state persists across pauses and resumes. A paused run is resumed from Streamlit UI button clicks (`app.py`), from the Chrome extension's Gmail panel through the local API (`extension/` and `api.py`), or from the terminal script (`test_runner.py`). The notification emails are for reference only; replying to them does nothing.

## Run locally
Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `NOTIFY_EMAIL` (the address that receives the agent's notification emails) and `AGENT_EMAIL` (the agent Gmail account's own address). The app stops at startup with an error naming the variable if either address is missing.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires Gmail API credentials (`credentials.json`) — not committed to this repo.
