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
    # Extract Policy Constraints
    max_fear = policy.get("thresholds", {}).get("max_fear_score", 3)
    
    # Extract Dynamic Media Quotas
    quotas = policy.get("media_quotas", {})
    q_podcasts = quotas.get("podcasts", 4)
    q_videos = quotas.get("videos", 4)
    q_research = quotas.get("research", 2)
    q_news = quotas.get("news", 1)
    q_deep_dive = quotas.get("deep_dive", 1)

    # Extract Cognitive Fingerprint
    fingerprint = policy.get("cognitive_fingerprint", {})
    w_sys = fingerprint.get("systemic_curiosity", 0.14)
    w_nuance = fingerprint.get("nuance_endurance", 0.17)
    w_temp = fingerprint.get("temporal_horizon", 0.19)
    w_const = fingerprint.get("constructive_realism", 0.18)
    w_abs = fingerprint.get("theoretical_abstraction", 0.32)
    
    candidates = []
    now_ms = int(time.time() * 1000)
    
    print("📡 Fetching raw data from all sources...")
    raw_items = []
    raw_items.extend(fetch_rss_whitelist())
    raw_items.extend(fetch_youtube_whitelist())
    raw_items.extend(fetch_relevant_news())
    raw_items.extend(fetch_listen_notes('resilience OR relationship psychology'))
    raw_items.extend(fetch_podcast_index('anthropology OR sociology OR digital subculture'))

    print(f"📊 DIAGNOSTIC: Pulled {len(raw_items)} total raw items from the APIs.")

    # --- 1. PYTHON HARD FILTERING ---
    for item in raw_items:
        if not is_unseen(item["canonical_hash"], memory):
            continue
        if not passes_veto_check(item):
            continue
            
        # Natively drop high-harm news before wasting Gemini tokens
        if item["source_type"] == "news" and not item.get("scoring_metrics", {}).get("hopeful_rewrite_eligible", True):
            continue
            
        # Extended freshness to 30 days for academic feeds, kept at 7 for news
        if item["source_type"] == "rss":
            if (now_ms - item["published_date_ms"]) > (30 * 24 * 60 * 60 * 1000):
                continue 
        elif item["source_type"] == "news":
            if (now_ms - item["published_date_ms"]) > (7 * 24 * 60 * 60 * 1000):
                continue
                
        candidates.append(item)

    print(f"📊 DIAGNOSTIC: {len(candidates)} items survived memory/veto/age filters.")

    # Widened the funnel to 90 to prevent Bucket Starvation
    candidates = candidates[:90]
    if not candidates:
        return []

    print(f"🧠 Sending {len(candidates)} items to Gemini for Semantic Triage...")
    
    # --- 2. GEMINI SEMANTIC TRIAGE ---
    scored_metrics = semantic_triage(candidates)
    score_map = {s["native_id"]: s for s in scored_metrics}
    
    print(f"📊 DIAGNOSTIC: Gemini successfully scored {len(score_map)} items.")

    # --- 3. THE COGNITIVE SORTING HAT ---
    valid_items = []
    fear_rejects = 0

    for item in candidates:
        scores = score_map.get(item["native_id"])
        if not scores:
            continue
            
        # Track how many are being rejected for fear/slop
        if scores.get("fear_score", 0) > max_fear or scores.get("ai_slop_penalty", 0) > 4:
            fear_rejects += 1
            continue

        s_sys = scores.get("systemic_score", 0)
        s_nuance = scores.get("nuance_score", 0)
        s_temp = scores.get("temporal_score", 0)
        s_const = scores.get("constructive_score", 0)
        s_abs = scores.get("abstraction_score", 0)

        item["sort_weight"] = (
            (s_sys * w_sys) +
            (s_nuance * w_nuance) +
            (s_temp * w_temp) +
            (s_const * w_const) +
            (s_abs * w_abs)
        )
        item["deep_dive_score"] = s_sys + s_nuance + s_temp
        
        valid_items.append(item)

    print(f"📊 DIAGNOSTIC: {fear_rejects} items were rejected for high fear/slop scores.")
    print(f"📊 DIAGNOSTIC: {len(valid_items)} elite items available for bucketing.")

    # --- 4. DYNAMIC BUCKET SYSTEM ---
    final_selection = []
    seen_ids = set()

    # Deep Dive
    valid_items.sort(key=lambda x: x["deep_dive_score"], reverse=True)
    count = 0
    for d in valid_items:
        if count >= q_deep_dive: break
        d["category"] = "deep_dive"
        final_selection.append(d)
        seen_ids.add(d["native_id"])
        count += 1

    # Re-sort remaining by pure cognitive alignment
    valid_items.sort(key=lambda x: x["sort_weight"], reverse=True)

    podcasts = [i for i in valid_items if i["source_type"] == "podcast"]
    videos = [i for i in valid_items if i["source_type"] == "youtube"]
    research = [i for i in valid_items if i["source_type"] == "rss"]
    news_items = [i for i in valid_items if i["source_type"] == "news"]
    
    print(f"📊 DIAGNOSTIC BUCKET INVENTORY: Podcasts: {len(podcasts)}, Videos: {len(videos)}, RSS: {len(research)}, News: {len(news_items)}")

    # Podcasts
    count = 0
    for p in podcasts:
        if count >= q_podcasts: break
        if p["native_id"] not in seen_ids:
            p["category"] = "positivity"
            final_selection.append(p)
            seen_ids.add(p["native_id"])
            count += 1

    # Videos
    count = 0
    for v in videos:
        if count >= q_videos: break
        if v["native_id"] not in seen_ids:
            v["category"] = "positivity"
            final_selection.append(v)
            seen_ids.add(v["native_id"])
            count += 1

    # Research
    count = 0
    for r in research:
        if count >= q_research: break
        if r["native_id"] not in seen_ids:
            r["category"] = "positivity"
            final_selection.append(r)
            seen_ids.add(r["native_id"])
            count += 1
            
    # News
    count = 0
    for n in news_items:
        if count >= q_news: break
        if n["native_id"] not in seen_ids:
            n["category"] = "positivity"
            final_selection.append(n)
            seen_ids.add(n["native_id"])
            count += 1

    return final_selection
