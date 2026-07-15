import os
import json
import requests
import concurrent.futures
from datetime import datetime, timezone
from dateutil import parser

# Normalize job object structure
def normalize_job(title, company, location, is_remote, posted_date, url, source):
    return {
        "job_title": title,
        "company": company,
        "location": location,
        "is_remote": is_remote,
        "posted_date": posted_date,
        "job_url": url,
        "source": source
    }

def fetch_greenhouse(slug):
    jobs = []
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                loc = job.get("location", {}).get("name", "")
                url = job.get("absolute_url", "")
                updated_at = job.get("updated_at", "")
                # Remote heuristic for Greenhouse
                is_remote = "remote" in title.lower() or "remote" in loc.lower() or "anywhere" in loc.lower()
                jobs.append(normalize_job(title, slug.capitalize(), loc, is_remote, updated_at, url, f"Greenhouse ({slug})"))
    except Exception as e:
        print(f"Error fetching Greenhouse {slug}: {e}")
    return jobs

def fetch_lever(slug):
    jobs = []
    try:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for job in data:
                title = job.get("text", "")
                loc = job.get("categories", {}).get("location", "")
                url = job.get("hostedUrl", "")
                created_at = datetime.fromtimestamp(job.get("createdAt", 0)/1000, tz=timezone.utc).isoformat()
                workplace = job.get("workplaceType", "")
                is_remote = workplace == "remote" or "remote" in title.lower() or "remote" in loc.lower()
                jobs.append(normalize_job(title, slug.capitalize(), loc, is_remote, created_at, url, f"Lever ({slug})"))
    except Exception as e:
        print(f"Error fetching Lever {slug}: {e}")
    return jobs

def fetch_ashby(slug):
    jobs = []
    try:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                loc = job.get("location", "")
                url = job.get("jobUrl", "")
                published_at = job.get("publishedAt", "")
                is_remote = job.get("isRemote", False) or "remote" in loc.lower()
                jobs.append(normalize_job(title, slug.capitalize(), loc, is_remote, published_at, url, f"Ashby ({slug})"))
    except Exception as e:
        print(f"Error fetching Ashby {slug}: {e}")
    return jobs

def fetch_himalayas():
    print("Fetching from Himalayas API...")
    jobs = []
    queries = ["AI", "growth", "automation", "marketing"]
    for q in queries:
        try:
            # 100 limit is max for Himalayas public API
            url = f"https://himalayas.app/jobs/api?q={q}&country=India&limit=100"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    company = job.get("companyName", "")
                    loc = "Remote India"
                    url = job.get("applicationLink", job.get("jobUrl", ""))
                    posted = job.get("postedAt", "") # Unix timestamp or iso string
                    if isinstance(posted, int):
                        posted = datetime.fromtimestamp(posted, tz=timezone.utc).isoformat()
                    jobs.append(normalize_job(title, company, loc, True, posted, url, "Himalayas"))
        except Exception as e:
            print(f"Error fetching Himalayas ({q}): {e}")
    return jobs

def fetch_remoteok():
    print("Fetching from RemoteOK JSON feed...")
    jobs = []
    tags = ["ai", "marketing", "growth"]
    for tag in tags:
        try:
            url = f"https://remoteok.com/api?tag={tag}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # First item is usually legal boilerplate, actual jobs start at index 1
                for job in data[1:]:
                    title = job.get("position", "")
                    company = job.get("company", "")
                    loc = job.get("location", "")
                    url = job.get("url", "")
                    posted = job.get("date", "")
                    jobs.append(normalize_job(title, company, loc, True, posted, url, "RemoteOK"))
        except Exception as e:
            print(f"Error fetching RemoteOK ({tag}): {e}")
    return jobs

def fetch_workable(slug):
    jobs = []
    try:
        url = f"https://jobs.workable.com/api/v2/jobs?query=growth&remote=true&company={slug}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for job in data.get('jobs', []):
                title = job.get('title', '')
                company = slug.title()
                loc = job.get('location', {}).get('country', 'Remote')
                j_url = job.get('url', '')
                posted = job.get('published_on', '')
                jobs.append(normalize_job(title, company, loc, True, posted, j_url, "Workable"))
    except Exception as e:
        pass
    return jobs

def run_layer1():
    print("=== Layer 1: Direct ATS & Public API Fetch (Concurrent) ===")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Try loading dynamic slugs first, fallback to static
    dynamic_slugs_file = os.path.join(base_dir, "data", "ats_company_slugs_dynamic.json")
    static_slugs_file = os.path.join(base_dir, "data", "ats_company_slugs.json")
    
    slugs = {}
    if os.path.exists(dynamic_slugs_file):
        with open(dynamic_slugs_file, "r") as f:
            slugs = json.load(f)
        print("Loaded dynamically harvested ATS slugs.")
    elif os.path.exists(static_slugs_file):
        with open(static_slugs_file, "r") as f:
            slugs = json.load(f)
        print("Loaded static ATS slugs.")
        
    all_jobs = []
    
    greenhouse_slugs = slugs.get('greenhouse', [])
    lever_slugs = slugs.get('lever', [])
    ashby_slugs = slugs.get('ashby', [])
    workable_slugs = slugs.get('workable', [])
    
    print(f"Fetching from {len(greenhouse_slugs)} Greenhouse, {len(lever_slugs)} Lever, {len(ashby_slugs)} Ashby, {len(workable_slugs)} Workable boards concurrently...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_slug = {}
        for slug in greenhouse_slugs:
            future_to_slug[executor.submit(fetch_greenhouse, slug)] = slug
        for slug in lever_slugs:
            future_to_slug[executor.submit(fetch_lever, slug)] = slug
        for slug in ashby_slugs:
            future_to_slug[executor.submit(fetch_ashby, slug)] = slug
        for slug in workable_slugs:
            future_to_slug[executor.submit(fetch_workable, slug)] = slug
            
        future_himalayas = executor.submit(fetch_himalayas)
        future_remoteok = executor.submit(fetch_remoteok)
        
        for future in concurrent.futures.as_completed(future_to_slug):
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as exc:
                print(f"ATS fetch generated an exception: {exc}")
                
        all_jobs.extend(future_himalayas.result())
        all_jobs.extend(future_remoteok.result())
    
    print(f"Layer 1 complete: Found {len(all_jobs)} raw jobs.")
    return all_jobs

if __name__ == "__main__":
    jobs = run_layer1()
    print(f"Sample job: {jobs[0] if jobs else 'None'}")
