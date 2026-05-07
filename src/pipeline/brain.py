import json
import yaml
import time
from src.adapters.podcast import fetch_listen_notes, fetch_podcast_index
from src.adapters.news import fetch_relevant_news
from src.adapters.youtube import fetch_youtube_whitelist
from src.adapters.rss import fetch_rss_whitelist
from src.pipeline.memory_mgr import is_unseen, passes_veto_check
from src.pipeline.philosophy import semantic_triage, apply_variety_engine

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

    # Load RLHF feedback adjustments
    try:
        with open("state/feedback.json", "r") as f:
            feedback_data = json.load(f)
    except FileNotFoundError:
        feedback_data = {"source_adjustments": {}, "source_type_adjustments": {}}

    feedback_source_adj = feedback_data.get("source_adjustments", {})
    feedback_type_adj = feedback_data.get("source_type_adjustments", {})
    
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
    # Abstraction should enrich the system, not dominate it.
    # Too much anti-abstraction drifts toward wholesome anti-intellectualism.
    w_abs = fingerprint.get("theoretical_abstraction", 0.12)
    
    candidates = []
    now_ms = int(time.time() * 1000)
    
    print("📡 Fetching raw data from all sources...")
    raw_items = []
    raw_items.extend(fetch_rss_whitelist())
    raw_items.extend(fetch_youtube_whitelist())
    raw_items.extend(fetch_relevant_news())
    
    # 🎯 MULTI-DIMENSIONAL HUNTING ARCHITECTURE
    # Actively hunts across psychological pillars to prevent emotional monotony and intellectual monoculture.
    psychological_pillars = [
        {"theme": "humanity", "weight": 0.25, "queries": ['"human connection"', '"community"', '"mutual aid"']},
        {"theme": "competence", "weight": 0.25, "queries": ['"makers"', '"engineering"', '"craftsmanship"', '"problem solving"']},
        {"theme": "wonder", "weight": 0.20, "queries": ['"discovery"', '"deep time"', '"natural world"']},
        {"theme": "beauty", "weight": 0.10, "queries": ['"art"', '"design"', '"aesthetics"']},
        {"theme": "joy", "weight": 0.10, "queries": ['"play"', '"hobby"', '"enthusiasm"']},
        {"theme": "wisdom", "weight": 0.10, "queries": ['"mental models"', '"stoicism"', '"perspective"']}
    ]

    import random
    
    # Weighted random selection for our two API hunting queries
    weights = [p["weight"] for p in psychological_pillars]
    chosen_pillar_1 = random.choices(psychological_pillars, weights=weights, k=1)[0]
    
    # Remove the first choice to ensure we hunt two different domains today
    remaining_pillars = [p for p in psychological_pillars if p["theme"] != chosen_pillar_1["theme"]]
    remaining_weights = [p["weight"] for p in remaining_pillars]
    chosen_pillar_2 = random.choices(remaining_pillars, weights=remaining_weights, k=1)[0]

    query_1 = random.choice(chosen_pillar_1["queries"])
    query_2 = random.choice(chosen_pillar_2["queries"])

    print(f"🎯 Today's Active Hunt: [{chosen_pillar_1['theme'].upper()}] & [{chosen_pillar_2['theme'].upper()}]")
    
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
        s_wonder = scores.get("wonder_score", 0)
        s_humanity = scores.get("humanity_signal_score", 0)
        s_reality = scores.get("reality_contact_score", 0)
        s_delight = scores.get("delight_score", 0)
        
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

        # RLHF nudge: blend in Max's direct feedback signals
        source_feedback = feedback_source_adj.get(source_name, {})
        type_feedback = feedback_type_adj.get(item.get("source_type", ""), {})

        # Normalise cumulative score to a bounded nudge (-2.0 to +2.0)
        def bounded_nudge(adj, cap=2.0):
            if not adj or adj.get("n", 0) == 0:
                return 0.0
            raw = adj["cumulative"] / max(adj["n"], 1)
            return max(-cap, min(cap, raw))

        rlhf_nudge = (bounded_nudge(source_feedback) * 0.6) + (bounded_nudge(type_feedback) * 0.4)

        item["sort_weight"] = (
            (s_sys * w_sys) +
            (s_nuance * w_nuance) +
            (s_temp * w_temp) +
            (s_const * w_const) +
            (s_abs * w_abs) +
            (s_geo * 0.15) +
            (s_state * 0.35) +
            (s_wonder * 0.25) +
            (s_humanity * 0.18) +
            (s_reality * 0.22) +
            (s_delight * 0.18) +
            rlhf_nudge
        ) - penalty
        
        # Weighted deep-dive: systemic and nuance matter more than temporal
        item["deep_dive_score"] = (s_sys * 0.45) + (s_nuance * 0.40) + (s_temp * 0.15)
        
        valid_items.append(item)

    # --- 4. DYNAMIC BUCKET SYSTEM ---
    final_selection = []
    SERENDIPITY_SLOT_COUNT = 1
    seen_ids = set()
    used_sources_today = set()   # NEW: Strict Intra-Day Lock
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

    MONTHLY_SOURCE_CAP = 4  # Max times a source can appear in a calendar month

    def add_item(item, category):
        """Helper to instantly update all our tracking sets when an item is selected."""
        item["category"] = category
        final_selection.append(item)
        seen_ids.add(item["native_id"])
        used_sources_today.add(item["source_name"])
        cluster = get_topic_cluster(item)
        if cluster:
            used_topic_clusters.add(cluster)

    def topic_is_fresh(item):
        cluster = get_topic_cluster(item)
        return cluster is None or cluster not in used_topic_clusters

    def source_under_monthly_cap(item, memory):
        from src.pipeline.memory_mgr import get_monthly_source_count
        count = get_monthly_source_count(memory, item.get("source_name", ""))
        return count < MONTHLY_SOURCE_CAP

    def is_eligible(item, memory, is_news=False):
        """Master check for intra-day locks, topic floods, and monthly limits."""
        if item["source_name"] in used_sources_today: return False
        
        # Relax strict topic/monthly caps slightly for News
        if not is_news:
            if not topic_is_fresh(item): return False
            if not source_under_monthly_cap(item, memory): return False
            
        return True

    # 1. Deep Dive
    valid_items.sort(key=lambda x: x["deep_dive_score"], reverse=True)
    count = 0
    for d in valid_items:
        if count >= q_deep_dive: break
        if not is_eligible(d, memory): continue
        
        add_item(d, "deep_dive")
        count += 1

    # Re-sort remaining by pure cognitive alignment
    valid_items.sort(key=lambda x: x["sort_weight"], reverse=True)

    podcasts = [i for i in valid_items if i["source_type"] == "podcast" and i["native_id"] not in seen_ids]
    videos = [i for i in valid_items if i["source_type"] == "youtube" and i["native_id"] not in seen_ids]
    research = [i for i in valid_items if i["source_type"] == "rss" and i["native_id"] not in seen_ids]
    news_items = [i for i in valid_items if i["source_type"] == "news" and i["native_id"] not in seen_ids]

    # Graceful degradation: if a bucket is starved, log it and note overflow pool
    overflow_pool = sorted(valid_items, key=lambda x: x["sort_weight"], reverse=True)
    if len(podcasts) < 2:
        print(f"Bucket warning: only {len(podcasts)} podcasts available. RSS items will fill gap.")
        all_podcasts_raw = [i for i in valid_items if i["source_type"] == "podcast"]
        print(f"Podcast diagnostic: {len(all_podcasts_raw)} podcasts survived scoring but {len([i for i in all_podcasts_raw if i['native_id'] in seen_ids])} already used today")
    if len(videos) < 2:
        print(f"Bucket warning: only {len(videos)} videos available. Podcasts will fill gap.")

    # 2. Flexible Audio/Video Quota (4-6 Videos, rest Podcasts)
    q_av_total = base_av
    q_min_vid = adapted_min_vid
    q_max_vid = adapted_max_vid
    
    selected_videos = []
    selected_podcasts = []
    
    # Minimum Videos
    for v in videos:
        if len(selected_videos) >= q_min_vid: break
        if is_eligible(v, memory):
            selected_videos.append(v)
            add_item(v, "positivity")
            
    # Minimum Podcasts
    min_pods = q_av_total - q_max_vid
    for p in podcasts:
        if len(selected_podcasts) >= min_pods: break
        if is_eligible(p, memory):
            selected_podcasts.append(p)
            add_item(p, "positivity")
            
    # Fill remaining AV slots based on captivating sort_weight
    wildcards = sorted(videos + podcasts, key=lambda x: x["sort_weight"], reverse=True)
    for best in wildcards:
        if (len(selected_videos) + len(selected_podcasts)) >= q_av_total: break
        if best["native_id"] in seen_ids: continue # skip if already picked
        if not is_eligible(best, memory): continue
        
        if best["source_type"] == "youtube" and len(selected_videos) < q_max_vid:
            selected_videos.append(best)
            add_item(best, "positivity")
        elif best["source_type"] == "podcast":
            selected_podcasts.append(best)
            add_item(best, "positivity")

    # 3. Research — with overflow fallback
    count = 0
    for r in research:
        if count >= q_research: break
        if not is_eligible(r, memory): continue
        add_item(r, "positivity")
        count += 1

    # If research bucket didn't fill, pull from overflow (any type except news)
    if count < q_research:
        for fallback in overflow_pool:
            if count >= q_research: break
            if fallback["native_id"] in seen_ids: continue
            if fallback["source_type"] == "news": continue
            if not is_eligible(fallback, memory): continue
            
            add_item(fallback, "positivity")
            count += 1
            print(f"Graceful fill: added '{fallback['title'][:50]}' from overflow pool")
            
    # 4. News
    count = 0
    for n in news_items:
        if count >= q_news: break
        if not is_eligible(n, memory, is_news=True): continue
        
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

    # Curriculum Arc: check monthly domain coverage and boost underrepresented domains
    from src.pipeline.memory_mgr import get_monthly_domain_counts
    from src.pipeline.philosophy import _get_register, REGISTER_TAXONOMY

    monthly_domains = get_monthly_domain_counts(memory)
    all_domains = set(REGISTER_TAXONOMY.keys())
    present_domains = set(monthly_domains.keys())
    absent_this_month = all_domains - present_domains

    if absent_this_month:
        # Find items in absent domains not yet selected
        selected_ids_now = {i["native_id"] for i in final_selection}
        for domain in absent_this_month:
            curriculum_candidate = next(
                (i for i in valid_items
                 if i["native_id"] not in selected_ids_now
                 and _get_register(i) == domain),
                None
            )
            if curriculum_candidate:
                # Swap out the lowest sort_weight item that isn't deep_dive
                swappable = [i for i in final_selection if i.get("category") != "deep_dive"]
                if swappable:
                    weakest = min(swappable, key=lambda i: i.get("sort_weight", 0))
                    final_selection = [
                        curriculum_candidate if i["native_id"] == weakest["native_id"] else i
                        for i in final_selection
                    ]
                    selected_ids_now.add(curriculum_candidate["native_id"])
                    print(f"Curriculum Arc: introduced '{domain}' domain (absent this month)")
                    break  # One curriculum swap per day is enough

    # --- SERENDIPITY SLOT ---
    # Prevents philosophical monoculture and over-curation.
    # Inject one high-quality but weakly-scored surprising item daily.

    unselected = [
        i for i in overflow_pool
        if i["native_id"] not in seen_ids
    ]

    serendipity_candidates = [
        i for i in unselected
        if score_map.get(i["native_id"], {}).get("fear_score", 0) <= 3
        and score_map.get(i["native_id"], {}).get("ai_slop_penalty", 0) <= 2
    ]

    if serendipity_candidates:
        surprise_pick = random.choice(serendipity_candidates[:15])
        surprise_pick["category"] = "serendipity"
        final_selection.append(surprise_pick)
        print(f"🎲 Serendipity Slot: {surprise_pick['title'][:60]}")
    
    # Variety Engine: prevent emotional register clustering within today's feed
    final_selection = apply_variety_engine(final_selection, valid_items, score_map)

    # 4-to-1 Audit
    high_agency = [i for i in final_selection if score_map.get(i["native_id"], {}).get("state_shift_score", 0) >= 6]
    ratio = len(high_agency) / max(len(final_selection), 1)
    if ratio < 0.75:
        print(f"4-to-1 Warning: Only {len(high_agency)}/{len(final_selection)} items are high-agency.")
    else:
        print(f"4-to-1 Check passed: {len(high_agency)}/{len(final_selection)} items are high-agency.")

    return final_selection
