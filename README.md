# 🚁 Skylark Drone Operations Coordinator

An AI-powered assistant for managing drone operations, pilot assignments, and fleet coordination with **2-way Google Sheets sync**.

## 🎯 Features

- **Pilot Roster Management**: Query pilots by skill, certification, location
- **Drone Fleet Tracking**: Monitor availability, capabilities, maintenance status
- **Mission/Project Management**: Track assignments and requirements
- **Conflict Detection**: Automatic detection of scheduling conflicts, skill mismatches
- **AI Chat Interface**: Natural language queries powered by OpenAI
- **2-Way Google Sheets Sync**: Data syncs bidirectionally with Google Sheets

## 📊 Data Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│   Google Sheets     │◄───────►│   Application       │
│  (Primary Data)     │  2-way  │   (FastAPI)         │
│                     │  sync   │                     │
│  • Pilot Roster     │         │  • AI Chat Agent    │
│  • Drone Fleet      │         │  • Conflict Detection│
│  • Missions         │         │  • Dashboard        │
└─────────────────────┘         └─────────────────────┘
         │
         ▼
   Edit directly in
   Google Sheets UI
   (changes reflect
    in app immediately)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd Skylark_drones
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up Google Sheets (Required for Full Functionality)

#### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Sheets API** and **Google Drive API**

#### Step 2: Create Service Account
1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **Service Account**
3. Name it (e.g., "skylark-drone-ops")
4. Click **Create and Continue** → **Done**
5. Click on the service account → **Keys** tab
6. **Add Key** → **Create new key** → **JSON**
7. Save the downloaded file as `credentials.json` in the project folder

#### Step 3: Run Setup Script
```bash
python setup_google_sheets.py
```

This will:
- Create a new Google Spreadsheet
- Upload your CSV data to three sheets (Pilot Roster, Drone Fleet, Missions)
- Generate a `.env` file with the configuration

#### Step 4: Share the Spreadsheet
1. Open the Google Sheets URL shown by the setup script
2. Click **Share**
3. Add the service account email (shown in setup output)
4. Give **Editor** access

### 3. (Optional) Add OpenAI API Key

For full AI chat functionality, add your OpenAI API key to `.env`:

```env
OPENAI_API_KEY=sk-your-key-here
```

### 4. Start the Application

```bash
python main.py
```

Open http://localhost:8000 in your browser.

## 📁 Project Structure

```
Skylark_drones/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── setup_google_sheets.py  # Google Sheets setup script
├── credentials.json        # Google service account (you create this)
├── .env                    # Environment variables (auto-generated)
│
├── pilot_roster.csv        # Initial pilot data
├── drone_fleet.csv         # Initial drone data  
├── missions.csv            # Initial mission data
│
├── app/
│   ├── models/schemas.py   # Pydantic data models
│   ├── routers/            # API endpoints
│   │   ├── pilots.py
│   │   └── drones.py
│   └── services/
│       ├── google_sheets_service.py  # Google Sheets 2-way sync
│       ├── agent_service.py          # AI chat agent
│       └── conflict_service.py       # Conflict detection
│
├── templates/index.html    # Chat UI
└── docs/DECISION_LOG.md    # Design decisions
```

## 🔄 2-Way Sync Explained

### App → Google Sheets
When you use the chat interface to:
- Assign a pilot to a project
- Flag a drone for maintenance
- Update any status

The change is **immediately written** to Google Sheets.

### Google Sheets → App
When you edit the spreadsheet directly:
- Add a new pilot row
- Change a drone's status
- Modify mission details

The app **reads fresh data** on every request, so changes appear immediately.

## 💬 Example Chat Commands

```
"Show me available pilots"
"Which drones have thermal imaging capability?"
"Find pilots in Bangalore with DGCA certification"
"Assign pilot P001 to project PRJ002"
"Flag drone D002 for maintenance"
"What conflicts do we have?"
"I need an urgent reassignment for Project-A"
```

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat UI interface |
| `/api/chat` | POST | Send message to AI agent |
| `/api/dashboard` | GET | Summary statistics |
| `/api/pilots` | GET | List all pilots |
| `/api/pilots/available` | GET | List available pilots |
| `/api/drones` | GET | List all drones |
| `/api/drones/available` | GET | List available drones |
| `/api/conflicts` | GET | Detect conflicts |
| `/api/projects` | GET | List all missions |
| `/api/connection` | GET | Check Google Sheets connection |

## 🛠️ Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_SHEET_ID` | Google Spreadsheet ID | Yes (for Sheets sync) |
| `GOOGLE_SHEETS_CREDENTIALS_FILE` | Path to credentials.json | Yes (for Sheets sync) |
| `OPENAI_API_KEY` | OpenAI API key | No (fallback mode available) |
| `PILOT_ROSTER_TAB` | Sheet tab name for pilots | No (default: "Pilot Roster") |
| `DRONE_FLEET_TAB` | Sheet tab name for drones | No (default: "Drone Fleet") |
| `MISSIONS_TAB` | Sheet tab name for missions | No (default: "Missions") |

## 📋 CSV Data Format

### pilot_roster.csv
```csv
pilot_id,name,skills,certifications,location,status,current_assignment,available_from
P001,Arjun,"Mapping, Survey","DGCA, Night Ops",Bangalore,Available,–,2/5/26
```

### drone_fleet.csv
```csv
drone_id,model,capabilities,status,location,current_assignment,maintenance_due
D001,DJI M300,"LiDAR, RGB",Available,Bangalore,–,3/1/26
```

### missions.csv
```csv
project_id,client,location,required_skills,required_certs,start_date,end_date,priority
PRJ001,Client A,Bangalore,Mapping,DGCA,2/6/26,2/8/26,High
```

## 🚀 Deployment

### Replit
The project includes `.replit` configuration. Just import and run.

### Railway/Render
Uses the `Procfile` for deployment:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Heroku
```bash
heroku create skylark-drone-ops
heroku config:set GOOGLE_SHEET_ID=your-sheet-id
heroku config:set OPENAI_API_KEY=your-key
git push heroku main
```

## 📝 License

MIT License
