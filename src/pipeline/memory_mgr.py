import hashlib
import json
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
    date_ms=None
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
        "published_date_ms": date_ms or int(datetime.now().timestamp() * 1000)
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
