import asyncio
import json
import os
import uuid
from typing import Dict, List, Any
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(title="Job Scout Freelance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for SSE queues
job_queues: Dict[str, asyncio.Queue] = {}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OPP_JSON_PATH = os.path.join(OUTPUT_DIR, "opportunities.json")

async def run_scan_pipeline(job_id: str):
    """Simulates a background scanning pipeline."""
    queue = job_queues.get(job_id)
    if not queue:
        return
    
    steps = [
        "Initializing precision scan...",
        "Connecting to intelligence network...",
        "Scanning target platforms (LinkedIn, X)...",
        "Extracting potential leads...",
        "Running heuristics and scoring algorithms...",
        "Compiling opportunities...",
        "Scan completed successfully."
    ]
    
    for step in steps:
        await asyncio.sleep(1) # simulate work
        await queue.put({"message": step})
        
    await queue.put({"message": "DONE"})

@app.post("/api/scan/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job_queues[job_id] = asyncio.Queue()
    
    background_tasks.add_task(run_scan_pipeline, job_id)
    return {"job_id": job_id, "status": "started"}

async def event_generator(job_id: str, request: Request):
    queue = job_queues.get(job_id)
    if not queue:
        yield f"data: {json.dumps({'error': 'Invalid job_id'})}\n\n"
        return

    try:
        while True:
            if await request.is_disconnected():
                break
            
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            
            if data.get("message") == "DONE":
                break
    finally:
        if job_id in job_queues:
            del job_queues[job_id]

@app.get("/api/scan/{job_id}/stream")
async def stream_scan(job_id: str, request: Request):
    return StreamingResponse(event_generator(job_id, request), media_type="text/event-stream")

@app.get("/api/opportunities")
async def get_opportunities():
    if os.path.exists(OPP_JSON_PATH):
        try:
            with open(OPP_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Mock data fallback
    return [
        {
            "title": "Opportunity from John Doe",
            "platform": "linkedin",
            "source_url": "https://linkedin.com/posts/johndoe123",
            "post_date": "2026-05-28T10:00:00Z",
            "days_old": 2,
            "company_or_person": "John Doe's Project",
            "category": "marketing/growth",
            "intent_signal": "Explicit need for help or freelancer",
            "opportunity_type": "freelance",
            "contact_path": "email",
            "email": "founder@example.com",
            "dm_available": True,
            "legitimacy_score": 90,
            "outreach_score": 95,
            "confidence": "high",
            "why_it_matters": "High intent keyword match mapped to mock logic."
        },
        {
            "title": "Opportunity from SaaS Founder",
            "platform": "x",
            "source_url": "https://x.com/saasfounder/status/123456789",
            "post_date": "2026-05-29T15:30:00Z",
            "days_old": 1,
            "company_or_person": "SaaS Founder",
            "category": "other",
            "intent_signal": "Explicit need for help or freelancer",
            "opportunity_type": "help-needed",
            "contact_path": "reply",
            "email": "",
            "dm_available": True,
            "legitimacy_score": 90,
            "outreach_score": 85,
            "confidence": "high",
            "why_it_matters": "High intent keyword match mapped to mock logic."
        }
    ]

@app.get("/api/opportunities/stats")
async def get_stats():
    opps = await get_opportunities()
    fresh = len(opps)
    high_intent = sum(1 for o in opps if o.get("confidence") == "high")
    contactable = sum(1 for o in opps if o.get("contact_path") or o.get("email"))
    return {
        "fresh": fresh,
        "high_intent": high_intent,
        "contactable": contactable,
        "pitches_sent": 0
    }

if __name__ == "__main__":
    uvicorn.run("freelance_api:app", host="0.0.0.0", port=8000, reload=True)
