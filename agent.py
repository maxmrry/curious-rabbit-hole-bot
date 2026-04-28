import sys
from src.pipeline.brain import load_policy, build_candidate_pool
from src.pipeline.memory_mgr import load_memory, update_memory, purge_memory, save_memory
from src.pipeline.philosophy import select_and_rewrite, get_daily_principle
from src.pipeline.rss_builder import build_feed

def main():
    print("🚀 Booting U-Curve Brain...")
    
    try:
        # 1. Load State & Policy
        policy = load_policy()
        memory = load_memory()
        
        # 2. Gather & Filter Data (Math & Rules)
        clean_pool = build_candidate_pool(memory)
        
        if len(clean_pool) < 5:
            print(f"⚠️ Only {len(clean_pool)} clean items found. Not enough to maintain 4:1 ratio. Aborting run to preserve feed quality.")
            sys.exit(0)
            
        # 3. Philosophy Engine (Gemini)
        print("🧠 Handing clean pool to Philosophy Engine for selection and reframing...")
        selected_items = select_and_rewrite(clean_pool)
        
        if not selected_items:
            print("🚨 Philosophy Engine failed to return items. Aborting.")
            sys.exit(1)
            
        # 4. Generate Anchor Principle
        daily_principle = get_daily_principle()
        
        # 5. Build RSS
        print("📝 Generating RSS Feed...")
        build_feed(selected_items, daily_principle)
        
        # 6. Update & Purge Memory
        memory = update_memory(selected_items, memory)
        ttl_days = policy.get("memory_limits", {}).get("ttl_days", 180)
        memory = purge_memory(memory, ttl_days)
        save_memory(memory)
        
        print("🎯 Mission Complete. System spinning down.")
        
    except Exception as e:
        print(f"\n🚨 CRITICAL ERROR ENCOUNTERED: {e}")
        # Could implement an error RSS feed fallback here if desired
        sys.exit(1)

if __name__ == "__main__":
    main()
