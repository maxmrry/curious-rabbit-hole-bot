import os
import random
from datetime import datetime

import yaml
from googleapiclient.discovery import build

from src.pipeline.memory_mgr import create_standard_item


def fetch_youtube_whitelist(whitelist_filepath='policy/source_whitelist.yaml'):
    """
    Fetches the latest videos ONLY from pre-approved YouTube channels.
    Uses daily random sampling to protect API quota.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("⚠️ No YouTube API key found. Skipping.")
        return []

    # Load the trusted channels
    try:
        with open(whitelist_filepath, 'r') as f:
            policy = yaml.safe_load(f) or {}
            trusted_channels = policy.get('youtube', [])

            if not isinstance(trusted_channels, list):
                print("🚨 Invalid whitelist format: 'youtube' should be a list.")
                return []

            # Randomly sample up to 10 channels per run (quota protection)
            daily_channels = random.sample(
                trusted_channels,
                min(10, len(trusted_channels))
            )

    except Exception as e:
        print(f"🚨 Failed to load whitelist: {e}")
        return []

    youtube = build('youtube', 'v3', developerKey=api_key)
    results = []

    for channel_id in daily_channels:
        try:
            request = youtube.search().list(
                part='snippet',
                channelId=channel_id,
                maxResults=3,  # grab only the 3 most recent
                type='video',
                order='date'
            )
            response = request.execute()

            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = item.get('id', {}).get('videoId')

                if not video_id:
                    continue
                    
                # 🛑 NATIVE SHORTS FILTER: Reject anything tagged as a Short
                title_desc = (snippet.get('title', '') + " " + snippet.get('description', '')).lower()
                if '#shorts' in title_desc or 'youtube.com/shorts' in title_desc:
                    continue

                pub_date = snippet.get('publishedAt')
                try:
                    date_ms = int(
                        datetime.fromisoformat(
                            pub_date.replace("Z", "+00:00")
                        ).timestamp() * 1000
                    ) if pub_date else None
                except Exception:
                    date_ms = None  # fallback if parsing fails

                # Extract high-res thumbnail
                thumbnails = snippet.get('thumbnails', {})
                high_res = thumbnails.get('high', {}).get('url') or thumbnails.get('default', {}).get('url')

                normalized = create_standard_item(
                    native_id=video_id,
                    title=snippet.get('title'),
                    description=snippet.get('description'),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source_type="youtube",
                    source_name=snippet.get('channelTitle'),
                    date_ms=date_ms,
                    image_url=high_res  # <--- ADDED
                )

                results.append(normalized)

        except Exception as e:
            print(f"🚨 YouTube fetch failed for channel {channel_id}: {e}")

    return results
