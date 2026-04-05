import random
import time
import datetime
import threading
from collections import deque

# Simulated political headlines and templates for Mock Mode
MOCK_TOPICS = ["Economy", "Election", "Healthcare", "Climate Policy", "Foreign Relations", "Education", "Infrastructure", "Trade Wars"]
MOCK_SENTIMENTS = {
    "positive": [
        "I'm really impressed with the new {topic} bill, it's a huge step forward!",
        "The recent improvements in {topic} are making everyone optimistic about the future.",
        "{topic} reforms are finally paying off, great news for the country.",
        "A historic win for {topic}! This is what we needed.",
        "Feeling positive about the direction we're headed with {topic}."
    ],
    "negative": [
        "The {topic} situation is a complete mess right now.",
        "I'm worried that the new {topic} policy will do more harm than good.",
        "Total failure in {topic} management, it's a disaster.",
        "Why is nobody talking about how bad the {topic} crisis is getting?",
        "Extremely disappointed with the latest {topic} update."
    ],
    "neutral": [
        "The debate on {topic} continues today at the capitol.",
        "New statistics on {topic} were released this morning.",
        "Official statement regarding {topic} expected tomorrow.",
        "Research shows mixed results in the {topic} field.",
        "Looking for more facts about the current state of {topic}."
    ]
}

class RedditScraper:
    def __init__(self, client_id=None, client_secret=None, user_agent="PoliticalSentimentBot/1.0"):
        self.enabled = False
        if client_id and client_secret:
            try:
                import praw
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
                self.enabled = True
            except Exception as e:
                print(f"Failed to initialize Reddit API: {e}")

    def fetch_recent(self, subreddit="politics", limit=10):
        if not self.enabled:
            return []
        try:
            posts = []
            for submission in self.reddit.subreddit(subreddit).new(limit=limit):
                posts.append({
                    "id": submission.id,
                    "text": submission.title + " " + submission.selftext[:200],
                    "timestamp": datetime.datetime.fromtimestamp(submission.created_utc).isoformat(),
                    "source": "Reddit",
                    "author": "u/" + str(submission.author)
                })
            return posts
        except Exception as e:
            print(f"Error fetching from Reddit: {e}")
            return []

class MockScraper:
    def generate_post(self):
        sentiment_type = random.choices(["positive", "negative", "neutral"], weights=[30, 40, 30])[0]
        topic = random.choice(MOCK_TOPICS)
        template = random.choice(MOCK_SENTIMENTS[sentiment_type])
        
        # Add random entities
        entities = [topic, random.choice(["Gov", "Policy", "Reform", "Budget", "Debate"])]
        
        return {
            "id": f"mock_{random.randint(10000, 99999)}",
            "text": template.format(topic=topic),
            "timestamp": datetime.datetime.now().isoformat(),
            "source": "MockStream",
            "author": f"User_{random.randint(100, 999)}",
            "entities": entities
        }

class PoliticalStreamer:
    def __init__(self, analyzer, reddit_keys=None):
        self.analyzer = analyzer
        self.reddit = RedditScraper(**(reddit_keys or {}))
        self.mock = MockScraper()
        
        # Buffer for latest posts
        self.buffer = deque(maxlen=100)
        self.stats_history = deque(maxlen=50) # Store aggregate stats over time
        self.entity_counts = {} # Tracking trending keywords
        
        self._running = False
        self._thread = None
        self.mode = "mock" if not self.reddit.enabled else "live"

    def _stream_worker(self):
        while self._running:
            if self.mode == "live":
                new_posts = self.reddit.fetch_recent(limit=5)
                if not new_posts:
                    post = self.mock.generate_post()
                    self._process_and_add(post)
                else:
                    existing_ids = [p['id'] for p in self.buffer]
                    for post in new_posts:
                        if post['id'] not in existing_ids:
                            # Basic keyword extraction for live data
                            post['entities'] = [w for w in post['text'].split() if len(w) > 5][:3]
                            self._process_and_add(post)
            else:
                post = self.mock.generate_post()
                self._process_and_add(post)
            
            self._update_stats()
            time.sleep(random.uniform(2, 5))

    def _process_and_add(self, post):
        analysis = self.analyzer.get_sentiment(post['text'])
        post.update(analysis)
        self.buffer.appendleft(post)
        
        # Update entity counts
        for ent in post.get('entities', []):
            self.entity_counts[ent] = self.entity_counts.get(ent, 0) + 1

    def _update_stats(self):
        if not self.buffer:
            return
        
        recent = list(self.buffer)[:20]
        avg_score = sum(p['score'] for p in recent) / len(recent)
        pos_count = sum(1 for p in recent if p['sentiment'] == "positive")
        neg_count = sum(1 for p in recent if p['sentiment'] == "negative")
        neu_count = sum(1 for p in recent if p['sentiment'] == "neutral")
        
        self.stats_history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "avg_sentiment": round(avg_score, 3),
            "pos_ratio": round(pos_count / len(recent), 2),
            "neg_ratio": round(neg_count / len(recent), 2),
            "neu_ratio": round(neu_count / len(recent), 2),
            "volume": len(self.buffer)
        })

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._stream_worker, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def get_snapshot(self):
        # Sort entities by popularity
        top_entities = sorted(self.entity_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        
        return {
            "latest_posts": list(self.buffer)[:15],
            "history": list(self.stats_history),
            "trending": [{"name": k, "count": v} for k, v in top_entities],
            "mode": self.mode
        }
