from fastapi import APIRouter
from api.db import get_db

router = APIRouter()

@router.get("/")
def get_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM opportunities")
    found = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM outreach")
    sent = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE status IN ('replied', 'positive')")
    replies = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'positive'")
    positive = cursor.fetchone()[0]
    
    # Just a mock for now for top categories based on why_relevant/skills matching
    # In a real setup, we'd have a 'category' column
    categories = {
        "AI": 0,
        "Automation": 0,
        "Growth": 0,
        "Marketing": 0
    }
    
    cursor.execute("SELECT skills_required FROM opportunities WHERE status != 'archived'")
    for row in cursor.fetchall():
        skills = str(row[0]).lower()
        if 'ai' in skills: categories['AI'] += 1
        if 'automation' in skills: categories['Automation'] += 1
        if 'growth' in skills: categories['Growth'] += 1
        if 'marketing' in skills: categories['Marketing'] += 1
        
    conn.close()
    
    return {
        "opportunities_found": found,
        "outreach_sent": sent,
        "replies_received": replies,
        "positive_replies": positive,
        "interviews_booked": int(positive * 0.4), # simulated for now
        "top_categories": categories,
        "top_angles": [
            {"type": "Direct AI Pitch", "response_rate": "14%"},
            {"type": "Growth Operator Flex", "response_rate": "11%"},
            {"type": "Automations Audit", "response_rate": "8%"}
        ]
    }
