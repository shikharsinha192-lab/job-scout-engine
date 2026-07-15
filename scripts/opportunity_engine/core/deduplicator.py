import hashlib
from typing import List, Dict, Any
from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz

class Deduplicator:
    def __init__(self, lsh_threshold: float = 0.7, rapidfuzz_threshold: float = 85.0):
        self.lsh_threshold = lsh_threshold
        self.rapidfuzz_threshold = rapidfuzz_threshold
        
    def get_minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=128)
        for d in text.lower().split():
            m.update(d.encode('utf8'))
        return m

    def deduplicate(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped = []
        seen_urls = set()
        lsh = MinHashLSH(threshold=self.lsh_threshold, num_perm=128)
        
        for opp in opportunities:
            url = opp.get('url')
            
            # Exact URL match
            if url and url in seen_urls:
                continue
                
            text = str(opp.get('text', ''))
            m = self.get_minhash(text)
            
            # LSH semantic match
            result = lsh.query(m)
            is_duplicate = False
            for dup_id in result:
                dup_opp = next((o for o in deduped if str(o.get('url', id(o))) == dup_id), None)
                if dup_opp:
                    dup_text = str(dup_opp.get('text', ''))
                    # RapidFuzz refinement
                    score = fuzz.token_sort_ratio(text, dup_text)
                    if score >= self.rapidfuzz_threshold:
                        is_duplicate = True
                        break
                        
            if not is_duplicate:
                uid = url if url else str(id(opp))
                if url:
                    seen_urls.add(url)
                lsh.insert(uid, m)
                deduped.append(opp)
                
        print(f"[Deduplicator] Reduced {len(opportunities)} -> {len(deduped)} items.")
        return deduped
