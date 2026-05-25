import os
import json
import time

FEEDBACK_PATH = "state/feedback.json"

# The new Emotional Math scale
SIGNAL_WEIGHTS = {
    -1: -4.0,  # too_gloomy — heavy penalty to source
     0: -2.0,  # not_interested — moderate penalty
     1:  0.0,  # neutral_okay — no math change, just logged for AI reflection
     2:  2.0,  # pretty_positive — solid boost
     3:  4.0,  # amazingly_hopeful — massive boost
}

def load_feedback():
    try:
        with open(FEEDBACK_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "source_adjustments": {},
            "source_type_adjustments": {},
            "recent_signals": []
        }

def save_feedback(data):
    os.makedirs("state", exist_ok=True)
    with open(FEEDBACK_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def ingest():
    item_id = os.getenv("ITEM_ID", "")
    # Default to 1 (neutral) if something goes wrong
    try:
        signal = int(os.getenv("SIGNAL", "1"))
    except ValueError:
        signal = 1
        
    source_name = os.getenv("SOURCE_NAME", "")
    source_type = os.getenv("SOURCE_TYPE", "")
    signal_label = os.getenv("SIGNAL_LABEL", "neutral_okay")
    context = os.getenv("CONTEXT", "")

    if not item_id:
        print("No item_id provided. Exiting.")
        return

    # Use the default 0.0 (neutral) if a weird signal comes through
    weight_delta = SIGNAL_WEIGHTS.get(signal, 0.0)
    feedback = load_feedback()
    now_ms = int(time.time() * 1000)

    # Adjust per-source score
    if source_name and weight_delta != 0:
        prev = feedback["source_adjustments"].get(source_name, {"cumulative": 0.0, "n": 0})
        feedback["source_adjustments"][source_name] = {
            "cumulative": round(prev["cumulative"] + weight_delta, 3),
            "n": prev["n"] + 1,
            "last_signal_ms": now_ms
        }

    # Adjust per-type score
    if source_type and weight_delta != 0:
        prev = feedback["source_type_adjustments"].get(source_type, {"cumulative": 0.0, "n": 0})
        feedback["source_type_adjustments"][source_type] = {
            "cumulative": round(prev["cumulative"] + weight_delta, 3),
            "n": prev["n"] + 1
        }

    # Log the signal so the AI Meta-Brain (reflection.py) can read it
    feedback["recent_signals"].append({
        "item_id": item_id,
        "signal": signal,
        "signal_label": signal_label,
        "source_name": source_name,
        "source_type": source_type,
        "context": context,
        "timestamp_ms": now_ms
    })

    # Keep only last 100 signals to prevent the file from getting too massive
    feedback["recent_signals"] = feedback["recent_signals"][-100:]

    save_feedback(feedback)
    print(f"Signal recorded: {signal_label} ({weight_delta} weight) for '{source_name}'")

if __name__ == "__main__":
    ingest()
