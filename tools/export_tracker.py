#!/usr/bin/env python3
"""
Export CA New Grad RN Program Tracker data.

Usage:
    python tools/export_tracker.py csv                  # Export to .tmp/programs.csv
    python tools/export_tracker.py csv --output FILE    # Export to specific file
    python tools/export_tracker.py sheets               # Sync to Google Sheets
    python tools/export_tracker.py sheets --setup       # Set up Google Sheets credentials
"""

import json
import csv
import sys
import os
from datetime import date

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "programs.json")
DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", ".tmp", "programs.csv")
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def export_csv(data, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    columns = [
        "id", "hospital", "program_name", "region", "city",
        "specialty_units", "program_length_months", "cohort_start",
        "info_session_dates", "app_open_date", "app_close_date",
        "requirements", "bsn_required", "application_url",
        "pay_range", "reputation", "reputation_notes",
        "application_status", "personal_notes", "last_updated"
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for program in data["programs"]:
            row = {}
            for col in columns:
                val = program.get(col, "")
                if isinstance(val, list):
                    val = "; ".join(val)
                row[col] = val
            writer.writerow(row)

    print(f"Exported {len(data['programs'])} programs to {output_path}")


def sheets_setup():
    """Guide user through Google Sheets API setup."""
    print("\n--- Google Sheets Setup ---\n")
    print("To sync your tracker to Google Sheets, you need:")
    print()
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a project (or use existing)")
    print("3. Enable the Google Sheets API and Google Drive API")
    print("4. Create OAuth 2.0 credentials (Desktop application)")
    print("5. Download the credentials JSON file")
    print(f"6. Save it as: {CREDENTIALS_FILE}")
    print()
    print("7. Install required packages:")
    print("   pip install google-auth google-auth-oauthlib google-api-python-client")
    print()
    print("After setup, run: python tools/export_tracker.py sheets")
    print()

    if os.path.exists(CREDENTIALS_FILE):
        print("credentials.json found.")
    else:
        print("credentials.json NOT found — complete steps above first.")


def export_sheets(data):
    """Sync program data to Google Sheets."""
    if not os.path.exists(CREDENTIALS_FILE):
        print("No credentials.json found. Run with --setup first:")
        print("  python tools/export_tracker.py sheets --setup")
        return

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("Missing Google API packages. Install them:")
        print("  pip install google-auth google-auth-oauthlib google-api-python-client")
        return

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("sheets", "v4", credentials=creds)

    # Check for existing spreadsheet ID in .env
    env_path = os.path.join(PROJECT_ROOT, ".env")
    spreadsheet_id = None
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GOOGLE_SHEET_ID="):
                    spreadsheet_id = line.strip().split("=", 1)[1].strip('"').strip("'")

    if not spreadsheet_id:
        # Create new spreadsheet
        spreadsheet = service.spreadsheets().create(
            body={
                "properties": {"title": "CA New Grad RN Tracker"},
                "sheets": [{"properties": {"title": "Programs"}}]
            }
        ).execute()
        spreadsheet_id = spreadsheet["spreadsheetId"]
        print(f"Created new spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")

        # Save ID to .env
        with open(env_path, "a") as f:
            f.write(f'\nGOOGLE_SHEET_ID="{spreadsheet_id}"\n')
        print(f"Saved spreadsheet ID to .env")
    else:
        print(f"Updating existing spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")

    # Prepare data
    headers = [
        "ID", "Hospital", "Program", "Region", "City", "BSN Req",
        "Reputation", "Program Length", "Pay Range",
        "App Open", "App Close", "Cohort Start",
        "Specialty Units", "Requirements",
        "Application URL", "Status", "Personal Notes", "Last Updated"
    ]

    rows = [headers]
    for p in data["programs"]:
        rows.append([
            p["id"],
            p["hospital"],
            p["program_name"],
            p["region"],
            p["city"],
            p["bsn_required"],
            p.get("reputation", 0),
            f"{p.get('program_length_months', '?')} months",
            p.get("pay_range", ""),
            p.get("app_open_date", ""),
            p.get("app_close_date", ""),
            p.get("cohort_start", ""),
            "; ".join(p.get("specialty_units", [])),
            p.get("requirements", ""),
            p.get("application_url", ""),
            p.get("application_status", "Not Started"),
            p.get("personal_notes", ""),
            p.get("last_updated", ""),
        ])

    # Clear and write
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range="Programs!A:Z"
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Programs!A1",
        valueInputOption="RAW",
        body={"values": rows}
    ).execute()

    # Format header row
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.6}
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)"
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount"
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 18}
                    }
                }
            ]
        }
    ).execute()

    print(f"Synced {len(data['programs'])} programs to Google Sheets.")
    print(f"View at: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    data = load_data()
    command = sys.argv[1]

    if command == "csv":
        output = DEFAULT_CSV
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            if idx + 1 < len(sys.argv):
                output = sys.argv[idx + 1]
        export_csv(data, output)

    elif command == "sheets":
        if "--setup" in sys.argv:
            sheets_setup()
        else:
            export_sheets(data)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
