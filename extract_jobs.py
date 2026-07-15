import json

file_path = r"C:\Users\91639\Documents\antigravity\job-scout-engine\temp_cutshort_data.json"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Cutshort's NEXT_DATA usually has the jobs in props -> pageProps -> initialState or similar
    jobs = []

    def recursive_search_jobs(obj):
        if isinstance(obj, dict):
            # Look for common cutshort job keys
            if "jobRole" in obj and "companyName" in obj:
                jobs.append(obj)
            elif "job_title" in obj and "company" in obj:
                jobs.append(obj)
            elif "title" in obj and "company" in obj and isinstance(obj["company"], dict):
                jobs.append(obj)
            
            for k, v in obj.items():
                if k in ["jobs", "jobList", "results", "candidateMatches", "matches"]:
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        # Might be our target array
                        pass
                recursive_search_jobs(v)
        elif isinstance(obj, list):
            for item in obj:
                recursive_search_jobs(item)

    recursive_search_jobs(data)

    print(f"Total raw job nodes found: {len(jobs)}")
    
    # Deduplicate and extract
    unique_jobs = {}
    for j in jobs:
        title = j.get("jobRole") or j.get("job_title") or j.get("title")
        company = j.get("companyName")
        if not company and "company" in j and isinstance(j["company"], dict):
            company = j["company"].get("name")
            
        location = j.get("locations", [])
        if isinstance(location, list) and len(location) > 0:
            if isinstance(location[0], dict):
                location = location[0].get("name", "Remote/Various")
            else:
                location = location[0]
        else:
            location = j.get("location_name", "N/A")
            
        exp_min = j.get("min_experience") or j.get("minExp") or j.get("minExperience")
        exp_max = j.get("max_experience") or j.get("maxExp") or j.get("maxExperience")
        exp = f"{exp_min}-{exp_max} Yrs" if exp_min is not None else "N/A"
        
        salary_min = j.get("min_salary") or j.get("minSalary")
        salary_max = j.get("max_salary") or j.get("maxSalary")
        salary = f"₹{salary_min}-{salary_max} LPA" if salary_min is not None else "N/A"

        if title and company:
            key = f"{title}-{company}"
            if key not in unique_jobs:
                unique_jobs[key] = {
                    "Title": title,
                    "Company": company,
                    "Location": location,
                    "Experience": exp,
                    "Salary": salary
                }

    print(f"Total Unique Jobs: {len(unique_jobs)}")
    print("-" * 50)
    for v in unique_jobs.values():
        print(f"Title: {v['Title']}\nCompany: {v['Company']}\nLocation: {v['Location']}\nExperience: {v['Experience']}\nSalary: {v['Salary']}\n" + "-"*50)

except Exception as e:
    print(f"Error extracting JSON: {e}")
