import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
from typing import List, Dict, Any
from scripts.core.apify_base import BaseScraper

class JobBoardExtractor(BaseScraper):
    ACTOR_ID = "apify/google-search-scraper"

    def execute(self, keyword: str):
        # 1. Fetch raw data from Apify using the base class 
        # (Assuming run_actor is implemented in BaseScraper)
        run_input = {"query": keyword, "maxItems": 80, "maxPages": 3}
        raw_data = self.execute_run(self.ACTOR_ID, run_input)

        # 2. Clean and deduplicate data
        cleaned_data = self.clean_and_deduplicate(raw_data)

        # 3. Output minimalist Markdown report to stdout
        self.print_markdown_report(keyword, cleaned_data)

        # 4. Save to Google Sheets
        self.save_to_sheets(cleaned_data, "job_boards")

    def clean_and_deduplicate(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        seen = set()

        for job in raw_data:
            title = str(job.get("title", "")).strip()
            company = str(job.get("company", "")).strip()
            url = str(job.get("url", "")).strip()
            
            is_promoted = job.get("isPromoted", False) or job.get("promoted", False)
            title_lower = title.lower()

            # Filter out sponsored/promoted noise
            if is_promoted or "sponsored" in title_lower or "promoted" in title_lower:
                continue

            # Remove exact duplicates based on composite key
            dedup_key = f"{title}|{company}|{url}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                cleaned.append(job)
        # Filter by last 2 weeks
        cleaned = self.filter_by_last_2_weeks(cleaned)
        return cleaned

    def print_markdown_report(self, keyword: str, data: List[Dict[str, Any]]):
        print(f"## Job Extraction Report: {keyword}")
        print(f"**Total distinct non-promoted jobs:** {len(data)}\n")
        
        for job in data:
            title = job.get('title', 'N/A')
            company = job.get('company', 'N/A')
            url = job.get('url', '#')
            print(f"- **{title}** @ {company} - [Link]({url})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python job_boards.py <keyword>")
        sys.exit(1)
        
    search_keyword = sys.argv[1]
    extractor = JobBoardExtractor()
    extractor.execute(search_keyword)
