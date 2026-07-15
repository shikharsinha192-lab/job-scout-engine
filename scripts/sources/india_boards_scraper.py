import os
import requests
from apify_client import ApifyClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

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

def fetch_cutshort_jobs():
    print("Fetching Cutshort via public API...")
    jobs = []
    # Cutshort's public API is occasionally reachable without auth. We'll try hitting it.
    try:
        url = "https://cutshort.io/api/public/jobs?limit=50&remote=true"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("jobs", []):
                title = item.get("title", "")
                company = item.get("company", {}).get("name", "Unknown")
                posted = item.get("created_on", datetime.now(timezone.utc).isoformat())
                j_url = f"https://cutshort.io/job/{item.get('slug', '')}"
                jobs.append(normalize_job(title, company, "Remote India", True, posted, j_url, "Cutshort"))
    except Exception as e:
        print(f"Error fetching Cutshort: {e}")
    return jobs

def fetch_india_boards_apify(keywords):
    print(f"Fetching Instahyre & IIMJobs via Apify Google Search...")
    jobs = []
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        return jobs
        
    client = ApifyClient(token)
    
    queries = []
    for k in keywords[:5]:
        queries.append(f'site:instahyre.com/job "{k}"')
        queries.append(f'site:iimjobs.com "{k}"')
        
    run_input = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": 1,
        "resultsPerPage": 10,
    }
    
    try:
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        for item in client.dataset(dataset_id).iterate_items():
            for result in item.get("organicResults", []):
                title = result.get("title", "")
                url = result.get("url", "")
                
                company = "India Startup"
                if " - " in title:
                    title = title.split(" - ")[0]
                
                posted = datetime.now(timezone.utc).isoformat()
                
                source = "Instahyre" if "instahyre.com" in url else "IIMJobs" if "iimjobs.com" in url else "India Board"
                jobs.append(normalize_job(title, company, "India", True, posted, url, source))
    except Exception as e:
        print(f"Error fetching India boards via Google: {e}")
        
    return jobs

def fetch_india_boards(keywords):
    jobs = []
    jobs.extend(fetch_cutshort_jobs())
    jobs.extend(fetch_india_boards_apify(keywords))
    return jobs

if __name__ == "__main__":
    j = fetch_india_boards(["growth marketer"])
    print(f"Found {len(j)} India board jobs. Sample: {j[0] if j else 'None'}")
