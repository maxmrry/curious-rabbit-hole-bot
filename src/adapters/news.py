import requests
from datetime import datetime
from src.pipeline.memory_mgr import create_standard_item

# --- SCORING WEIGHTS & KEYWORDS ---
EMOTION_WEIGHTS = {
    "calm": 2,
    "frustrating": -1,
    "scary": -4
}

ISSUE_WEIGHTS = {
    "Human Development": 2,
    "Science & Technology": 1,
    "General News": 0,
    "Existential Threats": -3
}

POSITIVE_KEYWORDS = [
    "agreement", "access", "stabilizer", "resilience", "cooperation",
    "open", "boost", "buffer", "reform", "support", "defense",
    "integration", "innovation", "recovery", "peace", "education"
]

NEGATIVE_KEYWORDS = [
    "war", "strike", "killed", "closure", "blockade", "recession",
    "nuclear", "casualty", "escalation", "threat", "attack",
    "civilian harm", "oil shock"
]

def score_article(article):
    """
    Applies the Power of Bad filtering logic.
    Calculates constructive value vs harm risk to determine rewrite eligibility.
    """
    # Combine relevant text fields for keyword scanning
    text_components = [
        article.get("title", ""),
        article.get("summary", ""),
        article.get("marketingBlurb", ""),
        article.get("relevanceSummary", ""),
        article.get("relevanceReasons", ""),
        article.get("antifactors", "")
    ]
    text = " ".join([str(t) for t in text_components if t]).lower()

    positive_hits = sum(1 for k in POSITIVE_KEYWORDS if k in text)
    negative_hits = sum(1 for k in NEGATIVE_KEYWORDS if k in text)

    emotion_tag = article.get("emotionTag", "")
    emotion_score = EMOTION_WEIGHTS.get(emotion_tag, 0)
    
    issue_name = article.get("issue", {}).get("name", "General News")
    issue_score = ISSUE_WEIGHTS.get(issue_name, 0)

    # Base constructive score
    constructive_score = (
        (positive_hits * 2) +
        emotion_score +
        issue_score +
        (1 if article.get("relevance", 0) >= 6 else 0)
    )

    # Base harm risk score
    harm_risk_score = (
        (negative_hits * 2) +
        (4 if emotion_tag == "scary" else 0) +
        (5 if "killed" in text else 0) +
        (4 if "war" in text else 0) +
        (5 if "nuclear" in text else 0)
    )

    positive_angle_score = constructive_score - harm_risk_score

    # Determine if it is ethically viable to frame positively
    rewrite_eligible = positive_angle_score >= 2 and harm_risk_score < 8

    return {
        "positive_angle_score": positive_angle_score,
        "constructive_score": constructive_score,
        "harm_risk_score": harm_risk_score,
        "hopeful_rewrite_eligible": rewrite_eligible,
        "raw_emotion": emotion_tag
    }

def fetch_relevant_news():
    """
    Fetches the latest global news, scores it, and normalizes it.
    """
    url = "https://actually-relevant-api.onrender.com/api/stories?issueSlug=general-news"
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("data", []):
            # 1. Run the psychological scoring math
            scores = score_article(item)
            
            # 2. Map to our universal internal memory schema
            # We pass the published date, converting standard ISO strings to milliseconds if needed
            pub_date = item.get("datePublished")
            date_ms = int(datetime.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp() * 1000) if pub_date else None
            
            normalized = create_standard_item(
                native_id=item.get("id", item.get("slug")),
                title=item.get("title", ""),
                description=item.get("summary", ""),
                url=item.get("sourceUrl", ""),
                source_type="news",
                source_name=item.get("sourceTitle", "Unknown Source"),
                date_ms=date_ms
            )
            
            # 3. Attach the scoring metadata so the filtering brain can sort it later
            normalized["scoring_metrics"] = scores
            results.append(normalized)
            
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"🚨 News API fetch failed: {e}")
        return []
