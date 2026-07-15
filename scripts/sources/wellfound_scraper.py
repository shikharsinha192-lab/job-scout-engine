import os
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

def fetch_wellfound_jobs(keywords, geo_filters):
    print(f"Fetching Wellfound via Apify with keywords: {keywords[:3]}...")
    jobs = []
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("Skipping Wellfound fetch: APIFY_API_TOKEN not found.")
        return jobs
        
    client = ApifyClient(token)
    
    queries = []
    for k in keywords[:5]:
        if "India" in geo_filters or "Remote India" in geo_filters:
            queries.append(f'site:wellfound.com/role/l/india "{k}"')
        else:
            queries.append(f'site:wellfound.com/remote "{k}"')
            
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
                
                company = "Wellfound Startup"
                if " | " in title:
                    title = title.split(" | ")[0]
                
                posted = datetime.now(timezone.utc).isoformat()
                jobs.append(normalize_job(title, company, "Remote", True, posted, url, "Wellfound"))
    except Exception as e:
        print(f"Error fetching Wellfound via Google: {e}")
        
    return jobs

if __name__ == "__main__":
    j = fetch_wellfound_jobs(["product manager"], ["India"])
    print(f"Found {len(j)} Wellfound jobs. Sample: {j[0] if j else 'None'}")
