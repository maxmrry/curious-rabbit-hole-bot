import hashlib
import json
import time
import os
from datetime import datetime


def generate_canonical_hash(url_or_id):
    """Creates a unique SHA-256 fingerprint for deduplication."""
    return hashlib.sha256(str(url_or_id).encode('utf-8')).hexdigest()


def load_memory(filepath='state/memory.json'):
    """Loads memory state from disk or initializes a new structure."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": 1, "seen_hashes": {}, "runs": {}}


def is_unseen(item_hash, memory):
    """Returns True if the item is entirely new to the system."""
    return item_hash not in memory.get("seen_hashes", {})


def create_standard_item(
    native_id,
    title,
    description,
    url,
    source_type,
    source_name,
    date_ms=None,
    image_url=None,  # NEW: Supports YouTube/Podcast thumbnails
    audio_url=None   # NEW: Supports direct MP3 links
):
    """Normalizes messy API data into our strict internal schema."""
    canonical_hash = generate_canonical_hash(native_id)

    return {
        "canonical_hash": canonical_hash,
        "native_id": str(native_id),
        "title": title.strip() if title else "Untitled",
        "description": description.strip() if description else "No description provided.",
        "url": url,
        "source_type": source_type,  # 'podcast', 'youtube', 'news', 'rss'
        "source_name": source_name,
        "published_date_ms": date_ms or int(datetime.now().timestamp() * 1000),
        "image_url": image_url,
        "audio_url": audio_url
    }


# Words that neutralise a veto term — if present alongside a veto word, allow through
VETO_ANTIDOTES = [
    "resilience", "solution", "recovery", "overcome", "reform",
    "progress", "rebuild", "stabilize", "manage", "address",
    "reduce", "prevent", "history of", "understanding", "analysis of"
]

def passes_veto_check(item, veto_filepath='policy/veto_terms.txt'):
    """
    Context-aware veto: blocks hard-ban words UNLESS neutralising antidote
    words are present, suggesting constructive framing.
    """
    try:
        with open(veto_filepath, 'r') as f:
            veto_words = [line.strip().lower() for line in f if line.strip()]
    except FileNotFoundError:
        return True

    title = item.get('title', '').lower()
    description = item.get('description', '').lower()
    text_to_check = f"{title} {description}"

    for word in veto_words:
        if word in text_to_check:
            # Check if an antidote word redeems it
            if any(antidote in text_to_check for antidote in VETO_ANTIDOTES):
                print(f"🟡 Soft-pass: '{item.get('title', 'Untitled')}' has '{word}' but antidote present.")
                continue
            print(f"🛡️ Vetoed: '{item.get('title', 'Untitled')}' (Trigger: '{word}')")
            return False
    return True


def update_memory(selected_items, memory):
    """Commits newly selected items and their sources to memory."""
    now_ms = int(time.time() * 1000)
    
    memory.setdefault("source_history", {})
    memory.setdefault("source_scores", {})  # NEW: tracks avg sort_weight per source
    memory.setdefault("type_performance", {})  # NEW: tracks avg score per source_type

    for item in selected_items:
        item_hash = item.get("canonical_hash")
        if not item_hash:
            continue

        memory.setdefault("seen_hashes", {})[item_hash] = {
            "native_id": item.get("native_id"),
            "source_type": item.get("source_type"),
            "last_seen_ms": now_ms
        }
        
        source_name = item.get("source_name")
        if source_name:
            memory["source_history"][source_name] = now_ms

            # Track rolling average sort_weight per source (lightweight signal)
            weight = item.get("sort_weight", 5.0)
            prev = memory["source_scores"].get(source_name, {"avg": weight, "n": 0})
            n = prev["n"] + 1
            new_avg = ((prev["avg"] * prev["n"]) + weight) / n
            memory["source_scores"][source_name] = {"avg": round(new_avg, 3), "n": min(n, 50)}

        # Track avg score per content type
        stype = item.get("source_type", "unknown")
        weight = item.get("sort_weight", 5.0)
        prev = memory["type_performance"].get(stype, {"avg": weight, "n": 0})
        n = prev["n"] + 1
        new_avg = ((prev["avg"] * prev["n"]) + weight) / n
        memory["type_performance"][stype] = {"avg": round(new_avg, 3), "n": min(n, 100)}

    return memory


def purge_memory(memory, ttl_days=180):
    """
    Prevents the JSON file from infinitely growing by deleting hashes older than TTL.
    """
    now_ms = int(time.time() * 1000)
    ttl_ms = ttl_days * 24 * 60 * 60 * 1000
    cutoff_time = now_ms - ttl_ms

    seen_hashes = memory.get("seen_hashes", {})
    initial_count = len(seen_hashes)

    # Keep only items newer than the cutoff time
    memory["seen_hashes"] = {
        k: v for k, v in seen_hashes.items()
        if v.get("last_seen_ms", 0) > cutoff_time
    }

    purged_count = initial_count - len(memory["seen_hashes"])
    if purged_count > 0:
        print(f"🧹 Memory Purge: Removed {purged_count} expired items.")

    return memory


def save_memory(memory, filepath='state/memory.json'):
    """Saves state back to disk."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(memory, f, indent=2)
