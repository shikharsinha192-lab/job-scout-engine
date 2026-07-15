import sys
import json
from scripts.core.apify_base import BaseScraper

class CompanySitesScraper(BaseScraper):
    ACTOR_ID = "apify/google-search-scraper"

    def clean_data(self, data):
        """Remove exact duplicates and filter out sponsored/promoted noise."""
        if not data:
            return []
            
        seen = set()
        cleaned = []
        for item in data:
            # Create a signature for deduplication
            try:
                if isinstance(item, dict):
                    # Dedup by URL if available, else full dictionary signature
                    signature = item.get("url", json.dumps(item, sort_keys=True))
                else:
                    signature = str(item)
            except Exception:
                signature = str(item)
                
            if signature in seen:
                continue
                
            # Filter out sponsored/promoted noise
            item_str = json.dumps(item).lower() if isinstance(item, dict) else str(item).lower()
            if "sponsored" in item_str or "promoted" in item_str:
                continue
                
            seen.add(signature)
            cleaned.append(item)
            
        # Filter by last 2 weeks
        cleaned = self.filter_by_last_2_weeks(cleaned)
        return cleaned

    def generate_report(self, data, keyword):
        """Output a minimalist Markdown report to stdout."""
        print(f"# Company Sites Report for '{keyword}'\n")
        print(f"**Total Cleaned Records:** {len(data)}\n")
        
        for item in data[:20]: # Print up to 20 to keep it minimalist
            if isinstance(item, dict):
                title = item.get("title", item.get("name", "Unknown Title"))
                url = item.get("url", item.get("website", "No URL"))
                print(f"- **{title}**: {url}")
            else:
                print(f"- {item}")
                
        if len(data) > 20:
            print(f"\n... and {len(data) - 20} more records.")
            
        print("\n--- End of Report ---")

    def execute(self, keyword):
        # Prepare input for the Apify Actor
        run_input = {
            "queries": keyword,
            "maxItems": 80,
            "maxPages": 3
        }
        
        # Execute the actor (assuming run_actor exists in BaseScraper)
        raw_data = self.execute_run(self.ACTOR_ID, run_input)
        
        # Clean data
        cleaned_data = self.clean_data(raw_data)
        
        # Generate markdown report to stdout
        self.generate_report(cleaned_data, keyword)
        
        # Save to sheets
        self.save_to_sheets(cleaned_data, "company_sites")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python company_sites.py <keyword>")
        sys.exit(1)
        
    keyword = sys.argv[1]
    scraper = CompanySitesScraper()
    scraper.execute(keyword)
