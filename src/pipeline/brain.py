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
    and mathematically selects items based on policy.yaml thresholds.
    """
    # Extract Policy Constraints
    pos_quota = policy.get("ratios", {}).get("positivity", 7)
    dive_quota = policy.get("ratios", {}).get("deep_dive", 2)
    max_fear = policy.get("thresholds", {}).get("max_fear_score", 3)
    min_constructive = policy.get("thresholds", {}).get("min_constructive_score", 5)
    
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

    pool_positivity = []
    pool_deep_dive = []

    # --- 3. THE SORTING HAT (Math) ---
    for item in candidates:
        scores = score_map.get(item["native_id"])
        if not scores:
            continue
            
        # Hard Brakes tied dynamically to policy.yaml
        if scores.get("fear_score", 0) > max_fear or scores.get("ai_slop_penalty", 0) > 4 or scores.get("timelessness_score", 10) < 5:
            continue

        c_score = scores.get("constructive_score", 0)
        a_score = scores.get("anthropology_score", 0)

        if c_score >= a_score and c_score >= min_constructive:
            item["sort_weight"] = c_score + scores.get("timelessness_score", 0)
            item["category"] = "positivity"
            pool_positivity.append(item)
        elif a_score > c_score and a_score >= min_constructive:
            item["sort_weight"] = a_score + scores.get("timelessness_score", 0)
            item["category"] = "deep_dive"
            pool_deep_dive.append(item)

    pool_positivity.sort(key=lambda x: x["sort_weight"], reverse=True)
    pool_deep_dive.sort(key=lambda x: x["sort_weight"], reverse=True)

    # --- 4. ENFORCE POLICY RATIOS ---
    final_selection = []
    final_selection.extend(pool_positivity[:pos_quota])
    final_selection.extend(pool_deep_dive[:dive_quota])
    
    return final_selection
