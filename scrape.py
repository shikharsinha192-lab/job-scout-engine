import argparse
import sys
import os
from config.scrape_config import get_role_keywords, GEO_MODES

# Future imports once the layers are fully upgraded
# from scripts.ats_direct_fetcher import run_layer1
# from scripts.feed_fetcher import run_layer2
# from scripts.dork_scraper import run_layer3
# from scripts.dedup_filter import run_layer4
# from scripts.batch_scorer import run_layer5
# from scripts.job_discovery_engine import export_results

def main():
    parser = argparse.ArgumentParser(description="Job Scout Engine: Multi-Mode Job Scraper")
    parser.add_argument("--mode", type=str, choices=["india_startup", "us_remote", "uae_remote", "yc_funded", "all"], required=True, help="Geography/Target mode")
    parser.add_argument("--roles", type=str, default="all", help="Comma-separated roles: growth,performance_mkt,ai_marketing,product,strategy,content,founders_office,all")
    parser.add_argument("--days", type=int, default=7, help="Freshness window in days (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Print stats but skip Gemini scoring and output files")

    args = parser.parse_args()
    
    roles_list = [r.strip() for r in args.roles.split(",")]
    keywords = get_role_keywords(roles_list)
    
    print(f"=== Job Scout Engine ===")
    print(f"Mode: {args.mode.upper()}")
    print(f"Roles: {args.roles} ({len(keywords)} keywords)")
    print(f"Freshness: past {args.days} days")
    print(f"========================")
    
    from scripts.job_discovery_engine import run_engine, export_to_db_and_csv
    
    geo_filters = []
    if args.mode != "all":
        geo_filters = GEO_MODES.get(args.mode, {}).get("filters", [])
        
    print(f"Executing pipeline...")
    final_jobs = run_engine(keywords, geo_filters)
    
    if args.dry_run:
        print(f"Dry run complete. Discovered {len(final_jobs)} jobs. Output skipped.")
    else:
        export_to_db_and_csv(final_jobs)

if __name__ == "__main__":
    main()
