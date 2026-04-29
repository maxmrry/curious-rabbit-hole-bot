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

    # --- Extract Cognitive Fingerprint ---
    fingerprint = policy.get("cognitive_fingerprint", {})
    w_sys = fingerprint.get("systemic_curiosity", 0.14)
    w_nuance = fingerprint.get("nuance_endurance", 0.17)
    w_temp = fingerprint.get("temporal_horizon", 0.19)
    w_const = fingerprint.get("constructive_realism", 0.18)
    w_abs = fingerprint.get("theoretical_abstraction", 0.32)

    # --- 3. THE COGNITIVE SORTING HAT (Weighted Math) ---
    valid_items = []

    for item in candidates:
        scores = score_map.get(item["native_id"])
        if not scores:
            continue
            
        # The Shield: Block severe anxiety triggers and algorithmic slop
        if scores.get("fear_score", 0) > max_fear or scores.get("ai_slop_penalty", 0) > 4:
            continue

        # Extract Gemini's 1-10 assessments
        s_sys = scores.get("systemic_score", 0)
        s_nuance = scores.get("nuance_score", 0)
        s_temp = scores.get("temporal_score", 0)
        s_const = scores.get("constructive_score", 0)
        s_abs = scores.get("abstraction_score", 0)

        # THE ALIGNMENT EQUATION: Multiply content scores by your unique cognitive weights
        alignment_score = (
            (s_sys * w_sys) +
            (s_nuance * w_nuance) +
            (s_temp * w_temp) +
            (s_const * w_const) +
            (s_abs * w_abs)
        )
        
        item["sort_weight"] = alignment_score
        valid_items.append(item)

    # Sort strictly by what aligns best with your cognitive fingerprint
    valid_items.sort(key=lambda x: x["sort_weight"], reverse=True)

    # --- 4. SELECT TOP 9 ITEMS ---
    # We no longer force source diversity or strict media ratios.
    # The top 9 items mathematically tailored to your brain win.
    return valid_items[:9]
