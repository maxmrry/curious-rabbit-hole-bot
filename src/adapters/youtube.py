import os
from datetime import datetime
import yaml
from googleapiclient.discovery import build
from src.pipeline.memory_mgr import create_standard_item

def fetch_youtube_whitelist(whitelist_filepath='policy/source_whitelist.yaml'):
    """
    Fetches the latest videos ONLY from pre-approved YouTube channels.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("⚠️ No YouTube API key found. Skipping.")
        return []

    # Load the trusted channels
    try:
        with open(whitelist_filepath, 'r') as f:
            policy = yaml.safe_load(f)
            trusted_channels = policy.get('youtube', [])
    except Exception as e:
        print(f"🚨 Failed to load whitelist: {e}")
        return []

    youtube = build('youtube', 'v3', developerKey=api_key)
    results = []

    for channel_id in trusted_channels:
        try:
            # We search ONLY within the specific channel, ordered by date
            request = youtube.search().list(
                part='snippet',
                channelId=channel_id,
                maxResults=3, # Just grab the 3 most recent to save quota
                type='video',
                order='date'
            )
            response = request.execute()
            
            for item in response.get('items', []):
                pub_date = item['snippet']['publishedAt']
                date_ms = int(datetime.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp() * 1000)
                
                normalized = create_standard_item(
                    native_id=item['id']['videoId'],
                    title=item['snippet']['title'],
                    description=item['snippet']['description'],
                    url=f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    source_type="youtube",
                    source_name=item['snippet']['channelTitle'],
                    date_ms=date_ms
                )
                results.append(normalized)
        except Exception as e:
            print(f"🚨 YouTube fetch failed for channel {channel_id}: {e}")

    return results
