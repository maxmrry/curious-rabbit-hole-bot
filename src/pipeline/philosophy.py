import os
import json
import time
import random
import google.generativeai as genai

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # Using flash as it is fast, cheap, and excellent at JSON structuring
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})

def safe_generate(prompt, retries=3):
    """Wraps Gemini calls in a protective retry loop."""
    for attempt in range(retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            if attempt < retries - 1:
                print(f"⚠️ API busy or failed. Retrying ({attempt + 1}/{retries})...")
                time.sleep(15)
            else:
                print(f"🚨 Gemini completely failed: {e}")
                return None

def select_and_rewrite(clean_pool):
    """
    Forces Gemini to select the 4:1 ratio and rewrite the descriptions constructively.
    """
    if not clean_pool:
        print("⚠️ No items in clean pool to process.")
        return []

    # To save tokens and avoid confusing the AI, we only send the top 15 candidates
    candidates = clean_pool[:15]
    
    # Prepare the text we send to Gemini
    pool_text = ""
    for i, item in enumerate(candidates):
        pool_text += f"\nID: {item['native_id']} | Source: {item['source_name']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = f"""
    You are the 'U-Curve Brain', a cognitive filter designed to protect a globally aware Gen Z user from algorithmic fear culture.
    You follow the principles of 'The Power of Bad': Bad is stronger than good, so we must actively balance the scales with constructive truth.

    I have provided a pool of vetted articles, videos, and podcasts below.
    
    TASK:
    1. Select EXACTLY 4 items that represent 'Positivity' (constructive progress, resilience, human cooperation, scientific breakthroughs, or relationship psychology).
    2. Select EXACTLY 1 item that represents a 'Deep Dive' (anthropology, sociology, or fascinating subcultures).
    3. Rewrite the description for the 5 selected items.
    
    REWRITE RULES:
    - Keep it under 80 words.
    - Be factually honest. Do not lie or use toxic positivity.
    - Extract the constructive angle. Focus on resilience, solutions, or fascinating insights.
    
    RETURN EXACTLY THIS JSON STRUCTURE:
    {{
        "selected": [
            {{
                "native_id": "the exact ID from the pool",
                "category": "positivity or deep_dive",
                "rewritten_description": "your 80-word constructive summary"
            }}
        ]
    }}

    CANDIDATE POOL:
    {pool_text}
    """

    response = safe_generate(prompt)
    if not response:
        return []

    try:
        # Gemini returns the structured JSON
        parsed_response = json.loads(response.text)
        selections = parsed_response.get("selected", [])
        
        # Merge Gemini's rewrites back with the original URLs and metadata
        final_feed_items = []
        for selection in selections:
            original_item = next((item for item in candidates if item["native_id"] == selection["native_id"]), None)
            if original_item:
                original_item["description"] = selection["rewritten_description"]
                original_item["category"] = selection["category"]
                final_feed_items.append(original_item)
                
        return final_feed_items
        
    except json.JSONDecodeError:
        print("🚨 Failed to parse Gemini JSON output.")
        return []

def get_daily_principle(filepath='policy/principles.json'):
    """Pulls a random psychological reminder from the Power of Bad principle bank."""
    try:
        with open(filepath, 'r') as f:
            principles = json.load(f)
            return random.choice(principles)
    except Exception as e:
        print("⚠️ Failed to load principles:", e)
        return "Protect your attention. A frightening headline is not the same as a truthful forecast."
