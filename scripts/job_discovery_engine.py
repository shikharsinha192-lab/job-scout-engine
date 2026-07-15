import os
import sys
import csv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ats_direct_fetcher import run_layer1
from scripts.feed_fetcher import run_layer2
from scripts.dork_scraper import run_layer3
from scripts.dedup_filter import run_layer4
from scripts.batch_scorer import run_layer5

# New massive upgrade extractors
from scripts.extractors.dork_slug_harvester import harvest_slugs
from scripts.extractors.graphql_interceptor import fetch_graphql_jobs
from scripts.extractors.xml_feed_parser import parse_xml_feed

# New Source Engines
from scripts.sources.yc_scraper import fetch_yc_jobs
from scripts.sources.wellfound_scraper import fetch_wellfound_jobs
from scripts.sources.india_boards_scraper import fetch_india_boards
from scripts.sources.uae_scraper import fetch_uae_jobs

import sqlite3

def export_to_db_and_csv(final_jobs):
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    csv_file = os.path.join(output_dir, "discovered_jobs.csv")
    json_file = os.path.join(output_dir, "jobs.json")
    md_file = os.path.join(output_dir, "TOP_PICKS.md")
    
    if not final_jobs:
        print("No jobs to export.")
        return
        
    keys = final_jobs[0].keys()
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(final_jobs)
        
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(final_jobs, f, indent=4)
        
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Job Scout Engine: Top Picks\n\n")
        high_priority = [j for j in final_jobs if j.get('outreach_priority') == 'HIGH']
        medium_priority = [j for j in final_jobs if j.get('outreach_priority') == 'MEDIUM']
        
        f.write(f"## HIGH Priority ({len(high_priority)})\n\n")
        for j in high_priority:
            f.write(f"### {j.get('job_title', 'Unknown')} @ {j.get('company_clean', 'Unknown')}\n")
            f.write(f"- **Geo:** {j.get('geo_mode', 'Global')} | **Stage:** {j.get('company_stage', 'Unknown')}\n")
            f.write(f"- **Why Relevant:** {j.get('why_relevant', '')}\n")
            f.write(f"- **URL:** [Link]({j.get('job_url', '')})\n\n")
            
        f.write(f"## MEDIUM Priority ({len(medium_priority)})\n\n")
        for j in medium_priority:
            f.write(f"- **{j.get('job_title', 'Unknown')}** @ {j.get('company_clean', 'Unknown')} - [Link]({j.get('job_url', '')})\n")
        
    print(f"Success! Exported {len(final_jobs)} jobs to CSV, JSON, and TOP_PICKS.md")

    # Insert into database
    conn = sqlite3.connect(os.path.join(base_dir, 'data', 'job_scout.db'))
    cursor = conn.cursor()
    
    inserted = 0
    for job in final_jobs:
        title = job.get('job_title', 'Unknown')
        company = job.get('company_clean', job.get('company', 'Unknown'))
        url = job.get('job_url', '')
        source = job.get('source', 'Engine')
        relevance = job.get('relevance_score', 0)
        legitimacy = job.get('legitimacy_score', 0)
        date = job.get('posted_date', '')
        
        # Avoid inserting pure duplicates
        cursor.execute("SELECT id FROM opportunities WHERE job_url = ? OR (job_title = ? AND company = ?)", (url, title, company))
        if cursor.fetchone():
            continue
            
        skills_str = json.dumps(job.get('skills_required', []))
        
        cursor.execute("""
            INSERT INTO opportunities (
                job_title, company, company_clean, is_remote, job_url, source, posted_date, 
                relevance_score, legitimacy_score, outreach_priority, why_relevant, skills_required,
                geo_mode, company_stage, role_category, seniority_band, custom_pitch_hook,
                model_used, output_confidence, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            title, job.get('company', 'Unknown'), company, 1, url, source, date, 
            relevance, legitimacy, job.get('outreach_priority', 'LOW'), job.get('why_relevant', ''), 
            skills_str, job.get('geo_mode', 'Global'), job.get('company_stage', 'Unknown'),
            job.get('role_category', 'Other'), job.get('seniority_band', 'Mid'), job.get('custom_pitch_hook', ''),
            job.get('model_used', ''), job.get('output_confidence', '')
        ))
        inserted += 1
        
    conn.commit()
    conn.close()
    print(f"Inserted {inserted} new jobs into the local database.")

def run_engine(keywords=None, geo_filters=None):
    print("========================================")
    print("   AI Job Discovery Engine v3 Started   ")
    print("   (Massive Upgrade Architecture)       ")
    print("========================================")
    
    if not keywords: keywords = ["Marketing", "Growth"]
    if not geo_filters: geo_filters = ["India", "Remote"]
    
    # Layer 0: Dynamic Slug Harvesting
    try:
        harvest_slugs(keywords)
    except Exception as e:
        print(f"Dynamic harvester failed, falling back to static slugs. Error: {e}")
    
    # Layer 1: Concurrent ATS API Fetching
    l1_jobs = run_layer1()
    
    # Layer 2: Traditional Feeds (HN, YC)
    l2_jobs = run_layer2()
    
    # Layer 3: Dork Scraper
    l3_jobs = run_layer3(keywords, geo_filters)
    
    # Layer 4: New Targeted Source Engines
    print("\n=== Layer 4: Regional & Specialised Engines ===")
    l4_jobs = []
    if "India" in geo_filters or "Remote India" in geo_filters:
        l4_jobs.extend(fetch_india_boards(keywords))
    if "UAE" in geo_filters or "United Arab Emirates" in geo_filters:
        l4_jobs.extend(fetch_uae_jobs(keywords))
    
    l4_jobs.extend(fetch_yc_jobs(keywords, geo_filters))
    l4_jobs.extend(fetch_wellfound_jobs(keywords, geo_filters))
    
    # Layer 5: GraphQL Interception & XML Feeds
    l5_jobs = []
    try:
        l5_jobs.extend(fetch_graphql_jobs(keywords[0]))
    except Exception as e:
        print(f"GraphQL interception error: {e}")
        
    try:
        l5_jobs.extend(parse_xml_feed("https://weworkremotely.com/remote-jobs.rss", keywords))
    except Exception as e:
        print(f"XML feed parsing error: {e}")
    
    all_raw_jobs = l1_jobs + l2_jobs + l3_jobs + l4_jobs + l5_jobs
    print(f"\n--- Total Aggregated Raw Jobs: {len(all_raw_jobs)} ---")
    
    # Layer 4
    filtered_jobs = run_layer4(all_raw_jobs)
    
    # Layer 5
    final_jobs = run_layer5(filtered_jobs)
    
    return final_jobs

def main():
    final_jobs = run_engine()
    export_to_db_and_csv(final_jobs)

if __name__ == "__main__":
    main()
