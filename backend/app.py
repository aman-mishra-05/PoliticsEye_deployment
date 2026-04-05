from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv

from analyzer import PoliticalAnalyzer
from scraper import PoliticalStreamer

load_dotenv()

app = Flask(__name__)
# Enable CORS for the frontend development server
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
REDDIT_KEYS = {
    "client_id": os.getenv("REDDIT_CLIENT_ID"),
    "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
    "user_agent": os.getenv("REDDIT_USER_AGENT", "PoliticalSentimentBot/1.0")
}

# Initialize Core
analyzer = PoliticalAnalyzer()
streamer = PoliticalStreamer(analyzer, reddit_keys=REDDIT_KEYS if REDDIT_KEYS['client_id'] else None)

# Startup logic moved to main block for Flask 2.3+ compatibility

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "mode": streamer.mode,
        "streaming": streamer._running
    })

@app.route('/api/snapshot', methods=['GET'])
def get_snapshot():
    snapshot = streamer.get_snapshot()
    # Add summary stats
    latest_posts = snapshot['latest_posts']
    if latest_posts:
        avg_sent = sum(p['score'] for p in latest_posts) / len(latest_posts)
        pos = sum(1 for p in latest_posts if p['sentiment'] == "positive")
        neg = sum(1 for p in latest_posts if p['sentiment'] == "negative")
        summary = {
            "avg_sentiment": round(avg_sent, 3),
            "pos_count": pos,
            "neg_count": neg,
            "total_count": len(latest_posts)
        }
    else:
        summary = {"avg_sentiment": 0, "pos_count": 0, "neg_count": 0, "total_count": 0}
        
    return jsonify({
        **snapshot,
        "summary": summary
    })

@app.route('/api/toggle-mode', methods=['POST'])
def toggle_mode():
    data = request.json
    requested_mode = data.get("mode")
    if requested_mode in ["mock", "live"]:
        if requested_mode == "live" and not streamer.reddit.enabled:
            return jsonify({"success": False, "error": "Reddit API credentials missing"}), 400
        streamer.mode = requested_mode
        return jsonify({"success": True, "new_mode": streamer.mode})
    return jsonify({"success": False, "error": "Invalid mode"}), 400

if __name__ == '__main__':
    # Force start the streamer if not started by first request
    streamer.start()
    app.run(debug=True, port=5000)
