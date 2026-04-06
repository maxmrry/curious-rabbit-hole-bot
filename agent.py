import json
import os
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
    """Gemini defines the theme and 3 specific search queries for variety."""
    prompt = f"""
    You are an elite cultural researcher and documentary curator. Your goal is to find deeply interesting, 
    fringe, or insightful content (documentaries, podcasts, anthropology, meta-discussions).
    
    Here is your current profile:
    - Core Interests: {', '.join(memory['core_interests'])}
    - The Director's Current Curiosities: {', '.join(CURRENT_CURIOSITIES)}
    - History (Do NOT repeat these): {', '.join(memory['history'][-10:])}
    
    Task:
    1. Define a 'Daily Theme'. You can either pick one of the 'Director's Current Curiosities' that hasn't been covered in History, OR pick a highly interesting adjacent topic to them. Be intelligent—don't get stuck on one topic for days.
    2. Provide 3 distinct search queries to find different angles (e.g. one for a documentary, one for a podcast, one for a specific fringe expert).
    
    Format your response EXACTLY as a JSON object:
    {{
        "daily_theme": "The psychological impact of declining birth rates in Gen Z",
        "queries": ["Gen Z baby bust documentary", "The Gray Area birth rate podcast", "anthropology of modern family structures"]
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
            maxResults=5,
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

def curate_videos(theme, videos):
    """Gemini reviews the search results and picks the best ones, discarding junk."""
    video_list_text = "\n".join([f"ID: {i} | Title: {v['title']} | Desc: {v['description']}" for i, v in enumerate(videos)])
    
    prompt = f"""
    You are curating a feed about: "{theme}".
    Review the following search results and pick the TOP 6 most high-quality, relevant items. 
    Discard anything irrelevant, low-effort, or spam. Prioritize documentaries, deep-dives, podcasts, and academic research.
    
    Results:
    {video_list_text}
    
    Respond with ONLY a comma-separated list of the IDs you choose (e.g. 0, 2, 5, 9).
    """
    response = model.generate_content(prompt)
    try:
        selected_ids = [int(i.strip()) for i in response.text.split(',')]
        return [videos[i] for i in selected_ids if i < len(videos)]
    except:
        return videos[:6]

def build_rss_feed(theme, videos, now):
    fg = FeedGenerator()
    fg.title('Curious Agent: Intelligence Feed')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/docs/', rel='alternate')
    fg.description('An intelligent agent exploring anthropology, fringe culture, and social dynamics.')
    
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='Curious Agent', link='https://maxmrry.github.io/curious-rabbit-hole-bot/docs/feed.xml')

    # 1. THE DAILY MESSAGE
    fe = fg.add_entry()
    fe.title(f"💡 Daily Rabbit Hole: {theme.upper()}")
    fe.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#theme-{now.strftime('%Y%m%d')}")
    fe.description(f"Today the agent is exploring: <b>{theme}</b>. It has curated {len(videos)} deep-dives for you.")
    fe.pubDate(now)
    fe.id(f"theme-{now.strftime('%Y%m%d')}")

    # 2. THE CURATED VIDEOS
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

def main():
    memory = load_memory()
    now = datetime.now(TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    
    if memory.get('last_topic_date') != today_str:
        print("Brain is thinking of new angles based on Director's Curiosities...")
        strategy = get_research_strategy(memory)
        memory['current_theme'] = strategy['daily_theme']
        memory['current_queries'] = strategy['queries']
        memory['last_topic_date'] = today_str
        memory['history'].append(strategy['daily_theme'])
        save_memory(memory)
    else:
        print(f"Continuing research on: {memory.get('current_theme', 'Unknown')}")

    print(f"Searching for: {', '.join(memory['current_queries'])}")
    all_raw_videos = search_youtube(memory['current_queries'])
    
    print("Agent is curating the best content...")
    curated_videos = curate_videos(memory['current_theme'], all_raw_videos)
    
    print("Publishing to RSS...")
    build_rss_feed(memory['current_theme'], curated_videos, now)
    print("Mission Complete.")

if __name__ == "__main__":
    main()
