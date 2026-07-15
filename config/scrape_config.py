"""
Job Scout Engine: Global Scraping Configuration
"""

ROLE_KEYWORDS = {
    "growth": [
        "growth marketer", "head of growth", "growth lead", "growth manager",
        "growth generalist", "founding growth"
    ],
    "performance_mkt": [
        "performance marketing", "paid media", "media buyer", "meta ads",
        "google ads", "sem", "ppc", "user acquisition"
    ],
    "ai_marketing": [
        "ai marketing", "marketing automation", "martech", "ai-native",
        "ai growth", "ai ops", "growth operator"
    ],
    "product": [
        "product manager", "product growth", "growth pm", "associate pm",
        "product strategy", "apm"
    ],
    "strategy": [
        "strategy", "gtm", "go-to-market", "revops", "revenue operations",
        "business development", "bizdev"
    ],
    "content": [
        "content marketing", "seo", "content lead", "content strategist"
    ],
    "founders_office": [
        "founder's office", "chief of staff", "0 to 1", "growth generalist"
    ]
}

GEO_MODES = {
    "india_startup": {
        "description": "Indian startups (Series A-C) and local remote roles",
        "filters": ["India", "Remote India"]
    },
    "us_remote": {
        "description": "US-based companies hiring remotely worldwide or specifically in APAC/India",
        "filters": ["worldwide", "open to all", "anywhere", "apac"]
    },
    "uae_remote": {
        "description": "UAE companies hiring remotely",
        "filters": ["UAE", "United Arab Emirates", "remote"]
    },
    "yc_funded": {
        "description": "YC-backed startups and highly funded early-stage startups globally",
        "filters": ["worldwide", "india"]
    }
}

def get_role_keywords(roles_list):
    """Returns a flat list of keywords based on requested roles, or all if 'all' is passed."""
    if "all" in [r.lower() for r in roles_list]:
        return [kw for keywords in ROLE_KEYWORDS.values() for kw in keywords]
    
    selected_keywords = []
    for role in roles_list:
        role = role.strip().lower()
        if role in ROLE_KEYWORDS:
            selected_keywords.extend(ROLE_KEYWORDS[role])
    return selected_keywords
