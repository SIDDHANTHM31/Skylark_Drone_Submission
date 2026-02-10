import os
import json
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date

# Try importing AI clients
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..models.schemas import (
    Pilot, Drone, Conflict, PilotStatus, DroneStatus,
    ChatMessage, UrgentReassignmentRequest
)
from .google_sheets_service import get_sheets_service
from .conflict_service import get_conflict_service
import logging

logger = logging.getLogger(__name__)


class AIAgentService:
    """AI-powered conversational agent for drone operations coordination."""
    
    def __init__(self):
        self.client = None
        self.model = None
        self.ai_provider = None
        self.ai_disabled_reason = None  # Track why AI is disabled
        
        # Try Gemini first (free tier available)
        gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if gemini_key and GEMINI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=gemini_key)
                self.model = 'gemini-2.5-flash'  # 2.0 has higher free tier limits (15 RPM vs 2 RPM)
                self.ai_provider = 'gemini'
                logger.info("✅ Using Google Gemini AI")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        
        # Fall back to OpenAI if Gemini not configured
        if not self.ai_provider:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key and openai_key != 'your_openai_api_key_here' and OPENAI_AVAILABLE:
                try:
                    self.client = OpenAI(api_key=openai_key)
                    self.ai_provider = 'openai'
                    logger.info("✅ Using OpenAI")
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI: {e}")
        
        if not self.ai_provider:
            logger.info("⚠️ No AI provider configured - running in demo mode")
            logger.info("   Add GEMINI_API_KEY or OPENAI_API_KEY to .env file")
        
        self.sheets_service = get_sheets_service()
        self.conflict_service = get_conflict_service()
        self.sessions: Dict[str, List[ChatMessage]] = {}
        self.gemini_chats: Dict[str, any] = {}  # Store Gemini chat sessions
        
        # Define available functions for the AI
        self.tools = self._define_tools()
        self.gemini_tools = self._define_gemini_tools()
        
        self.system_prompt = """You are an AI Drone Operations Coordinator for Skylark Drones. You help manage:

1. **Pilot Roster Management**: Track pilot availability, skills, certifications, and assignments
2. **Drone Fleet Management**: Monitor drone status, capabilities, locations, and maintenance
3. **Assignment Coordination**: Match pilots and drones to projects based on requirements
4. **Conflict Detection**: Identify scheduling conflicts, skill mismatches, and equipment issues
5. **Urgent Reassignments**: Handle emergency situations when pilots/drones become unavailable

Current date: {current_date}

When users ask questions, use the available functions to fetch real data. Be helpful, concise, and proactive about identifying potential issues.

For urgent reassignments, you should:
1. Understand the reason for reassignment (pilot sick, drone failure, emergency, etc.)
2. Find suitable replacements based on location, skills, and availability
3. Check for conflicts before recommending
4. Provide a clear action plan

Always format your responses clearly with bullet points or tables when showing lists of pilots/drones."""

    def _define_tools(self) -> List[dict]:
        """Define the tools/functions available to the AI agent (OpenAI format)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_all_pilots",
                    "description": "Get the complete list of all pilots with their details including status, skills, certifications, and current assignments",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_available_pilots",
                    "description": "Get list of available pilots, optionally filtered by skill level, certification, location, or drone model experience",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced", "Expert"], "description": "Minimum skill level required"},
                            "certification": {"type": "string", "description": "Required certification (e.g., 'DGCA RPC', 'Thermal Imaging')"},
                            "location": {"type": "string", "description": "Location to filter by (e.g., 'Mumbai', 'Delhi')"},
                            "drone_model": {"type": "string", "description": "Drone model the pilot should have experience with"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pilot_details",
                    "description": "Get detailed information about a specific pilot by their ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pilot_id": {"type": "string", "description": "The pilot's ID (e.g., 'P001')"}
                        },
                        "required": ["pilot_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_pilot_status",
                    "description": "Update a pilot's status (Available, On Leave, Unavailable, Assigned) and optionally their assignment details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pilot_id": {"type": "string", "description": "The pilot's ID"},
                            "status": {"type": "string", "enum": ["Available", "On Leave", "Unavailable", "Assigned"]},
                            "assignment": {"type": "string", "description": "Project name if assigning"},
                            "start_date": {"type": "string", "description": "Assignment start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "Assignment end date (YYYY-MM-DD)"}
                        },
                        "required": ["pilot_id", "status"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_drones",
                    "description": "Get the complete list of all drones with their details including status, capabilities, and assignments",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_available_drones",
                    "description": "Get list of available drones, optionally filtered by capability, location, or model",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "capability": {"type": "string", "description": "Required capability (e.g., 'Thermal Imaging', 'Mapping')"},
                            "location": {"type": "string", "description": "Location to filter by"},
                            "model": {"type": "string", "description": "Drone model to filter by"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_drone_details",
                    "description": "Get detailed information about a specific drone by its ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "drone_id": {"type": "string", "description": "The drone's ID (e.g., 'D001')"}
                        },
                        "required": ["drone_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_drone_status",
                    "description": "Update a drone's status (Available, Deployed, Maintenance, Unavailable) and optionally assignment details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "drone_id": {"type": "string", "description": "The drone's ID"},
                            "status": {"type": "string", "enum": ["Available", "Deployed", "Maintenance", "Unavailable"]},
                            "assignment": {"type": "string", "description": "Project name if deploying"},
                            "start_date": {"type": "string", "description": "Assignment start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "Assignment end date (YYYY-MM-DD)"}
                        },
                        "required": ["drone_id", "status"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "flag_drone_maintenance",
                    "description": "Flag a drone for maintenance with issue notes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "drone_id": {"type": "string", "description": "The drone's ID"},
                            "issue_notes": {"type": "string", "description": "Description of the maintenance issue"}
                        },
                        "required": ["drone_id", "issue_notes"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_projects",
                    "description": "Get list of all projects with their requirements, assignments, and status",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "detect_conflicts",
                    "description": "Run conflict detection to find all scheduling conflicts, skill mismatches, location issues, and maintenance problems",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_replacement_pilot",
                    "description": "Find suitable replacement pilots for an urgent reassignment based on project requirements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The project ID that needs a new pilot"},
                            "required_certifications": {"type": "array", "items": {"type": "string"}, "description": "List of required certifications"},
                            "required_skill_level": {"type": "string", "description": "Minimum skill level needed"},
                            "preferred_location": {"type": "string", "description": "Preferred location for the pilot"},
                            "exclude_pilot_id": {"type": "string", "description": "Pilot ID to exclude (the one being replaced)"}
                        },
                        "required": ["project_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_replacement_drone",
                    "description": "Find suitable replacement drones for an urgent reassignment based on project requirements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The project ID that needs a new drone"},
                            "required_capabilities": {"type": "array", "items": {"type": "string"}, "description": "List of required capabilities"},
                            "preferred_location": {"type": "string", "description": "Preferred location for the drone"},
                            "exclude_drone_id": {"type": "string", "description": "Drone ID to exclude (the one being replaced)"}
                        },
                        "required": ["project_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_reassignment",
                    "description": "Execute an urgent reassignment - updates pilot/drone status and assignment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_name": {"type": "string", "description": "The project name"},
                            "old_pilot_id": {"type": "string", "description": "ID of pilot being replaced (if any)"},
                            "new_pilot_id": {"type": "string", "description": "ID of replacement pilot (if any)"},
                            "old_drone_id": {"type": "string", "description": "ID of drone being replaced (if any)"},
                            "new_drone_id": {"type": "string", "description": "ID of replacement drone (if any)"},
                            "start_date": {"type": "string", "description": "Assignment start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "Assignment end date (YYYY-MM-DD)"},
                            "reason": {"type": "string", "description": "Reason for the reassignment"}
                        },
                        "required": ["project_name"]
                    }
                }
            }
        ]

    def _define_gemini_tools(self) -> List[dict]:
        """Define tools in Gemini format."""
        gemini_functions = []
        for tool in self.tools:
            func = tool["function"]
            gemini_functions.append({
                "name": func["name"],
                "description": func["description"],
                "parameters": func["parameters"]
            })
        return gemini_functions

    def _execute_function(self, function_name: str, arguments: dict) -> str:
        """Execute a function call and return the result as a string."""
        try:
            if function_name == "get_all_pilots":
                pilots = self.sheets_service.get_all_pilots()
                return json.dumps([p.model_dump() for p in pilots], default=str, indent=2)
            
            elif function_name == "get_available_pilots":
                pilots = self.sheets_service.get_available_pilots(
                    skill_level=arguments.get('skill_level'),
                    certification=arguments.get('certification'),
                    location=arguments.get('location'),
                    drone_model=arguments.get('drone_model')
                )
                return json.dumps([p.model_dump() for p in pilots], default=str, indent=2)
            
            elif function_name == "get_pilot_details":
                pilot = self.sheets_service.get_pilot_by_id(arguments['pilot_id'])
                if pilot:
                    return json.dumps(pilot.model_dump(), default=str, indent=2)
                return json.dumps({"error": f"Pilot {arguments['pilot_id']} not found"})
            
            elif function_name == "update_pilot_status":
                start_date = None
                end_date = None
                if arguments.get('start_date'):
                    start_date = datetime.strptime(arguments['start_date'], '%Y-%m-%d').date()
                if arguments.get('end_date'):
                    end_date = datetime.strptime(arguments['end_date'], '%Y-%m-%d').date()
                
                success = self.sheets_service.update_pilot_status(
                    pilot_id=arguments['pilot_id'],
                    status=arguments['status'],
                    assignment=arguments.get('assignment'),
                    start_date=start_date,
                    end_date=end_date
                )
                return json.dumps({"success": success, "message": f"Pilot status updated to {arguments['status']}" if success else "Failed to update"})
            
            elif function_name == "get_all_drones":
                drones = self.sheets_service.get_all_drones()
                return json.dumps([d.model_dump() for d in drones], default=str, indent=2)
            
            elif function_name == "get_available_drones":
                drones = self.sheets_service.get_available_drones(
                    capability=arguments.get('capability'),
                    location=arguments.get('location'),
                    model=arguments.get('model')
                )
                return json.dumps([d.model_dump() for d in drones], default=str, indent=2)
            
            elif function_name == "get_drone_details":
                drone = self.sheets_service.get_drone_by_id(arguments['drone_id'])
                if drone:
                    return json.dumps(drone.model_dump(), default=str, indent=2)
                return json.dumps({"error": f"Drone {arguments['drone_id']} not found"})
            
            elif function_name == "update_drone_status":
                start_date = None
                end_date = None
                if arguments.get('start_date'):
                    start_date = datetime.strptime(arguments['start_date'], '%Y-%m-%d').date()
                if arguments.get('end_date'):
                    end_date = datetime.strptime(arguments['end_date'], '%Y-%m-%d').date()
                
                success = self.sheets_service.update_drone_status(
                    drone_id=arguments['drone_id'],
                    status=arguments['status'],
                    assignment=arguments.get('assignment'),
                    start_date=start_date,
                    end_date=end_date
                )
                return json.dumps({"success": success, "message": f"Drone status updated to {arguments['status']}" if success else "Failed to update"})
            
            elif function_name == "flag_drone_maintenance":
                success = self.sheets_service.flag_maintenance_issue(
                    drone_id=arguments['drone_id'],
                    issue_notes=arguments['issue_notes']
                )
                return json.dumps({"success": success, "message": "Drone flagged for maintenance" if success else "Failed to flag"})
            
            elif function_name == "get_projects":
                projects = self.sheets_service.get_demo_projects()
                return json.dumps(projects, indent=2)
            
            elif function_name == "detect_conflicts":
                conflicts = self.conflict_service.detect_all_conflicts()
                return json.dumps([c.model_dump() for c in conflicts], default=str, indent=2)
            
            elif function_name == "find_replacement_pilot":
                return self._find_replacement_pilot(arguments)
            
            elif function_name == "find_replacement_drone":
                return self._find_replacement_drone(arguments)
            
            elif function_name == "execute_reassignment":
                return self._execute_reassignment(arguments)
            
            else:
                return json.dumps({"error": f"Unknown function: {function_name}"})
                
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return json.dumps({"error": str(e)})

    def _find_replacement_pilot(self, arguments: dict) -> str:
        """Find suitable replacement pilots based on project requirements."""
        project_id = arguments.get('project_id')
        required_certs = arguments.get('required_certifications', [])
        required_skill = arguments.get('required_skill_level', 'Intermediate')
        preferred_location = arguments.get('preferred_location')
        exclude_pilot_id = arguments.get('exclude_pilot_id')
        
        projects = self.sheets_service.get_demo_projects()
        project = next((p for p in projects if p['id'] == project_id), None)
        
        if project and not required_certs:
            required_certs = project.get('required_certifications', [])
        if project and not required_skill:
            required_skill = project.get('required_skill_level', 'Intermediate')
        if project and not preferred_location:
            preferred_location = project.get('location')
        
        all_pilots = self.sheets_service.get_all_pilots()
        candidates = []
        
        skill_order = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
        required_skill_idx = skill_order.index(required_skill) if required_skill in skill_order else 0
        
        for pilot in all_pilots:
            if pilot.id == exclude_pilot_id:
                continue
            if pilot.status != PilotStatus.AVAILABLE:
                continue
            
            score = 0
            issues = []
            
            missing_certs = [c for c in required_certs if c not in pilot.certifications]
            if missing_certs:
                issues.append(f"Missing certs: {', '.join(missing_certs)}")
            else:
                score += 30
            
            pilot_skill_idx = skill_order.index(pilot.skill_level) if pilot.skill_level in skill_order else 0
            if pilot_skill_idx >= required_skill_idx:
                score += 25
            else:
                issues.append(f"Skill level {pilot.skill_level} below required {required_skill}")
            
            if preferred_location and pilot.current_location.lower() == preferred_location.lower():
                score += 25
            elif preferred_location:
                issues.append(f"In {pilot.current_location}, not {preferred_location}")
            
            score += pilot_skill_idx * 5
            
            candidates.append({
                "pilot": pilot.model_dump(),
                "score": score,
                "issues": issues,
                "recommended": len(issues) == 0
            })
        
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return json.dumps({
            "project_id": project_id,
            "required_certifications": required_certs,
            "required_skill_level": required_skill,
            "preferred_location": preferred_location,
            "candidates": candidates[:5]
        }, default=str, indent=2)

    def _find_replacement_drone(self, arguments: dict) -> str:
        """Find suitable replacement drones based on project requirements."""
        project_id = arguments.get('project_id')
        required_caps = arguments.get('required_capabilities', [])
        preferred_location = arguments.get('preferred_location')
        exclude_drone_id = arguments.get('exclude_drone_id')
        
        projects = self.sheets_service.get_demo_projects()
        project = next((p for p in projects if p['id'] == project_id), None)
        
        if project and not required_caps:
            required_caps = project.get('required_capabilities', [])
        if project and not preferred_location:
            preferred_location = project.get('location')
        
        all_drones = self.sheets_service.get_all_drones()
        candidates = []
        
        for drone in all_drones:
            if drone.id == exclude_drone_id:
                continue
            if drone.status != DroneStatus.AVAILABLE:
                continue
            
            score = 0
            issues = []
            
            missing_caps = [c for c in required_caps if c not in drone.capabilities]
            if missing_caps:
                issues.append(f"Missing capabilities: {', '.join(missing_caps)}")
            else:
                score += 40
            
            if preferred_location and drone.current_location.lower() == preferred_location.lower():
                score += 30
            elif preferred_location:
                issues.append(f"In {drone.current_location}, not {preferred_location}")
            
            score += len(drone.capabilities) * 2
            
            candidates.append({
                "drone": drone.model_dump(),
                "score": score,
                "issues": issues,
                "recommended": len(issues) == 0
            })
        
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return json.dumps({
            "project_id": project_id,
            "required_capabilities": required_caps,
            "preferred_location": preferred_location,
            "candidates": candidates[:5]
        }, default=str, indent=2)

    def _execute_reassignment(self, arguments: dict) -> str:
        """Execute an urgent reassignment."""
        project_name = arguments.get('project_name')
        old_pilot_id = arguments.get('old_pilot_id')
        new_pilot_id = arguments.get('new_pilot_id')
        old_drone_id = arguments.get('old_drone_id')
        new_drone_id = arguments.get('new_drone_id')
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        reason = arguments.get('reason', 'Urgent reassignment')
        
        results = {"success": True, "actions": []}
        
        try:
            if old_pilot_id:
                self.sheets_service.update_pilot_status(old_pilot_id, "Available")
                results["actions"].append(f"Released pilot {old_pilot_id} from assignment")
            
            if new_pilot_id:
                start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
                end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
                self.sheets_service.update_pilot_status(
                    new_pilot_id, "Assigned", project_name, start, end
                )
                results["actions"].append(f"Assigned pilot {new_pilot_id} to {project_name}")
            
            if old_drone_id:
                self.sheets_service.update_drone_status(old_drone_id, "Available")
                results["actions"].append(f"Released drone {old_drone_id} from deployment")
            
            if new_drone_id:
                start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
                end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
                self.sheets_service.update_drone_status(
                    new_drone_id, "Deployed", project_name, start, end
                )
                results["actions"].append(f"Deployed drone {new_drone_id} to {project_name}")
            
            results["reason"] = reason
            
        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
        
        return json.dumps(results, indent=2)

    def create_session(self) -> str:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = []
        return session_id

    def get_session_history(self, session_id: str) -> List[ChatMessage]:
        """Get chat history for a session."""
        return self.sessions.get(session_id, [])

    def _generate_fallback_response(self, message: str) -> str:
        """Generate a simple response when no AI is available."""
        message_lower = message.lower()
        
        if 'pilot' in message_lower and ('available' in message_lower or 'list' in message_lower or 'show' in message_lower):
            pilots = self.sheets_service.get_available_pilots()
            if pilots:
                response = "**Available Pilots:**\n\n"
                for p in pilots:
                    response += f"• **{p.name}** ({p.id}) - {p.skill_level}, {p.current_location}\n"
                    response += f"  Certifications: {', '.join(p.certifications)}\n"
                return response
            return "No pilots are currently available."
        
        elif 'drone' in message_lower and ('available' in message_lower or 'list' in message_lower or 'show' in message_lower):
            drones = self.sheets_service.get_available_drones()
            if drones:
                response = "**Available Drones:**\n\n"
                for d in drones:
                    response += f"• **{d.model}** ({d.id}) - {d.current_location}\n"
                    response += f"  Capabilities: {', '.join(d.capabilities)}\n"
                return response
            return "No drones are currently available."
        
        elif 'conflict' in message_lower or 'issue' in message_lower or 'problem' in message_lower:
            conflicts = self.conflict_service.detect_all_conflicts()
            if conflicts:
                response = f"**Found {len(conflicts)} Conflicts:**\n\n"
                for c in conflicts:
                    response += f"• **{c.type.value}** ({c.severity.value}): {c.description}\n"
                return response
            return "No conflicts detected. All systems operational!"
        
        elif 'project' in message_lower:
            projects = self.sheets_service.get_demo_projects()
            response = "**Current Projects:**\n\n"
            for p in projects:
                response += f"• **{p['name']}** ({p['id']}) - {p['status']}\n"
                response += f"  Location: {p['location']}, Dates: {p['start_date']} to {p['end_date']}\n"
            return response
        
        elif 'help' in message_lower:
            return """**I can help you with:**

• **Pilots**: "Show available pilots", "List all pilots"
• **Drones**: "Show available drones", "List all drones"  
• **Conflicts**: "Check for conflicts", "Any issues?"
• **Projects**: "Show projects", "List projects"

⚠️ **Note**: Running in demo mode. Add `GEMINI_API_KEY` to your .env file for full AI capabilities."""
        
        return """I'm running in demo mode with limited capabilities.

Try asking:
• "Show available pilots"
• "Show available drones"
• "Check for conflicts"
• "Show projects"

💡 **Tip**: Add `GEMINI_API_KEY` to your .env file for full AI-powered conversations!"""

    async def chat(self, message: str, session_id: Optional[str] = None) -> Tuple[str, str, List[dict]]:
        """Process a chat message and return AI response."""
        # Create session if not provided
        if not session_id:
            session_id = self.create_session()
        elif session_id not in self.sessions:
            self.sessions[session_id] = []
        
        # Add user message to history
        user_message = ChatMessage(role="user", content=message)
        self.sessions[session_id].append(user_message)
        
        function_calls = []
        
        # No AI provider or temporarily disabled - use fallback
        if not self.ai_provider or self.ai_disabled_reason:
            response_text = self._generate_fallback_response(message)
            if self.ai_disabled_reason:
                response_text += f"\n\n⚠️ *AI temporarily unavailable: {self.ai_disabled_reason}*"
            assistant_message = ChatMessage(role="assistant", content=response_text)
            self.sessions[session_id].append(assistant_message)
            return response_text, session_id, function_calls
        
        try:
            if self.ai_provider == 'gemini':
                response_text, function_calls = await self._chat_with_gemini(session_id, message)
            else:
                response_text, function_calls = await self._chat_with_openai(session_id, message)
            
            assistant_message = ChatMessage(role="assistant", content=response_text)
            self.sessions[session_id].append(assistant_message)
            return response_text, session_id, function_calls
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"AI chat error: {e}")
            
            # Check for quota/rate limit errors and fall back to demo mode
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower() or 'rate' in error_str.lower():
                logger.warning("API quota exceeded - falling back to demo mode")
                self.ai_disabled_reason = "API quota exceeded. Using demo mode until quota resets."
                
                response_text = self._generate_fallback_response(message)
                response_text += "\n\n⚠️ *AI quota temporarily exceeded. Running in demo mode with basic responses. Your quota will reset shortly.*"
                
                assistant_message = ChatMessage(role="assistant", content=response_text)
                self.sessions[session_id].append(assistant_message)
                return response_text, session_id, []
            
            error_response = f"I encountered an error processing your request. Please try again. (Error: {str(e)[:100]})"
            return error_response, session_id, []

    async def _chat_with_gemini(self, session_id: str, message: str) -> Tuple[str, List[dict]]:
        """Handle chat with Gemini AI."""
        function_calls = []
        
        # Build conversation history for context
        history_text = ""
        for msg in self.sessions[session_id][-10:]:  # Last 10 messages for context
            if msg.role == "user":
                history_text += f"User: {msg.content}\n"
            else:
                history_text += f"Assistant: {msg.content}\n"
        
        # Create the prompt with system instructions and available functions
        system_prompt = self.system_prompt.format(current_date=date.today().isoformat())
        
        functions_description = """
Available functions you can call:
- get_all_pilots(): Get all pilots
- get_available_pilots(skill_level?, certification?, location?, drone_model?): Get available pilots with optional filters
- get_pilot_details(pilot_id): Get details for a specific pilot
- update_pilot_status(pilot_id, status, assignment?, start_date?, end_date?): Update pilot status
- get_all_drones(): Get all drones
- get_available_drones(capability?, location?, model?): Get available drones with optional filters
- get_drone_details(drone_id): Get details for a specific drone
- update_drone_status(drone_id, status, assignment?, start_date?, end_date?): Update drone status
- flag_drone_maintenance(drone_id, issue_notes): Flag drone for maintenance
- get_projects(): Get all projects
- detect_conflicts(): Detect scheduling and assignment conflicts
- find_replacement_pilot(project_id, ...): Find replacement pilots
- find_replacement_drone(project_id, ...): Find replacement drones
- execute_reassignment(project_name, ...): Execute a reassignment

To call a function, respond with JSON in this format:
{"function_call": {"name": "function_name", "arguments": {...}}}

After receiving function results, provide a helpful response to the user.
"""
        
        full_prompt = f"""{system_prompt}

{functions_description}

{history_text}
User: {message}

If you need data to answer the question, call the appropriate function. Otherwise, respond directly."""

        # Initial response from Gemini using the new SDK
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt
        )
        response_text = response.text
        
        # Check if Gemini wants to call a function
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Try to parse function call from response
            try:
                # Look for JSON function call in response
                if '{"function_call"' in response_text:
                    import re
                    json_match = re.search(r'\{"function_call":\s*\{[^}]+\}\}', response_text)
                    if json_match:
                        func_call = json.loads(json_match.group())
                        func_name = func_call["function_call"]["name"]
                        func_args = func_call["function_call"].get("arguments", {})
                        
                        # Execute the function
                        result = self._execute_function(func_name, func_args)
                        function_calls.append({
                            "name": func_name,
                            "arguments": func_args,
                            "result": result
                        })
                        
                        # Get follow-up response with function result
                        follow_up_prompt = f"""{full_prompt}

I called the function {func_name} and got this result:
{result}

Now provide a helpful response to the user based on this data. Do not call another function unless absolutely necessary."""
                        
                        response = self.client.models.generate_content(
                            model=self.model,
                            contents=follow_up_prompt
                        )
                        response_text = response.text
                        continue
            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"No function call found in response: {e}")
            
            # No more function calls needed
            break
        
        # Clean up any remaining function call JSON from the response
        response_text = response_text.replace('{"function_call"', '').strip()
        if response_text.startswith('{') and '"name"' in response_text:
            # Response is just a function call, need to process it
            response_text = "I apologize, but I couldn't complete that request. Please try rephrasing your question."
        
        return response_text, function_calls

    async def _chat_with_openai(self, session_id: str, message: str) -> Tuple[str, List[dict]]:
        """Handle chat with OpenAI."""
        function_calls = []
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": self.system_prompt.format(current_date=date.today().isoformat())}
        ]
        
        # Add conversation history
        for msg in self.sessions[session_id][-10:]:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Initial API call
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            tools=self.tools,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        # Process tool calls if any
        while assistant_message.tool_calls:
            messages.append(assistant_message)
            
            for tool_call in assistant_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                result = self._execute_function(func_name, func_args)
                function_calls.append({
                    "name": func_name,
                    "arguments": func_args,
                    "result": result
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            # Get next response
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )
            assistant_message = response.choices[0].message
        
        return assistant_message.content, function_calls


# Singleton instance
_agent_service = None

def get_agent_service() -> AIAgentService:
    """Get the singleton agent service instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AIAgentService()
    return _agent_service

def reset_agent_service():
    """Reset the agent service to pick up new API keys or clear disabled state."""
    global _agent_service
    _agent_service = None
    return get_agent_service()
