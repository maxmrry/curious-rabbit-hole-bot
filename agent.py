import json
import os
import sys
import google.generativeai as genai
from googleapiclient.discovery import build
from feedgen.feed import FeedGenerator
from datetime import datetime
import pytz
import re

# --- CONFIGURATION ---
TIMEZONE = pytz.timezone('Europe/London')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 🧠 YOUR DIRECTIVES: Change these whenever you want to steer the bot!
CURRENT_CURIOSITIES = [
    "declining birth rates and Gen Z",
    "the psychology of the manosphere",
    "Louis Theroux style fringe documentaries",
    "Human anthropology, ecology, sociology, psychology, why we do things, interesting biological mechanisms, environmental disruptors and ways to mitigate",
    "the power of negativity bias"
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
# ---------------------

def load_memory():
    with open('memory.json', 'r') as f:
        return json.load(f)

def save_memory(memory):
    with open('memory.json', 'w') as f:
        json.dump(memory, f, indent=4)

def get_research_strategy(memory):
    """Gemini picks 3 distinct themes and 1 specific query for each."""
    prompt = f"""
    You are an elite cultural researcher. Your goal is to curate a daily variety feed of deeply interesting content.
    
    Here is your current profile:
    - Core Interests: {', '.join(memory.get('core_interests', []))}
    - The Director's Current Curiosities: {', '.join(CURRENT_CURIOSITIES)}
    - History (Do NOT repeat these): {', '.join(memory.get('history', [])[-15:])}
    
    Task:
    1. Define exactly 3 distinct 'Daily Themes'. Mix them up! Pick one from the Director's Curiosities, one from Core Interests, and one completely surprising adjacent topic.
    2. Provide exactly 1 highly specific YouTube search query for EACH theme (3 queries total) prioritizing documentaries, podcasts, and deep-dives.
    
    Format your response EXACTLY as a JSON object:
    {{
        "daily_themes": ["Gen Z birth rate psychology", "Heaven's Gate early internet cult", "Anthropology of digital nomads"],
        "queries": ["Gen Z baby bust documentary", "Heaven's gate early internet cult deep dive", "digital nomad anthropology podcast"]
    }}
    """
    response = model.generate_content(prompt)
    json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
    return json.loads(json_str)

def search_youtube(queries):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    raw_results = []
    
    for q in queries:
        request = youtube.search().list(
            q=q,
            part='snippet',
            maxResults=4, # Grabs top 4 for each of the 3 themes (12 total)
            type='video',
            order='relevance'
        )
        response = request.execute()
        for item in response.get('items', []):
            raw_results.append({
                'title': item['snippet']['title'],
                'link': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'description': item['snippet']['description'],
                'thumbnail': item['snippet']['thumbnails']['high']['url'],
                'id': item['id']['videoId']
            })
    return raw_results

def curate_videos(themes, videos):
    theme_str = ", ".join(themes)
    video_list_text = "\n".join([f"ID: {i} | Title: {v['title']} | Desc: {v['description']}" for i, v in enumerate(videos)])
    
    prompt = f"""
    You are curating a feed covering these topics: {theme_str}.
    Review the following search results and pick the TOP 6-8 most high-quality, relevant items that represent a good mix of all three topics. 
    Discard anything irrelevant, low-effort, or spam.
    
    Results:
    {video_list_text}
    
    Respond with ONLY a comma-separated list of the IDs you choose (e.g. 0, 2, 5, 9, 10, 11).
    """
    response = model.generate_content(prompt)
    try:
        selected_ids = [int(i.strip()) for i in response.text.split(',')]
        return [videos[i] for i in selected_ids if i < len(videos)]
    except:
        return videos[:8]

def build_rss_feed(themes, videos, now):
    fg = FeedGenerator()
    fg.title('Curious Agent: Intelligence Feed')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('An intelligent agent exploring anthropology, fringe culture, and social dynamics.')
    
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='Curious Agent', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    # Format the daily message: "Topic A, Topic B & Topic C"
    if len(themes) > 1:
        themes_formatted = ", ".join(themes[:-1]) + " & " + themes[-1]
    else:
        themes_formatted = themes[0]

    fe = fg.add_entry()
    fe.title(f"🔵 Daily Rabbit Holes: {themes_formatted.upper()}")
    fe.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#themes-{now.strftime('%Y%m%d')}")
    fe.description(f"Today the agent is exploring: <b>{themes_formatted}</b>.<br><br>It has curated {len(videos)} deep-dives for you.")
    fe.pubDate(now)
    fe.id(f"themes-{now.strftime('%Y%m%d')}")

    for v in videos:
        fe = fg.add_entry()
        fe.title(v['title'])
        fe.link(href=v['link'])
        desc_html = f"<img src='{v['thumbnail']}' alt='thumbnail'/><br><br>{v['description']}"
        fe.description(desc_html)
        fe.enclosure(v['thumbnail'], 0, 'image/jpeg')
        fe.pubDate(now)
        fe.id(f"yt:{v['id']}")

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')

def build_error_feed(error_msg, now):
    fg = FeedGenerator()
    fg.title('Curious Agent: SYSTEM OFFLINE')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('The agent encountered a critical error and requires maintenance.')
    
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='Curious Agent Error', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    fe = fg.add_entry()
    fe.title("⚠️ CRITICAL ERROR: Agent requires maintenance")
    fe.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#error-{now.strftime('%Y%m%d%H%M')}")
    fe.description(f"The autonomous agent crashed during its last run. <br><br><b>Error Details:</b><br><code>{error_msg}</code>")
    fe.pubDate(now)
    fe.id(f"error-{now.strftime('%Y%m%d%H%M')}")

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')

def main():
    now = datetime.now(TIMEZONE)
    
    try:
        memory = load_memory()
        today_str = now.strftime("%Y-%m-%d")
        
        # Handle the transition from the old "current_theme" string to the new "current_themes" list
        if 'current_theme' in memory:
            memory['current_themes'] = [memory['current_theme']]
            del memory['current_theme']
            save_memory(memory)

        if memory.get('last_topic_date') != today_str:
            print("Brain is thinking of new multi-topic angles...")
            strategy = get_research_strategy(memory)
            memory['current_themes'] = strategy['daily_themes']
            memory['current_queries'] = strategy['queries']
            memory['last_topic_date'] = today_str
            # Add all 3 new themes to history
            memory['history'].extend(strategy['daily_themes'])
            save_memory(memory)
        else:
            print(f"Continuing research on: {', '.join(memory.get('current_themes', []))}")

        print(f"Searching for: {', '.join(memory['current_queries'])}")
        all_raw_videos = search_youtube(memory['current_queries'])
        
        print("Agent is curating the best content...")
        curated_videos = curate_videos(memory['current_themes'], all_raw_videos)
        
        print("Publishing to RSS...")
        build_rss_feed(memory['current_themes'], curated_videos, now)
        print("Mission Complete.")
        
    except Exception as e:
        print(f"\n🚨 CRITICAL ERROR ENCOUNTERED: {e}")
        build_error_feed(str(e), now)
        sys.exit(1)

if __name__ == "__main__":
    main()
