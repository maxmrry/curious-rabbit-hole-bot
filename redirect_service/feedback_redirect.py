import os
import requests
from flask import Flask, request, redirect

app = Flask(__name__)

@app.route("/health")
def health():
    return "ok", 200

GITHUB_TOKEN = os.getenv("GH_DISPATCH_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # e.g. "maxmrry/curious-rabbit-hole-bot"
REDIRECT_SECRET = os.getenv("REDIRECT_SECRET")  # simple shared secret

SIGNAL_LABELS = {
    "1": "useful",
    "2": "fascinating",
    "0": "skip"
}

@app.route("/signal")
def receive_signal():
    token = request.args.get("token", "")
    if token != REDIRECT_SECRET:
        return "Unauthorised", 403

    item_id = request.args.get("item", "")
    signal = request.args.get("signal", "1")
    source = request.args.get("source", "")
    source_type = request.args.get("type", "")

    if not item_id:
        return "Missing item", 400

    payload = {
        "event_type": "feedback_signal",
        "client_payload": {
            "item_id": item_id,
            "signal": int(signal),
            "signal_label": SIGNAL_LABELS.get(signal, "useful"),
            "source_name": source,
            "source_type": source_type
        }
    }

    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/dispatches",
        json=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        },
        timeout=10
    )

    dest = request.args.get(
        "dest",
        "https://maxmrry.github.io/curious-rabbit-hole-bot/"
    )

    if resp.status_code == 204:
        return f"""
        <html>
            <body style="background-color: #4CAF50; color: white; text-align: center; padding-top: 50px;">
                <h1>✅ Signal sent successfully</h1>
                <p>Item: {item_id}</p>
                <p>Redirecting...</p>
                <script>
                    setTimeout(() => window.location.href = "{dest}", 5000);
                </script>
            </body>
        </html>
        """
    else:
        return f"""
        <html>
            <body style="background-color: #f44336; color: white; text-align: center; padding-top: 50px;">
                <h1>❌ Signal failed</h1>
                <p>Status: {resp.status_code}</p>
                <p>Still redirecting...</p>
                <script>
                    setTimeout(() => window.location.href = "{dest}", 2000);
                </script>
            </body>
        </html>
        """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
