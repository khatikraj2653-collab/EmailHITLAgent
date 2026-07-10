"""
One-time Gmail OAuth setup script.

Run this TWICE:
  1st run -> log in as hitl.ai.raj.2605@gmail.com  -> produces token_agent.json
  2nd run -> log in as khatikraj1054@gmail.com     -> produces token_real.json

Usage:
  python auth_setup.py agent
  python auth_setup.py real
"""

import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("agent", "real"):
        print("Usage: python auth_setup.py [agent|real]")
        print("  agent -> for hitl.ai.raj.2605@gmail.com")
        print("  real  -> for khatikraj1054@gmail.com")
        sys.exit(1)

    account_type = sys.argv[1]
    token_filename = f"token_{account_type}.json"

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_filename, "w") as f:
        f.write(creds.to_json())

    print(f"\nSuccess! Saved credentials to {token_filename}")
    print(f"Make sure you logged in with the correct account for '{account_type}'.")

if __name__ == "__main__":
    main()
