import yaml
import time
from src.adapters.podcast import fetch_listen_notes, fetch_podcast_index
from src.adapters.news import fetch_relevant_news
from src.adapters.youtube import fetch_youtube_whitelist
from src.adapters.rss import fetch_rss_whitelist
from src.pipeline.memory_mgr import is_unseen, passes_veto_check
from src.pipeline.philosophy import semantic_triage

def load_policy(filepath='policy/policy.yaml'):
    """Loads the hardcoded ratios and rules for the agent."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("🚨 Critical: policy.yaml not found.")
        return {}

def select_daily_items(memory, policy):
    """
    Gathers data, applies hard age-limits, calls Gemini for Semantic Triage, 
    and mathematically selects the absolute best cognitive items based on the Mental State Model.
    """
    # Extract Policy Constraints
    max_fear = policy.get("thresholds", {}).get("max_fear_score", 3)
    
    candidates = []
    now_ms = int(time.time() * 1000)
    fourteen_days_ms = 14 * 24 * 60 * 60 * 1000
    
    print("📡 Fetching raw data from all sources...")
    raw_items = []
    raw_items.extend(fetch_rss_whitelist())
    raw_items.extend(fetch_youtube_whitelist())
    raw_items.extend(fetch_listen_notes('post-traumatic growth OR relationship psychology'))
    raw_items.extend(fetch_listen_notes('anthropology OR sociology OR digital subculture'))
    raw_items.extend(fetch_relevant_news())

    # --- 1. PYTHON HARD FILTERING ---
    for item in raw_items:
        if not is_unseen(item["canonical_hash"], memory):
            continue
        if not passes_veto_check(item):
            continue
            
        if item["source_type"] in ["news", "rss"]:
            if (now_ms - item["published_date_ms"]) > fourteen_days_ms:
                continue 
                
        candidates.append(item)

    candidates = candidates[:60]
    if not candidates:
        return []

    print(f"🧠 Sending {len(candidates)} items to Gemini for Semantic Triage...")
    
    # --- 2. GEMINI SEMANTIC TRIAGE ---
    scored_metrics = semantic_triage(candidates)
    score_map = {s["native_id"]: s for s in scored_metrics}

    # --- 3. THE COGNITIVE EQUATION (Math) ---
    valid_items = []

    for item in candidates:
        scores = score_map.get(item["native_id"])
        if not scores:
            continue
            
        # The Shield: Block severe anxiety triggers and algorithmic slop
        if scores.get("fear_penalty", 0) > max_fear or scores.get("slop_penalty", 0) > 4:
            continue

        a_score = scores.get("agency_score", 0)
        p_score = scores.get("perspective_score", 0)
        anthro_score = scores.get("anthropology_score", 0)

        # The Psych Score: Reward Agency, Perspective, and Anthropology, while heavily taxing Fear.
        psych_score = (a_score * 1.2) + (p_score * 1.0) + (anthro_score * 1.2) - (scores.get("fear_penalty", 0) * 2.0)

        # Only allow high-signal cognitive nutrition through
        if psych_score >= 10: 
            item["sort_weight"] = psych_score
            valid_items.append(item)

    # Sort strictly by what is best for the user's mental state today
    valid_items.sort(key=lambda x: x["sort_weight"], reverse=True)

    # --- 4. SELECT TOP 9 ITEMS ---
    # We no longer force source diversity or strict media ratios.
    # If one source or medium provides incredible signal today, we consume it.
    return valid_items[:9]
