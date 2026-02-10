# Decision Log - Skylark Drone Operations Coordinator

## Overview
This document outlines key architectural decisions, trade-offs, and assumptions made during development of the AI Drone Operations Coordinator agent.

---

## Key Assumptions

### 1. Data Model Assumptions
- **Pilot IDs** follow format `P001`, `P002`, etc.
- **Drone IDs** follow format `D001`, `D002`, etc.
- **Certifications** are standardized strings (e.g., "DGCA RPC", "Thermal Imaging")
- **Skill levels** are ordered: Beginner < Intermediate < Advanced < Expert
- **One pilot per assignment** at a time (no multi-pilot assignments modeled)

### 2. Operational Assumptions
- Assignments have discrete start/end dates (no partial-day assignments)
- Location matching is city-level (not GPS coordinates)
- Maintenance status means drone is completely unavailable
- "On Leave" pilots cannot be assigned regardless of dates

### 3. Google Sheets Assumptions
- Sheet structure follows predefined column order
- Service account has edit permissions
- Data is updated in real-time (no caching layer)

---

## Trade-offs Chosen

### 1. Demo Data vs. Database
**Decision**: Built-in demo data with optional Google Sheets sync

**Why**: 
- Allows immediate testing without external setup
- Google Sheets provides familiar interface for non-technical users
- Avoids database setup complexity for a 6-hour project

**Trade-off**: No persistent storage in demo mode; data resets on restart

### 2. OpenAI Function Calling vs. Custom NLP
**Decision**: Use OpenAI's function calling with GPT-4

**Why**:
- Natural language understanding out-of-the-box
- Structured function outputs reduce parsing errors
- Handles ambiguous queries gracefully
- Maintains conversation context

**Trade-off**: 
- Requires API key and incurs costs
- Latency depends on OpenAI API response time
- Fallback mode has limited conversational ability

### 3. Single-Page Chat UI vs. Multi-Page Dashboard
**Decision**: Combined chat interface with dashboard summary

**Why**:
- Conversational interface is the primary interaction mode
- Dashboard provides at-a-glance status without switching contexts
- Reduces complexity for MVP

**Trade-off**: Less detailed views for individual pilots/drones (must ask agent)

### 4. Synchronous Conflict Detection vs. Background Jobs
**Decision**: Run conflict detection on-demand

**Why**:
- Simpler architecture
- Always returns current state
- Adequate for expected data volumes (<100 pilots/drones)

**Trade-off**: May be slow with very large datasets

### 5. Stateless Sessions vs. Persistent Chat History
**Decision**: In-memory session storage

**Why**:
- Sufficient for single-user demo
- No database dependency
- Sessions persist during runtime

**Trade-off**: Chat history lost on server restart

---

## Interpretation: "Urgent Reassignments"

### My Interpretation
An urgent reassignment occurs when an active project suddenly loses its assigned pilot or drone and needs an immediate replacement. This could happen due to:

1. **Pilot unavailability**: Sickness, emergency, sudden leave
2. **Drone failure**: Mechanical issues, crash, unexpected maintenance
3. **Client request**: Scope change requiring different capabilities
4. **External factors**: Weather, regulatory issues at location

### Implementation Approach

The agent handles urgent reassignments through a **guided workflow**:

1. **Intake**: Understand the reason and affected project
2. **Analysis**: Identify what's needed (certifications, capabilities, location)
3. **Search**: Find suitable replacements with scoring algorithm
4. **Validation**: Check for conflicts before recommending
5. **Execution**: Update statuses and create audit trail

**Scoring Algorithm** for replacement candidates:
- +30 points: Has all required certifications/capabilities
- +25 points: Meets skill level requirement
- +25 points: Same location as project
- +5 points per skill level above minimum
- -10 points: High flight hours (drone) indicating wear

**Example Interaction**:
```
User: "Pilot P002 is sick, need replacement for Project Alpha"

Agent: 
1. Fetches Project Alpha requirements
2. Searches available pilots matching criteria
3. Scores and ranks candidates
4. Presents top 3 options with trade-offs
5. On confirmation, executes reassignment
```

---

## What I'd Do Differently With More Time

### 1. Persistent Database
Replace in-memory storage with PostgreSQL or MongoDB for:
- Persistent data across restarts
- Better query performance
- Transaction support for reassignments

### 2. Real-time Notifications
Add WebSocket support for:
- Instant conflict alerts
- Assignment update notifications
- Dashboard auto-refresh

### 3. Advanced Scheduling
Implement:
- Calendar view for assignments
- Drag-and-drop reassignments
- Availability forecasting

### 4. Approval Workflows
Add:
- Multi-step approval for reassignments
- Manager notifications
- Audit log UI

### 5. Enhanced Conflict Resolution
- Suggest resolutions automatically
- One-click conflict fixes
- Conflict severity trends over time

### 6. Mobile-Responsive UI
- Better mobile chat experience
- Push notifications
- Offline capability for field use

### 7. Analytics Dashboard
- Pilot utilization metrics
- Drone flight hour tracking
- Project timeline Gantt charts

### 8. Integration Ecosystem
- Slack/Teams notifications
- Calendar sync (Google/Outlook)
- SMS alerts for urgent issues

---

## Technical Debt Acknowledged

1. **Error handling**: Could be more granular with specific error types
2. **Test coverage**: No automated tests (time constraint)
3. **Input validation**: Relies heavily on Pydantic; could add more business rules
4. **Rate limiting**: No protection against API abuse
5. **Logging**: Basic logging; could add structured logging with correlation IDs

---

## Security Considerations

For production deployment:
- [ ] Add authentication (OAuth2/JWT)
- [ ] Implement role-based access control
- [ ] Encrypt sensitive data at rest
- [ ] Add API rate limiting
- [ ] Audit logging for all changes
- [ ] Input sanitization for XSS prevention

---

*Document Version: 1.0*
*Last Updated: February 2026*
