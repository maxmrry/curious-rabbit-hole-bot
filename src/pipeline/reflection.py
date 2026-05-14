import json
import os
import time
from src.pipeline.philosophy import safe_generate

def run_weekly_reflection(policy_filepath='policy/policy.yaml', feedback_filepath='state/feedback.json'):
    """
    The Meta-Brain. Reads Max's recent emotional signals and asks Gemini to
    re-weight the core algorithm to mathematically course-correct the feed.
    """
    print("🧠 Initiating AI Meta-Reflection...")
    
    try:
        with open(feedback_filepath, "r") as f:
            feedback_data = json.load(f)
    except FileNotFoundError:
        print("   No feedback data found yet. Skipping reflection.")
        return

    signals = feedback_data.get("recent_signals", [])
    if not signals:
        print("   No recent signals to analyze. Skipping reflection.")
        return

    # Check if we have reflected recently (e.g., in the last 3 days)
    last_reflection = feedback_data.get("last_reflection_ms", 0)
    now_ms = int(time.time() * 1000)
    if (now_ms - last_reflection) < (3 * 24 * 60 * 60 * 1000):
        print("   Reflected too recently. Letting the current algorithm breathe.")
        return

    # Tally the emotional signals
    tallies = {"amazingly_hopeful": 0, "pretty_positive": 0, "not_interested": 0, "too_gloomy": 0}
    for s in signals[-20:]: # Look at the last 20 clicks
        ctx = s.get("context", "")
        if ctx in tallies:
            tallies[ctx] += 1

    # Only run if there is actual actionable data
    if sum(tallies.values()) < 3:
        print("   Not enough emotional data to justify a shift yet. Waiting for more clicks.")
        return

    # Pull baseline weights from Policy
    import yaml
    try:
        with open(policy_filepath, 'r') as f:
            policy = yaml.safe_load(f)
    except Exception:
        policy = {}
        
    current_weights = policy.get("cognitive_fingerprint", {
        "systemic_curiosity": 0.14, "nuance_endurance": 0.17, "temporal_horizon": 0.19, 
        "constructive_realism": 0.18, "grounded_tangibility": 0.12
    })

    prompt = f"""
    You are the Architect of the 'U-Curve Brain', an RSS feed designed to protect an anxious, globally aware Gen Z male from doom-scrolling, while keeping him grounded in human agency and competence.
    
    Here is how Max has emotionally reacted to the feed recently:
    - {tallies['amazingly_hopeful']} items made him feel amazingly positive/hopeful.
    - {tallies['pretty_positive']} items made him feel pretty positive.
    - {tallies['not_interested']} items bored him (Not Interested).
    - {tallies['too_gloomy']} items triggered a negative/gloomy reaction.
    
    Current Algorithm Weights:
    {json.dumps(current_weights, indent=2)}
    
    YOUR MISSION:
    Look at his reactions. If he is feeling 'too gloomy', you must lower weights for heavy, systemic/temporal news and drastically increase weights for 'delight_score', 'wonder_score', and 'humanity_signal_score'. If he is 'not interested', you must increase 'constructive_realism' and 'grounded_tangibility' to give him more tactile, actionable engineering/maker content.
    
    Generate a new set of dynamic weights (they should roughly sum to 1.0) and write a 1-sentence internal thought explaining your reasoning.
    
    RETURN EXACTLY THIS JSON:
    {{
        "ai_rationale": "Max is getting bogged down by heavy systemic news, so I am shifting the algorithm towards tactile engineering and human delight.",
        "ai_weight_overrides": {{
            "w_sys": 0.10,
            "w_nuance": 0.15,
            "w_temp": 0.10,
            "w_const": 0.25,
            "w_grounded": 0.25,
            "w_wonder": 0.15
        }}
    }}
    """

    response = safe_generate(prompt)
    if not response: 
        print("   AI Reflection failed to generate a response.")
        return

    try:
        parsed = json.loads(response.text)
        new_weights = parsed.get("ai_weight_overrides", {})
        rationale = parsed.get("ai_rationale", "")
        
        print(f"   🤖 AI Architect Decision: {rationale}")
        
        # Save the new algorithm rules back to feedback.json
        feedback_data["ai_weight_overrides"] = new_weights
        feedback_data["last_reflection_ms"] = now_ms
        
        with open(feedback_filepath, 'w') as f:
            json.dump(feedback_data, f, indent=2)
            
        print("   ✅ New algorithmic weights locked in for tomorrow's run.")
        
    except json.JSONDecodeError:
        print("   Failed to parse AI reflection JSON.")
