#!/usr/bin/env python3
"""
Google Sheets Setup Script for Skylark Drone Operations

This script helps you:
1. Connect to an existing Google Spreadsheet
2. Upload your CSV data to Google Sheets
3. Set up the connection for 2-way sync

Prerequisites:
1. Create a Google Cloud Project
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account and download credentials.json
4. Create a Google Spreadsheet manually and share it with the service account

Usage:
    python setup_google_sheets.py
"""

import os
import csv
import sys

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("❌ Required packages not installed. Run:")
    print("   pip install gspread google-auth")
    sys.exit(1)

# Configuration
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')

# CSV files
PILOT_CSV = 'pilot_roster.csv'
DRONE_CSV = 'drone_fleet.csv'
MISSIONS_CSV = 'missions.csv'


def get_google_client():
    """Initialize Google Sheets client."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Credentials file not found: {CREDENTIALS_FILE}")
        print("\nTo set up Google Sheets integration:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable 'Google Sheets API' and 'Google Drive API'")
        print("4. Go to 'Credentials' → 'Create Credentials' → 'Service Account'")
        print("5. Download the JSON key file and save as 'credentials.json'")
        print("6. Run this script again")
        sys.exit(1)
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def get_service_account_email():
    """Get the service account email from credentials file."""
    import json
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)
        return creds_data.get('client_email', 'unknown')


def open_spreadsheet_by_url(client, url):
    """Open a spreadsheet by URL."""
    try:
        spreadsheet = client.open_by_url(url)
        return spreadsheet
    except gspread.exceptions.SpreadsheetNotFound:
        return None
    except gspread.exceptions.APIError as e:
        if 'PERMISSION_DENIED' in str(e) or '403' in str(e):
            return "permission_denied"
        raise


def setup_pilot_roster(spreadsheet):
    """Create and populate Pilot Roster sheet."""
    # Check if sheet exists
    try:
        sheet = spreadsheet.worksheet("Pilot Roster")
        print("   Found existing 'Pilot Roster' sheet")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Pilot Roster", rows=100, cols=10)
        print("   Created 'Pilot Roster' sheet")
    
    # Clear existing data
    sheet.clear()
    
    # Read CSV and upload
    if os.path.exists(PILOT_CSV):
        with open(PILOT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
        
        if data:
            sheet.update(f'A1:H{len(data)}', data)
            print(f"   ✅ Uploaded {len(data)-1} pilots from {PILOT_CSV}")
    else:
        # Create header row
        headers = ['pilot_id', 'name', 'skills', 'certifications', 'location', 'status', 'current_assignment', 'available_from']
        sheet.update('A1:H1', [headers])
        print("   ⚠️  No CSV found, created empty sheet with headers")
    
    return sheet


def setup_drone_fleet(spreadsheet):
    """Create and populate Drone Fleet sheet."""
    try:
        sheet = spreadsheet.worksheet("Drone Fleet")
        print("   Found existing 'Drone Fleet' sheet")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Drone Fleet", rows=100, cols=10)
        print("   Created 'Drone Fleet' sheet")
    
    sheet.clear()
    
    if os.path.exists(DRONE_CSV):
        with open(DRONE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
        
        if data:
            sheet.update(f'A1:G{len(data)}', data)
            print(f"   ✅ Uploaded {len(data)-1} drones from {DRONE_CSV}")
    else:
        headers = ['drone_id', 'model', 'capabilities', 'status', 'location', 'current_assignment', 'maintenance_due']
        sheet.update('A1:G1', [headers])
        print("   ⚠️  No CSV found, created empty sheet with headers")
    
    return sheet


def setup_missions(spreadsheet):
    """Create and populate Missions sheet."""
    try:
        sheet = spreadsheet.worksheet("Missions")
        print("   Found existing 'Missions' sheet")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Missions", rows=100, cols=10)
        print("   Created 'Missions' sheet")
    
    sheet.clear()
    
    if os.path.exists(MISSIONS_CSV):
        with open(MISSIONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
        
        if data:
            sheet.update(f'A1:H{len(data)}', data)
            print(f"   ✅ Uploaded {len(data)-1} missions from {MISSIONS_CSV}")
    else:
        headers = ['project_id', 'client', 'location', 'required_skills', 'required_certs', 'start_date', 'end_date', 'priority']
        sheet.update('A1:H1', [headers])
        print("   ⚠️  No CSV found, created empty sheet with headers")
    
    return sheet


def remove_default_sheet(spreadsheet):
    """Remove the default 'Sheet1' if it exists."""
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default_sheet)
        print("   Removed default 'Sheet1'")
    except gspread.WorksheetNotFound:
        pass


def create_env_file(spreadsheet_id, service_account_email):
    """Create or update .env file with Google Sheets configuration."""
    env_content = f"""# Skylark Drone Operations - Environment Configuration

# OpenAI API Key (for AI chat functionality)
OPENAI_API_KEY=your_openai_api_key_here

# Google Sheets Configuration
GOOGLE_SHEET_ID={spreadsheet_id}
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
PILOT_ROSTER_TAB=Pilot Roster
DRONE_FLEET_TAB=Drone Fleet
MISSIONS_TAB=Missions

# Server Configuration
PORT=8000
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print(f"\n✅ Created .env file with Google Sheets configuration")


def main():
    print("=" * 60)
    print("🚁 Skylark Drone Operations - Google Sheets Setup")
    print("=" * 60)
    
    # Initialize client
    print("\n📡 Connecting to Google Sheets...")
    client = get_google_client()
    
    # Get service account email
    service_account_email = get_service_account_email()
    print(f"   Service Account: {service_account_email}")
    
    # Instructions for manual spreadsheet creation
    print("\n" + "=" * 60)
    print("📋 STEP 1: Create a Google Spreadsheet")
    print("=" * 60)
    print("""
1. Open Google Sheets: https://sheets.google.com
2. Click '+ Blank' to create a new spreadsheet
3. Name it: 'Skylark Drone Operations'
4. Copy the URL from your browser
   (It looks like: https://docs.google.com/spreadsheets/d/XXXXX/edit)
""")
    
    print("=" * 60)
    print("📋 STEP 2: Share with Service Account")
    print("=" * 60)
    print(f"""
1. In the spreadsheet, click 'Share' (top right)
2. Paste this email: {service_account_email}
3. Select 'Editor' permission
4. Uncheck 'Notify people'
5. Click 'Share'
""")
    
    # Get spreadsheet URL from user
    print("=" * 60)
    spreadsheet_url = input("📎 Paste your Google Spreadsheet URL here: ").strip()
    
    if not spreadsheet_url:
        print("❌ No URL provided. Exiting.")
        sys.exit(1)
    
    # Try to open the spreadsheet
    print("\n📊 Connecting to spreadsheet...")
    result = open_spreadsheet_by_url(client, spreadsheet_url)
    
    if result == "permission_denied":
        print(f"""
❌ Permission denied! The service account doesn't have access.

Please share the spreadsheet with:
   {service_account_email}

Make sure to:
1. Click 'Share' in Google Sheets
2. Add the email above
3. Select 'Editor' permission
4. Click 'Share'

Then run this script again.
""")
        sys.exit(1)
    
    if result is None:
        print("❌ Could not find spreadsheet. Please check the URL and try again.")
        sys.exit(1)
    
    spreadsheet = result
    print(f"   ✅ Connected to: {spreadsheet.title}")
    
    # Setup sheets
    print("\n📋 Setting up worksheets...")
    setup_pilot_roster(spreadsheet)
    setup_drone_fleet(spreadsheet)
    setup_missions(spreadsheet)
    remove_default_sheet(spreadsheet)
    
    # Create .env file
    create_env_file(spreadsheet.id, service_account_email)
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print(f"""
Your data has been uploaded to Google Sheets!

📊 Spreadsheet URL: {spreadsheet_url}
📋 Spreadsheet ID: {spreadsheet.id}

The spreadsheet now has 3 tabs:
  • Pilot Roster - {PILOT_CSV}
  • Drone Fleet - {DRONE_CSV}
  • Missions - {MISSIONS_CSV}

Next steps:

1. (Optional) Add your OpenAI API key to .env file:
   OPENAI_API_KEY=sk-...

2. Start the application:
   python main.py

3. Open http://localhost:8000 in your browser

The application will now read/write data directly to Google Sheets!
Any changes made through the chat interface will be synced to the spreadsheet.
Any changes you make directly in Google Sheets will appear in the app.
""")


if __name__ == "__main__":
    main()
