from pydantic import BaseModel

class RawSignal(BaseModel):
    url: str
    platform: str
    text: str
    author: str
    date: str
    intelligence_layer: str
    query_used: str
    days_old: int = 0
    pre_extracted_email: str | None = None
    subreddit: str | None = None
    score: float | None = None
