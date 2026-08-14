import os
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_PROJECT'] = 'HITL-Email-Agent'

"""
Streamlit UI for the Email HITL Agent.
Supports approval via in-app buttons AND email replies still get sent as notifications.
"""

import streamlit as st
import uuid
from langgraph.types import Command
from graph import build_graph

st.set_page_config(page_title="Email HITL Agent", layout="centered")
st.title("📧 Email HITL Agent")

if "app" not in st.session_state:
    st.session_state.app = build_graph()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "graph_state" not in st.session_state:
    st.session_state.graph_state = "idle"  # idle | awaiting_selection | awaiting_decision | awaiting_draft_choice | done

if "timeline" not in st.session_state:
    st.session_state.timeline = []

app = st.session_state.app


def get_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def get_current_interrupt():
    state = app.get_state(get_config())
    if state.next and state.tasks and state.tasks[0].interrupts:
        return state.tasks[0].interrupts[0].value
    return None


# --- Start a new check ---
if st.session_state.graph_state == "idle":
    st.write("Check your inbox for new emails to process.")
    if st.button("📬 Check Inbox Now", type="primary"):
        st.session_state.thread_id = str(uuid.uuid4())
        with st.spinner("Loading recent emails..."):
            app.invoke({}, config=get_config())

        interrupt_data = get_current_interrupt()
        if interrupt_data:
            st.session_state.graph_state = "awaiting_selection"
            st.session_state.interrupt_data = interrupt_data
            st.rerun()
        else:
            st.info("No emails found in the inbox.")


# --- Stage 0: pick any email (read or unread) from the last 20 ---
elif st.session_state.graph_state == "awaiting_selection":
    data = st.session_state.interrupt_data
    email_list = data.get("email_list", [])

    st.subheader("Choose an email")
    st.caption(f"Showing the {len(email_list)} most recent inbox emails — pick any one to act on.")

    if not email_list:
        st.info("No emails found.")
        if st.button("← Back"):
            st.session_state.graph_state = "idle"
            st.rerun()
    else:
        for email in email_list:
            with st.container(border=True):
                label = f"{'🔵 ' if email.get('unread') else ''}**{email['subject']}**"
                st.markdown(label)
                st.caption(f"From: {email['from']}")
                st.write(email.get("snippet", ""))
                if st.button("Select →", key=f"select_{email['id']}"):
                    with st.spinner("Loading email and drafting..."):
                        app.invoke(Command(resume=email["id"]), config=get_config())
                    interrupt_data = get_current_interrupt()
                    if interrupt_data:
                        st.session_state.graph_state = "awaiting_decision"
                        st.session_state.interrupt_data = interrupt_data
                    else:
                        st.session_state.graph_state = "idle"
                    st.rerun()

        st.markdown("---")
        if st.button("Cancel"):
            app.invoke(Command(resume=""), config=get_config())
            st.session_state.graph_state = "idle"
            st.rerun()


# --- Stage 1: Accept / Reject / Something else ---
elif st.session_state.graph_state == "awaiting_decision":
    data = st.session_state.interrupt_data
    st.subheader("New Email")
    st.markdown(f"**From:** {data['sender']}")
    st.markdown(f"**Subject:** {data['subject']}")
    st.markdown("**Summary:**")
    st.info(data.get("email_summary", "(no summary available)"))
    st.markdown("**Body:**")
    st.text_area("Email content", data.get("body", ""), height=200, disabled=True, label_visibility="collapsed")
    st.caption("A notification with these details has also been emailed to you.")

    col1, col2 = st.columns(2)

    if col1.button("✅ Response", use_container_width=True):
        with st.spinner("Drafting replies..."):
            app.invoke(Command(resume="response"), config=get_config())
        interrupt_data = get_current_interrupt()
        if interrupt_data:
            st.session_state.graph_state = "awaiting_draft_choice"
            st.session_state.interrupt_data = interrupt_data
        else:
            st.session_state.graph_state = "idle"
        st.rerun()

    if col2.button("❌ Ignore", use_container_width=True):
        app.invoke(Command(resume="ignore"), config=get_config())
        st.session_state.graph_state = "idle"
        st.rerun()


# --- Stage 2: Short / Long / Redraft ---
elif st.session_state.graph_state == "awaiting_draft_choice":
    data = st.session_state.interrupt_data

    st.subheader("Original Email")
    st.markdown(f"**From:** {data.get('sender', '')}")
    st.markdown(f"**Subject:** {data.get('subject', '')}")
    st.text_area("Original email content", data.get("body", ""), height=150, disabled=True, label_visibility="collapsed", key="original_email_readonly")
    st.markdown("---")

    st.subheader("Draft Options")

    history = data.get("draft_history", [])

    if len(history) > 1:
        version_labels = [f"Version {h['version']}" + (f" (feedback: {h['feedback']})" if h.get("feedback") else " (original)") for h in history]
        tabs = st.tabs(version_labels)
        for tab, h in zip(tabs, history):
            with tab:
                st.markdown("**Short Version:**")
                st.write(h["short"])
                st.markdown("**Long Version:**")
                st.write(h["long"])
    else:
        st.markdown("**Short Version:**")
        st.write(data["draft_short"])
        st.markdown("**Long Version:**")
        st.write(data["draft_long"])

    st.info("These drafts have also been emailed to you for review. The buttons below always act on the latest (most recent) version.")

    col1, col2 = st.columns(2)

    if col1.button("📤 Send Short", use_container_width=True, type="primary"):
        with st.spinner("Sending..."):
            app.invoke(Command(resume="short"), config=get_config())
        st.session_state.graph_state = "done"
        st.rerun()

    if col2.button("📤 Send Long", use_container_width=True, type="primary"):
        with st.spinner("Sending..."):
            app.invoke(Command(resume="long"), config=get_config())
        st.session_state.graph_state = "done"
        st.rerun()

    st.markdown("---")
    feedback = st.text_area("Or request changes (redraft):", key="redraft_feedback")
    if st.button("🔄 Redraft"):
        with st.spinner("Regenerating drafts..."):
            app.invoke(Command(resume=f"redraft: {feedback}"), config=get_config())
        interrupt_data = get_current_interrupt()
        st.session_state.interrupt_data = interrupt_data
        st.rerun()


# --- Done ---
elif st.session_state.graph_state == "done":
    st.success("Reply sent!")
    final_state = app.get_state(get_config()).values

    st.subheader("Original Email")
    st.markdown(f"**From:** {final_state.get('sender', '')}")
    st.markdown(f"**Subject:** {final_state.get('subject', '')}")
    st.text_area("Original email content", final_state.get("body", ""), height=150, disabled=True, label_visibility="collapsed", key="done_original_email")

    history = final_state.get("draft_history", [])
    if history:
        st.markdown("---")
        st.subheader("Draft Versions")
        version_labels = [f"Version {h['version']}" + (f" (feedback: {h['feedback']})" if h.get("feedback") else " (original)") for h in history]
        tabs = st.tabs(version_labels)
        for tab, h in zip(tabs, history):
            with tab:
                st.markdown("**Short Version:**")
                st.write(h["short"])
                st.markdown("**Long Version:**")
                st.write(h["long"])

    st.markdown("---")
    st.markdown(f"**You selected:** {final_state.get('chosen_draft', '')}")

    st.markdown("---")
    st.subheader("Summary")
    st.write(final_state.get("summary", "Summary not available."))

    if st.button("Check Inbox Again"):
        st.session_state.graph_state = "idle"
        st.rerun()