"""
Terminal test runner for the Email HITL Agent graph.
Simulates the human replying at each interrupt point via terminal input.
"""
import uuid
from graph import build_graph
from langgraph.types import Command

app = build_graph()
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

print("Starting graph... fetching email and sending notification.\n")
result = app.invoke({}, config=config)

# Loop until the graph has no more pending interrupts
while True:
    state = app.get_state(config)
    if not state.next:
        break

    interrupt_data = state.tasks[0].interrupts[0].value
    print("PAUSED. Agent is waiting for input:")
    print(interrupt_data)

    if "draft_short" in interrupt_data:
        choice = input("\nYour reply (SHORT / LONG / REDRAFT: feedback): ")
    else:
        choice = input("\nYour reply (ACCEPT / REJECT / SOMETHING ELSE): ")

    result = app.invoke(Command(resume=choice), config=config)

print("\nDone. Check your email for the final sent reply and summary.")
