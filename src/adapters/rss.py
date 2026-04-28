import time
import yaml
import feedparser
from src.pipeline.memory_mgr import create_standard_item

def fetch_rss_whitelist(whitelist_filepath='policy/source_whitelist.yaml'):
    """
    Fetches the latest articles from pre-approved RSS feeds.
    """
    try:
        with open(whitelist_filepath, 'r') as f:
            policy = yaml.safe_load(f)
            trusted_feeds = policy.get('rss', [])
    except Exception as e:
        print(f"🚨 Failed to load whitelist: {e}")
        return []

    results = []

    for feed_url in trusted_feeds:
        try:
            feed = feedparser.parse(feed_url)
            
            # Limit to the 3 most recent entries per feed
            for entry in feed.entries[:3]:
                # Attempt to safely parse the publication date
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date_ms = int(time.mktime(entry.published_parsed) * 1000)
                else:
                    date_ms = int(time.time() * 1000)
                
                # Some feeds use 'summary', others use 'description'
                description = getattr(entry, 'summary', getattr(entry, 'description', ''))

                normalized = create_standard_item(
                    native_id=entry.link, # RSS IDs are usually the permalink
                    title=entry.title,
                    description=description,
                    url=entry.link,
                    source_type="rss",
                    source_name=feed.feed.get('title', 'Unknown RSS Source'),
                    date_ms=date_ms
                )
                results.append(normalized)
        except Exception as e:
            print(f"🚨 RSS fetch failed for {feed_url}: {e}")

    return results
