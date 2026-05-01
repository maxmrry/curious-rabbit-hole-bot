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
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
    text_model = genai.GenerativeModel('gemini-2.5-flash') # Standard text model for anchors

def safe_generate(prompt, retries=3, is_json=True):
    for attempt in range(retries):
        try:
            if is_json:
                return model.generate_content(prompt)
            else:
                return text_model.generate_content(prompt)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(15)
            else:
                print(f"🚨 Gemini completely failed: {e}")
                return None

def semantic_triage(candidates):
    if not candidates:
        return []

    pool_text = ""
    for item in candidates:
        pub_date_str = datetime.datetime.fromtimestamp(item['published_date_ms'] / 1000.0).strftime('%Y-%m-%d')
        pool_text += f"\nID: {item['native_id']} | Date: {pub_date_str} | Source: {item['source_name']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = f"""
    You are the 'U-Curve Brain', an advanced cognitive filter for an employed Gen Z male in the UK/EU.
    Score the following candidates from 0 to 10 based on these metrics:

    1. systemic_score (0-10): Focuses on structural mechanisms and human cooperation.
    2. nuance_score (0-10): Embraces complex ambiguity.
    3. temporal_score (0-10): History or anthropology, BUT ONLY IF it teaches something positive or relatable about human drivers today.
    4. constructive_score (0-10): Grounded realism, accessible tech, and actionable truth.
    5. abstraction_score (0-10): Big ideas. CRITICAL RULE: Heavily penalize pure detached academia (like abstract math, ancient geography, or dense policy) that has no tangible life application.
    6. fear_score (0-10): Engagement-bait or panic. (10 = maximum toxic panic).
    7. ai_slop_penalty (0-10): Generic AI-generated garbage.
    8. geo_affinity_score (0-10): Western relevance. UK-centric = 10, Europe = 8, US = 6. Highly specific non-Western macroeconomics (e.g., Egypt policies) = 2.

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
                "ai_slop_penalty": 0,
                "geo_affinity_score": 8
            }}
        ]
    }}

    CANDIDATES:
    {pool_text}
    """

    response = safe_generate(prompt)
    if not response: return []

    try:
        parsed = json.loads(response.text)
        return parsed.get("scores", [])
    except json.JSONDecodeError:
        return []

def reframe_items(selected_items):
    if not selected_items: return []

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nID: {item['native_id']}\nType: {item['source_type']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = """
    You are a high-level cognitive filter for an employed, globally aware Gen Z male living in the UK/EU.
    Rewrite descriptions to provide a clean, objective synopsis.
    
    RULES:
    - Keep it under 60 words (News can be up to 80).
    - Be factually honest. DO NOT inject "toxic positivity."
    - IF TYPE IS 'news': Append one final sentence explaining the tangible, positive consequence of this event for a young professional in the UK/EU today (e.g., how it provides economic, environmental, or geopolitical stability).
    
    RETURN EXACTLY THIS JSON STRUCTURE:
    {
        "rewrites": [
            {
                "native_id": "exact ID",
                "rewritten_description": "your objective synopsis"
            }
        ]
    }
    ITEMS:
    """ + pool_text

    response = safe_generate(prompt)
    if not response: return selected_items

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
    try:
        with open(filepath, 'r') as f:
            principles = json.load(f)
            raw_principle = random.choice(principles)
            
            prompt = f"""
            Take this clinical psychological principle: "{raw_principle}"
            Translate it into a single, direct, relatable sentence of advice for a 20-something navigating modern life. Do not use quotes. Make it sound empowering.
            """
            response = safe_generate(prompt, is_json=False)
            if response and response.text:
                return response.text.strip().replace('"', '')
            return raw_principle
    except Exception:
        return "Notice three neutral things today to actively break the brain's hunt for threats."

def get_daily_principle(filepath='policy/adages.txt'):
    try:
        with open(filepath, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            raw_adage = random.choice(lines)
            
            prompt = f"""
            I have a raw, messy adage from a list: "{raw_adage}"
            1. Clean up any broken text, hyphens, or brackets so it reads as a perfect, classic adage. Do not use quotes.
            2. Add a space, then add a short, grounded sentence in brackets [like this] explaining how a 20-something young professional can apply this to their life to reduce anxiety or gain perspective.
            """
            response = safe_generate(prompt, is_json=False)
            if response and response.text:
                return response.text.strip().replace('"', '')
            return "A smooth sea never made a skilled sailor. [Embrace friction today as the exact training required for tomorrow's competence.]"
    except Exception:
        return "A smooth sea never made a skilled sailor. [Embrace friction today as the exact training required for tomorrow's competence.]"
