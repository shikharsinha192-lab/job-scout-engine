import sys
import os
import logging

# Ensure the scripts directory is accessible for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.core.apify_base import BaseScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedditScraper(BaseScraper):
    ACTOR_ID = "trudax/reddit-scraper-lite"
    def __init__(self):
        super().__init__()

    def clean_data(self, data):
        """Removes duplicates and filters out sponsored/promoted content."""
        seen_ids = set()
        cleaned_data = []
        
        for item in data:
            # Simple deduplication based on ID, URL or Content
            item_id = item.get('id') or item.get('url') or item.get('text', '')
            if item_id in seen_ids:
                continue
            
            # Filter sponsored/promoted
            # Checking common flags that might indicate ads in Reddit actor output
            is_promoted = item.get('isSponsored', False) or item.get('promoted', False)
            if is_promoted:
                continue
            
            # Further filtering: text contents matching typical ad tags
            text = str(item.get('text', '')).lower()
            title = str(item.get('title', '')).lower()
            if 'promoted' in text or 'promoted' in title:
                continue

            seen_ids.add(item_id)
            cleaned_data.append(item)
        # Filter by last 2 weeks
        cleaned_data = self.filter_by_last_2_weeks(cleaned_data)
        return cleaned_data

    def run(self, keyword):
        run_input = {
            "searches": [keyword],
            "ignoreStartUrls": True,
            "maxItems": 100,
            "searchPosts": True
        }
        
        logger.info(f"Running Reddit extraction for: {keyword}")
        
        raw_data = self.execute_run(self.ACTOR_ID, run_input)
        cleaned_data = self.clean_data(raw_data)
        
        # Minimalist Markdown report to stdout
        print(f"\n## Reddit Extraction Report")
        print(f"**Keyword:** `{keyword}`")
        print(f"- **Raw Count:** {len(raw_data)}")
        print(f"- **Clean Count:** {len(cleaned_data)}")
        
        if cleaned_data:
            print("\n### Top Results Preview")
            for i, item in enumerate(cleaned_data[:3], 1):
                title = item.get('title') or (item.get('text', '')[:50] + '...')
                url = item.get('url', 'N/A')
                print(f"{i}. [{title}]({url})")
        print("\n---\n")

        # Push to Google Sheets
        self.save_to_sheets(cleaned_data, "reddit")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing keyword argument.")
        print("Usage: python reddit.py <keyword>")
        sys.exit(1)
        
    search_keyword = sys.argv[1]
    scraper = RedditScraper()
    scraper.run(search_keyword)
