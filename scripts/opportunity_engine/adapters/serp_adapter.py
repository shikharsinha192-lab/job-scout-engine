import os
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Any
import httpx
from .base_adapter import BaseAdapter
from ..models.opportunity import RawSignal

class SerpAdapter(BaseAdapter):
    def __init__(self, query_bank_path: str = "scripts/opportunity_engine/data/query_bank.json"):
        super().__init__()
        self.query_bank_path = query_bank_path
        
        # Adjust path if we are running from a different directory
        actual_path = self.query_bank_path
        if not os.path.exists(actual_path):
            actual_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "query_bank.json")
            
        with open(actual_path, 'r', encoding='utf-8') as f:
            self.query_bank = json.load(f)
            
        self.api_key = os.getenv("SERPAPI_KEY")

    async def _fetch_raw_data(self) -> List[Any]:
        if not self.api_key:
            self.logger.info("No SERPAPI_KEY found, returning robust mock data.")
            return self._get_mock_data()
            
        raw_items = []
        async with httpx.AsyncClient() as client:
            for layer in self.query_bank:
                layer_name = layer.get("layer_name")
                queries = layer.get("serp_queries", [])
                
                for query in queries:
                    try:
                        params = {
                            "engine": "google",
                            "q": query,
                            "api_key": self.api_key,
                            "num": 5
                        }
                        response = await client.get("https://serpapi.com/search", params=params)
                        if response.status_code == 200:
                            data = response.json()
                            results = data.get("organic_results", [])
                            for res in results:
                                res['layer_name'] = layer_name
                                res['query_used'] = query
                                raw_items.append(res)
                    except Exception as e:
                        self.logger.error(f"Error searching SerpAPI for {query}: {e}")
        return raw_items

    def _normalize(self, raw_item: Any) -> RawSignal:
        if "is_mock" in raw_item:
            return RawSignal(**raw_item["data"])
            
        title = raw_item.get("title", "")
        snippet = raw_item.get("snippet", "")
        link = raw_item.get("link", "")
        
        platform = "Web"
        if "linkedin.com" in link:
            platform = "LinkedIn"
        elif "twitter.com" in link or "x.com" in link:
            platform = "X"
            
        return RawSignal(
            url=link,
            platform=platform,
            text=f"{title}\n{snippet}",
            author="Unknown", # Hard to parse robustly from generic SERP
            date=datetime.now(timezone.utc).isoformat(), # SERP doesn't always provide precise date
            intelligence_layer=raw_item["layer_name"],
            query_used=raw_item["query_used"],
            days_old=0
        )

    def _get_mock_data(self) -> List[Any]:
        return [
            {
                "is_mock": True,
                "data": {
                    "url": "https://linkedin.com/posts/mock1",
                    "platform": "LinkedIn",
                    "text": "We are looking for a fractional CMO to help scale our paid ads.",
                    "author": "Jane Doe",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "intelligence_layer": "ASYMMETRIC_SIGNALS",
                    "query_used": "looking for a fractional cmo",
                    "days_old": 1
                }
            },
            {
                "is_mock": True,
                "data": {
                    "url": "https://twitter.com/mock2",
                    "platform": "X",
                    "text": "Can't afford a full time marketer but need help with our GTM strategy.",
                    "author": "John Smith",
                    "date": datetime.now(timezone.utc).isoformat(),
                    "intelligence_layer": "ASYMMETRIC_SIGNALS",
                    "query_used": "can't afford a full time marketer",
                    "days_old": 0
                }
            }
        ]
