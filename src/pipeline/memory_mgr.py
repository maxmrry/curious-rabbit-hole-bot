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


def passes_veto_check(item, veto_filepath='policy/veto_terms.txt'):
    """
    Checks if the item contains any hard-banned words.
    Returns True if safe, False if vetoed.
    """
    try:
        with open(veto_filepath, 'r') as f:
            veto_words = [line.strip().lower() for line in f if line.strip()]
    except FileNotFoundError:
        # Fail open: if no policy file exists, allow everything
        return True

    text_to_check = f"{item.get('title', '')} {item.get('description', '')}".lower()

    for word in veto_words:
        if word in text_to_check:
            print(f"🛡️ Vetoed: '{item.get('title', 'Untitled')}' (Trigger word: {word})")
            return False

    return True


def update_memory(selected_items, memory):
    """Commits newly selected items to memory so they are never seen again."""
    now_ms = int(time.time() * 1000)

    for item in selected_items:
        item_hash = item.get("canonical_hash")
        if not item_hash:
            continue  # skip malformed items instead of crashing

        memory.setdefault("seen_hashes", {})[item_hash] = {
            "native_id": item.get("native_id"),
            "source_type": item.get("source_type"),
            "last_seen_ms": now_ms
        }

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
