from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers
from app.routers import pilots, drones
from app.services.agent_service import get_agent_service, reset_agent_service
from app.services.conflict_service import get_conflict_service
from app.services.google_sheets_service import get_sheets_service
from app.models.schemas import ChatRequest, ChatResponse, Conflict, PilotStatus, DroneStatus

# Create FastAPI app
app = FastAPI(
    title="Skylark Drone Operations Coordinator",
    description="AI-powered drone operations coordination system with Google Sheets integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(pilots.router)
app.include_router(drones.router)


@app.on_event("startup")
async def startup_event():
    """Log startup information and connection status."""
    sheets = get_sheets_service()
    conn_info = sheets.get_connection_info()
    
    logger.info("=" * 60)
    logger.info("🚁 Skylark Drone Operations Coordinator")
    logger.info("=" * 60)
    logger.info(f"Data Source: {conn_info['mode']}")
    
    if conn_info.get('connected'):
        logger.info(f"📊 Google Sheets URL: {conn_info.get('spreadsheet_url')}")
        logger.info(f"🔄 Sync Mode: {conn_info.get('sync')}")
    else:
        logger.info("⚠️  Running in DEMO mode (CSV files)")
        logger.info("   To enable Google Sheets, run: python setup_google_sheets.py")
    
    logger.info("=" * 60)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main chat interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return AI response."""
    agent = get_agent_service()
    response_text, session_id, actions = await agent.chat(
        message=request.message,
        session_id=request.session_id
    )
    
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        actions_taken=actions
    )


@app.get("/api/conflicts", response_model=list[Conflict])
async def get_conflicts():
    """Detect and return all current conflicts."""
    service = get_conflict_service()
    return service.detect_all_conflicts()


@app.get("/api/projects")
async def get_projects():
    """Get all projects/missions."""
    sheets = get_sheets_service()
    return sheets.get_demo_projects()


@app.get("/api/dashboard")
async def get_dashboard():
    """Get dashboard summary data."""
    sheets = get_sheets_service()
    conflict_service = get_conflict_service()
    
    pilots = sheets.get_all_pilots()
    drones = sheets.get_all_drones()
    projects = sheets.get_demo_projects()
    conflicts = conflict_service.detect_all_conflicts()
    
    return {
        "pilots": {
            "total": len(pilots),
            "available": len([p for p in pilots if p.status == PilotStatus.AVAILABLE]),
            "assigned": len([p for p in pilots if p.status == PilotStatus.ASSIGNED]),
            "on_leave": len([p for p in pilots if p.status == PilotStatus.ON_LEAVE]),
        },
        "drones": {
            "total": len(drones),
            "available": len([d for d in drones if d.status == DroneStatus.AVAILABLE]),
            "deployed": len([d for d in drones if d.status == DroneStatus.DEPLOYED]),
            "maintenance": len([d for d in drones if d.status == DroneStatus.MAINTENANCE]),
        },
        "projects": {
            "total": len(projects),
            "active": len([p for p in projects if p.get('status') == 'Active']),
            "pending": len([p for p in projects if 'Pending' in p.get('status', '')]),
        },
        "conflicts": {
            "total": len(conflicts),
            "critical": len([c for c in conflicts if c.severity == 'Critical']),
            "high": len([c for c in conflicts if c.severity == 'High']),
            "medium": len([c for c in conflicts if c.severity == 'Medium']),
        },
        "connection": sheets.get_connection_info()
    }


@app.get("/api/connection")
async def get_connection_status():
    """Get current data source connection status."""
    sheets = get_sheets_service()
    return sheets.get_connection_info()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    sheets = get_sheets_service()
    return {
        "status": "healthy", 
        "service": "Skylark Drone Operations Coordinator",
        "data_source": sheets.get_connection_info()
    }


@app.post("/api/reset-ai")
async def reset_ai_service():
    """Reset the AI service to pick up new API keys or clear disabled state."""
    agent = reset_agent_service()
    return {
        "status": "reset",
        "ai_provider": agent.ai_provider,
        "ai_disabled_reason": agent.ai_disabled_reason,
        "message": f"AI service reset. Provider: {agent.ai_provider or 'None (demo mode)'}"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
