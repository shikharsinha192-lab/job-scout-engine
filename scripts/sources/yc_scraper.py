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

def fetch_yc_jobs(keywords, geo_filters):
    print(f"Fetching Work at a Startup (YC) via Apify with keywords: {keywords[:3]}...")
    jobs = []
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("Skipping YC fetch: APIFY_API_TOKEN not found.")
        return jobs
        
    client = ApifyClient(token)
    
    # We will use the Google Search scraper to find roles on workatastartup.com since the HTML scraper might get blocked
    queries = []
    for k in keywords[:5]: # Take top 5 keywords
        # If geo is India, add India/remote. If US, add remote.
        if "India" in geo_filters or "Remote India" in geo_filters:
            queries.append(f'site:workatastartup.com/jobs "{k}" ("India" OR "remote")')
        else:
            queries.append(f'site:workatastartup.com/jobs "{k}" "remote"')
            
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
                # The title from Google usually looks like "Growth Manager at Stripe | Y Combinator"
                company = "YC Startup"
                if " at " in title:
                    parts = title.split(" at ")
                    if len(parts) > 1:
                        company = parts[1].split("|")[0].strip()
                        title = parts[0].strip()
                        
                # Default posted date to today since we can't get it from Google easily without tbs,
                # but dedup layer will handle it if we mark it correctly.
                posted = datetime.now(timezone.utc).isoformat()
                jobs.append(normalize_job(title, company, "Remote", True, posted, url, "YC Work at a Startup"))
    except Exception as e:
        print(f"Error fetching YC jobs via Google: {e}")
        
    return jobs

if __name__ == "__main__":
    j = fetch_yc_jobs(["growth marketer", "product manager"], ["India", "Remote India"])
    print(f"Found {len(j)} YC jobs. Sample: {j[0] if j else 'None'}")
