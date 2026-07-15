import os
import sys
import sqlite3

# Adjust path to import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.db import get_db
from main import clean_title_company

def import_legacy_data():
    file_path = os.path.join("data", "filtered_recent_job_listings_1_150.md")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    conn = get_db()
    cursor = conn.cursor()
    
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'):
                continue
                
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 6:
                continue
                
            try:
                row_id = int(parts[1])
            except ValueError:
                continue
                
            raw_title_company = parts[2]
            salary = parts[3]
            link = parts[4]
            rationale = parts[5]
            
            # Use existing clean logic
            title, company = clean_title_company(raw_title_company)
            company_clean = company.replace(" ", "_")
            
            # Simple priority logic
            priority = "HIGH" if "⭐" in salary else "MEDIUM"
            
            # Categorization based on rationale
            skills = "Marketing"
            if "Growth" in title: skills = "Growth Marketing"
            if "Performance" in title: skills = "Performance Marketing"
            if "AI" in rationale or "automation" in rationale.lower(): skills += ", AI, Automation"
            
            cursor.execute('''
                INSERT INTO opportunities (
                    job_title, company, company_clean, job_url, source, posted_date, 
                    is_remote, legitimacy_score, relevance_score, outreach_priority, 
                    why_relevant, skills_required, status, batch_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, company, company_clean, link, "Legacy Markdown", "2026-05-23",
                1, 95, 85, priority,
                rationale, skills, 'approved', 'Legacy_Import'
            ))
            count += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully imported {count} jobs into SQLite database as 'approved'.")

if __name__ == "__main__":
    import_legacy_data()
