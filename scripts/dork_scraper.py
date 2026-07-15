import os
import json
from datetime import datetime, timedelta, timezone
from apify_client import ApifyClient
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

def run_layer3(keywords=None, geo_filters=None):
    print("=== Layer 3: Advanced Apify Google Dork Search ===")
    
    if keywords is None:
        keywords = ["growth marketing", "ai automation", "product manager"]
    if geo_filters is None:
        geo_filters = ["India", "Remote"]
        
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("Error: APIFY_API_TOKEN not set in .env. Skipping Layer 3.")
        return []

    client = ApifyClient(token)
    
    date_10_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    
    queries = []
    # Generate 20+ precise queries dynamically
    geo_str = " OR ".join([f'"{g}"' for g in geo_filters])
    
    for k in keywords[:7]:
        queries.append(f'site:linkedin.com/jobs "{k}" ({geo_str}) after:{date_10_days_ago}')
        queries.append(f'(site:greenhouse.io OR site:lever.co OR site:ashbyhq.com) "{k}" ({geo_str}) after:{date_10_days_ago}')
        queries.append(f'site:wellfound.com "{k}" ({geo_str}) after:{date_10_days_ago}')
        queries.append(f'(site:x.com OR site:twitter.com) ("we are hiring" OR "actively hiring") "{k}" ({geo_str}) after:{date_10_days_ago}')

    all_jobs = []
    
    print(f"Executing {len(queries)} precision queries via Apify...")
    
    # Use standard apify/google-search-scraper. Queries must be a newline-separated string.
    queries_str = "\n".join(queries)
    run_input = {
        "queries": queries_str,
        "maxPagesPerQuery": 1,
        "resultsPerPage": 10,
        "customDataFunction": "async ({ input, $, request, response, html }) => {\n  return {\n    pageTitle: $('title').text(),\n  };\n}",
        "tbs": "qdr:w"  # Force past week Google filter
    }

    try:
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        for item in client.dataset(dataset_id).iterate_items():
            for result in item.get("organicResults", []):
                title = result.get("title", "")
                snippet = result.get("description", "")
                url = result.get("url", "")
                # We extract snippets only. Gemini will parse company/title from this snippet in Layer 5.
                all_jobs.append(normalize_job(
                    title=title,
                    company="TBD", # To be parsed by Gemini
                    location="Remote India",
                    is_remote=True,
                    posted_date=date_10_days_ago, # Bound by operator
                    url=url,
                    source="Google Dork snippet"
                ))
    except Exception as e:
        print(f"Error during Apify run: {e}")

    print(f"Layer 3 complete: Found {len(all_jobs)} raw snippets.")
    return all_jobs

if __name__ == "__main__":
    jobs = run_layer3()
    print(f"Sample job: {jobs[0] if jobs else 'None'}")
