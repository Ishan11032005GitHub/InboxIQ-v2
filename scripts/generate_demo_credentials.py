"""
scripts/generate_demo_credentials.py

Run this ONCE while logged in as your demo Google account
(e.g. inboxiq.demo@gmail.com) to generate the credentials
that go into your .env file.

Usage
-----
1. Place your downloaded OAuth client JSON at the repo root as credentials.json
   (download from Google Cloud Console → APIs & Services → Credentials →
    your OAuth 2.0 Client → Download JSON)

2. Run:
       python scripts/generate_demo_credentials.py

3. A browser window opens — log in as the DEMO account (inboxiq.demo@gmail.com)
   and grant the requested permissions.

4. Copy the printed JSON and add it to your .env as a single line:
       DEMO_GOOGLE_CREDENTIALS={"token":"ya29...","refresh_token":"1//0g...",...}
"""

import json
import os
import sys

# Allow running from the repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "credentials.json")


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(
            f"\n❌ credentials.json not found at: {os.path.abspath(CREDENTIALS_FILE)}"
            "\n\nDownload it from:"
            "\n  Google Cloud Console → APIs & Services → Credentials"
            "\n  → your OAuth 2.0 Client ID → Download JSON"
            "\n  Save as credentials.json in the repo root.\n"
        )
        sys.exit(1)

    print("\n🔐 Opening browser — log in as your DEMO Google account...\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
    )

    # Runs a local server on port 8888 to catch the OAuth callback
    creds = flow.run_local_server(
        port=8888,
        prompt="consent",
        access_type="offline",
    )

    creds_json = creds.to_json()

    print("\n✅ Demo credentials generated!\n")
    print("=" * 70)
    print("Add the following line to your .env file (as a SINGLE line):")
    print("=" * 70)
    print(f"\nDEMO_GOOGLE_CREDENTIALS={creds_json}\n")
    print("=" * 70)

    # Optionally write directly to .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            contents = f.read()

        if "DEMO_GOOGLE_CREDENTIALS" in contents:
            print(
                "⚠️  DEMO_GOOGLE_CREDENTIALS already exists in .env — "
                "update it manually with the value above."
            )
        else:
            with open(env_path, "a") as f:
                f.write(f"\nDEMO_GOOGLE_CREDENTIALS={creds_json}\n")
            print(f"✅ Automatically appended to {os.path.abspath(env_path)}")
    else:
        print(f"ℹ️  No .env found at {os.path.abspath(env_path)} — add the line manually.")


if __name__ == "__main__":
    main()