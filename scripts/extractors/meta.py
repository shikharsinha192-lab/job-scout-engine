import sys
from scripts.core.apify_base import BaseScraper

class MetaScraper(BaseScraper):
    ACTOR_ID = "apify/instagram-scraper"

    def run(self, keyword):
        # Handle "OR" logic by splitting into multiple keywords
        if " OR " in keyword:
            keywords = [k.strip() for k in keyword.split(" OR ")]
        else:
            keywords = [keyword.strip()]
            
        all_items = []
        for kw in keywords:
            # Prepare run input
            run_input = {
                "search": kw,
                "searchType": "hashtag",
                "searchLimit": 30,
                "resultsType": "posts",
                "resultsLimit": 100
            }

            # Run actor
            print(f"Starting Meta extraction for: {kw}")
            items = self.execute_run(self.ACTOR_ID, run_input)
            if items:
                all_items.extend(items)

        if not all_items:
            print("No items found.")
            return

        # Clean and deduplicate
        cleaned_data = self.clean_data(all_items)

        # Generate minimalist Markdown report
        self.generate_report(cleaned_data, keyword)

        # Save to Google Sheets
        self.save_to_sheets(cleaned_data, "meta")
        print("Extraction complete.")

    def clean_data(self, items):
        seen = set()
        cleaned = []
        for item in items:
            # Basic deduplication using URL or ID as unique identifier
            identifier = item.get("url") or item.get("id") or item.get("link", "")
            if not identifier:
                continue

            if identifier in seen:
                continue

            # Filter sponsored/promoted noise
            title = str(item.get("title", "")).lower()
            description = str(item.get("description", "")).lower()
            text = str(item.get("text", "")).lower()
            
            is_sponsored_flag = item.get("isSponsored") or item.get("is_sponsored")
            
            if is_sponsored_flag:
                continue
                
            if any(keyword in title or keyword in description or keyword in text for keyword in ["sponsored", "promoted", "ad"]):
                continue

            seen.add(identifier)
            cleaned.append(item)
            
        # Filter by last 2 weeks
        cleaned = self.filter_by_last_2_weeks(cleaned)
        return cleaned

    def generate_report(self, items, keyword):
        print(f"\n# Meta Extraction Report: {keyword}")
        print(f"Total Unique/Non-Sponsored Items Found: {len(items)}\n")
        
        for i, item in enumerate(items[:10], 1): # Limit report output to top 10
            title = item.get("title") or item.get("text", "")[:50] + "..."
            url = item.get("url") or item.get("link", "No URL")
            print(f"{i}. **{title}**")
            print(f"   {url}")
            
        if len(items) > 10:
            print("\n... and more.")
        print("\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python meta.py <keyword>")
        sys.exit(1)

    keyword = sys.argv[1]
    scraper = MetaScraper()
    scraper.run(keyword)
