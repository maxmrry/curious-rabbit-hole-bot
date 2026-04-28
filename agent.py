import sys
from src.pipeline.brain import load_policy, select_daily_items
from src.pipeline.memory_mgr import load_memory, update_memory, purge_memory, save_memory
from src.pipeline.philosophy import reframe_items, get_daily_principle
from src.pipeline.rss_builder import build_feed

def main():
    print("🚀 Booting U-Curve Brain...")
    
    try:
        # 1. Load State & Policy
        policy = load_policy()
        memory = load_memory()
        
        # 2. Gather, Score, & Select (Math, Rules & Triage)
        selected_items = select_daily_items(memory)
        
        if len(selected_items) < 5:
            print(f"⚠️ Only found {len(selected_items)} elite items. We require 5 to maintain the 4:1 ratio. Aborting run to preserve feed quality.")
            sys.exit(0)
            
        # 3. Philosophy Engine (Reframing)
        print("🧠 Reframing descriptions constructively...")
        selected_items = reframe_items(selected_items)
        
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
