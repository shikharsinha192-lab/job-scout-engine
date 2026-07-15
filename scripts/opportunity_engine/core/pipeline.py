import os
import json
import sqlite3
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from scripts.opportunity_engine.adapters.serp_adapter import SerpAdapter
from scripts.opportunity_engine.core.freshness_filter import FreshnessFilter
from scripts.opportunity_engine.core.heuristic_filter import HeuristicFilter
from scripts.opportunity_engine.core.deduplicator import Deduplicator
from scripts.opportunity_engine.core.llm_evaluator import LLMEvaluator

class OpportunityPipeline:
    def __init__(self, use_mock_data: bool = True, max_days_old: int = 7, queue: Optional[asyncio.Queue] = None):
        self.use_mock_data = use_mock_data
        self.max_days_old = max_days_old
        self.queue = queue
        self.adapters = [
            SerpAdapter(use_mock_data=use_mock_data)
        ]
        self.freshness_filter = FreshnessFilter(max_days_old=max_days_old)
        self.heuristic_filter = HeuristicFilter()
        self.deduplicator = Deduplicator(lsh_threshold=0.7, rapidfuzz_threshold=85.0)
        self.llm_evaluator = LLMEvaluator(use_mock_api=use_mock_data)
        
        # Concurrency-safe SQLite Cache
        self.db_path = "data/cache/evaluated_urls.db"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS cache (
                                url TEXT PRIMARY KEY,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                            )''')
            # TTL: Purge entries older than max_days_old + 1
            cutoff_date = datetime.now() - timedelta(days=self.max_days_old + 1)
            conn.execute("DELETE FROM cache WHERE timestamp < ?", (cutoff_date,))

    def is_cached(self, url: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM cache WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    def save_to_cache(self, urls: List[str]):
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("INSERT OR IGNORE INTO cache (url) VALUES (?)", [(u,) for u in urls])

    async def emit_progress(self, message: str):
        if self.queue:
            await self.queue.put({"type": "progress", "message": message})
        print(f"[Pipeline] {message}")

    async def _run_adapter(self, adapter) -> List[Dict[str, Any]]:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, adapter.execute)
            return result
        except Exception as e:
            await self.emit_progress(f"Adapter {adapter.__class__.__name__} failed: {e}")
            return []

    async def run(self):
        await self.emit_progress(f"Starting extraction with {len(self.adapters)} adapters (Freshness: {self.max_days_old} days)")
        
        # Concurrently run adapters
        results = await asyncio.gather(*(self._run_adapter(adapter) for adapter in self.adapters))
        
        all_raw_opps = []
        for res in results:
            all_raw_opps.extend(res)
            
        await self.emit_progress(f"Total raw opportunities collected: {len(all_raw_opps)}")
        
        # Filter out cached ones before deduplication
        uncached_opps = []
        for opp in all_raw_opps:
            url = opp.get("url")
            if url and self.is_cached(url):
                continue
            uncached_opps.append(opp)
            
        await self.emit_progress(f"After cache check: {len(uncached_opps)} opportunities remaining.")
        
        # 1. Deduplicate
        deduped_opps = self.deduplicator.deduplicate(uncached_opps)
        await self.emit_progress(f"After deduplication: {len(deduped_opps)} opportunities.")
        
        # 2. Freshness Filter
        fresh_opps = self.freshness_filter.filter(deduped_opps)
        await self.emit_progress(f"After freshness check: {len(fresh_opps)} opportunities.")
        
        # 3. Heuristic Triage
        triage_opps = self.heuristic_filter.filter_batch(fresh_opps)
        await self.emit_progress(f"After heuristic triage: {len(triage_opps)} opportunities.")
        
        # 4. LLM Evaluation
        if triage_opps:
            await self.emit_progress(f"Starting LLM evaluation for {len(triage_opps)} opportunities...")
            loop = asyncio.get_event_loop()
            evaluated_opps = await loop.run_in_executor(None, self.llm_evaluator.evaluate_batch, triage_opps)
        else:
            evaluated_opps = []
            
        await self.emit_progress(f"LLM Evaluation complete. {len(evaluated_opps)} viable opportunities found.")
        
        # 5. Output and Update Cache
        if evaluated_opps:
            self.save_output(evaluated_opps)
        
        # Cache URLs spent on compute
        urls_to_cache = [opp.get('url') for opp in triage_opps if opp.get('url')]
        if urls_to_cache:
            self.save_to_cache(urls_to_cache)
            
        await self.emit_progress("Pipeline execution finished.")

    def save_output(self, data: List[Dict[str, Any]]):
        output_dir = "data/opportunities"
        os.makedirs(output_dir, exist_ok=True)
        # Avoid timestamp collisions
        safe_suffix = uuid.uuid4().hex[:6]
        filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_suffix}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"[Pipeline] Saved {len(data)} opportunities to {filepath}")

if __name__ == "__main__":
    async def main():
        pipeline = OpportunityPipeline(use_mock_data=True, max_days_old=7)
        await pipeline.run()
    asyncio.run(main())
