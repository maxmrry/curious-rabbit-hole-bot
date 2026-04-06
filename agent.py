import json
import os
import google.generativeai as genai
from googleapiclient.discovery import build
from feedgen.feed import FeedGenerator
from datetime import datetime
import pytz

# --- CONFIGURATION ---
TIMEZONE = pytz.timezone('Europe/London') # Or 'Europe/Paris'

# Securely load API keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
# ---------------------

def load_memory():
    with open('memory.json', 'r') as f:
        return json.load(f)

def save_memory(memory):
    with open('memory.json', 'w') as f:
        json.dump(memory, f, indent=4)

def get_next_rabbit_hole(memory):
    prompt = f"""
    You are a curious web-research agent. 
    Your core interests are: {', '.join(memory['core_interests'])}.
    Your current rabbit hole is: '{memory['current_rabbit_hole']}'.
    You have already looked into these topics recently: {', '.join(memory['history'][-5:])}.
    
    Based on this trajectory, what is ONE specific, highly interesting adjacent topic, documentary, or cultural phenomenon you want to learn about today? 
    Respond with ONLY the exact search phrase you would type into YouTube. Keep it under 6 words.
    """
    response = model.generate_content(prompt)
    return response.text.replace('"', '').strip()

def search_youtube(query):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        q=query,
        part='snippet',
        maxResults=10, # Grab the top 10 videos
        type='video',
        order='relevance'
    )
    response = request.execute()
    
    videos = []
    for item in response.get('items', []):
        videos.append({
            'title': item['snippet']['title'],
            'link': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            'description': item['snippet']['description'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'published': item['snippet']['publishedAt'],
            'id': item['id']['videoId']
        })
    return videos

def build_rss_feed(topic, videos, now):
    fg = FeedGenerator()
    fg.title('Daily Rabbit Hole Feed')
    
    # Point the alternate link to the docs folder so the RSS app finds the index.html favicon
    fg.link(href='https://YOUR_USERNAME.github.io/YOUR_REPO/docs/', rel='alternate')
    fg.description('An autonomous agent exploring interesting topics.')
    
    # --- ADD MAIN FEED IMAGE ---
    # Replace with your actual raw image URL
    image_url = 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='Daily Rabbit Hole Feed', link='https://YOUR_USERNAME.github.io/YOUR_REPO/docs/feed.xml')
    # ---------------------------

    # 1. Add the "Daily Topic Reminder"
    fe = fg.add_entry()
    fe.title(f"🐇 Today's Rabbit Hole: {topic.upper()}")
    fe.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#topic-{now.strftime('%Y%m%d')}")
    fe.description(f"The agent is currently researching: <b>{topic}</b>")
    fe.pubDate(now)
    fe.id(f"topic-{now.strftime('%Y%m%d')}")

    # 2. Add the videos found for this topic
    # We offset the time slightly so they appear below the reminder in the RSS reader
    for idx, v in enumerate(videos):
        fe = fg.add_entry()
        fe.title(v['title'])
        fe.link(href=v['link'])
        
        # Inject thumbnail
        desc_html = f"<img src='{v['thumbnail']}' alt='thumbnail'/><br><br>{v['description']}"
        fe.description(desc_html)
        fe.enclosure(v['thumbnail'], 0, 'image/jpeg')
        
        fe.pubDate(now) 
        fe.id(f"yt:video:{v['id']}")

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')

def main():
    memory = load_memory()
    now = datetime.now(TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    
    # DAILY LOGIC: Check if we need a new topic
    if memory.get('last_topic_date') != today_str:
        print("New day! Pondering next rabbit hole...")
        new_topic = get_next_rabbit_hole(memory)
        print(f"Decided to research: {new_topic}")
        
        memory['history'].append(new_topic)
        memory['current_rabbit_hole'] = new_topic
        memory['last_topic_date'] = today_str
        save_memory(memory)
    else:
        print(f"Still exploring today's topic: {memory['current_rabbit_hole']}")

    # HOURLY LOGIC: Search YouTube & Build RSS
    print("Fetching top videos...")
    videos = search_youtube(memory['current_rabbit_hole'])
    
    print("Building RSS feed...")
    build_rss_feed(memory['current_rabbit_hole'], videos, now)
    print("Done!")

if __name__ == "__main__":
    main()
