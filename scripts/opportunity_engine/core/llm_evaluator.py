import os
import uuid
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai

class SignalScore(BaseModel):
    id: str = Field(description="The original ID of the opportunity")
    title: str = Field(description="A synthesized short title for this opportunity")
    company: str = Field(description="The company name, if detectable")
    category: str = Field(description="Category of the opportunity (e.g. marketing, development, sales)")
    intent_signal: str = Field(description="The core reason this is a good opportunity")
    opportunity_type: str = Field(description="e.g. freelance, full-time, consultation")
    contact_path: str = Field(description="How to contact them: email, dm, reply")
    email: str = Field(description="Email address if present in text", default="")
    dm_available: bool = Field(description="Whether a DM is likely available on this platform")
    legitimacy_score: int = Field(description="0-100 score on how real/legit this post looks")
    outreach_score: int = Field(description="0-100 score on how likely they are to respond to outreach")
    freshness_score: int = Field(description="0-100 score based on how recent this is")
    confidence: str = Field(description="High, Medium, or Low confidence in this assessment")
    why_it_matters: str = Field(description="1-2 sentences on why this is a strong signal")
    intelligence_layer: str = Field(description="Additional insights or context deduced from the post")
    dedupe_key: str = Field(description="A unique semantic key to help deduplicate similar posts")

class BatchSignalScores(BaseModel):
    scores: List[SignalScore]

class LLMEvaluator:
    def __init__(self, use_mock_api: bool = True):
        self.use_mock_api = use_mock_api
        self.api_key = os.getenv("GEMINI_API_KEY_PAID")
        if not self.use_mock_api:
            self.client = genai.Client(api_key=self.api_key)

    def _mock_evaluate(self, opp: Dict[str, Any]) -> Dict[str, Any]:
        text = str(opp.get('text', '') or '').lower()
        is_marketing = 'marketing' in text or 'growth' in text or 'cac' in text or 'ai' in text
        is_hiring = 'freelance' in text or 'hiring' in text or 'help' in text or 'audit' in text
        
        confidence = "High" if (is_marketing and is_hiring) else "Low"
        score = 90 if confidence == "High" else 20
        
        return {
            "id": opp.get("id", str(uuid.uuid4())),
            "title": f"Opportunity from {opp.get('author', 'Unknown')}",
            "company": opp.get('author', 'Unknown'),
            "category": "marketing/growth" if is_marketing else "other",
            "intent_signal": "Explicit need for help or freelancer" if is_hiring else "None",
            "opportunity_type": "freelance" if 'freelance' in text else "help-needed",
            "contact_path": "dm" if 'dm' in text else "reply",
            "email": "founder@example.com" if 'founder@example.com' in text else "",
            "dm_available": True,
            "legitimacy_score": score,
            "outreach_score": score,
            "freshness_score": 90,
            "confidence": confidence,
            "why_it_matters": "High intent keyword match mapped to mock logic.",
            "intelligence_layer": "Mock intelligence layer",
            "dedupe_key": opp.get('url', str(uuid.uuid4()))
        }

    def _live_evaluate_batch(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not opportunities:
            return []
            
        # Prepare inputs
        inputs = []
        for opp in opportunities:
            inputs.append({
                "id": opp.get("id", str(uuid.uuid4())),
                "text": opp.get("text", ""),
                "platform": opp.get("platform", ""),
                "author": opp.get("author", ""),
                "date": opp.get("date", ""),
                "url": opp.get("url", "")
            })
            
        prompt = f"Evaluate the following {len(inputs)} job/freelance opportunities and score them. Return a JSON array matching the schema.\n\nOpportunities:\n{json.dumps(inputs, indent=2)}"
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': BatchSignalScores,
            },
        )
        
        try:
            result = json.loads(response.text)
            scores = result.get("scores", [])
            return scores
        except Exception as e:
            print(f"[LLMEvaluator] Failed to parse LLM response: {e}")
            return []

    def _safe_int(self, val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def evaluate_batch(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not opportunities:
            return []
            
        print(f"[LLMEvaluator] Executing BATCH evaluation for {len(opportunities)} opportunities...")
        evaluated = []
        
        # We need to assign IDs if they don't have them, so we can map back the original data
        for opp in opportunities:
            if "id" not in opp:
                opp["id"] = str(uuid.uuid4())
                
        if self.use_mock_api:
            raw_results = [self._mock_evaluate(opp) for opp in opportunities]
        else:
            raw_results = self._live_evaluate_batch(opportunities)
            
        # Map back to original opportunities
        opp_map = {opp["id"]: opp for opp in opportunities}
        
        for result in raw_results:
            opp_id = result.get("id")
            if not opp_id or opp_id not in opp_map:
                continue
                
            opp = opp_map[opp_id]
            
            # Merge result with original opp metadata
            merged = {**opp, **result}
            
            # Incorporate pre-extracted heuristic emails
            if opp.get('pre_extracted_email') and not merged.get('email'):
                merged['email'] = opp['pre_extracted_email']
                merged['contact_path'] = 'email'
            
            # Safe parsing
            merged['outreach_score'] = self._safe_int(merged.get('outreach_score'), default=0)
            merged['days_old'] = self._safe_int(opp.get('days_old'), default=99)
            
            # Disqualification Filter
            if str(merged.get("confidence")).lower() == "low" or merged['outreach_score'] < 50:
                print(f"[LLMEvaluator] Dropped low confidence/score opp: {merged.get('url')}")
                continue
            
            if not merged.get("contact_path") and not merged.get("email") and not merged.get("dm_available"):
                print(f"[LLMEvaluator] Dropped due to no contact path: {merged.get('url')}")
                continue
                
            evaluated.append(merged)
            
        # Ranking Logic with safe ints
        evaluated.sort(key=lambda x: (
            x.get('days_old', 99), 
            -x.get('outreach_score', 0)
        ))
        
        print(f"[LLMEvaluator] BATCH Evaluation complete. {len(evaluated)} opportunities passed filters.")
        return evaluated
