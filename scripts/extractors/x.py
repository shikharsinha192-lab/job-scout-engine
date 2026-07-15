import os
import sys
import json
import logging
from typing import List, Dict, Any

# Ensure scripts module can be imported when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from scripts.core.apify_base import BaseScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper(BaseScraper):
    ACTOR_ID = "altimis/scweet"
    
    def __init__(self):
        super().__init__()
        
    def extract(self, keyword: str) -> List[Dict[str, Any]]:
        """Extract data using Apify."""
        # This payload might need to be adjusted based on the specific X (Twitter) actor used.
        run_input = {
            "source_mode": "search",
            "search_query": keyword,
            "max_items": 100
        }
        return self.execute_run(self.ACTOR_ID, run_input)
        
    def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out sponsored/promoted noise and remove duplicates."""
        seen = set()
        cleaned = []
        
        for item in data:
            # Skip sponsored/promoted tweets
            is_promoted = item.get("isPromoted", False) or item.get("isAd", False)
            if is_promoted:
                continue
                
            # Deduplicate by ID or URL, fallback to JSON string representation
            item_id = item.get("id") or item.get("url")
            if not item_id:
                # If no clear ID, create a stable string representation
                item_id = json.dumps(item, sort_keys=True)
                
            if item_id not in seen:
                seen.add(item_id)
                cleaned.append(item)
                
        # Filter by last 2 weeks
        cleaned = self.filter_by_last_2_weeks(cleaned)
        return cleaned

    def generate_markdown_report(self, data: List[Dict[str, Any]], keyword: str) -> str:
        """Generate a minimalist Markdown report."""
        lines = [
            f"# X Data Extraction Report",
            f"**Keyword:** `{keyword}`",
            f"**Total Valid Items:** {len(data)}",
            "",
            "## Sample Highlights"
        ]
        
        for i, item in enumerate(data[:10], 1):
            author = item.get("author", {}).get("userName") or item.get("userName") or "Unknown"
            text = item.get("text") or item.get("fullText") or "No text available"
            text_preview = text.replace('\n', ' ')[:100] + ('...' if len(text) > 100 else '')
            url = item.get("url", "#")
            
            lines.append(f"{i}. **@{author}**: {text_preview} [Link]({url})")
            
        return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python x.py <keyword>")
        sys.exit(1)
        
    keyword = sys.argv[1]
    
    scraper = XScraper()
    
    logger.info(f"Extracting data from X for keyword: {keyword}")
    raw_data = scraper.extract(keyword)
    
    logger.info("Cleaning and deduplicating data...")
    cleaned_data = scraper.clean_data(raw_data)
    
    print("\n--- REPORT START ---\n")
    print(scraper.generate_markdown_report(cleaned_data, keyword))
    print("\n--- REPORT END ---\n")
    
    logger.info("Saving to Google Sheets...")
    scraper.save_to_sheets(cleaned_data, "x")
    logger.info("Execution complete.")
