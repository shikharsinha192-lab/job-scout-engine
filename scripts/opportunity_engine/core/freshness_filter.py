from datetime import datetime
import dateutil.parser
from typing import List, Dict, Any

class FreshnessFilter:
    def __init__(self, max_days_old: int = 7):
        self.max_days_old = max_days_old

    def _parse_and_get_delta(self, date_string: str) -> int:
        if not date_string:
            return 999
            
        try:
            post_date = dateutil.parser.parse(date_string)
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            now = datetime.now(post_date.tzinfo)
            delta = (now - post_date).days
            
            # Reject future dates (delta < 0) as invalid data
            if delta < 0:
                print(f"[FreshnessFilter] Rejecting invalid future date: {date_string}")
                return 999
                
            return delta
        except (ValueError, OverflowError, TypeError) as e:
            # Catch specific parsing errors, not bare Except
            print(f"[FreshnessFilter] Error parsing date '{date_string}': {e}")
            return 999
        except Exception as e:
            print(f"[FreshnessFilter] Unexpected parsing failure: {e}")
            return 999

    def filter(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        fresh_opps = []
        for opp in opportunities:
            days_old = self._parse_and_get_delta(opp.get('date', ''))
            
            if 0 <= days_old <= self.max_days_old:
                opp['days_old'] = days_old
                fresh_opps.append(opp)
        return fresh_opps
