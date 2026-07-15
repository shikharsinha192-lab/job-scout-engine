from datetime import datetime, timedelta, timezone
from dateutil import parser
import re

def parse_date(date_string):
    if not date_string:
        return None
        
    # Handle "X days ago"
    match = re.search(r'(\d+)\s+days?\s+ago', str(date_string).lower())
    if match:
        days = int(match.group(1))
        return datetime.now(timezone.utc) - timedelta(days=days)
        
    try:
        dt = parser.parse(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        return None

def is_remote_india_eligible(job):
    # If is_remote boolean is true
    if job.get("is_remote"):
        return True
    
    loc = str(job.get("location", "")).lower()
    title = str(job.get("job_title", "")).lower()
    
    if "remote" in loc or "remote" in title:
        return True
    if "india" in loc or "anywhere" in loc or "apac" in loc or "global" in loc:
        return True
        
    return False

def run_layer4(all_raw_jobs):
    print(f"=== Layer 4: Dedup & Freshness Gate ===")
    print(f"Incoming raw jobs: {len(all_raw_jobs)}")
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=10)
    
    deduped = {}
    seen_urls = set()
    
    for job in all_raw_jobs:
        c_name = str(job.get('company', '')).lower().strip()
        j_title = str(job.get('job_title', '')).lower().strip()
        fingerprint = f"{c_name}:::{j_title}"
        
        # Freshness Check
        dt = parse_date(job.get('posted_date'))
        if dt and dt < cutoff_date:
            continue # Too old
            
        # Location Check
        if not is_remote_india_eligible(job):
            continue
            
        # URL Check (strict dedup)
        job_url = str(job.get('job_url', '')).strip()
        if job_url and job_url in seen_urls:
            continue
            
        # Dedup logic: prefer ATS > YC/HN > Dork Snippet
        existing = deduped.get(fingerprint)
        if existing:
            src_score_new = 3 if "greenhouse" in job['source'].lower() or "lever" in job['source'].lower() or "ashby" in job['source'].lower() else 2 if "y combinator" in job['source'].lower() or "hacker news" in job['source'].lower() else 1
            src_score_old = 3 if "greenhouse" in existing['source'].lower() or "lever" in existing['source'].lower() or "ashby" in existing['source'].lower() else 2 if "y combinator" in existing['source'].lower() or "hacker news" in existing['source'].lower() else 1
            
            if src_score_new > src_score_old:
                deduped[fingerprint] = job
                if job_url: seen_urls.add(job_url)
        else:
            deduped[fingerprint] = job
            if job_url: seen_urls.add(job_url)
            
    filtered_jobs = list(deduped.values())
    print(f"Layer 4 complete: {len(filtered_jobs)} verified unique, fresh jobs.")
    return filtered_jobs
