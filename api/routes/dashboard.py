from fastapi import APIRouter
from api.db import get_db

router = APIRouter()

@router.get("/stats")
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    # New opportunities found today
    cursor.execute("SELECT COUNT(*) FROM opportunities WHERE date(created_at) = date('now')")
    today_found = cursor.fetchone()[0]
    
    # Opportunities ready for outreach (approved and email found)
    cursor.execute("SELECT COUNT(*) FROM opportunities WHERE status = 'approved' AND email_hunt_status = 'email_found'")
    ready_outreach = cursor.fetchone()[0]
    
    # Outreach sent this week
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE sent_at >= datetime('now', '-7 days')")
    sent_week = cursor.fetchone()[0]
    
    # Positive responses
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'positive'")
    positive_replies = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "today_found": today_found,
        "ready_for_outreach": ready_outreach,
        "sent_this_week": sent_week,
        "positive_replies": positive_replies
    }

@router.get("/daily-batch")
def get_daily_batch(limit: int = 15):
    conn = get_db()
    cursor = conn.cursor()
    
    # Prioritize: HIGH priority, not yet processed
    cursor.execute("""
        SELECT * FROM opportunities 
        WHERE status = 'new'
        ORDER BY 
            CASE outreach_priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
            relevance_score DESC,
            legitimacy_score DESC
        LIMIT ?
    """, (limit,))
    
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs
