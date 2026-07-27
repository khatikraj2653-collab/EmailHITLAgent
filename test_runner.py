"""
Terminal test runner for the Email HITL Agent graph.
Simulates the human replying at each interrupt point via terminal input.
"""

import uuid
from graph import build_graph

app = build_graph()

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

print("Starting graph... fetching email and sending notification.\n")
result = app.invoke({}, config=config)

# Check if we're paused at an interrupt
state = app.get_state(config)

if state.next:
    interrupt_data = state.tasks[0].interrupts[0].value
    print("PAUSED. Agent is waiting for input:")
    print(interrupt_data)

    decision = input("\nYour reply (ACCEPT / REJECT / SOMETHING ELSE): ")
    result = app.invoke({"human_decision": decision}, config=config)

    # Resume via Command if using interrupt() properly
    from langgraph.types import Command
    result = app.invoke(Command(resume=decision), config=config)

    state = app.get_state(config)
    if state.next:
        interrupt_data = state.tasks[0].interrupts[0].value
        print("\nPAUSED AGAIN. Agent is waiting for input:")
        print(interrupt_data)

        choice = input("\nYour reply (SHORT / LONG / REDRAFT: feedback): ")
        result = app.invoke(Command(resume=choice), config=config)

        # Handle redraft loop
        while True:
            state = app.get_state(config)
            if not state.next:
                break
            interrupt_data = state.tasks[0].interrupts[0].value
            print("\nPAUSED AGAIN. Agent is waiting for input:")
            print(interrupt_data)
            choice = input("\nYour reply (SHORT / LONG / REDRAFT: feedback): ")
            result = app.invoke(Command(resume=choice), config=config)

print("\nDone. Check your email for the final sent reply and summary.")
