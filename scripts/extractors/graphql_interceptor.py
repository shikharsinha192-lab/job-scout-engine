import requests
import json

def fetch_graphql_jobs(query_keyword="Marketing"):
    print("Initiating GraphQL Payload Spoofing...")
    # This is a generalized GraphQL interception technique.
    # For protected sites like Wellfound, headers like x-apollo-operation-name and specific User-Agents are injected here.
    url = "https://api.graphql.jobs/"
    
    # Example GraphQL query payload extracted from a Network tab interception
    query = """
    query GetJobs($input: JobsInput) {
      jobs(input: $input) {
        id
        title
        company {
          name
          websiteUrl
        }
        locationNames
        applyUrl
        createdAt
        isRemote
      }
    }
    """
    
    variables = {
        "input": {
            "type": "",
            "slug": ""
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://graphql.jobs",
        "x-apollo-operation-name": "GetJobs" # Spoofing Apollo client
    }
    
    jobs_normalized = []
    
    try:
        res = requests.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            jobs_list = data.get("data", {}).get("jobs", [])
            for job in jobs_list:
                title = job.get("title", "")
                company = job.get("company", {}).get("name", "") if job.get("company") else ""
                
                # Filter strictly by keyword
                if query_keyword.lower() not in title.lower():
                    continue
                    
                loc = job.get("locationNames", "")
                apply_url = job.get("applyUrl", "")
                posted = job.get("createdAt", "")
                is_remote = job.get("isRemote", False) or "remote" in str(loc).lower()
                
                jobs_normalized.append({
                    "job_title": title,
                    "company": company,
                    "location": str(loc),
                    "is_remote": is_remote,
                    "posted_date": posted,
                    "job_url": apply_url,
                    "source": "GraphQL Bypass API"
                })
        else:
            print(f"GraphQL request failed with status: {res.status_code}")
    except Exception as e:
        print(f"GraphQL interception error: {e}")
        
    print(f"GraphQL Interception Complete. Found {len(jobs_normalized)} jobs for keyword '{query_keyword}'.")
    return jobs_normalized

if __name__ == "__main__":
    jobs = fetch_graphql_jobs("Engineer")
    print(f"Sample: {jobs[0] if jobs else 'None'}")
