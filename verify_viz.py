
import os
import sys
from pathlib import Path

# Add the chat directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from chat_bot import process_message

def test_visualization_chaining():
    # The query that previously failed by generating raw SQL
    message = "Give me chart of transaction count in the last three months"
    conversation_id = "test_viz_session_final"
    tenant_id = "DMC"
    employee_id = "obinna.kelechi.adewale@dignityconcept.tech"
    push_name = "VizVerifier"

    print(f"--- Testing Visualization Chaining with query: '{message}' ---")
    try:
        response = process_message(
            message_content=message,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            employee_id=employee_id,
            push_name=push_name
        )
        print("\nFinal Response:")
        print(response)
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_visualization_chaining()
