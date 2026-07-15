from bs4 import BeautifulSoup
import requests

def scrape_linkedin_jd(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        jd_div = soup.find('div', class_='show-more-less-html__markup')
        if jd_div:
            return jd_div.get_text(separator='\n', strip=True)
    except:
        pass
    return "JD Not Found"

urls = [
    "https://in.linkedin.com/jobs/view/founding-growth-marketer-at-animaker-inc-4428478123",
    "https://in.linkedin.com/jobs/view/growth-generalist-at-consuma-4428915430",
    "https://in.linkedin.com/jobs/view/head-of-growth-at-bambinos-live-future-school-4430369942",
    "https://in.linkedin.com/jobs/view/growth-manager-at-drinkprime-4430532954"
]

for u in urls:
    print(f"\n--- URL: {u} ---")
    print(scrape_linkedin_jd(u)[:500] + "...")
