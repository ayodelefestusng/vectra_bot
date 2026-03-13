
import os
import sys
import logging
from pathlib import Path

# Add the chat directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from chat_bot import process_message

def test_process_message():
    message = "Show me available leave types"
    conversation_id = "test_verification_session"
    tenant_id = "DMC"
    employee_id = "obinna.kelechi.adewale@dignityconcept.tech"
    push_name = "AntigravityVerifier"

    print(f"--- Testing process_message with query: '{message}' ---")
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
    test_process_message()
