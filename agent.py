import sys
from src.pipeline.brain import load_policy, select_daily_items
from src.pipeline.memory_mgr import load_memory, update_memory, purge_memory, save_memory
from src.pipeline.philosophy import reframe_items
from src.pipeline.rss_builder import build_feed

def main():
    print("🚀 Booting U-Curve Brain...")
    
    try:
        # 1. Load State & Policy
        policy = load_policy()
        memory = load_memory()
        
        # Dynamically calculate total expected items from policy.yaml
        quotas = policy.get("media_quotas", {})
        expected_total = sum(quotas.values()) if quotas else 11
        
        # 2. Gather, Score, & Select
        selected_items = select_daily_items(memory, policy)
        
        # Dynamic safety check (Allows a 2-item buffer in case APIs have a slow day)
        if len(selected_items) < (expected_total - 2):
            print(f"⚠️ Only found {len(selected_items)} elite items. Expected near {expected_total}. Aborting run to preserve feed quality.")
            sys.exit(0)
            
        # 3. Philosophy Engine (Reframing)
        print("🧠 Reframing descriptions objectively...")
        selected_items = reframe_items(selected_items)
        
        if not selected_items:
            print("🚨 Philosophy Engine failed to return items. Aborting.")
            sys.exit(1)
            
        # 4. Build RSS (Adage and Protocol handled automatically inside)
        print("📝 Generating RSS Feed...")
        build_feed(selected_items)
        
        # 5. Update & Purge Memory
        memory = update_memory(selected_items, memory)
        ttl_days = policy.get("memory_limits", {}).get("ttl_days", 180)
        memory = purge_memory(memory, ttl_days)
        save_memory(memory)
        
        print("🎯 Mission Complete. System spinning down.")
        
    except Exception as e:
        print(f"\n🚨 CRITICAL ERROR ENCOUNTERED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
