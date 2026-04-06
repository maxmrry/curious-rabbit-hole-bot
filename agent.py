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

# 🧠 YOUR DIRECTIVES: The jumping-off points for the bot to explore adjacent topics
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
    prompt = f"""
    You are an elite cultural researcher and curator. You look for highly intellectual, niche, and stimulating content.
    
    Profile:
    - The Director's Curiosities: {', '.join(CURRENT_CURIOSITIES)}
    
    Taste Profile (CRITICAL):
    - LIKES: {', '.join(memory.get('liked_examples', []))} (Seek meta-discussions, academic seminars, in-depth journalism, niche experts)
    - DISLIKES: {', '.join(memory.get('disliked_examples', []))} (Avoid basic advice, life-hacks, uneducated rambling, pop-science)
    
    History (Do NOT repeat anything on this list or closely related to it): {', '.join(memory.get('history', [])[-15:])}
    
    Task:
    1. Define exactly 3 distinct 'Daily Themes'. DO NOT just pick the Director's Curiosities literally. Instead, use them as inspiration to find highly interesting, specific, and niche ADJACENT topics. Connect the dots to something fringe or deeply intellectual that hasn't been covered in the History.
    2. Provide 1 highly specific YouTube search query for EACH theme. Use keywords like "seminar", "lecture", "documentary", "meta-analysis", or "anthropology".
    
    Format EXACTLY as JSON:
    {{
        "daily_themes": ["Adjacent Theme A", "Adjacent Theme B", "Adjacent Theme C"],
        "queries": ["Query A", "Query B", "Query C"]
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
            maxResults=6, # Grabs a wider net (18 total) so the curator has more to filter through
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

def curate_videos(themes, videos, memory):
    theme_str = ", ".join(themes)
    video_list_text = "\n".join([f"ID: {i} | Title: {v['title']} | Desc: {v['description']}" for i, v in enumerate(videos)])
    
    prompt = f"""
    You are the final editorial filter for a high-end intelligence feed covering: {theme_str}.
    Your job is to aggressively filter out garbage and only keep the absolute best 6-8 videos.
    
    FILTERING RULES:
    1. REJECT anything resembling these disliked topics: {', '.join(memory.get('disliked_examples', []))}
    2. REJECT basic "how-to" advice, life-hacks, vlogs, and uneducated rambling.
    3. KEEP highly specific, intellectually stimulating, meta-discussions, and in-depth niche lectures (even if they have low views).
    4. KEEP content matching the tone of these liked topics: {', '.join(memory.get('liked_examples', []))}
    
    Results:
    {video_list_text}
    
    Respond with ONLY a comma-separated list of the IDs you choose (e.g. 0, 2, 5, 9, 10).
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
        
        # Clean up legacy 'core_interests' if they still exist in memory
        if 'core_interests' in memory:
            del memory['core_interests']
            save_memory(memory)

        if 'current_theme' in memory:
            memory['current_themes'] = [memory['current_theme']]
            del memory['current_theme']
            save_memory(memory)

        if memory.get('last_topic_date') != today_str:
            print("Brain is thinking of new adjacent multi-topic angles...")
            strategy = get_research_strategy(memory)
            memory['current_themes'] = strategy['daily_themes']
            memory['current_queries'] = strategy['queries']
            memory['last_topic_date'] = today_str
            memory['history'].extend(strategy['daily_themes'])
            save_memory(memory)
        else:
            print(f"Continuing research on: {', '.join(memory.get('current_themes', []))}")

        print(f"Searching for: {', '.join(memory['current_queries'])}")
        all_raw_videos = search_youtube(memory['current_queries'])
        
        print("Agent is curating the best content...")
        curated_videos = curate_videos(memory['current_themes'], all_raw_videos, memory)
        
        print("Publishing to RSS...")
        build_rss_feed(memory['current_themes'], curated_videos, now)
        print("Mission Complete.")
        
    except Exception as e:
        print(f"\n🚨 CRITICAL ERROR ENCOUNTERED: {e}")
        build_error_feed(str(e), now)
        sys.exit(1)

if __name__ == "__main__":
    main()
