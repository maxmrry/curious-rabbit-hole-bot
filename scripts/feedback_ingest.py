import os
import json
import time
from datetime import datetime

FEEDBACK_PATH = "state/feedback.json"

SIGNAL_WEIGHTS = {
    0: -2.0,   # skip — actively disliked
    1:  1.0,   # useful — solid, incremental positive
    2:  3.0,   # fascinating — strong positive, high agency
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
    signal = int(os.getenv("SIGNAL", "1"))
    source_name = os.getenv("SOURCE_NAME", "")
    source_type = os.getenv("SOURCE_TYPE", "")
    signal_label = os.getenv("SIGNAL_LABEL", "useful")

    if not item_id:
        print("No item_id provided. Exiting.")
        return

    weight_delta = SIGNAL_WEIGHTS.get(signal, 1.0)
    feedback = load_feedback()
    now_ms = int(time.time() * 1000)

    # Adjust per-source score
    if source_name:
        prev = feedback["source_adjustments"].get(source_name, {"cumulative": 0.0, "n": 0})
        feedback["source_adjustments"][source_name] = {
            "cumulative": round(prev["cumulative"] + weight_delta, 3),
            "n": prev["n"] + 1,
            "last_signal_ms": now_ms
        }

    # Adjust per-type score
    if source_type:
        prev = feedback["source_type_adjustments"].get(source_type, {"cumulative": 0.0, "n": 0})
        feedback["source_type_adjustments"][source_type] = {
            "cumulative": round(prev["cumulative"] + weight_delta, 3),
            "n": prev["n"] + 1
        }

    # Log the signal for auditability
    feedback["recent_signals"].append({
        "item_id": item_id,
        "signal": signal,
        "signal_label": signal_label,
        "source_name": source_name,
        "source_type": source_type,
        "timestamp_ms": now_ms
    })

    # Keep only last 90 signals
    feedback["recent_signals"] = feedback["recent_signals"][-90:]

    save_feedback(feedback)
    print(f"Signal recorded: {signal_label} for '{source_name}' ({source_type})")

if __name__ == "__main__":
    ingest()
