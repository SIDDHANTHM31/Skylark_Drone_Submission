# Google Cloud Setup Guide for Skylark Drone Operations

This guide will walk you through setting up Google Cloud credentials to enable 2-way sync with Google Sheets.

## Step 1: Create a Google Cloud Project

1. **Open Google Cloud Console**
   - Go to: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create a New Project**
   - Click the project dropdown at the top of the page (next to "Google Cloud")
   - Click **"New Project"** in the popup
   - Enter these details:
     - **Project name**: `Skylark-Drone-Operations`
     - **Organization**: Leave as default (or select your organization)
   - Click **"Create"**
   - Wait for the project to be created (you'll see a notification)

3. **Select Your Project**
   - Click the project dropdown again
   - Select **"Skylark-Drone-Operations"** from the list

---

## Step 2: Enable Google Sheets API

1. **Go to API Library**
   - In the left sidebar, click **"APIs & Services"** → **"Library"**
   - Or go directly to: https://console.cloud.google.com/apis/library

2. **Search for Google Sheets API**
   - In the search box, type: `Google Sheets API`
   - Click on **"Google Sheets API"** in the results

3. **Enable the API**
   - Click the blue **"Enable"** button
   - Wait for it to be enabled

---

## Step 3: Enable Google Drive API

1. **Go Back to API Library**
   - Click **"APIs & Services"** → **"Library"** again

2. **Search for Google Drive API**
   - In the search box, type: `Google Drive API`
   - Click on **"Google Drive API"** in the results

3. **Enable the API**
   - Click the blue **"Enable"** button
   - Wait for it to be enabled

---

## Step 4: Create a Service Account

1. **Go to Credentials**
   - In the left sidebar, click **"APIs & Services"** → **"Credentials"**
   - Or go to: https://console.cloud.google.com/apis/credentials

2. **Create Service Account**
   - Click **"+ Create Credentials"** at the top
   - Select **"Service Account"**

3. **Fill in Service Account Details**
   - **Service account name**: `skylark-sheets-service`
   - **Service account ID**: (auto-filled based on name)
   - **Description**: `Service account for Skylark Drone Operations Google Sheets sync`
   - Click **"Create and Continue"**

4. **Skip Optional Steps**
   - For "Grant this service account access to project" - click **"Continue"** (skip)
   - For "Grant users access to this service account" - click **"Done"** (skip)

---

## Step 5: Create and Download the JSON Key

1. **Click on the Service Account**
   - In the Credentials page, under "Service Accounts", click on the service account you just created
   - (It will be named something like `skylark-sheets-service@skylark-drone-operations.iam.gserviceaccount.com`)

2. **Go to Keys Tab**
   - Click the **"Keys"** tab at the top

3. **Create a New Key**
   - Click **"Add Key"** → **"Create new key"**
   - Select **"JSON"** format
   - Click **"Create"**

4. **Save the File**
   - A JSON file will be automatically downloaded
   - **IMPORTANT**: Rename this file to `credentials.json`
   - Move it to your project folder: `/Users/siddhanthm/Documents/Skylark_drones/credentials.json`

---

## Step 6: Note the Service Account Email

After creating the service account, note down the email address. It looks like:
```
skylark-sheets-service@skylark-drone-operations.iam.gserviceaccount.com
```

You'll need this email to share your Google Spreadsheet with the service account.

---

## Step 7: Run the Setup Script

Once you have the `credentials.json` file in place, run:

```bash
cd /Users/siddhanthm/Documents/Skylark_drones
source venv/bin/activate
python setup_google_sheets.py
```

This will:
1. Create a new Google Spreadsheet
2. Upload your CSV data
3. Generate the `.env` file
4. Show you the spreadsheet URL and service account email

---

## Step 8: Share the Spreadsheet

1. Open the Google Sheets URL shown by the setup script
2. Click the **"Share"** button (top right)
3. In the "Add people and groups" field, paste the service account email
4. Select **"Editor"** permission
5. Uncheck "Notify people"
6. Click **"Share"**

---

## Troubleshooting

### "credentials.json not found"
- Make sure you downloaded the JSON key file
- Make sure it's renamed to exactly `credentials.json`
- Make sure it's in the project root folder: `/Users/siddhanthm/Documents/Skylark_drones/`

### "Google Sheets API has not been used in project"
- Go back to Step 2 and make sure you enabled the Google Sheets API
- Make sure you're in the correct project

### "The caller does not have permission"
- Make sure you shared the spreadsheet with the service account email
- Make sure you gave it "Editor" access, not "Viewer"

### "invalid_grant" error
- The service account key might be corrupted
- Delete the key in Google Cloud Console and create a new one

---

## Quick Links

- Google Cloud Console: https://console.cloud.google.com/
- API Library: https://console.cloud.google.com/apis/library
- Credentials: https://console.cloud.google.com/apis/credentials

---

## What the credentials.json file looks like

Your `credentials.json` file should look something like this (with different values):

```json
{
  "type": "service_account",
  "project_id": "skylark-drone-operations",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "skylark-sheets-service@skylark-drone-operations.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

If your file doesn't have these fields, you may have downloaded the wrong type of credentials.
