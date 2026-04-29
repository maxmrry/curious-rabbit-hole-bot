import os
import json
import time
import random
import datetime
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
        pub_date_str = datetime.datetime.fromtimestamp(item['published_date_ms'] / 1000.0).strftime('%Y-%m-%d')
        pool_text += f"\nID: {item['native_id']} | Date: {pub_date_str} | Source: {item['source_name']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    current_year = datetime.datetime.now().year

    prompt = f"""
    You are the 'U-Curve Brain', an advanced cognitive containment filter.

    Score the following content candidates from 0 to 10 based on these highly specific metrics:

    1. systemic_score (0-10): Focuses on structural mechanisms, ecologies, and how systems work (rather than personal drama).
    2. nuance_score (0-10): Embraces complex, high-friction ambiguity and grey-areas.
    3. temporal_score (0-10): Deep-time perspective, macro-history, or evolutionary anthropology.
    4. constructive_score (0-10): Grounded realism, actionable truth, and resilience (NO fake toxic positivity).
    5. abstraction_score (0-10): High-level theoretical concepts, big philosophical ideas, and deep frameworks.
    6. fear_score (0-10): Engagement-bait, doom-mongering, or apocalyptic framing. (10 = maximum toxic panic).
    7. ai_slop_penalty (0-10): Does this read like generic, faceless AI-generated garbage? (10 = absolute slop).

    RETURN EXACTLY THIS JSON STRUCTURE:
    {{
        "scores": [
            {{
                "native_id": "the exact ID from the pool",
                "systemic_score": 5,
                "nuance_score": 8,
                "temporal_score": 2,
                "constructive_score": 7,
                "abstraction_score": 9,
                "fear_score": 1,
                "ai_slop_penalty": 0
            }}
        ]
    }}

    CANDIDATES:
    {pool_text}
    """

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
    Generates a clean, objective 60-word synopsis of the final chosen items.
    Does not fabricate or inject artificial positivity.
    """
    if not selected_items:
        return []

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nID: {item['native_id']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = """
    You are a high-level cognitive filter. Your job is to rewrite the descriptions of these media items to provide a clean, objective synopsis.
    
    REWRITE RULES:
    - Keep it under 60 words.
    - Be factually honest. DO NOT fabricate, editorialize, or inject artificial "toxic positivity."
    - Clearly state what the content is about and what the user will learn from it.
    - Speak with stoic, mature clarity.
    
    RETURN EXACTLY THIS JSON STRUCTURE:
    {
        "rewrites": [
            {
                "native_id": "exact ID",
                "rewritten_description": "your 60-word objective synopsis"
            }
        ]
    }

    ITEMS:
    """ + pool_text

    response = safe_generate(prompt)
    if not response:
        return selected_items

    try:
        parsed = json.loads(response.text)
        rewrites = {x["native_id"]: x["rewritten_description"] for x in parsed.get("rewrites", [])}
        
        for item in selected_items:
            if item["native_id"] in rewrites:
                item["description"] = rewrites[item["native_id"]]
        return selected_items
    except json.JSONDecodeError:
        return selected_items

def get_daily_protocol(filepath='policy/principles.json'):
    """Pulls a random psychological reminder from the Power of Bad principle bank."""
    try:
        with open(filepath, 'r') as f:
            principles = json.load(f)
            return random.choice(principles)
    except Exception as e:
        print(f"⚠️ Failed to load principles: {e}")
        return "The Power of Bad: Bad is stronger than good, but it is usable. Exploit the bias for smarter decisions instead of being controlled by it."

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
