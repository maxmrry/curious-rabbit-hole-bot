import json
import os
import google.generativeai as genai
from googleapiclient.discovery import build
from datetime import datetime

# 🔒 Securely load API keys from GitHub Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# Configure Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
# We use gemini-1.5-flash as it is lightning fast and perfect for this reasoning task
model = genai.GenerativeModel('gemini-1.5-flash') 

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
    # Clean up the output to ensure it's just the search string
    return response.text.replace('"', '').strip()

def search_youtube(query):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        q=query,
        part='snippet',
        maxResults=3,
        type='video'
    )
    response = request.execute()
    
    videos = []
    for item in response.get('items', []):
        videos.append({
            'title': item['snippet']['title'],
            'link': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            'description': item['snippet']['description']
        })
    return videos

def update_log(query, videos):
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # We append to a markdown file to create a readable "diary" of the bot's discoveries
    with open('discoveries.md', 'a', encoding='utf-8') as f:
        f.write(f"## 🐇 Discovery for {date_str}: {query}\n\n")
        for v in videos:
            f.write(f"* **[{v['title']}]({v['link']})**\n")
            f.write(f"  > {v['description']}\n\n")
        f.write("---\n\n")

def main():
    print("Waking up the agent...")
    memory = load_memory()
    
    # 1. Think
    print("Pondering next rabbit hole...")
    new_topic = get_next_rabbit_hole(memory)
    print(f"Decided to research: {new_topic}")
    
    # 2. Search
    print("Searching YouTube...")
    videos = search_youtube(new_topic)
    
    # 3. Log
    print("Recording discoveries...")
    update_log(new_topic, videos)
    
    # 4. Remember
    print("Updating memory...")
    memory['history'].append(new_topic)
    memory['current_rabbit_hole'] = new_topic
    save_memory(memory)
    
    print("Done! Going back to sleep.")

if __name__ == "__main__":
    main()
