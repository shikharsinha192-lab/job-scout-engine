import os
import json
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

def harvest_slugs(queries=["Marketing", "Growth", "Performance"], num_pages=1):
    print("Initiating Dork Slug Harvester (Apify Google Search)...")
    slugs = {"lever": set(), "greenhouse": set(), "ashby": set()}
    
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("Skipping dynamic slug harvesting: No APIFY_API_TOKEN found.")
        return {"lever": [], "greenhouse": [], "ashby": []}

    client = ApifyClient(token)
    
    boards = [
        ("lever", "site:jobs.lever.co"),
        ("greenhouse", "site:boards.greenhouse.io"),
        ("ashby", "site:jobs.ashbyhq.com")
    ]
    
    all_queries = []
    for board_name, site_dork in boards:
        for q in queries:
            all_queries.append(f'{site_dork} "{q}"')
            
    print(f"Executing {len(all_queries)} queries for ATS slugs...")
    
    run_input = {
        "queries": "\n".join(all_queries),
        "maxPagesPerQuery": num_pages,
        "resultsPerPage": 20,
    }

    try:
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        for item in client.dataset(dataset_id).iterate_items():
            for result in item.get("organicResults", []):
                url = result.get("url", "")
                
                if 'jobs.lever.co/' in url:
                    parts = url.split('jobs.lever.co/')
                    if len(parts) > 1:
                        slug = parts[-1].split('/')[0].strip()
                        if slug and slug != 'lever': slugs["lever"].add(slug)
                elif 'boards.greenhouse.io/' in url:
                    parts = url.split('boards.greenhouse.io/')
                    if len(parts) > 1:
                        slug = parts[-1].split('/')[0].strip()
                        if slug: slugs["greenhouse"].add(slug)
                elif 'jobs.ashbyhq.com/' in url:
                    parts = url.split('jobs.ashbyhq.com/')
                    if len(parts) > 1:
                        slug = parts[-1].split('/')[0].strip()
                        if slug: slugs["ashby"].add(slug)
    except Exception as e:
        print(f"Error during Apify slug harvest run: {e}")
                
    output = {
        "lever": list(slugs["lever"]),
        "greenhouse": list(slugs["greenhouse"]),
        "ashby": list(slugs["ashby"])
    }
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_file = os.path.join(base_dir, "data", "ats_company_slugs_dynamic.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=4)
        
    print(f"Harvester completed. Found: Lever({len(output['lever'])}), Greenhouse({len(output['greenhouse'])}), Ashby({len(output['ashby'])})")
    return output

if __name__ == "__main__":
    res = harvest_slugs(["Performance Marketing", "Growth Marketing"])
    print(res)
