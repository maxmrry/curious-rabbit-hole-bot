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

def semantic_triage(candidates):
    """
    Passes the raw pool to Gemini to contextually score them on a 0-10 scale.
    This prevents static keyword blacklists from blocking good content.
    """
    if not candidates:
        return []

    pool_text = ""
    for item in candidates:
        # We include the publication date so Gemini can judge if it's outdated panic
        import datetime
        pub_date_str = datetime.datetime.fromtimestamp(item['published_date_ms'] / 1000.0).strftime('%Y-%m-%d')
        pool_text += f"\nID: {item['native_id']} | Date: {pub_date_str} | Source: {item['source_name']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = """
    You are the 'U-Curve Brain' operating in the year 2026. 
    Score the following content candidates from 0 to 10 based on these metrics:
    
    1. constructive_score (0-10): Showcases progress, resilience, human cooperation, or actionable philosophy.
    2. anthropology_score (0-10): Fascinating deep dive into human behavior, sociology, or niche subcultures.
    3. fear_score (0-10): Engagement-bait, doom-mongering, or apocalyptic framing. (10 = maximum toxic panic).
    4. timelessness_score (0-10): Is this universally relevant? (10 = timeless philosophy/science. 0 = outdated 2021 pandemic news or old election cycles).
    5. ai_slop_penalty (0-10): Does this read like generic, faceless AI-generated garbage? (10 = absolute AI slop).

    RETURN EXACTLY THIS JSON STRUCTURE:
    {
        "scores": [
            {
                "native_id": "the exact ID from the pool",
                "constructive_score": 8,
                "anthropology_score": 2,
                "fear_score": 1,
                "timelessness_score": 9,
                "ai_slop_penalty": 0
            }
        ]
    }

    CANDIDATES:
    """ + pool_text

    response = safe_generate(prompt)
    if not response:
        return []

    try:
        parsed = json.loads(response.text)
        return parsed.get("scores", [])
    except json.JSONDecodeError:
        print("🚨 Failed to parse Gemini Semantic Triage JSON.")
        return []

def reframe_items(selected_items):
    """
    Rewrites the descriptions of the final mathematically chosen 5 items.
    """
    if not selected_items:
        return []

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nID: {item['native_id']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = """
    Rewrite the descriptions for these 5 items constructively.
    
    REWRITE RULES:
    - Keep it under 80 words.
    - Be factually honest. Do not lie or use toxic positivity.
    - Extract the constructive angle. Focus on resilience, solutions, or fascinating insights.
    
    RETURN EXACTLY THIS JSON STRUCTURE:
    {
        "rewrites": [
            {
                "native_id": "exact ID",
                "rewritten_description": "your 80-word constructive summary"
            }
        ]
    }

    ITEMS:
    """ + pool_text

    response = safe_generate(prompt)
    if not response:
        return selected_items # Fallback to original descriptions if API fails

    try:
        parsed = json.loads(response.text)
        rewrites = {x["native_id"]: x["rewritten_description"] for x in parsed.get("rewrites", [])}
        
        for item in selected_items:
            if item["native_id"] in rewrites:
                item["description"] = rewrites[item["native_id"]]
        return selected_items
    except json.JSONDecodeError:
        return selected_items

def get_daily_principle():
    """Uses Gemini to generate a timeless historical adage or proverb."""
    prompt = """
    Provide a single, timeless historical proverb, adage, or piece of Stoic/Zen wisdom 
    that relates to resilience, perspective, or human endurance. 
    Do not use clinical psychology terms. Keep it poetic but grounded.
    
    Format: "The quote." - Author/Origin
    """
    response = safe_generate(prompt)
    if response and response.text:
        return response.text.strip().replace('"', '').replace('{', '').replace('}', '')
    return "A smooth sea never made a skilled sailor. - English Proverb"
