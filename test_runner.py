"""
Terminal test runner for the Email HITL Agent graph.
Simulates the human replying at each interrupt point via terminal input.
"""
import uuid
from graph import build_graph
from langgraph.types import Command

app = build_graph()
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

print("Starting graph... listing recent inbox emails.\n")
result = app.invoke({}, config=config)

# Loop until the graph has no more pending interrupts
while True:
    state = app.get_state(config)
    if not state.next:
        break

    interrupt_data = state.tasks[0].interrupts[0].value

    if "email_list" in interrupt_data:
        print("PAUSED. Pick an email:")
        for i, e in enumerate(interrupt_data.get("email_list", [])):
            flag = "UNREAD" if e.get("unread") else "read"
            print(f"  [{i}] ({flag}) {e['from']} — {e['subject']}")
        idx = input("\nEnter the number of the email to act on (blank to cancel): ").strip()
        try:
            choice = interrupt_data["email_list"][int(idx)]["id"]
        except (ValueError, IndexError):
            choice = ""
    elif "draft_short" in interrupt_data:
        print("PAUSED. Agent is waiting for input:")
        print(interrupt_data)
        choice = input("\nYour reply (SHORT / LONG / REDRAFT: feedback): ")
    else:
        print("PAUSED. Agent is waiting for input:")
        print(interrupt_data)
        choice = input("\nYour reply (ACCEPT / REJECT / SOMETHING ELSE): ")

    result = app.invoke(Command(resume=choice), config=config)

print("\nDone. Check your email for the final sent reply and summary.")
