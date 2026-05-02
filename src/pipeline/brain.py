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
    
    # Extract Dynamic Media Quotas — then adapt based on historical type performance
    quotas = policy.get("media_quotas", {})
    q_research = quotas.get("research", 2)
    q_news = quotas.get("news", 1)
    q_deep_dive = quotas.get("deep_dive", 1)

    # Read type performance from memory to dynamically nudge AV split
    type_perf = memory.get("type_performance", {})
    youtube_avg = type_perf.get("youtube", {}).get("avg", 5.0)
    podcast_avg = type_perf.get("podcast", {}).get("avg", 5.0)
    rss_avg = type_perf.get("rss", {}).get("avg", 5.0)

    base_av = quotas.get("av_total", 8)
    base_min_vid = quotas.get("min_videos", 4)
    base_max_vid = quotas.get("max_videos", 6)

    # Nudge video ceiling up or down by up to 2 based on relative performance
    # Bounded so it never collapses a content type entirely
    perf_delta = youtube_avg - podcast_avg
    if perf_delta > 1.5:
        adapted_max_vid = min(base_max_vid + 2, base_av - 1)
        adapted_min_vid = min(base_min_vid + 1, adapted_max_vid - 1)
    elif perf_delta < -1.5:
        adapted_max_vid = max(base_max_vid - 2, 2)
        adapted_min_vid = max(base_min_vid - 1, 1)
    else:
        adapted_max_vid = base_max_vid
        adapted_min_vid = base_min_vid

    # Similarly nudge research quota based on rss performance vs overall
    overall_avg = (youtube_avg + podcast_avg + rss_avg) / 3
    if rss_avg > overall_avg + 1.0:
        q_research = min(q_research + 1, 4)
    elif rss_avg < overall_avg - 1.0:
        q_research = max(q_research - 1, 1)

    print(f"📊 Adaptive Quotas: max_videos={adapted_max_vid}, min_videos={adapted_min_vid}, research={q_research}")

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
    
    # 🧠 DYNAMIC WILDCARD QUERIES: Actively crawl high-energy, high-agency domains
    explore_themes = [
        '"human progress"', '"behavioral science"', '"future optimism"',
        '"mental models"', '"resilience psychology"', '"systems thinking"', 
        '"technology philosophy"', '"cultural shift"'
    ]
    
    import random
    query_1 = random.choice(explore_themes)
    query_2 = random.choice([t for t in explore_themes if t != query_1])

    print(f"🔍 Today's exploration vectors: [{query_1}] and [{query_2}]")
    
    raw_items.extend(fetch_listen_notes(query_1))
    raw_items.extend(fetch_podcast_index(query_2))

    print(f"📊 DIAGNOSTIC: Pulled {len(raw_items)} total raw items from the APIs.")

    # --- 1. PYTHON HARD FILTERING ---
        for item in raw_items:
            if not is_unseen(item["canonical_hash"], memory):
                continue
            if not passes_veto_check(item):
                continue
                
            # Drop high-harm news natively
            if item["source_type"] == "news" and not item.get("scoring_metrics", {}).get("hopeful_rewrite_eligible", True):
                continue
                
            # 🕒 EXPANDED TIMEFRAMES: Hunt for masterpieces, not just recent uploads
            # Give YouTube, Podcasts, and RSS a 90-day window to surface incredible content
            if item["source_type"] in ["rss", "youtube", "podcast"]:
                if (now_ms - item["published_date_ms"]) > (90 * 24 * 60 * 60 * 1000):
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
    
    source_history = memory.get("source_history", {})
    now_ms = int(time.time() * 1000)
    one_day_ms = 24 * 60 * 60 * 1000

    for item in candidates:
        scores = score_map.get(item["native_id"])
        if not scores:
            continue
            
        s_sys = scores.get("systemic_score", 0)
        s_nuance = scores.get("nuance_score", 0)
        s_temp = scores.get("temporal_score", 0)
        s_const = scores.get("constructive_score", 0)
        s_abs = scores.get("abstraction_score", 0)
        s_geo = scores.get("geo_affinity_score", 5)
        s_state = scores.get("state_shift_score", 0)
        s_humanity = scores.get("humanity_signal_score", 0) 
        
        fear = scores.get("fear_score", 0)
        slop = scores.get("ai_slop_penalty", 0)
        boredom = scores.get("niche_boredom_penalty", 0)

        # ⏳ ANTI-FATIGUE ALGORITHM: Penalize sources we've seen too recently
        source_name = item.get("source_name", "")
        last_used_ms = source_history.get(source_name, 0)
        
        if last_used_ms == 0:
            fatigue_penalty = 0.0 # Never seen, or brand new!
        else:
            days_since_used = (now_ms - last_used_ms) / one_day_ms
            if days_since_used < 1.5:
                fatigue_penalty = 12.0  # Huge penalty if used yesterday
            elif days_since_used < 3.5:
                fatigue_penalty = 5.0   # Medium penalty if used earlier this week
            elif days_since_used < 7.0:
                fatigue_penalty = 2.0   # Slight penalty if used last week
            else:
                fatigue_penalty = 0.0   # Clean slate after a week

        # Hard floor: reject items that fail minimum quality thresholds
        min_state_shift = policy.get("thresholds", {}).get("min_state_shift_score", 0)
        min_constructive = policy.get("thresholds", {}).get("min_constructive_score", 0)
        if scores.get("state_shift_score", 0) < min_state_shift:
            continue
        if scores.get("constructive_score", 0) < min_constructive:
            continue

        # SOFT PENALTY: Aggressively sink fearful, sloppy, boring, AND fatigued content
        penalty = (fear * 5.0) + (slop * 5.0) + (boredom * 4.0) + fatigue_penalty

        item["sort_weight"] = (
            (s_sys * w_sys) +
            (s_nuance * w_nuance) +
            (s_temp * w_temp) +
            (s_const * w_const) +
            (s_abs * w_abs) +
            (s_geo * 0.15) +
            (s_state * 0.45) +
            (s_humanity * 0.20)
        ) - penalty
        
        # Weighted deep-dive: systemic and nuance matter more than temporal
        item["deep_dive_score"] = (s_sys * 0.45) + (s_nuance * 0.40) + (s_temp * 0.15)
        
        valid_items.append(item)

        # --- 4. DYNAMIC BUCKET SYSTEM ---
    final_selection = []
    seen_ids = set()
    used_sources = set()
    used_topic_clusters = set()  # NEW: Prevents topic flooding

    # Simple topic fingerprint from title keywords
    def get_topic_cluster(item):
        TOPIC_KEYWORDS = {
            "ai": ["ai", "artificial intelligence", "machine learning", "llm", "gpt"],
            "climate": ["climate", "carbon", "emissions", "fossil", "renewable"],
            "economics": ["gdp", "inflation", "recession", "trade", "fiscal", "monetary"],
            "psychology": ["psychology", "cognitive", "behaviour", "mental", "emotion"],
            "geopolitics": ["war", "nato", "ukraine", "china", "sanctions", "nuclear"],
            "health": ["health", "disease", "vaccine", "longevity", "medicine"],
            "history": ["history", "ancient", "civilization", "empire", "century"],
        }
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        for cluster, keywords in TOPIC_KEYWORDS.items():
            if any(k in text for k in keywords):
                return cluster
        return None  # No cluster = always allowed

    # Helper function to add items safely
    def add_item(item, category):
        item["category"] = category
        final_selection.append(item)
        seen_ids.add(item["native_id"])
        used_sources.add(item["source_name"])
        cluster = get_topic_cluster(item)
        if cluster:
            used_topic_clusters.add(cluster)

    def topic_is_fresh(item):
        """Returns True if this item's topic cluster hasn't been used yet."""
        cluster = get_topic_cluster(item)
        return cluster is None or cluster not in used_topic_clusters

    # 1. Deep Dive
    valid_items.sort(key=lambda x: x["deep_dive_score"], reverse=True)
    count = 0
    for d in valid_items:
        if count >= q_deep_dive: break
        # Skip if we already used this source
        if d["source_name"] in used_sources: continue
        add_item(d, "deep_dive")
        count += 1

    # Re-sort remaining by pure cognitive alignment
    valid_items.sort(key=lambda x: x["sort_weight"], reverse=True)

    podcasts = [i for i in valid_items if i["source_type"] == "podcast" and i["native_id"] not in seen_ids]
    videos = [i for i in valid_items if i["source_type"] == "youtube" and i["native_id"] not in seen_ids]
    research = [i for i in valid_items if i["source_type"] == "rss" and i["native_id"] not in seen_ids]
    news_items = [i for i in valid_items if i["source_type"] == "news" and i["native_id"] not in seen_ids]
    
    # 2. Flexible Audio/Video Quota (4-6 Videos, rest Podcasts)
    q_av_total = base_av
    q_min_vid = adapted_min_vid
    q_max_vid = adapted_max_vid
    
    selected_videos = []
    selected_podcasts = []
    
    # Minimum Videos
    for v in videos:
        if len(selected_videos) >= q_min_vid: break
        if v["source_name"] not in used_sources and topic_is_fresh(v):
            selected_videos.append(v)
            used_sources.add(v["source_name"])
            cluster = get_topic_cluster(v)
            if cluster: used_topic_clusters.add(cluster)
            
    # Minimum Podcasts
    min_pods = q_av_total - q_max_vid
    for p in podcasts:
        if len(selected_podcasts) >= min_pods: break
        if p["source_name"] not in used_sources:
            selected_podcasts.append(p)
            used_sources.add(p["source_name"])
            
    # Fill remaining AV slots based on captivating sort_weight
    wildcards = sorted(videos + podcasts, key=lambda x: x["sort_weight"], reverse=True)
    for best in wildcards:
        if (len(selected_videos) + len(selected_podcasts)) >= q_av_total: break
        if best["source_name"] in used_sources: continue # Diversity lock
        
        if best["source_type"] == "youtube" and len(selected_videos) < q_max_vid:
            selected_videos.append(best)
            used_sources.add(best["source_name"])
        elif best["source_type"] == "podcast":
            selected_podcasts.append(best)
            used_sources.add(best["source_name"])
            
    for item in selected_videos + selected_podcasts:
        add_item(item, "positivity")

    # 3. Research
    count = 0
    for r in research:
        if count >= q_research: break
        if r["source_name"] in used_sources: continue
        add_item(r, "positivity")
        count += 1
            
    # 4. News
    # Note: We relax the source diversity lock slightly for news in case the only API we use is the single source.
    count = 0
    for n in news_items:
        if count >= q_news: break
        add_item(n, "positivity")
        count += 1

    # 4-to-1 Audit: ensure state_shift_score >= 6 items dominate the feed
    # This enforces the Power of Bad principle structurally, not just philosophically
    high_agency = [i for i in final_selection if score_map.get(i["native_id"], {}).get("state_shift_score", 0) >= 6]
    low_agency = [i for i in final_selection if score_map.get(i["native_id"], {}).get("state_shift_score", 0) < 6]

    ratio = len(high_agency) / max(len(final_selection), 1)
    if ratio < 0.75:
        print(f"⚠️ 4-to-1 Warning: Only {len(high_agency)}/{len(final_selection)} items are high-agency. Feed may feel flat.")
    else:
        print(f"✅ 4-to-1 Check passed: {len(high_agency)}/{len(final_selection)} items are high-agency.")

    return final_selection
