from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
import sys
import os

from api.stream import log
from api.db import get_db

# Import the engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.job_discovery_engine import run_engine

router = APIRouter()

class ScrapeRequest(BaseModel):
    prompt: str

import contextlib
import io

class StreamToLog:
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            if line.strip():
                log(line)
    def flush(self):
        pass

def run_scrape_task(prompt: str):
    log(f"Starting search: {prompt}")
    
    try:
        # Redirect all print() statements inside the pipeline to our SSE queue
        with contextlib.redirect_stdout(StreamToLog()):
            final_jobs = run_engine()
        
        # Save to DB
        conn = get_db()
        cursor = conn.cursor()
        
        added = 0
        for job in final_jobs:
            cursor.execute('''
                INSERT INTO opportunities (
                    job_title, company, company_clean, job_url, source, posted_date, 
                    is_remote, legitimacy_score, relevance_score, outreach_priority, 
                    why_relevant, skills_required, recruiter_email, model_used, output_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job.get('job_title'), job.get('company'), job.get('company_clean'),
                job.get('job_url'), job.get('source'), job.get('posted_date'),
                1 if job.get('is_remote') else 0,
                job.get('legitimacy_score'), job.get('relevance_score'),
                job.get('outreach_priority'), job.get('why_relevant'),
                str(job.get('skills_required', [])), job.get('recruiter_email'),
                job.get('model_used'), job.get('output_confidence')
            ))
            added += 1
            
        conn.commit()
        conn.close()
        
        log(f"Search complete. {added} verified jobs added to database.")
    except Exception as e:
        log(f"Error during scrape: {str(e)}")


@router.post("/start")
async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    # Run the massive job discovery engine in the background
    background_tasks.add_task(run_scrape_task, req.prompt)
    return {"message": "Scrape started in background"}
