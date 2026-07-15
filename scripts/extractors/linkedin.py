import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
from scripts.core.apify_base import BaseScraper

class LinkedInScraper(BaseScraper):
    ACTOR_ID = "cheap_scraper/linkedin-job-scraper"

    def clean_data(self, data):
        cleaned = []
        seen = set()
        for item in data:
            # Create an identifier to detect duplicates
            item_id = item.get("id") or item.get("url") or (item.get("title"), item.get("company"))
            if item_id in seen:
                continue
            
            # Filter out sponsored or promoted jobs
            is_promoted = item.get("isPromoted", False)
            is_sponsored = item.get("sponsored", False)
            if is_promoted or is_sponsored:
                continue
                
            seen.add(item_id)
            cleaned.append(item)
        # Filter by last 2 weeks
        cleaned = self.filter_by_last_2_weeks(cleaned)
        return cleaned

    def execute(self, keyword):
        import urllib.parse
        encoded_query = urllib.parse.quote(keyword)
        start_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&location=India"
        
        run_input = {
            "startUrls": [{"url": start_url}],
            "maxItems": 150,
            "maxPages": 3
        }
        
        # run_actor is assumed to be provided by BaseScraper
        raw_data = self.execute_run(self.ACTOR_ID, run_input)
        cleaned_data = self.clean_data(raw_data)
        
        # Output minimalist Markdown report to stdout
        print(f"## LinkedIn Scrape Report for '{keyword}'\n")
        if not cleaned_data:
            print("No jobs found or all were filtered out.\n")
        else:
            for job in cleaned_data:
                title = job.get('title', 'Unknown Title')
                company = job.get('companyName', job.get('company', 'Unknown Company'))
                url = job.get('url', '#')
                print(f"- [{title}]({url}) @ **{company}**")
        print("\n")
        
        # Save results using the base class method
        self.save_to_sheets(cleaned_data, "linkedin")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python linkedin.py <keyword>")
        sys.exit(1)
        
    keyword = sys.argv[1]
    scraper = LinkedInScraper()
    scraper.execute(keyword)
