from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys

# Add parent directory to path to allow importing scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.stream import event_generator, log
from api.db import get_db

app = FastAPI(title="Job Scout Engine API")

# CORS: allow all origins for local dev (frontend may run on a different port or as file://)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes import dashboard, scrape, schedule, opportunities, outreach, analytics

app.include_router(dashboard.router, prefix="/api/dashboard")
app.include_router(scrape.router, prefix="/api/scrape")
app.include_router(schedule.router, prefix="/api/schedule")
app.include_router(opportunities.router, prefix="/api/opportunities")
app.include_router(outreach.router, prefix="/api/outreach")
app.include_router(analytics.router, prefix="/api/analytics")

@app.get("/api/logs/stream")
async def log_stream():
    """SSE endpoint for streaming logs"""
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="Frontend building...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="127.0.0.1", port=8080, reload=True)
