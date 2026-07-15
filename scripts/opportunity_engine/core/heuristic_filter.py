import re
from typing import List, Dict, Any
from email_validator import validate_email, EmailNotValidError
import phonenumbers

class HeuristicFilter:
    def __init__(self):
        self.intent_keywords = [
            r"\blooking for\b", r"\bhiring\b", r"\bneed help\b", r"\bseeking\b",
            r"\bfreelance\b", r"\bcontract\b", r"\bconsultant\b", r"\baudit\b",
            r"\bbudget\b", r"\bagency\b", r"\bcan someone help\b", r"\banyone recommend\b"
        ]
        self.intent_regex = re.compile("|".join(self.intent_keywords), re.IGNORECASE)
        self.email_regex = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
        self.linkedin_regex = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+")
        
        self.pain_money_keywords = [
            r"\bstruggling\b", r"\burgent\b", r"\basap\b", r"\bdesperate\b", r"\bblocker\b",
            r"\bbudget\b", r"\bpay\b", r"\brates\b", r"\bcost\b", r"\bpricing\b"
        ]
        self.pain_money_regex = re.compile("|".join(self.pain_money_keywords), re.IGNORECASE)

    def evaluate(self, opp: Dict[str, Any]) -> bool:
        # Safe extraction
        text = opp.get('text')
        if not text or not isinstance(text, str):
            return False
            
        if not self.intent_regex.search(text):
            return False
            
        # Robust Email Extraction
        emails = self.email_regex.findall(text)
        valid_emails = []
        for e in emails:
            try:
                valid = validate_email(e, check_deliverability=False)
                valid_emails.append(valid.normalized)
            except EmailNotValidError:
                pass
        
        if valid_emails:
            opp['pre_extracted_email'] = valid_emails[0]
            
        # Phone Extraction
        try:
            for match in phonenumbers.PhoneNumberMatcher(text, "US"):
                opp['pre_extracted_phone'] = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
                break
        except Exception:
            pass
            
        # LinkedIn Profile Extraction
        linkedin_matches = self.linkedin_regex.findall(text)
        if linkedin_matches:
            opp['pre_extracted_linkedin'] = linkedin_matches[0]
            
        # Urgency Scoring
        urgency_score = 0
        days_old = opp.get('days_old', 99)
        if days_old < 3: # < 72h
            urgency_score += 1
            
        replies = opp.get('replies', 0)
        if isinstance(replies, int) and replies <= 3:
            urgency_score += 1
            
        if self.pain_money_regex.search(text):
            urgency_score += 1
            
        opp['urgency_score'] = urgency_score
            
        return True

    def filter_batch(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"[HeuristicFilter] Processing {len(opportunities)} items...")
        passed = []
        for opp in opportunities:
            if self.evaluate(opp):
                passed.append(opp)
                
        print(f"[HeuristicFilter] {len(passed)} items passed heuristic gating.")
        return passed
