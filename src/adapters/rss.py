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
                # 🛑 Strip tracking URLs so deduplication works perfectly
                clean_url = entry.link.split('?')[0]
                
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date_ms = int(time.mktime(entry.published_parsed) * 1000)
                else:
                    date_ms = int(time.time() * 1000)
                
                description = getattr(entry, 'summary', getattr(entry, 'description', ''))

                # 🖼️ NATIVE THUMBNAIL HUNTER
                image_url = None
                if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                    image_url = entry.media_thumbnail[0]['url']
                elif 'media_content' in entry and len(entry.media_content) > 0:
                    for media in entry.media_content:
                        if media.get('medium') == 'image':
                            image_url = media.get('url')
                            break
                if not image_url and hasattr(entry, 'links'):
                    for link in entry.links:
                        if link.get('type', '').startswith('image/'):
                            image_url = link.get('href')
                            break

                normalized = create_standard_item(
                    native_id=clean_url, 
                    title=entry.title,
                    description=description,
                    url=clean_url,
                    source_type="rss",
                    source_name=feed.feed.get('title', 'Unknown RSS Source'),
                    date_ms=date_ms,
                    image_url=image_url # <--- Now passes the image to your feed!
                )
                results.append(normalized)
        except Exception as e:
            print(f"🚨 RSS fetch failed for {feed_url}: {e}")

    return results
