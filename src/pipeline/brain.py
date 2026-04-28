import yaml
from src.adapters.podcast import fetch_listen_notes, fetch_podcast_index
from src.adapters.news import fetch_relevant_news
from src.adapters.youtube import fetch_youtube_whitelist
from src.adapters.rss import fetch_rss_whitelist
from src.pipeline.memory_mgr import is_unseen, passes_veto_check

def load_policy(filepath='policy/policy.yaml'):
    """Loads the hardcoded ratios and rules for the agent."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("🚨 Critical: policy.yaml not found.")
        return {}

def build_candidate_pool(memory):
    """
    Orchestrates all adapters, gathers data, and applies strict hard-filtering.
    Returns a clean pool of highly vetted, unseen items.
    """
    candidates = []
    
    # --- 1. GATHER DATA ---
    print("📡 Fetching from RSS Whitelist...")
    candidates.extend(fetch_rss_whitelist())
    
    print("📡 Fetching from YouTube Whitelist...")
    candidates.extend(fetch_youtube_whitelist())
    
    print("📡 Fetching Podcasts (Positivity & Deep Dives)...")
    # We supply specific queries to guarantee we have material for both ratios
    candidates.extend(fetch_listen_notes('post-traumatic growth OR resilience OR relationship psychology'))
    candidates.extend(fetch_listen_notes('anthropology OR sociology OR subculture'))
    
    print("📡 Fetching Global News...")
    news_items = fetch_relevant_news()
    
    # Apply the mathematical news filter immediately
    for news in news_items:
        metrics = news.get("scoring_metrics", {})
        if metrics.get("hopeful_rewrite_eligible", False):
            candidates.append(news)
        else:
            print(f"🛑 Dropped News: '{news['title']}' (Failed positivity math)")

    # --- 2. HARD FILTERING ---
    clean_pool = []
    dropped_seen = 0
    
    for item in candidates:
        # Check 1: Is it a duplicate?
        if not is_unseen(item["canonical_hash"], memory):
            dropped_seen += 1
            continue
            
        # Check 2: Does it contain apocalyptic/fearmongering veto words?
        if not passes_veto_check(item):
            continue
            
        clean_pool.append(item)
        
    print(f"🧠 Brain Summary: Dropped {dropped_seen} seen items. Clean candidate pool size: {len(clean_pool)}")
    return clean_pool
