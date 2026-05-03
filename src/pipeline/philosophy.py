import os
import json
import time
import random
import datetime
import google.generativeai as genai

# Seasonal psychological context for UK latitude
# Multiple angles per season so the Max Entry doesn't repeat the same frame
SEASONAL_ANGLES = {
    "winter": [
        "It is the middle of winter in the UK. Daylight is short and the brain's threat-detection runs hotter in low light. This is documented biology, not weakness. Frame with warmth and forward momentum.",
        "January in England is statistically the lowest-mood month in the year. That is a population average, not a sentence. Frame today around the specific and the concrete — small progress over abstract optimism.",
        "Winter in the UK means the brain is running on less light than it evolved for. Acknowledge this honestly but briefly. The antidote is not cheerfulness but engagement — content that pulls attention outward.",
        "The first weeks of the year carry cultural weight that is largely manufactured. Frame today around what is genuinely new rather than what is symbolically new.",
    ],
    "early_spring": [
        "Early spring in the UK. The turn is beginning — days are lengthening, which has a measurable effect on baseline mood. Frame around renewal and motion.",
        "March light in England shifts something in the nervous system before the conscious mind registers it. Frame today around emerging momentum — things that are beginning, not just things that are.",
    ],
    "late_spring": [
        "Late spring in the UK. One of the highest baseline wellbeing periods of the year. Frame to capitalise on this cognitive lift — big ideas land better now.",
        "May in England. Long evenings are returning. Frame around expansion — ideas that open outward, connections that cross borders, futures worth imagining.",
    ],
    "summer": [
        "Summer in the UK. Long days, higher social energy, lower ruminative thinking. Frame toward action, exploration, and expansion.",
        "British summer is brief and cherished. Frame around what is alive and working in the world — not despite difficulty but alongside it.",
    ],
    "early_autumn": [
        "Early autumn in the UK. A transition month — psychologically associated with new beginnings despite the darkening. Frame around structure and momentum.",
        "September carries the cultural memory of new starts. Frame today around deliberate direction — the satisfaction of choosing what to pay attention to.",
    ],
    "late_autumn": [
        "Late autumn in the UK. Light is dropping, the brain begins its winter threat-heightening cycle. Prioritise grounding, perspective, and resilience framing.",
        "November in England. The instinct is to contract. The content today pushes back against that — not with false brightness but with evidence that the world is larger than any given month.",
    ],
}

def _get_season_key(month):
    if month in (12, 1, 2): return "winter"
    elif month == 3: return "early_spring"
    elif month in (4, 5): return "late_spring"
    elif month in (6, 7, 8): return "summer"
    elif month == 9: return "early_autumn"
    elif month in (10, 11): return "late_autumn"
    return "winter"

def _get_seasonal_context(dt):
    from src.pipeline.memory_mgr import load_memory, save_memory
    memory = load_memory()
    season_key = _get_season_key(dt.month)
    angles = SEASONAL_ANGLES.get(season_key, SEASONAL_ANGLES["winter"])

    used_key = f"used_seasonal_angles_{season_key}"
    used_indices = memory.get(used_key, [])
    fresh = [i for i in range(len(angles)) if i not in used_indices[-len(angles)+1:]]
    candidate_indices = fresh if fresh else list(range(len(angles)))

    chosen = random.choice(candidate_indices)
    memory.setdefault(used_key, []).append(chosen)
    memory[used_key] = memory[used_key][-20:]
    save_memory(memory)

    return angles[chosen]

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
    Score the following candidates from 0 to 10 based on these metrics.
    
    CALIBRATION EXAMPLES (use these to anchor your scoring):
    
    Example A — High quality:
    Title: "How microfinance quietly lifted 100 million people out of poverty"
    Source: Our World in Data
    Scores: systemic=9, nuance=7, temporal=3, constructive=9, abstraction=6,
            fear=0, ai_slop=0, geo_affinity=7, niche_boredom=0, state_shift=9, humanity_signal=10
    
    Example B — Low quality (doom engagement bait):
    Title: "Why the global economy is about to collapse and nobody is talking about it"
    Source: Unknown Blog
    Scores: systemic=3, nuance=1, temporal=2, constructive=1, abstraction=2,
            fear=9, ai_slop=7, geo_affinity=5, niche_boredom=2, state_shift=1, humanity_signal=0
    
    Example C — Medium quality (interesting but dry):
    Title: "Proceedings of the 2024 International Symposium on Monetary Policy Frameworks"
    Source: IMF
    Scores: systemic=6, nuance=5, temporal=2, constructive=4, abstraction=5,
            fear=0, ai_slop=0, geo_affinity=5, niche_boredom=8, state_shift=2, humanity_signal=1
    
    Example D — High quality (psychological/personal relevance):
    Title: "The surprising science of why humans are terrible at predicting their own unhappiness"
    Source: Yale Courses
    Scores: systemic=5, nuance=8, temporal=3, constructive=8, abstraction=7,
            fear=0, ai_slop=0, geo_affinity=7, niche_boredom=0, state_shift=9, humanity_signal=5
    
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
    11. humanity_signal_score (0-10): Does this showcase human cooperation, ingenuity, scientific progress, or civilisational resilience at scale? (10 = profound demonstration of what humans can achieve together, 0 = purely individual or institutionally dry).

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
                "state_shift_score": 9,
                "humanity_signal_score": 7
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

# Emotional register taxonomy for variety checking
REGISTER_TAXONOMY = {
    "optimism_tech": ["technology", "innovation", "breakthrough", "ai", "research", "discovery"],
    "optimism_society": ["cooperation", "community", "peace", "democracy", "rights", "progress"],
    "optimism_health": ["health", "medicine", "longevity", "wellbeing", "mental", "therapy"],
    "introspective": ["psychology", "behaviour", "cognitive", "mind", "self", "identity"],
    "historical": ["history", "ancient", "century", "civilisation", "era", "past"],
    "economic": ["economy", "trade", "growth", "work", "labour", "market", "fiscal"],
    "environmental": ["climate", "nature", "ecology", "planet", "species", "biodiversity"],
    "philosophical": ["meaning", "ethics", "philosophy", "consciousness", "truth", "wisdom"],
}

def _get_register(item):
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    for register, keywords in REGISTER_TAXONOMY.items():
        if any(k in text for k in keywords):
            return register
    return "general"

def apply_variety_engine(selected_items, valid_items, score_map):
    """
    Checks for emotional register clustering in the final selection.
    If any register appears 3+ times, swaps the weakest instance for the
    highest-scoring item in the most underrepresented register.
    """
    from collections import Counter

    register_counts = Counter(_get_register(i) for i in selected_items)
    overrepresented = [r for r, count in register_counts.items() if count >= 3]

    if not overrepresented:
        return selected_items

    all_registers = set(REGISTER_TAXONOMY.keys())
    present_registers = set(register_counts.keys())
    absent_registers = all_registers - present_registers

    if not absent_registers:
        return selected_items  # Everything represented, no swap needed

    selected_ids = {i["native_id"] for i in selected_items}
    target_register = random.choice(list(absent_registers))

    # Find the best unselected item in the target register
    candidate = next(
        (i for i in valid_items
         if i["native_id"] not in selected_ids
         and _get_register(i) == target_register),
        None
    )

    if not candidate:
        return selected_items

    # Find the weakest item in the most overrepresented register
    worst_register = max(overrepresented, key=lambda r: register_counts[r])
    weakest = min(
        [i for i in selected_items if _get_register(i) == worst_register],
        key=lambda i: i.get("sort_weight", 0)
    )

    print(f"Variety Engine: swapping '{weakest['title'][:50]}' ({worst_register}) for '{candidate['title'][:50]}' ({target_register})")

    selected_items = [candidate if i["native_id"] == weakest["native_id"] else i for i in selected_items]
    return selected_items

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

# Narrative theme families — prevents the same emotional arc repeating
NARRATIVE_THEME_FAMILIES = [
    "resilience", "progress", "cooperation", "ingenuity", "perspective",
    "stability", "adaptation", "agency", "understanding", "renewal"
]

def _classify_narrative_theme(headline):
    headline_lower = headline.lower()
    for theme in NARRATIVE_THEME_FAMILIES:
        if theme in headline_lower:
            return theme
    return "general"

def generate_daily_narrative(selected_items):
    """Stitches the daily items into a single overarching theme, avoiding recent themes."""
    if not selected_items:
        return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

    from src.pipeline.memory_mgr import load_memory, save_memory
    memory = load_memory()
    recent_themes = memory.get("used_narrative_themes", [])[-7:]

    pool_text = ""
    for item in selected_items:
        pool_text += f"\nTitle: {item['title']}\n---"

    avoid_clause = ""
    if recent_themes:
        avoid_clause = f"\nAVOID these theme families used recently: {', '.join(recent_themes)}. Find a genuinely different angle."

    prompt = f"""
    Look at the titles of these media items curated for today.
    Find the hidden connective tissue. What is the overarching macro-theme of human progress, resilience, or systemic understanding today?
    {avoid_clause}
    
    RETURN EXACTLY THIS JSON:
    {{
        "headline": "Today's Pattern: [Your punchy 5-7 word theme]",
        "explanation": "A single, grounded 20-word sentence explaining how these items connect to show progress, resilience, or stabilization."
    }}
    ITEMS:
    {pool_text}
    """

    response = safe_generate(prompt)
    if not response:
        return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

    try:
        result = json.loads(response.text)
        # Record the theme family used
        used_family = _classify_narrative_theme(result.get("headline", ""))
        memory.setdefault("used_narrative_themes", []).append(used_family)
        memory["used_narrative_themes"] = memory["used_narrative_themes"][-30:]
        save_memory(memory)
        return result
    except json.JSONDecodeError:
        return {"headline": "Today's Pattern: Quiet Resilience", "explanation": "Systems are holding steady."}

def get_ratchet_memory_note(memory):
    """
    Every 7 days, surfaces a streak note for Max.
    Returns a string if it's a milestone day, otherwise empty string.
    """
    runs = memory.get("runs", {})
    streak = len([k for k, v in runs.items() if v.get("success", False)])
    if streak > 0 and streak % 7 == 0:
        return (
            f"This system has now run successfully for {streak} days. "
            f"That is {streak} mornings where the first thing you read was chosen by "
            f"an algorithm designed exclusively to work for you. "
            f"Most people's feeds are optimised by systems working against them. Yours is not."
        )
    return ""

def generate_max_entry(selected_items, now):
    """
    Generates a personalised cold open entry addressed directly to Max.
    Sets the psychological frame for the entire day's feed.
    """
    from src.pipeline.memory_mgr import load_memory
    memory = load_memory()

    seasonal_context = _get_seasonal_context(now)
    ratchet_note = get_ratchet_memory_note(memory)

    titles = "\n".join([f"- {item['title']}" for item in selected_items[:10]])

    ratchet_section = f"\nADDITIONALLY, if appropriate, weave in this milestone note naturally: {ratchet_note}" if ratchet_note else ""

    prompt = f"""
You are writing the opening entry of a daily RSS feed for a person named Max.
Max is a Gen Z male in his 20s, employed, living in north-west England. He is globally aware, 
intellectually curious, and is actively working to deconstruct the fear-culture and doom-framing 
that dominates media for his generation. He is not naive — he knows the world has problems. 
He has chosen to build a system that counterbalances his brain's natural negativity bias.

SEASONAL CONTEXT (use this to calibrate tone, do not quote it directly):
{seasonal_context}

TODAY'S FEED CONTAINS THESE ITEMS:
{titles}

YOUR TASK:
Write a single opening paragraph of exactly 3-5 sentences addressed directly to Max (use "you", not "one" or "people").
This is not a summary. It is a psychological frame-setter — the cognitive equivalent of a trusted friend 
saying "here is what today is actually about" before handing him the newspaper.

RULES:
- Do not use motivational poster language. No "seize the day", no "you've got this."
- Do not summarise the items. Synthesise the underlying human truth they collectively point to.
- Be direct, warm, and grounded. Stoic in register, not cold.
- One sentence should acknowledge something genuinely difficult or uncertain in the world without dwelling on it.
- End on forward motion — not false hope, but genuine agency.
- No emojis. No exclamation marks. Write like a thoughtful person, not an algorithm.
- Address him as Max once, naturally. Not at the start.
{ratchet_section}

Return only the paragraph. No title, no preamble.
"""

    response = safe_generate(prompt, is_json=False)
    if response and response.text:
        return response.text.strip().replace('"', '')
    return (
        "The world generates more noise than signal on any given day. "
        "Today's feed has been filtered with that in mind, Max. "
        "What follows is chosen because it builds something — perspective, understanding, or quiet momentum. "
        "That is enough."
    )

def get_daily_protocol(filepath='policy/principles.json'):
    try:
        from src.pipeline.memory_mgr import load_memory, save_memory
        memory = load_memory()
        used_indices = memory.get("used_principle_indices", [])

        with open(filepath, 'r', encoding='utf-8') as f:
            principles = json.load(f)

        total = len(principles)
        recent_cutoff = max(10, int(total * 0.3))
        recent_used = set(used_indices[-recent_cutoff:])
        fresh_indices = [i for i in range(total) if i not in recent_used]
        candidate_indices = fresh_indices if fresh_indices else list(range(total))

        chosen_index = random.choice(candidate_indices)
        raw_principle = principles[chosen_index]

        memory.setdefault("used_principle_indices", []).append(chosen_index)
        memory["used_principle_indices"] = memory["used_principle_indices"][-60:]
        save_memory(memory)

        clean_principle = (
            str(raw_principle)
            .replace("\"", "'")
            .replace("\n", " ")
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

# Emotional theme clusters for adage deduplication
ADAGE_CLUSTERS = {
    "impermanence": ["turns up", "passes", "tide", "time", "moment", "end", "last", "change"],
    "agency": ["make", "do", "act", "begin", "start", "choice", "hand", "key"],
    "perspective": ["look", "see", "eye", "view", "side", "fool", "wise", "judge"],
    "resilience": ["strong", "chain", "sailor", "storm", "bend", "fall", "rise"],
    "connection": ["friend", "dog", "man", "home", "house", "love", "trust"],
    "caution": ["straw", "penny", "rots", "head", "weak", "bite", "bark"],
}

def _get_adage_cluster(text):
    text_lower = text.lower()
    for cluster, keywords in ADAGE_CLUSTERS.items():
        if any(k in text_lower for k in keywords):
            return cluster
    return "general"

def get_daily_principle(filepath='policy/adages.txt'):
    try:
        from src.pipeline.memory_mgr import load_memory, save_memory
        memory = load_memory()
        recent_clusters = memory.get("adage_cluster_history", [])[-5:]

        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        fresh_lines = [l for l in lines if _get_adage_cluster(l) not in recent_clusters]
        candidate_pool = fresh_lines if fresh_lines else lines
        raw_adage = random.choice(candidate_pool)

        used_cluster = _get_adage_cluster(raw_adage)
        memory.setdefault("adage_cluster_history", []).append(used_cluster)
        memory["adage_cluster_history"] = memory["adage_cluster_history"][-30:]
        save_memory(memory)

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