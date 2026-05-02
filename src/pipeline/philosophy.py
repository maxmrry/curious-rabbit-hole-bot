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

    1. systemic_score (0-10): Focuses on structural mechanisms and global progress.
    2. nuance_score (0-10): Embraces complex ambiguity without resorting to fear.
    3. temporal_score (0-10): History/anthropology, ONLY IF it provides a relatable lens for the present.
    4. constructive_score (0-10): Grounded realism, accessible tech, and actionable truth.
    5. abstraction_score (0-10): Big ideas with tangible life applications.
    6. fear_score (0-10): Engagement-bait or doom. (10 = maximum toxic panic).
    7. ai_slop_penalty (0-10): Generic AI-generated garbage, toxic "feel-good fluff", OR saccharine oversimplification. Score 8+ for anything that makes a complex problem sound solved, uses phrases like "this will change everything", or feels emotionally manipulative in a positive direction. Grounded optimism scores 0. Unearned optimism scores high.
    8. geo_affinity_score (0-10): Western relevance. UK-centric = 10, Europe = 8, US = 6.
    9. niche_boredom_penalty (0-10): CRITICAL. Score 10 for dry institutional housekeeping, campus lectures, or highly specific niche subcultures. 
    10. state_shift_score (0-10): CORE DRIVER. Does this actually improve mental state, offer agency, and provide "felt momentum"? (10 = highly empowering/energizing, 0 = emotionally flat/draining).

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
                "geo_affinity_score": 8,
                "niche_boredom_penalty": 0,
                "state_shift_score": 9
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
    """Rewrites descriptions, optimizes titles for curiosity, and adds Doom Immunity."""
    if not selected_items: return []

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nID: {item['native_id']}\nType: {item['source_type']}\nTitle: {item['title']}\nDesc: {item['description']}\n---"

    prompt = """
    You are a high-level cognitive filter for an employed Gen Z male in the UK/EU.
    Your job is to rewrite the metadata of these media items.
    
    RULES:
    1. "hook_title": Rewrite the title so it creates a healthy curiosity gap (e.g., instead of "Global Health Data", use "Why preventable disease is plummeting globally"). Do not use clickbait.
    2. "rewritten_description": Keep it under 60 words. Be objective. If it is News, always end with one sentence grounding the content in tangible personal relevance — how might this affect the daily life, mental models, relationships, or career of a young employed person in the UK? Make it specific, not generic.
    3. "doom_inoculation": If the original text contains panic words (crisis, unprecedented, breaking, escalation), write a 1-sentence stoic counter-frame (e.g., "This language triggers false urgency; global systems adapt slowly."). Otherwise, leave it blank.
    
    RETURN EXACTLY THIS JSON:
    {
        "rewrites": [
            {
                "native_id": "exact ID",
                "hook_title": "Optimized Title",
                "rewritten_description": "Objective synopsis",
                "doom_inoculation": "Stoic counter-frame or empty string"
            }
        ]
    }
    ITEMS:
    """ + pool_text

    response = safe_generate(prompt)
    if not response: return selected_items

    try:
        parsed = json.loads(response.text)
        rewrites = {x["native_id"]: x for x in parsed.get("rewrites", [])}
        for item in selected_items:
            update = rewrites.get(item["native_id"])
            if update:
                item["title"] = update.get("hook_title", item["title"])
                desc = update.get("rewritten_description", item["description"])
                inoculation = update.get("doom_inoculation", "")
                if inoculation:
                    desc += f"<br><br><i>🛡️ <b>System Note:</b> {inoculation}</i>"
                item["description"] = desc
        return selected_items
    except json.JSONDecodeError:
        return selected_items

def generate_daily_narrative(selected_items):
    """Stitches the daily items into a single overarching theme."""
    if not selected_items: return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nTitle: {item['title']}\n---"

    prompt = """
    Look at the titles of these media items curated for today. 
    Find the hidden connective tissue. What is the overarching macro-theme of human progress, resilience, or systemic understanding today?
    
    RETURN EXACTLY THIS JSON:
    {
        "headline": "Today's Pattern: [Your punchy 5-7 word theme]",
        "explanation": "A single, grounded 20-word sentence explaining how these items connect to show progress, resilience, or stabilization."
    }
    ITEMS:
    """ + pool_text

    response = safe_generate(prompt)
    if not response: return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

def get_daily_protocol(filepath='policy/principles.json'):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            principles = json.load(f)
            raw_principle = random.choice(principles)
            
            # 🔧 FIX: Using escaped quotes (\") so code editor colors don't break
            clean_principle = (
                str(raw_principle)
                .replace("\"", "'")      # avoid breaking quotes
                .replace("\n", " ")      # remove line breaks
                .strip()
            )
            
            prompt = f"""
            Take this clinical psychological principle: "{clean_principle}"
            Translate it into a single, direct, relatable sentence of advice. Do not use quotes. Make it sound empowering and stoic.
            CONTEXT: The reader is a Gen Z English male in his 20s, employed, globally aware, and actively trying to deconstruct modern fear-culture.
            CRITICAL RULE: Apply this principle holistically. Dynamically vary the application—relate it to romantic relationships, friendships, personal self-worth, media consumption, OR career. Do not just focus on work. Keep it to one punchy sentence.
            """
            
            response = safe_generate(prompt, is_json=False)
            if response and response.text:
                return response.text.strip().replace("\"", "")
            return raw_principle
    except Exception:
        return "Notice three neutral things today to actively break the brain's hunt for threats."

def get_daily_principle(filepath='policy/adages.txt'):
    try:
        # 🔧 FIX: Added encoding='utf-8' to prevent UnicodeDecodeError on weird characters
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            raw_adage = random.choice(lines)
            
            prompt = f"""
            I have a raw, messy adage from a list: "{raw_adage}"
            1. Clean up any broken text, hyphens, or brackets so it reads as a perfect, classic adage. Do not use quotes.
            2. Add a space, then add a very brief, simple sentence in rounded brackets (like this) explaining how the reader can apply this to their life to reduce anxiety or gain perspective.
            CONTEXT: The reader is a Gen Z English male in his 20s, employed, globally aware, and actively trying to deconstruct modern fear-culture.
            CRITICAL RULE: Do not over-analyze. Keep the bracketed text punchy, grounded, and extremely short (maximum 12 words).
            """
            
            response = safe_generate(prompt, is_json=False)
            if response and response.text:
                return response.text.strip().replace("\"", "")
            return "A smooth sea never made a skilled sailor. (Embrace today's friction as training for tomorrow.)"
    except Exception:
        return "A smooth sea never made a skilled sailor. (Embrace today's friction as training for tomorrow.)"
