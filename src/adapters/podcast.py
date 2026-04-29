import os
import time
import hashlib
import requests
from src.pipeline.memory_mgr import create_standard_item

def fetch_listen_notes(query):
    """Fetches high-quality podcasts using Listen Notes."""
    api_key = os.getenv("LISTEN_NOTES_API_KEY")
    if not api_key:
        print("⚠️ No Listen Notes API key found. Skipping.")
        return []

    url = f"https://listen-api.listennotes.com/api/v2/search?q={query}&type=episode&language=English"
    headers = {"X-ListenAPI-Key": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", []):
            normalized = create_standard_item(
                native_id=item["id"],
                title=item["title_original"],
                description=item["description_original"],
                url=item["listennotes_url"],
                source_type="podcast",
                source_name=item["podcast"]["title_original"],
                date_ms=item["pub_date_ms"],
                image_url=item.get("image") or item.get("thumbnail"),
                audio_url=item.get("audio")
            )
            results.append(normalized)
        return results
    except Exception as e:
        print(f"🚨 Listen Notes fetch failed: {e}")
        return []

def fetch_podcast_index(query):
    """Fetches high-quality podcasts using Podcast Index."""
    api_key = os.getenv("PODCAST_INDEX_API_KEY")
    api_secret = os.getenv("PODCAST_INDEX_API_SECRET")
    
    if not api_key or not api_secret:
        print("⚠️ No Podcast Index credentials found. Skipping.")
        return []

    # Podcast Index requires a specific auth hash
    unix_time = str(int(time.time()))
    auth_str = api_key + api_secret + unix_time
    auth_hash = hashlib.sha1(auth_str.encode('utf-8')).hexdigest()

    headers = {
        "X-Auth-Date": unix_time,
        "X-Auth-Key": api_key,
        "Authorization": auth_hash,
        "User-Agent": "CuriousRabbitHoleBot/2.0"
    }
    
    url = f"https://api.podcastindex.org/api/1.0/search/byterm?q={query}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("feeds", []):
            normalized = create_standard_item(
                native_id=item["id"],
                title=item["title"],
                description=item.get("description", ""),
                url=item["url"],
                source_type="podcast",
                source_name=item["author"] or "Unknown Author",
                date_ms=item.get("newestItemPubdate", int(time.time())) * 1000
            )
            results.append(normalized)
        return results
    except Exception as e:
        print(f"🚨 Podcast Index fetch failed: {e}")
        return []
